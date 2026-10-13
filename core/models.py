from dataclasses import dataclass, field
from typing import Tuple

# Стандартные размеры ГОСТ форматов (длинная x короткая в мм)
GOST_FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

# Расширенные форматы ГОСТ 2.301-68 (AxN: короткая_сторона * N × длинная_сторона)
GOST_EXTENDED = {}
for _base_name, (_fw, _fh) in GOST_FORMATS.items():
    _short = min(_fw, _fh)
    _long = max(_fw, _fh)
    for _mult in range(3, 10):
        _ext_name = f"{_base_name}x{_mult}"
        _ext_w = _short * _mult
        _ext_h = _long
        GOST_EXTENDED[_ext_name] = (max(_ext_w, _ext_h), min(_ext_w, _ext_h))

# Объединяем все форматы
ALL_FORMATS = {**GOST_FORMATS, **GOST_EXTENDED}

def detect_paper_format(width: float, height: float, block_name: str = "") -> str:
    """
    Определяет формат бумаги. Сначала пытается извлечь его из названия блока.
    Если не вышло, определяет по размерам BoundingBox рамки.
    """
    import re
    
    # 1. Пытаемся найти формат (A0..A4, A4x9 и т.д.) прямо в имени блока
    if block_name:
        w, h = max(width, height), min(width, height)
        for fmt in sorted(ALL_FORMATS.keys(), key=len, reverse=True):
            if re.search(r'\b' + re.escape(fmt) + r'\b', block_name, re.IGNORECASE) or \
               re.search(r'_' + re.escape(fmt) + r'[_PPL]', block_name, re.IGNORECASE):
                
                # Валидация: проверяем, что рамка действительно масштабируется в этот формат
                fw, fh = ALL_FORMATS[fmt]
                scale_w = w / fw
                scale_h = h / fh
                rw = round(scale_w)
                rh = round(scale_h)
                
                # Допускаем погрешность до 5% для блоков (из-за торчащих атрибутов)
                if rw == rh and rw >= 1:
                    err_w = abs(scale_w - rw)
                    err_h = abs(scale_h - rh)
                    if err_w / rw < 0.05 and err_h / rh < 0.05:
                        return fmt
                
                # Если валидация не прошла, продолжаем поиск (вдруг имя обманчиво)
    # 2. Математическое определение по размерам
    w, h = max(width, height), min(width, height)
    
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
        matches.sort(key=lambda x: (round(x[0], 4), x[1]))
        return matches[0][2]
    
    # Фолбэк: определяем по короткой стороне
    fallback = []
    for fmt, (fw, fh) in ALL_FORMATS.items():
        scale = h / fh
        r = round(scale)
        if r >= 1:
            err = abs(scale - r)
            if err / r < 0.005:
                fallback.append((err, r, fmt))
    
    if fallback:
        fallback.sort(key=lambda x: (round(x[0], 4), x[1]))
        return fallback[0][2]
    
    return "A2"

def get_paper_size_mm(paper_format: str) -> Tuple[float, float]:
    """Возвращает физические размеры формата в мм (ширина, высота)"""
    if paper_format in ALL_FORMATS:
        return ALL_FORMATS[paper_format]
    return (594, 420)  # A2 по умолчанию

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
