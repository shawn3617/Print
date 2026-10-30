import re
import time
from typing import List, Any
from core.models import Frame, detect_paper_format, ALL_FORMATS
from parsers.base_parser import BaseParser

from core.resource_utils import get_resource_path


def clean_rtf(text: str) -> str:
    """Очищает строку от RTF-разметки (используется СПДС в полях Sheet/PageNumber)."""
    if not text or "{\\rtf" not in text:
        return text
    s = text
    s = re.sub(r'\{\\[^}]*\}', '', s)
    s = re.sub(r'\\[a-zA-Z0-9]+ ?', '', s)
    s = re.sub(r'<[^>]*>', '', s)
    s = re.sub(r'[{}]', '', s)
    return s.strip()

class SPDSParser(BaseParser):
    def __init__(self, spds_names: List[str] = None):
        """
        :param spds_names: Список возможных EntityName СПДС-объектов (для COM-сканирования в fallback)
        """
        self.spds_names = [name.lower() for name in (spds_names or ["mcsdbobjectformat", "spdbformat"])]
        # Путь к LISP-экспортеру на базе алгоритмов SHEETS.lsp
        self.lisp_path = get_resource_path("core/lisp/spds_export.lsp")

    def _find_frames_via_lisp(self, doc: Any) -> List[Frame]:
        """Быстрый поиск СПДС-рамок через AutoLISP-экспорт во временный JSON"""
        t_start = time.perf_counter()
        data = self._run_lisp_export(doc, self.lisp_path, "sht-export-spds", prefix="acad_spds")
        frames = self._convert_items_to_frames(data)
        t_elapsed = time.perf_counter() - t_start
        print(f"[SPDSParser] LISP экспорт выполнен за {t_elapsed:.3f} сек (найдено {len(frames)} рамок)")
        return frames

    def _convert_items_to_frames(self, data: list) -> List[Frame]:
        fmt_map = {k.upper(): k for k in ALL_FORMATS.keys()}
        frames = []
        for item in data:
            hdl = item.get("handle", "")
            num = str(item.get("sheet_number") or "").strip()
            if not num or num.lower() == "unknown":
                num = "Unknown"

            name = str(item.get("sheet_name") or "").strip()
            name = re.sub(r'[\r\n\t]+', ' ', name).strip()
            name = re.sub(r'\s+', ' ', name)
            if name.lower() == "unknown":
                name = ""

            raw_fmt = item.get("format", "")
            mult = item.get("multiplicity", 1)
            sc = float(item.get("scale", 1.0))
            ori = str(item.get("orientation", "")).strip().lower()
            min_x = float(item.get("min_x", 0.0))
            min_y = float(item.get("min_y", 0.0))
            max_x = float(item.get("max_x", 0.0))
            max_y = float(item.get("max_y", 0.0))

            w = max_x - min_x
            h = max_y - min_y

            # 1. Поиск в явном свойстве СПДС (с учетом кратности AxN)
            detected_fmt = None
            if raw_fmt:
                clean_fmt = raw_fmt.strip().upper().replace('А', 'A').replace('Х', 'X')
                if mult > 1 and "X" not in clean_fmt:
                    clean_fmt = f"{clean_fmt}X{mult}"
                m_fmt = re.search(r'\b(A[0-4](?:X\d+)?)\b', clean_fmt)
                if m_fmt:
                    fmt_key = m_fmt.group(1).upper()
                    if fmt_key in fmt_map:
                        detected_fmt = fmt_map[fmt_key]

            # 2. Если габариты нулевые, но формат определен - рассчитываем габариты из формата и масштаба
            if (w <= 0 or h <= 0) and detected_fmt and detected_fmt in ALL_FORMATS:
                dim1, dim2 = ALL_FORMATS[detected_fmt]
                if "верт" in ori or "vert" in ori or "port" in ori:
                    fw = min(dim1, dim2) * sc
                    fh = max(dim1, dim2) * sc
                else:
                    fw = max(dim1, dim2) * sc
                    fh = min(dim1, dim2) * sc
                max_x = min_x + fw
                max_y = min_y + fh
                w = fw
                h = fh

            # 3. Геометрический расчет формата по габаритам
            if not detected_fmt:
                detected_fmt = detect_paper_format(w, h, scale=sc)

            shifr = clean_rtf(str(item.get("shifr") or "").strip())
            fields = item.get("fields") or {}
            form = str(item.get("form") or "").strip()
            obj_name = clean_rtf(str(fields.get("ComplexName") or "").strip())
            bld_name = clean_rtf(str(fields.get("DrawingName1") or "").strip()) if form == "3" else ""

            num = clean_rtf(num)
            name = clean_rtf(name)

            # Распознавание титульного листа СПДС:
            # Титульный лист в СПДС не имеет номера листа и либо явно назван «Титульный лист»/«Обложка»,
            # либо у него нет основной надписи (пустой номер, пустое наименование и пустой шифр).
            has_num = bool(num and num.lower() != "unknown")
            is_title = (
                name.lower() in ("титульный лист", "титул", "обложка")
                or (not has_num and not name and not shifr)
            )
            if is_title:
                num = ""
                name = "Титульный лист"

            frame = Frame(
                object_id=0,
                sheet_number=num,
                sheet_name=name,
                min_point=(min_x, min_y, 0.0),
                max_point=(max_x, max_y, 0.0),
                source_type="SPDS",
                paper_format=detected_fmt,
                handle=hdl,
                doc_code=shifr,
                object_name=obj_name,
                building_name=bld_name
            )
            frames.append(frame)

        return frames

    def _find_frames_fallback_com(self, doc: Any) -> List[Frame]:
        """Резервный перебор объектов через COM, если LISP недоступен"""
        frames = []
        try:
            model_space = doc.ModelSpace
        except Exception:
            return frames

        for i in range(model_space.Count):
            try:
                obj = model_space.Item(i)
                entity_name = getattr(obj, 'EntityName', '').lower()

                if entity_name in self.spds_names:
                    min_pt, max_pt = obj.GetBoundingBox()
                    w = max_pt[0] - min_pt[0]
                    h = max_pt[1] - min_pt[1]
                    frame = Frame(
                        object_id=getattr(obj, 'ObjectID', 0),
                        sheet_number="Unknown",
                        sheet_name="Unknown",
                        min_point=min_pt,
                        max_point=max_pt,
                        source_type="SPDS",
                        paper_format=detect_paper_format(w, h),
                        handle=getattr(obj, 'Handle', '')
                    )
                    frames.append(frame)
            except Exception:
                continue

        return frames

    def find_frames(self, doc: Any) -> List[Frame]:
        # Приоритетно быстрый экспорт через LISP-скрипт
        try:
            return self._find_frames_via_lisp(doc)
        except Exception as e:
            print(f"Предупреждение: LISP скан СПДС не сработал ({e}), пробуем перебор COM...")
            return self._find_frames_fallback_com(doc)
