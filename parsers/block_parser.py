import time
import re
import fnmatch
from typing import List, Any
from core.models import Frame, ALL_FORMATS, detect_paper_format
from parsers.base_parser import BaseParser
from core.resource_utils import get_resource_path, get_lisp_path


DEFAULT_BLOCK_NAMES = [
    "*SHT*", "*Формат*", "*Format*", "*Рамк*", "*Ramk*",
    "*Штамп*", "*Stamp*", "*Лист*", "*Sheet*", "*Title*",
    "*Титул*", "*Обложк*", "*BRU*", "*vcFormat*"
]

DEFAULT_SHEET_TAGS = [
    "!НОМЕР", "!ЛИСТ", "!LIST", "!SHEET", "!PAGE",
    "SHEET", "ЛИСТ", "НОМЕР", "НОМЕР_ЛИСТА", "SH_NUM",
    "LIST", "PAGE", "ЛИСТ_№", "N_ЛИСТА", "НОМЕРЛИСТА"
]

DEFAULT_TITLE_TAGS = [
    "CHERTEZH", "ЧЕРТЕЖ", "TITLE", "НАИМЕНОВАНИЕ", "НАЗВАНИЕ",
    "НАИМЕНОВАНИЕ_ЛИСТА", "НАИМЕНОВАНИЕЛИСТА", "SHEET_NAME", "DWG_NAME", "ИМЯ_ЛИСТА"
]

DEFAULT_SHIFR_TAGS = [
    "!ШИФР", "!DOC_CODE", "!DOCUM", "!CODE",
    "DOCUM", "SHIFR", "ШИФР", "DOC_CODE", "CODE",
    "DESIGNATION", "ОБОЗНАЧЕНИЕ", "ОБОЗНАЧЕНИЕ_ДОКУМЕНТА", "DWG_CODE", "ПРОЕКТ"
]

DEFAULT_OBJECT_TAGS = [
    "OBJECT", "ОБЪЕКТ", "OBJECT_NAME", "НАИМЕНОВАНИЕ_ОБЪЕКТА",
    "ОБЪЕКТ_СТРОИТЕЛЬСТВА", "COMPLEXNAME", "ПРЕДПРИЯТИЕ",
    "НАИМЕНОВАНИЕ2", "НАИМЕНОВАНИЕ_ОБЪЕКТА1", "PROJECT_NAME"
]

DEFAULT_BUILDING_TAGS = [
    "BUILD", "BUILDING", "ЗДАНИЕ", "BUILDING_NAME",
    "НАИМЕНОВАНИЕ_ЗДАНИЯ", "СООРУЖЕНИЕ", "СООРУЖЕНИЕ2",
    "ПОЗИЦИЯ", "DRAWINGNAME1"
]


def clean_mtext(text: str) -> str:
    """Удаляет коды форматирования MText AutoCAD (\\W0.8;, \\H1.5;, \\P и т.д.)."""
    if not text:
        return ""
    text = re.sub(r"\\[WwHhCcQqTtAaFfOoPpLlKk][^;]*;", "", text)
    text = text.replace(r"\P", " ").replace(r"\p", " ")
    text = text.replace("{", "").replace("}", "")
    return " ".join(text.split())


class BlockParser(BaseParser):
    def __init__(
        self,
        block_names: List[str] = None,
        sheet_attr_tags: List[str] = None,
        title_attr_tags: List[str] = None,
        shifr_attr_tags: List[str] = None,
        object_attr_tags: List[str] = None,
        building_attr_tags: List[str] = None,
    ):
        """
        :param block_names: Список имен блоков или масок (по умолчанию охватывает все популярные рамки)
        :param sheet_attr_tags: Список тегов атрибутов номера листа
        :param title_attr_tags: Список тегов атрибутов названия листа
        :param shifr_attr_tags: Список тегов атрибутов шифра / обозначения (графа 1)
        :param object_attr_tags: Список тегов атрибутов наименования объекта (графа 2)
        :param building_attr_tags: Список тегов атрибутов наименования здания (графа 3)
        """
        raw_names = block_names or DEFAULT_BLOCK_NAMES
        self.block_names = [name.lower() for name in raw_names]
        self.sheet_attr_tags = [tag.upper() for tag in (sheet_attr_tags or DEFAULT_SHEET_TAGS)]
        self.title_attr_tags = [tag.upper() for tag in (title_attr_tags or DEFAULT_TITLE_TAGS)]
        self.shifr_attr_tags = [tag.upper() for tag in (shifr_attr_tags or DEFAULT_SHIFR_TAGS)]
        self.object_attr_tags = [tag.upper() for tag in (object_attr_tags or DEFAULT_OBJECT_TAGS)]
        self.building_attr_tags = [tag.upper() for tag in (building_attr_tags or DEFAULT_BUILDING_TAGS)]

        # Путь к LISP-экстрактору рамок-блоков
        self.lisp_path = get_lisp_path("core/lisp/block_export.lsp")

    @staticmethod
    def _get_attr_value(attrs: dict, tags: List[str]) -> str:
        for t in tags:
            if t in attrs and attrs[t]:
                return attrs[t]
        return ""

    @staticmethod
    def _extract_explicit_format(attrs: dict) -> str:
        """Извлекает формат ГОСТ напрямую из атрибутов блока (например ФОРМАТ="A2x4" или !ФОРМАТ="A4")."""
        for tag in ("!ФОРМАТ", "ФОРМАТ", "FORMAT", "!FORMAT", "РАЗМЕР_ЛИСТА", "РАЗМЕРЛИСТА", "РАЗМЕР"):
            val = attrs.get(tag, "").strip()
            if val:
                norm = val.upper().replace("А", "A").replace(" ", "")
                norm = norm.replace("Х", "x").replace("X", "x")
                if norm.startswith("FORMAT"):
                    norm = norm[6:]
                if norm in ALL_FORMATS:
                    return norm
        return ""

    @classmethod
    def _extract_sheet_name(cls, attrs: dict, tags: List[str]) -> str:
        """Извлекает наименование листа с поддержкой составных многострочных тегов."""
        for prefix in ("НАИМЕНОВАНИЕ_ЛИСТА", "НАИМЕНОВАНИЕЛИСТА", "TITLE_", "NAME_"):
            matching_keys = [k for k in attrs.keys() if k.startswith(prefix) and attrs[k].strip()]
            if matching_keys:
                matching_keys.sort()
                parts = [attrs[k] for k in matching_keys]
                return clean_mtext(" ".join(parts))
        return clean_mtext(cls._get_attr_value(attrs, tags) or "Unknown")

    @classmethod
    def _extract_object_name(cls, attrs: dict, tags: List[str]) -> str:
        """Извлекает наименование объекта с поддержкой составных тегов."""
        for prefix in ("НАИМЕНОВАНИЕ_ОБЪЕКТА", "ОБЪЕКТ_"):
            matching_keys = [k for k in attrs.keys() if k.startswith(prefix) and attrs[k].strip()]
            if matching_keys:
                matching_keys.sort()
                parts = [attrs[k] for k in matching_keys]
                return clean_mtext(" ".join(parts))
        return clean_mtext(cls._get_attr_value(attrs, tags))

    @classmethod
    def _extract_building_name(cls, attrs: dict, tags: List[str]) -> str:
        """Извлекает наименование здания / сооружения с поддержкой составных тегов."""
        for prefix in ("НАИМЕНОВАНИЕ_ЗДАНИЯ", "ЗДАНИЕ_"):
            matching_keys = [k for k in attrs.keys() if k.startswith(prefix) and attrs[k].strip()]
            if matching_keys:
                matching_keys.sort()
                parts = [attrs[k] for k in matching_keys]
                return clean_mtext(" ".join(parts))
        return clean_mtext(cls._get_attr_value(attrs, tags))

    @staticmethod
    def _check_is_title(sheet_num: str, sheet_name: str, block_name: str) -> tuple:
        """
        Проверяет, является ли блок титульным листом.
        Возвращает (sheet_number, sheet_name).
        """
        clean_name = (sheet_name or "").replace("\r", " ").replace("\n", " ").strip()
        if clean_name.lower() == "unknown":
            clean_name = ""

        clean_num = (sheet_num or "").strip()
        if clean_num.lower() == "unknown":
            clean_num = ""

        b_lower = (block_name or "").lower().strip()
        is_title = (
            clean_name.lower() in ("титульный лист", "титул", "обложка")
            or "титул" in b_lower
            or "title" in b_lower
            or "обложк" in b_lower
            or b_lower.endswith("_t")
            or b_lower.endswith("_т")
            or "_t_" in b_lower
            or "_т_" in b_lower
        )
        if is_title:
            return "", "Титульный лист"
        return clean_num or "Unknown", clean_name

    def _convert_items_to_frames(self, items: list) -> List[Frame]:
        # 1. Разделяем блоки на форматы (границы листа) и вложенные штампы
        formats = []
        stamps = []
        for item in items:
            b_name = (item.get("block_name") or "").lower()
            is_stamp = ("stamp" in b_name or "штамп" in b_name) and not ("format" in b_name or "рамк" in b_name or "sht" in b_name)
            if is_stamp:
                stamps.append(item)
            else:
                formats.append(item)

        frames = []
        for fmt_item in formats:
            layout_name = fmt_item.get("layout", "Model") or "Model"
            is_model = layout_name.lower() == "model"
            source_type = "Block" if is_model else "Block (Лист)"

            hdl = fmt_item.get("handle", "")
            b_name = fmt_item.get("block_name", "")
            sc = float(fmt_item.get("scale", 1.0))
            min_x = float(fmt_item.get("min_x", 0.0))
            min_y = float(fmt_item.get("min_y", 0.0))
            max_x = float(fmt_item.get("max_x", 0.0))
            max_y = float(fmt_item.get("max_y", 0.0))

            w = max_x - min_x
            h = max_y - min_y

            # 2. Ищем штамп, геометрически попадающий внутрь этой рамки и на том же листе
            margin = max(100.0, w * 0.02) if is_model else max(10.0, w * 0.02)
            matched_stamp = None
            for st in stamps:
                st_layout = st.get("layout", "Model") or "Model"
                if st_layout.lower() != layout_name.lower():
                    continue
                sx1 = float(st.get("min_x", 0.0))
                sy1 = float(st.get("min_y", 0.0))
                sx2 = float(st.get("max_x", 0.0))
                sy2 = float(st.get("max_y", 0.0))
                if sx1 >= min_x - margin and sy1 >= min_y - margin and sx2 <= max_x + margin and sy2 <= max_y + margin:
                    matched_stamp = st
                    break

            attrs = {k.upper(): str(v).strip() for k, v in fmt_item.get("attrs", {}).items()}
            if matched_stamp:
                stamp_attrs = {k.upper(): str(v).strip() for k, v in matched_stamp.get("attrs", {}).items()}
                for k, v in stamp_attrs.items():
                    if v and (k not in attrs or not attrs[k]):
                        attrs[k] = v

            explicit_fmt = self._extract_explicit_format(attrs)
            fmt = explicit_fmt or detect_paper_format(w, h, b_name, scale=sc)

            num = self._get_attr_value(attrs, self.sheet_attr_tags) or fmt_item.get("sheet_number", "Unknown")
            name = self._extract_sheet_name(attrs, self.title_attr_tags)
            if name == "Unknown" and fmt_item.get("sheet_name", "Unknown") != "Unknown":
                name = clean_mtext(fmt_item.get("sheet_name"))

            doc_code = clean_mtext(self._get_attr_value(attrs, self.shifr_attr_tags))
            object_name = self._extract_object_name(attrs, self.object_attr_tags)
            building_name = self._extract_building_name(attrs, self.building_attr_tags)

            num, name = self._check_is_title(num, name, b_name)

            frame = Frame(
                object_id=0,
                sheet_number=num,
                sheet_name=name,
                min_point=(min_x, min_y, 0.0),
                max_point=(max_x, max_y, 0.0),
                source_type=source_type,
                paper_format=fmt,
                handle=hdl,
                doc_code=doc_code,
                object_name=object_name,
                building_name=building_name,
                layout_name=layout_name
            )
            frames.append(frame)

        return frames

    def _has_block_definitions(self, doc: Any) -> bool:
        # LISP-экспорт sht-export-blocks выполняется за долю секунды и сам эффективно
        # ищет вхождения блоков; COM-перебор doc.Blocks приводил к зависанию на 16+ сек.
        return True

    def _find_frames_via_lisp(self, doc: Any) -> List[Frame]:
        t_start = time.perf_counter()
        patterns = []
        for p in self.block_names:
            patterns.append(p.upper())
            patterns.append(p.lower())
        patterns_str = ",".join(dict.fromkeys(patterns))

        data = self._run_lisp_export(
            doc, self.lisp_path, "sht-export-blocks",
            [patterns_str, ",".join(self.sheet_attr_tags), ",".join(self.title_attr_tags)],
            prefix="acad_blocks")
        frames = self._convert_items_to_frames(data)
        print(f"[BlockParser] LISP экспорт выполнен за {time.perf_counter() - t_start:.3f} сек "
              f"(найдено {len(frames)} рамок)")
        return frames

    def _find_frames_fallback_com(self, doc: Any) -> List[Frame]:
        items = []
        spaces_to_scan = []
        try:
            if hasattr(doc, "ModelSpace"):
                spaces_to_scan.append(("Model", doc.ModelSpace))
        except Exception:
            pass

        try:
            if hasattr(doc, "Layouts"):
                for i in range(doc.Layouts.Count):
                    lyt = doc.Layouts.Item(i)
                    if getattr(lyt, "ModelType", False) or lyt.Name.lower() == "model":
                        continue
                    try:
                        spaces_to_scan.append((lyt.Name, lyt.Block))
                    except Exception:
                        pass
        except Exception:
            pass

        for lyt_name, space in spaces_to_scan:
            try:
                cnt = space.Count
            except Exception:
                continue

            for i in range(cnt):
                try:
                    obj = space.Item(i)
                    if getattr(obj, 'EntityName', '') == 'AcDbBlockReference':
                        block_name = ""
                        try:
                            block_name = obj.EffectiveName
                        except Exception:
                            try:
                                block_name = obj.Name
                            except Exception:
                                pass

                        matched = False
                        for pattern in self.block_names:
                            if fnmatch.fnmatch(block_name.lower(), pattern.lower()):
                                matched = True
                                break

                        if matched:
                            min_pt, max_pt = obj.GetBoundingBox()
                            attrs = {}
                            if obj.HasAttributes:
                                for attr in obj.GetAttributes():
                                    attrs[attr.TagString.upper()] = attr.TextString.strip()

                            blk_scale = getattr(obj, 'XScaleFactor', 1.0)
                            items.append({
                                "handle": getattr(obj, 'Handle', ''),
                                "layout": lyt_name,
                                "block_name": block_name,
                                "sheet_number": "Unknown",
                                "sheet_name": "Unknown",
                                "scale": blk_scale,
                                "min_x": min_pt[0],
                                "min_y": min_pt[1],
                                "max_x": max_pt[0],
                                "max_y": max_pt[1],
                                "attrs": attrs
                            })
                except Exception:
                    continue

        return self._convert_items_to_frames(items)

    @staticmethod
    def _collect_model_texts(doc: Any) -> List[tuple]:
        """
        Быстро извлекает свободные надписи (TEXT и MTEXT) из пространства модели
        через SelectionSet AutoCAD (занимает ~0.01 сек).
        Возвращает: [((min_x + max_x)/2, (min_y + max_y)/2, cleaned_text), ...]
        """
        import pythoncom
        import win32com.client
        from parsers.polyline_parser import _clean_text

        ss_name = "BLOCK_FREE_TEXTS_SS"
        try:
            try:
                doc.SelectionSets.Item(ss_name).Delete()
            except Exception:
                pass
            ss = doc.SelectionSets.Add(ss_name)
            ftype = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_I2, [0, 410])
            fdata = win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, ["TEXT,MTEXT", "Model"])
            no_arg = getattr(pythoncom, "ArgNotFound", pythoncom.Missing)
            ss.Select(5, no_arg, no_arg, ftype, fdata)

            texts = []
            for i in range(ss.Count):
                try:
                    t = ss.Item(i)
                    val = _clean_text(getattr(t, "TextString", ""))
                    if val:
                        mn, mx = t.GetBoundingBox()
                        texts.append(((mn[0] + mx[0]) / 2.0, (mn[1] + mx[1]) / 2.0, val))
                except Exception:
                    continue
            return texts
        except Exception:
            return []
        finally:
            try:
                ss.Delete()
            except Exception:
                pass

    def _enrich_frames_with_free_texts(self, frames: List[Frame], doc: Any) -> List[Frame]:
        """
        Если блок рамки или вложенного штампа не имеет заполненных атрибутов
        (номер/название листа Unknown или пусто, шифр пуст), сканирует свободные
        надписи модели в зоне штампа (Форма 3/4/6 по ГОСТ Р 21.1101).
        """
        needs_enrichment = [
            f for f in frames
            if (f.sheet_number in ("Unknown", "") or f.sheet_name in ("Unknown", ""))
            and getattr(f, "layout_name", "Model").lower() == "model"
        ]
        if not needs_enrichment or not doc:
            return frames

        texts = self._collect_model_texts(doc)
        if not texts:
            return frames

        from parsers.polyline_parser import _read_stamp

        for frame in needs_enrichment:
            w = abs(frame.max_point[0] - frame.min_point[0])
            h = abs(frame.max_point[1] - frame.min_point[1])
            sc = 1.0
            if frame.paper_format in ALL_FORMATS:
                gw, gh = ALL_FORMATS[frame.paper_format]
                sc_x = w / max(gw, gh) if w > h else w / min(gw, gh)
                if sc_x > 0.1:
                    sc = round(sc_x) if abs(sc_x - round(sc_x)) < 0.05 else sc_x

            # Пробуем 2 варианта привязки правого нижнего угла штампа:
            # 1) Внешняя граница формата с полями ГОСТ 5 мм: (max_x - 5*sc, min_y + 5*sc)
            # 2) Внутренняя граница листа (без полей): (max_x, min_y)
            anchors = [
                (frame.max_point[0] - 5.0 * sc, frame.min_point[1] + 5.0 * sc),
                (frame.max_point[0], frame.min_point[1])
            ]
            for ax, ay in anchors:
                num, name, code, obj, bld, _ = _read_stamp((ax, ay), sc, texts)
                if num and num != "Unknown":
                    if frame.sheet_number in ("Unknown", ""):
                        frame.sheet_number = num
                if name and name != "Unknown":
                    if frame.sheet_name in ("Unknown", ""):
                        frame.sheet_name = name
                if code and not frame.doc_code:
                    frame.doc_code = code
                if obj and not frame.object_name:
                    frame.object_name = obj
                if bld and not frame.building_name:
                    frame.building_name = bld

                if frame.sheet_number not in ("Unknown", "") or (frame.sheet_name and frame.sheet_name != "Unknown"):
                    break

        return frames

    def find_frames(self, doc: Any) -> List[Frame]:
        # 1. Быстрая проверка наличия определений блоков в таблице Blocks (0.001 сек)
        if not self._has_block_definitions(doc):
            return []

        # 2. Быстрый экспорт через LISP-мост
        try:
            frames = self._find_frames_via_lisp(doc)
        except Exception as e:
            print(f"Предупреждение: LISP поиск блоков не сработал ({e}), запуск резервного метода...")
            frames = self._find_frames_fallback_com(doc)

        # 3. Геометрическое дообогащение текстами россыпью для блоков без атрибутов
        return self._enrich_frames_with_free_texts(frames, doc)

