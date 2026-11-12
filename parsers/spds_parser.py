import re
import time
from typing import List, Any
from core.models import Frame, detect_paper_format, detect_paper_format_detailed, ALL_FORMATS
from parsers.base_parser import BaseParser
from core.logger import log_warn
from core.resource_utils import get_resource_path, get_lisp_path


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


def _join_stamp_fields(fields: dict, *keys: str) -> str:
    lines = (clean_rtf(str(fields.get(key) or "").strip()) for key in keys)
    return " ".join(line for line in lines if line)


class SPDSParser(BaseParser):
    def __init__(self, spds_names: List[str] = None):
        """
        :param spds_names: Список возможных EntityName СПДС-объектов (для COM-сканирования в fallback)
        """
        self.spds_names = [name.lower() for name in (spds_names or ["mcsdbobjectformat", "spdbformat"])]
        # Путь к LISP-экспортеру на базе алгоритмов SHEETS.lsp
        self.lisp_path = get_lisp_path("core/lisp/spds_export.lsp")

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
            det_res = detect_paper_format_detailed(w, h, scale=sc)
            if not detected_fmt:
                detected_fmt = det_res.paper_format
                scale_val = det_res.scale
                reason = det_res.reason
                is_ambig = det_res.is_ambiguous
            else:
                scale_val = det_res.scale
                reason = f"Свойства СПДС ({detected_fmt})"
                is_ambig = False

            shifr = clean_rtf(str(item.get("shifr") or "").strip())
            fields = item.get("fields") or {}
            form = str(item.get("form") or "").strip()
            if form == "3":
                obj_name = _join_stamp_fields(fields, "ComplexName", "ComplexName1", "ComplexName2")
                bld_name = _join_stamp_fields(fields, "DrawingName1", "DrawingName2", "DrawingName3")
            else:
                obj_name = _join_stamp_fields(fields, "ComplexName")
                bld_name = ""

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

            layout_name = item.get("layout", "Model") or "Model"
            is_model = layout_name.lower() == "model"
            source_type = "SPDS" if is_model else "SPDS (Лист)"

            frame = Frame(
                object_id=0,
                sheet_number=num,
                sheet_name=name,
                min_point=(min_x, min_y, 0.0),
                max_point=(max_x, max_y, 0.0),
                source_type=source_type,
                paper_format=detected_fmt,
                handle=hdl,
                doc_code=shifr,
                object_name=obj_name,
                building_name=bld_name,
                layout_name=layout_name,
                scale=scale_val,
                format_reason=reason,
                possible_formats=[(c.paper_format, c.scale) for c in det_res.candidates],
                is_ambiguous=is_ambig
            )
            frames.append(frame)

        return frames

    def _find_frames_fallback_com(self, doc: Any) -> List[Frame]:
        """Резервный перебор объектов через COM, если LISP недоступен"""
        frames = []
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

            is_model = lyt_name.lower() == "model"
            source_type = "SPDS" if is_model else "SPDS (Лист)"

            for i in range(cnt):
                try:
                    obj = space.Item(i)
                    entity_name = getattr(obj, 'EntityName', '').lower()

                    if entity_name in self.spds_names:
                        min_pt, max_pt = obj.GetBoundingBox()
                        w = max_pt[0] - min_pt[0]
                        h = max_pt[1] - min_pt[1]
                        det_res = detect_paper_format_detailed(w, h)
                        frame = Frame(
                            object_id=getattr(obj, 'ObjectID', 0),
                            sheet_number="Unknown",
                            sheet_name="Unknown",
                            min_point=min_pt,
                            max_point=max_pt,
                            source_type=source_type,
                            paper_format=det_res.paper_format,
                            handle=getattr(obj, 'Handle', ''),
                            layout_name=lyt_name,
                            scale=det_res.scale,
                            format_reason=det_res.reason,
                            possible_formats=[(c.paper_format, c.scale) for c in det_res.candidates],
                            is_ambiguous=det_res.is_ambiguous
                        )
                        frames.append(frame)
                except Exception:
                    continue

        return frames

    def find_frames(self, doc: Any) -> List[Frame]:
        # Приоритетно быстрый экспорт через LISP-скрипт
        try:
            frames = self._find_frames_via_lisp(doc)
        except Exception as e:
            print(f"Предупреждение: LISP скан СПДС не сработал ({e}), пробуем перебор COM...")
            log_warn(f"LISP скан СПДС не сработал ({e}), пробуем перебор COM", exc=e, module="SPDSParser")
            frames = self._find_frames_fallback_com(doc)

        from parsers.block_parser import BlockParser
        return BlockParser()._enrich_frames_with_free_texts(frames, doc)
