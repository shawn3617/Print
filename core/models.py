from dataclasses import dataclass, field
from typing import Any, Tuple, List

# Стандартные размеры ГОСТ форматов (длинная x короткая в мм)
GOST_FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# Дополнительные форматы по ГОСТ 2.301-68 (Таблица 2)
# Точные стандартные размеры в мм (длинная сторона x короткая сторона)
GOST_EXTENDED = {
    # Кратные A4 (297 x ...)
    "A4x3": (630, 297),
    "A4x4": (841, 297),
    "A4x5": (1051, 297),
    "A4x6": (1261, 297),
    "A4x7": (1471, 297),
    "A4x8": (1682, 297),
    "A4x9": (1892, 297),
    # Кратные A3 (420 x ...)
    "A3x3": (891, 420),
    "A3x4": (1189, 420),
    "A3x5": (1486, 420),
    "A3x6": (1783, 420),
    "A3x7": (2080, 420),
    # Кратные A2 (594 x ...)
    "A2x3": (1261, 594),
    "A2x4": (1682, 594),
    "A2x5": (2102, 594),
    # Кратные A1 (841 x ...)
    "A1x3": (1783, 841),
    "A1x4": (2378, 841),
    # Кратные A0 (1189 x ...)
    "A0x2": (1682, 1189),
    "A0x3": (2523, 1189),
}

# Дополняем произвольными кратными до x9 по формуле, если какого-то нет в таблице 2
for _base_name, (_fw, _fh) in GOST_FORMATS.items():
    _short = min(_fw, _fh)
    _long = max(_fw, _fh)
    _min_mult = 2 if _base_name == "A0" else 3
    for _mult in range(_min_mult, 10):
        _ext_name = f"{_base_name}x{_mult}"
        if _ext_name not in GOST_EXTENDED and not (_base_name == "A0" and _mult == 1):
            _ext_w = _short * _mult
            _ext_h = _long
            GOST_EXTENDED[_ext_name] = (max(_ext_w, _ext_h), min(_ext_w, _ext_h))

# Объединяем все форматы
ALL_FORMATS = {**GOST_FORMATS, **GOST_EXTENDED}

@dataclass
class FormatCandidate:
    """Кандидат формата бумаги при математическом распознавании"""
    paper_format: str                     # Формат (напр. "A2", "A4")
    scale: int                            # Масштаб (напр. 100, 200)
    error: float = 0.0                    # Погрешность геометрии
    reason: str = ""                      # Основание выбора


@dataclass
class FormatDetectionResult:
    """Детальный результат распознавания формата бумаги"""
    paper_format: str                     # Итоговый выбранный формат
    scale: int = 1                        # Выбранный масштаб
    reason: str = ""                      # Текстовое основание выбора
    candidates: List[FormatCandidate] = field(default_factory=list) # Все подходящие кандидаты
    is_ambiguous: bool = False            # Флаг неоднозначности (есть равноценные альтернативы)


def detect_paper_format_detailed(width: float, height: float, block_name: str = "", scale: float = None) -> FormatDetectionResult:
    """
    Детально определяет формат бумаги, масштаб, основание выбора и альтернативные варианты.
    Сначала пытается извлечь формат из названия блока.
    Если передан точный масштаб scale, вычисляет физический размер в мм.
    Иначе определяет по размерам BoundingBox с приоритетом стандартных масштабов ГОСТ (1:100, 1:50, 1:1...).
    Фиксирует неоднозначность (например, A2 М1:100 = A4 М1:200).
    """
    import re
    w, h = max(width, height), min(width, height)

    # 1. Пытаемся найти формат прямо в имени блока
    if block_name:
        for fmt in sorted(ALL_FORMATS.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(fmt) + r'\b', block_name, re.IGNORECASE) or \
               re.search(r'_' + re.escape(fmt) + r'[_PPL]', block_name, re.IGNORECASE):
                
                fw, fh = ALL_FORMATS[fmt]
                scale_w = w / fw
                scale_h = h / fh
                rw = round(scale_w)
                rh = round(scale_h)
                
                if rw == rh and rw >= 1:
                    err_w = abs(scale_w - rw)
                    err_h = abs(scale_h - rh)
                    if err_w / rw < 0.05 and err_h / rh < 0.05:
                        cand = FormatCandidate(fmt, rw, err_w + err_h, f"Имя блока «{block_name}»")
                        return FormatDetectionResult(
                            paper_format=fmt,
                            scale=rw,
                            reason=f"Имя блока «{block_name}»",
                            candidates=[cand],
                            is_ambiguous=False
                        )

    # 2. Если известен точный масштаб (например, из свойств СПДС)
    if scale and scale > 0:
        w_mm = w / scale
        h_mm = h / scale
        best_fmt = None
        min_err = float('inf')
        for fmt, (fw, fh) in ALL_FORMATS.items():
            diff = abs(w_mm - fw) + abs(h_mm - fh)
            if diff < min_err:
                min_err = diff
                best_fmt = fmt
        if best_fmt and min_err < 15.0:
            sc_int = int(round(scale)) if abs(scale - round(scale)) < 0.01 else scale
            cand = FormatCandidate(best_fmt, sc_int, min_err, f"Свойства СПДС (М 1:{sc_int})")
            return FormatDetectionResult(
                paper_format=best_fmt,
                scale=sc_int,
                reason=f"Свойства СПДС (М 1:{sc_int})",
                candidates=[cand],
                is_ambiguous=False
            )

    # 3. Математическое определение по размерам
    matches = []  # Список (суммарная_ошибка, масштаб, формат)
    for fmt, (fw, fh) in ALL_FORMATS.items():
        scale_w = w / fw
        scale_h = h / fh
        rw = round(scale_w)
        rh = round(scale_h)
        
        if rw == rh and rw >= 1:
            err_w = abs(scale_w - rw)
            err_h = abs(scale_h - rh)
            total_err = err_w + err_h
            if err_w / rw < 0.005 and err_h / rh < 0.005:
                matches.append((total_err, rw, fmt))

    if matches:
        def match_priority(m):
            err, sc, fmt = m
            r_err = round(err, 4)
            # Приоритет стандартным масштабам чертежей по ГОСТ 2.302-68:
            # 1:100 — абсолютный стандарт в проектировании (архитектура, конструкции, СПДС)
            scale_rank = 0
            if sc == 100:
                scale_rank = -10
            elif sc in [1, 50, 20, 200]:
                scale_rank = -5
            return (r_err, scale_rank, sc)
            
        matches.sort(key=match_priority)
        best_err, best_sc, best_fmt = matches[0]

        candidates = [
            FormatCandidate(
                paper_format=fmt,
                scale=sc,
                error=round(err, 4),
                reason=f"Геометрия М1:{sc}"
            )
            for err, sc, fmt in matches
        ]

        # Проверяем неоднозначность: если есть альтернативный кандидат со стандартным масштабом
        # и малой погрешностью (например, A2 М1:100 и A4 М1:200)
        standard_scales = {1, 2, 5, 10, 20, 25, 50, 100, 200, 500}
        alts = [
            c for c in candidates
            if c.paper_format != best_fmt and c.scale in standard_scales and c.error < 0.01
        ]
        is_ambiguous = len(alts) > 0

        reason_str = f"Геометрия М1:{best_sc}"
        if is_ambiguous:
            reason_str += f" (неоднозначно: альтернатива {alts[0].paper_format} М1:{alts[0].scale})"

        return FormatDetectionResult(
            paper_format=best_fmt,
            scale=best_sc,
            reason=reason_str,
            candidates=candidates,
            is_ambiguous=is_ambiguous
        )

    # 4. Фолбэк: определяем по короткой стороне
    fallback = []
    for fmt, (fw, fh) in ALL_FORMATS.items():
        scale_val = h / fh
        r = round(scale_val)
        if r >= 1:
            err = abs(scale_val - r)
            if err / r < 0.005:
                fallback.append((err, r, fmt))

    if fallback:
        def fallback_priority(m):
            err, sc, fmt = m
            r_err = round(err, 4)
            scale_rank = -10 if sc == 100 else (-5 if sc in [1, 50, 20, 200] else 0)
            return (r_err, scale_rank, sc)
        fallback.sort(key=fallback_priority)
        best_err, best_sc, best_fmt = fallback[0]
        cands = [
            FormatCandidate(
                paper_format=fmt,
                scale=sc,
                error=round(err, 4),
                reason=f"Приближение по высоте М1:{sc}"
            )
            for err, sc, fmt in fallback
        ]
        return FormatDetectionResult(
            paper_format=best_fmt,
            scale=best_sc,
            reason=f"Приближение по высоте М1:{best_sc}",
            candidates=cands,
            is_ambiguous=True
        )

    return FormatDetectionResult(
        paper_format="A2",
        scale=1,
        reason="По умолчанию (A2)",
        candidates=[FormatCandidate("A2", 1, 0.0, "По умолчанию")],
        is_ambiguous=True
    )


def detect_paper_format(width: float, height: float, block_name: str = "", scale: float = None) -> str:
    """
    Определяет формат бумаги (обратная совместимость).
    Возвращает строку формата (напр. 'A4', 'A3', 'A2').
    """
    return detect_paper_format_detailed(width, height, block_name=block_name, scale=scale).paper_format

def detect_format_from_media_name(media_name: str) -> str:
    """
    Определяет формат ГОСТ (A0..A4, A3x3 и т.д.) по названию формата бумаги плоттера.
    """
    import re
    if not media_name:
        return "A3"
        
    # 1. Поиск физических размеров в названии (например 420.00 x 297.00 или 1485 x 420)
    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', media_name)]
    dims = [n for n in nums if n >= 100]
    if len(dims) >= 2:
        pw, ph = max(dims[-2:]), min(dims[-2:])
        for fmt, (fw, fh) in ALL_FORMATS.items():
            if abs(pw - max(fw, fh)) < 3 and abs(ph - min(fw, fh)) < 3:
                return fmt

    # 2. Поиск точного совпадения имени формата (например A3, A4, A3x4)
    for fmt in sorted(ALL_FORMATS.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(fmt) + r'\b', media_name, re.IGNORECASE):
            return fmt

    return "A3"

def get_paper_size_mm(paper_format: str) -> Tuple[float, float]:
    """Возвращает физические размеры формата в мм (ширина, высота)"""
    if paper_format in ALL_FORMATS:
        return ALL_FORMATS[paper_format]
    return (594, 420)  # A2 по умолчанию

def natural_sheet_sort_key(sheet_number: str):
    """
    Ключ для естественной (естественно-числовой) сортировки номеров листов.
    Корректно упорядочивает листы вида: '1', '2', ..., '4', '4.1', '4а', '4б', ..., '10'.
    Разбивает строку на числовые и буквенные составляющие.
    """
    import re
    if not sheet_number:
        return [(0, 0)]
    s = str(sheet_number).strip()
    tokens = re.split(r'(\d+)', s)
    result = []
    for token in tokens:
        if not token:
            continue
        if token.isdigit():
            result.append((0, int(token)))
        else:
            result.append((1, token.lower()))
    return result if result else [(0, 0)]

def frame_natural_sort_key(frame: Any):
    """
    Ключ сортировки рамок чертежа:
    - Титульный лист всегда идет первым (приоритет 0);
    - Остальные листы сортируются по естественному порядку номеров (приоритет 1);
    - При одинаковых номерах учитывается имя файла чертежа (dwg_name).
    """
    sheet_name = getattr(frame, "sheet_name", "") or ""
    is_title = 0 if sheet_name.strip().lower() == "титульный лист" else 1
    sheet_number = getattr(frame, "sheet_number", "") or ""
    dwg_part = (getattr(frame, "dwg_name", "") or "").lower()
    return (is_title, natural_sheet_sort_key(sheet_number), dwg_part)

@dataclass

class Frame:
    """
    Класс, описывающий найденную рамку чертежа.
    """
    object_id: int                          # ID объекта в AutoCAD (ObjectID)
    sheet_number: str                       # Номер листа (извлеченный из штампа/атрибутов)
    sheet_name: str                         # Название листа
    min_point: Tuple[float, float, float]   # Левый нижний угол BoundingBox (X, Y, Z)
    max_point: Tuple[float, float, float]   # Правый верхний угол BoundingBox (X, Y, Z)
    source_type: str                        # Тип источника (SPDS, Polyline, Block)
    paper_format: str = "A2"               # Формат бумаги (A4, A3, A2, A1, A0, A3x5 и т.д.)
    handle: str = ""                        # Handle объекта в AutoCAD (устойчивый HEX-идентификатор)
    dwg_path: str = ""                      # Полный путь к исходному DWG-файлу
    dwg_name: str = ""                      # Имя файла чертежа (например "План.dwg")
    doc_code: str = ""                      # Обозначение документа (графа 1)
    object_name: str = ""                   # Наименование объекта строительства (графа 2)
    building_name: str = ""                 # Наименование здания / сооружения (графа 3)
    layout_name: str = "Model"              # Имя вкладки пространства листа ("Model", "Лист1", "Layout1" и т.д.)
    fallback_warning: str = ""              # Предупреждение о резервном формате / нестыковках бумаги
    scale: int = 1                          # Масштаб чертежа (100 для 1:100)
    format_reason: str = ""                 # Основание выбора формата ("Имя блока", "Геометрия М1:100", "Вручную")
    possible_formats: List[Tuple[str, int]] = field(default_factory=list) # Альтернативы [(format, scale)]
    is_ambiguous: bool = False              # Флаг неоднозначности формата
    user_override: bool = False             # Флаг ручного изменения пользователем

