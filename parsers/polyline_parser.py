import re
from typing import List, Any, Optional, Tuple

import pythoncom
import win32com.client

from core.models import Frame, detect_paper_format, ALL_FORMATS, natural_sheet_sort_key
from parsers.base_parser import BaseParser


# Масштабы, к которым «притягивается» найденный масштаб рамки.
# Форматы A0..A4 подобны (стороны относятся как 1:√2), поэтому A2 в М1:100 и A1 в М1:70.7
# геометрически одинаковы — выбираем вариант с «круглым» масштабом.
NICE_SCALES = [1, 2, 2.5, 4, 5, 10, 15, 20, 25, 40, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 1000]

# Поля по ГОСТ 21.101: слева 20 мм, сверху/справа/снизу 5 мм
MARGIN_LEFT, MARGIN_OTHER = 20.0, 5.0

# Графы формы 3 (185×55, основной комплект рабочих чертежей) — в мм от правого нижнего угла ВНУТРЕННЕЙ рамки:
CELL_SHEET_NUM_F3 = (-35.0, -20.0, 15.0, 25.0)    # графа 7 «Лист»
CELL_SHEET_NAME_F3 = (-120.0, -50.0, 0.0, 16.0)   # графа 4 «Наименование листа» (нижняя строка)
CELL_BUILDING_NAME_F3 = (-120.0, -50.0, 15.0, 30.0) # графа 3 «Наименование здания (сооружения)»
CELL_OBJECT_NAME_F3 = (-120.0, 0.0, 30.0, 45.0)    # графа 2 «Наименование объекта строительства»
CELL_DOC_CODE_F3 = (-120.0, 0.0, 45.0, 56.0)       # графа 1 «Обозначение документа (шифр)»

# Графы формы 4 (185×55, чертежи строительных изделий):
CELL_SHEET_NUM_F4 = (-40.0, -22.0, 14.0, 22.0)    # «Лист» — значение справа от надписи в строке Y≈17
CELL_SHEET_NAME_F4 = (-120.0, -50.0, 18.0, 36.0)  # графа 5 «Наименование изделия» (над строкой листа)
CELL_DOC_CODE_F4 = (-120.0, 0.0, 38.0, 56.0)       # графа 1 «Обозначение документа (шифр)»

# Стандартные служебные заголовки граф штампа и должностей (не могут быть наименованием листа)
STAMP_HEADER_LABELS = {
    "изм.", "изм", "кол. уч.", "кол.уч.", "кол. уч", "кол", "лист", "листов",
    "№ док.", "№док.", "№ док", "подп.", "подп", "подпись", "дата",
    "стадия", "масса", "масштаб", "формат",
    "разраб.", "разраб", "проверил", "пров.", "пров", "рук. группы", "рук.гр.", "рук. гр.",
    "гип", "нач. отд.", "нач.отд.", "н. контр.", "н.контр.", "утв.", "утв"
}

# Графы формы 6 (185×15, последующие листы):
CELL_SHEET_NUM_F6 = (-35.0, -20.0, 0.0, 15.0)     # графа 7 «Лист»
CELL_DOC_CODE_F6 = (-185.0, -10.0, 0.0, 15.0)     # графа 1 «Обозначение документа (шифр)»

STAMP_ZONE = (-185.0, 0.0, 0.0, 60.0)             # вся основная надпись


def _clean_text(s: str) -> str:
    """Убирает коды форматирования MText ({\\fArial|b0;...}, \\P, \\A1; и т.п.)."""
    s = s or ""
    s = s.replace("\\P", " ").replace("\\~", " ")
    s = re.sub(r"\\[ACcFfHhQqTtWwp][^;\\{}]*;", "", s)
    s = re.sub(r"\\[LlOoKk]", "", s)
    s = s.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def match_candidates(w: float, h: float) -> List[dict]:
    """
    Все варианты, чем может быть прямоугольник w×h (w — по X, h — по Y): внешней границей
    листа ('outer') или внутренней рамкой ('inner') формата из ALL_FORMATS в «круглом» масштабе.
    Вариантов бывает несколько: форматы A0..A4 подобны, и 59400×42000 — это и A2 в М1:100,
    и A4 в М1:200, и почти A0 в М1:50. Какой верный — решает choose_candidate().
    """
    res = []
    for fmt, (fw, fh) in ALL_FORMATS.items():
        long_, short_ = max(fw, fh), min(fw, fh)
        for orient, (sw, sh) in (("landscape", (long_, short_)), ("portrait", (short_, long_))):
            for kind, cw, ch in (("outer", sw, sh),
                                 ("inner", sw - MARGIN_LEFT - MARGIN_OTHER, sh - 2 * MARGIN_OTHER)):
                if cw <= 0 or ch <= 0:
                    continue
                sx, sy = w / cw, h / ch
                if abs(sx - sy) / sx > 0.004:      # пропорции не совпали
                    continue
                sc = (sx + sy) / 2
                nice = min(NICE_SCALES, key=lambda n: abs(n - sc) / n)
                err = abs(nice - sc) / nice
                if err > 0.004:                     # масштаб «некруглый»
                    continue
                res.append({"kind": kind, "format": fmt, "scale": float(nice),
                            "orientation": orient, "err": err})
    return res


def _expected_other(bb, c):
    """Где должна лежать парная полилиния (внутренняя для outer, внешняя для inner)."""
    s = c["scale"]
    if c["kind"] == "outer":
        return (bb[0] + MARGIN_LEFT * s, bb[1] + MARGIN_OTHER * s, bb[2] - MARGIN_OTHER * s, bb[3] - MARGIN_OTHER * s)
    return (bb[0] - MARGIN_LEFT * s, bb[1] - MARGIN_OTHER * s, bb[2] + MARGIN_OTHER * s, bb[3] + MARGIN_OTHER * s)


def _anchor(bb, c):
    """Правый нижний угол внутренней рамки — от него отсчитываются графы штампа."""
    s = c["scale"]
    if c["kind"] == "outer":
        return (bb[2] - MARGIN_OTHER * s, bb[1] + MARGIN_OTHER * s)
    return (bb[2], bb[1])


# Заголовки граф справа в основной надписи формы 3 — для проверки масштаба по текстам: (текст, dx, dy) в мм
STAMP_LABELS = (("стадия", -42.5, 27.5), ("лист", -27.5, 27.5), ("листов", -10.0, 27.5))


def _label_score(anchor, s, texts) -> int:
    ax, ay = anchor
    score = 0
    for word, ex, ey in STAMP_LABELS:
        for tx, ty, val in texts:
            if val.strip().lower() == word and abs((tx - ax) / s - ex) < 4 and abs((ty - ay) / s - ey) < 4:
                score += 1
                break
    return score


def choose_candidate(bb, cands, all_bboxes, texts, ltscale=None):
    """Выбирает верный вариант формата/масштаба:
    1) есть парная полилиния (внутренняя рамка там, где ей положено быть при этом масштабе);
    2) заголовки «Стадия / Лист / Листов» стоят на своих местах в штампе;
    3) масштаб совпадает с масштабом типа линий полилинии;
    4) иначе — наименьшая погрешность."""
    if not cands:
        return None
    def key(c):
        s = c["scale"]
        exp = _expected_other(bb, c)
        tol = 1.0 * s  # 1 мм на листе
        paired = any(all(abs(o[i] - exp[i]) < tol for i in range(4)) for o in all_bboxes if o is not bb)
        return (
            1 if paired else 0,
            _label_score(_anchor(bb, c), s, texts),
            1 if (ltscale and abs(ltscale - s) / s < 0.01) else 0,
            1 if c["kind"] == "outer" else 0,
            -c["err"],
        )
    return max(cands, key=key)


def _inside(inner, outer, tol: float) -> bool:
    return (inner[0] >= outer[0] - tol and inner[1] >= outer[1] - tol and
            inner[2] <= outer[2] + tol and inner[3] <= outer[3] + tol)


def _fallback_scale(width: float, height: float) -> float:
    """Старое определение масштаба — для полилиний, не похожих на формат ГОСТ."""
    dims = [210, 297, 420, 594, 841, 1189]
    best_scale, min_diff = 1.0, float("inf")
    for d in dims:
        for actual in (width, height):
            scale = actual / d
            diff = abs(round(scale) - scale)
            if diff < 0.05 and diff < min_diff:
                min_diff, best_scale = diff, round(scale)
    return max(1.0, float(best_scale))


def analyze(polys: List[dict], texts: List[Tuple[float, float, str]]) -> List[dict]:
    """
    Чистая геометрия, без COM (можно проверять без AutoCAD).
    polys: [{'bbox': (minx, miny, maxx, maxy), 'ref': COM-объект}, ...]
    texts: [(x_центра, y_центра, текст), ...]
    Возвращает рамки: {'bbox', 'scale', 'format', 'sheet_number', 'sheet_name', 'ref', 'texts'}.
    """
    items = []
    for p in polys:
        x1, y1, x2, y2 = p["bbox"]
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            continue
        items.append({"p": p, "w": w, "h": h, "area": w * h})
    all_bboxes = [it["p"]["bbox"] for it in items]
    for it in items:
        it["m"] = choose_candidate(it["p"]["bbox"], match_candidates(it["w"], it["h"]),
                                   all_bboxes, texts, it["p"].get("ltscale"))
    items.sort(key=lambda it: -it["area"])

    frames = []
    for it in items:
        bb, m = it["p"]["bbox"], it["m"]

        # Полилиния внутри уже найденного листа — его внутренняя рамка (или линии штампа):
        # отдельным листом не считаем, но угол внутренней рамки берём как угол штампа.
        host = next((f for f in frames if _inside(bb, f["bbox"], tol=0.01 * f["w"])), None)
        if host is not None:
            if m and m["kind"] == "inner" and not host["anchor_from_inner"] \
                    and abs(m["scale"] - host["scale"]) / host["scale"] < 0.01:
                host["anchor"] = (bb[2], bb[1])
                host["anchor_from_inner"] = True
            continue

        if m is None:
            # Не формат ГОСТ — как раньше: лист = полилиния, угол штампа = её правый нижний угол
            frames.append({"bbox": bb, "w": it["w"], "scale": _fallback_scale(it["w"], it["h"]),
                           "format": None, "anchor": (bb[2], bb[1]), "anchor_from_inner": True,
                           "ref": it["p"]["ref"]})
            continue

        s = m["scale"]
        anchor = _anchor(bb, m)
        # Есть только внутренняя рамка — печатаем по внешней границе листа
        frame_bb = bb if m["kind"] == "outer" else _expected_other(bb, m)
        frames.append({"bbox": frame_bb, "w": frame_bb[2] - frame_bb[0], "scale": s, "format": m["format"],
                       "anchor": anchor, "anchor_from_inner": m["kind"] == "inner", "ref": it["p"]["ref"]})

    for f in frames:
        (
            f["sheet_number"],
            f["sheet_name"],
            f["doc_code"],
            f["object_name"],
            f["building_name"],
            f["texts"],
        ) = _read_stamp(f["anchor"], f["scale"], texts)

    # Сортировка: титульный лист всегда первым, затем по номеру листа
    frames.sort(key=lambda f: (
        0 if (f["sheet_name"] or "").strip().lower() == "титульный лист" else 1,
        natural_sheet_sort_key(f["sheet_number"])
    ))
    return frames


def _is_title_page(local: List[Tuple[float, float, str]]) -> bool:
    """
    Проверяет, является ли лист титульным (без штампа).
    На титульном листе нет графы «Лист», нет таблицы изменений/подписей в штампе.
    """
    # Тексты строго внутри зоны штампа (Y >= 0)
    in_stamp = [t for t in local if t[1] >= 0]
    if not in_stamp:
        return True

    # Если среди текстов есть заголовок чертежа (План, Разрез, Схема...) или номер листа — это точно не титул!
    title_keywords = (
        "план", "разрез", "фасад", "схема", "узел", "узлы", "сечение", "сечения",
        "спецификаци", "ведомост", "общие данные", "опалубк", "армирован"
    )
    for t in in_stamp:
        val_lower = t[2].strip().lower()
        if any(kw in val_lower for kw in title_keywords):
            return False
        if re.match(r'^\d+[а-яА-Яa-zA-Z]?(?:[-.]\d+)?$', val_lower):
            return False

    # Если в зоне штампа 3 и более текстов — это заполненная основная надпись, а не титул
    if len(in_stamp) >= 3:
        return False

    # Если есть графа «Лист» или «Листов» — это точно не титульный лист
    if any(t[2].strip().lower() in ("лист", "листов") for t in in_stamp):
        return False

    # Если есть заголовки штампа (таблица изменений, разработчики, стадия)
    if any(t[2].strip().lower() in STAMP_HEADER_LABELS for t in in_stamp):
        return False

    # Если заполнена графа шифра (dx: -120..0, dy: 45..56)
    if any(-120.0 <= t[0] <= 0.0 and 45.0 <= t[1] <= 56.0 for t in in_stamp):
        return False

    return True


def _detect_stamp_form(local: List[Tuple[float, float, str]]) -> int:
    """
    Определяет форму штампа по ГОСТ 21.101:
    - форма 4: чертежи строительных изделий (наличие «Масса»/«Масштаб» в правой колонке или «Лист ... Листов» на Y=14..22)
    - форма 6: последующие листы (штамп высотой 15 мм, нет надписей выше Y=18)
    - форма 3: основной комплект рабочих чертежей (по умолчанию)
    """
    # Если есть описательный заголовок листа (План, Разрез, Схема...) — это точно не форма 6
    title_keywords = (
        "план", "разрез", "фасад", "схема", "узел", "узлы", "сечение", "сечения",
        "спецификаци", "ведомост", "общие данные", "опалубк", "армирован"
    )
    has_title = any(any(kw in t[2].lower() for kw in title_keywords) or len(t[2].strip()) > 8 for t in local)

    # Если выше 18 мм вообще нет текстов и нет заголовков листа — это форма 6 (малый штамп 15 мм)
    if not has_title and not any(t[1] > 18.0 for t in local):
        return 6

    # Форма 4: есть графа «Масса» или «Масштаб» справа (X > -45)
    if any(t[2].strip().lower() in ("масса", "масштаб") and t[0] > -45.0 for t in local):
        return 4

    # Форма 4: «Лист» и «Листов» в одной строке на высоте Y=14..22
    for t in local:
        if t[2].strip().lower() == "лист" and t[0] > -55.0 and 14.0 <= t[1] <= 22.0:
            if any(o[2].strip().lower() == "листов" and abs(o[1] - t[1]) < 4.0 and o[0] > t[0] for o in local):
                return 4

    return 3


def _read_stamp(anchor, s, texts):
    """Номер и наименование листа, шифр, объект, здание по графам основной надписи."""
    ax, ay = anchor
    local = []  # (dx_мм, dy_мм, текст) от правого нижнего угла внутренней рамки
    for tx, ty, val in texts:
        dx, dy = (tx - ax) / s, (ty - ay) / s
        if STAMP_ZONE[0] <= dx <= STAMP_ZONE[1] + 2 and STAMP_ZONE[2] - 2 <= dy <= STAMP_ZONE[3]:
            local.append((dx, dy, val))

    def in_cell(cell):
        return [t for t in local if cell[0] <= t[0] <= cell[1] and cell[2] <= t[1] <= cell[3]]

    # Титульный лист (без штампа): без номера, наименование «Титульный лист»
    if _is_title_page(local):
        return "", "Титульный лист", "", "", "", [t[2] for t in local]

    form = _detect_stamp_form(local)
    doc_code = ""
    object_name = ""
    building_name = ""

    if form == 4:
        cell_num = CELL_SHEET_NUM_F4
        cell_name = CELL_SHEET_NAME_F4
        # Графа 1 (шифр)
        code_cells = [t for t in in_cell(CELL_DOC_CODE_F4) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        doc_code = " ".join(t[2].strip() for t in sorted(code_cells, key=lambda t: -t[1]))
    elif form == 6:
        cell_num = CELL_SHEET_NUM_F6
        cell_name = None
        # Графа 1 (шифр)
        code_cells = [t for t in in_cell(CELL_DOC_CODE_F6) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        doc_code = " ".join(t[2].strip() for t in sorted(code_cells, key=lambda t: -t[1]))
    else:  # form 3
        cell_num = CELL_SHEET_NUM_F3
        cell_name = CELL_SHEET_NAME_F3
        # Графа 1: обозначение документа (шифр)
        code_cells = [t for t in in_cell(CELL_DOC_CODE_F3) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        doc_code = " ".join(t[2].strip() for t in sorted(code_cells, key=lambda t: -t[1]))
        # Графа 2: наименование объекта строительства
        obj_cells = [t for t in in_cell(CELL_OBJECT_NAME_F3) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        object_name = " ".join(t[2].strip() for t in sorted(obj_cells, key=lambda t: -t[1]))
        # Графа 3: наименование здания (сооружения)
        bld_cells = [t for t in in_cell(CELL_BUILDING_NAME_F3) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        building_name = " ".join(t[2].strip() for t in sorted(bld_cells, key=lambda t: -t[1]))

    # номер листа: графа «Лист» соответствующей формы, иначе — рядом с надписью «Лист»
    cell = [t for t in in_cell(cell_num) if t[2].strip().lower() not in ("лист", "листов")]
    number = max(cell, key=lambda t: t[1])[2] if cell else _number_near_label(local)

    # наименование листа: графа 4 / 5, строки сверху вниз (исключая служебные заголовки граф)
    if cell_name:
        name_cells = [t for t in in_cell(cell_name) if t[2].strip().lower() not in STAMP_HEADER_LABELS]
        name = " ".join(t[2].strip() for t in sorted(name_cells, key=lambda t: -t[1]))
    else:
        name = ""

    # Если в графе наименования пусто, но в building_name или object_name попало наименование чертежа
    title_keywords = (
        "план", "разрез", "фасад", "схема", "узел", "узлы", "сечение", "сечения",
        "спецификаци", "ведомост", "общие данные", "опалубк", "армирован"
    )
    if not name or name == "Unknown":
        if building_name and any(kw in building_name.lower() for kw in title_keywords):
            name = building_name
            building_name = ""
        elif object_name and any(kw in object_name.lower() for kw in title_keywords):
            name = object_name
            object_name = ""

    # Для формы 6 наименование листа по ГОСТ отсутствует — оставляем пустым, не 'Unknown'
    if form == 6 and not name:
        final_name = ""
    else:
        final_name = name or "Unknown"

    return (number or "Unknown"), final_name, doc_code, object_name, building_name, [t[2] for t in local]


def _number_near_label(local):
    """Запасной поиск номера: значение под надписью «Лист» (формы 3, 5, 6)
    или справа от неё в той же строке (форма 4: «Лист  12   Листов  30»)."""
    labels = [t for t in local if t[2].strip().lower() == "лист"]
    if not labels:
        return ""
    lx, ly, _ = max(labels, key=lambda t: t[0])   # самый правый «Лист»
    others = [t for t in local if t[2].strip().lower() not in ("лист", "листов")]
    below = [t for t in others if abs(t[0] - lx) < 7 and -12 < t[1] - ly < 0]
    if below:
        return max(below, key=lambda t: t[1])[2]
    right = [t for t in others if abs(t[1] - ly) < 3 and 0 < t[0] - lx < 20]
    if right:
        return min(right, key=lambda t: t[0])[2]
    return ""


class PolylineParser(BaseParser):
    def __init__(self, target_layer: str = "0000_Формат"):
        """
        :param target_layer: Имя слоя, на котором лежат рамки и тексты
        """
        self.target_layer_name = target_layer
        self.target_layer = target_layer.lower()

    def _select_on_layer(self, doc: Any) -> Optional[list]:
        """
        Объекты модели на целевом слое (полилинии и тексты) одним запросом через набор выбора.
        Это в десятки раз быстрее, чем перебирать через COM каждый объект ModelSpace.
        Если набор выбора не сработал — None (тогда перебираем по-старому).
        """
        ss_name = "PDFPRINT_POLY_SS"
        try:
            try:
                doc.SelectionSets.Item(ss_name).Delete()
            except Exception:
                pass
            ss = doc.SelectionSets.Add(ss_name)
            ftype = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0, 8, 410])
            fdata = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT,
                                            ["LWPOLYLINE,POLYLINE,TEXT,MTEXT", self.target_layer_name, "Model"])
            try:
                # 5 = acSelectionSetAll; точки не нужны — передаём «пропущенный аргумент»
                no_arg = getattr(pythoncom, "ArgNotFound", pythoncom.Missing)
                ss.Select(5, no_arg, no_arg, ftype, fdata)
                objs = [ss.Item(i) for i in range(ss.Count)]
            finally:
                try:
                    ss.Delete()
                except Exception:
                    pass
            return objs
        except Exception as e:
            print(f"[PolylineParser] Набор выбора не сработал ({e}), перебор ModelSpace...")
            return None

    def find_frames(self, doc: Any) -> List[Frame]:
        frames = []

        # Быстрая проверка таблицы слоев
        try:
            layers = doc.Layers
            if not any(getattr(layers.Item(i), 'Name', '').lower() == self.target_layer
                       for i in range(layers.Count)):
                return frames
        except Exception:
            pass

        # 1. Полилинии и тексты с нужного слоя
        objs = self._select_on_layer(doc)
        if objs is None:
            objs = []
            model_space = doc.ModelSpace
            for i in range(model_space.Count):
                try:
                    obj = model_space.Item(i)
                    if getattr(obj, 'Layer', '').lower() == self.target_layer:
                        objs.append(obj)
                except Exception:
                    continue

        polys = []
        texts = []  # (x_центра, y_центра, текст) — габариты текста считаем один раз
        for obj in objs:
            try:
                ent_name = getattr(obj, 'EntityName', '')
                if 'Polyline' in ent_name:
                    mn, mx = obj.GetBoundingBox()
                    try:
                        lts = float(obj.LinetypeScale)
                    except Exception:
                        lts = None
                    polys.append({"bbox": (mn[0], mn[1], mx[0], mx[1]), "ref": obj, "ltscale": lts})
                elif ent_name in ('AcDbText', 'AcDbMText'):
                    val = _clean_text(getattr(obj, 'TextString', ''))
                    if val:
                        # реальные габариты — чтобы не зависеть от выравнивания (Alignment)
                        t_min, t_max = obj.GetBoundingBox()
                        texts.append(((t_min[0] + t_max[0]) / 2, (t_min[1] + t_max[1]) / 2, val))
            except Exception:
                continue

        # 2. Геометрия: внешняя граница + внутренняя рамка = один лист; графы штампа по ГОСТ
        for f in analyze(polys, texts):
            try:
                x1, y1, x2, y2 = f["bbox"]
                poly = f["ref"]
                fmt = f["format"] or detect_paper_format(x2 - x1, y2 - y1, scale=f["scale"])
                frame = Frame(
                    object_id=getattr(poly, 'ObjectID', 0),
                    sheet_number=f["sheet_number"],
                    sheet_name=f["sheet_name"],
                    min_point=(x1, y1, 0.0),
                    max_point=(x2, y2, 0.0),
                    source_type="Polyline",
                    paper_format=fmt,
                    handle=getattr(poly, 'Handle', ''),
                    doc_code=f.get("doc_code", ""),
                    object_name=f.get("object_name", ""),
                    building_name=f.get("building_name", "")
                )
                frame._debug_texts = f["texts"]
                frames.append(frame)
            except Exception as e:
                print(f"Ошибка при обработке полилинии: {e}")

        return frames
