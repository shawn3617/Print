import os
import re
import time
import json
import tempfile
from typing import List, Any
from core.models import Frame, detect_paper_format, ALL_FORMATS
from parsers.base_parser import BaseParser

class SPDSParser(BaseParser):
    def __init__(self, spds_names: List[str] = None):
        """
        :param spds_names: Список имен EntityName объектов (для совместимости и fallback)
        """
        self.spds_names = [name.lower() for name in (spds_names or ["mcsdbobjectformat", "spdbformat"])]
        # Путь к LISP-экстрактору на базе алгоритма SHEETS.lsp
        self.lisp_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "core", "lisp", "spds_export.lsp")
        ).replace("\\", "/")

    def _load_sanitized_json(self, filepath: str) -> list:
        """Считывает JSON, заменяя спецсимволы AutoCAD (\\U+2205 и др.) на реальный Unicode и экранируя слэши"""
        with open(filepath, "r", encoding="cp1251") as f:
            text = f.read()
        # 1. Заменяем спецсимволы AutoCAD вида \U+XXXX на Unicode
        clean = re.sub(r'\\U\+([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
        # 2. Экранируем любые недопустимые обратные слэши
        clean = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', clean)
        return json.loads(clean)

    def _find_frames_via_lisp(self, doc: Any) -> List[Frame]:
        """Быстрый поиск всех СПДС-рамок через AutoLISP ядро за доли секунды"""
        if not os.path.exists(self.lisp_path):
            raise FileNotFoundError(f"LISP-скрипт не найден: {self.lisp_path}")

        temp_dir = tempfile.gettempdir()
        temp_json = os.path.join(temp_dir, f"acad_spds_{os.getpid()}_{id(doc)}.json")
        out_path = temp_json.replace("\\", "/")

        if os.path.exists(temp_json):
            try:
                os.remove(temp_json)
            except Exception:
                pass

        try:
            t_start = time.perf_counter()
            lisp_cmd = f'(progn (load "{self.lisp_path}") (sht-export-spds "{out_path}"))\n'
            doc.SendCommand(lisp_cmd)

            data = None
            max_attempts = 100  # до 5 секунд (обычно отрабатывает за 0.05 - 0.15 сек)
            for _ in range(max_attempts):
                time.sleep(0.05)
                if os.path.exists(temp_json) and os.path.getsize(temp_json) > 0:
                    try:
                        data = self._load_sanitized_json(temp_json)
                        break
                    except (json.JSONDecodeError, PermissionError):
                        pass

            if data is None:
                raise TimeoutError("AutoCAD не вернул данные экспорта СПДС за отведенное время.")

            fmt_map = {k.upper(): k for k in ALL_FORMATS.keys()}
            frames = []
            for item in data:
                hdl = item.get("handle", "")
                num = item.get("sheet_number", "Unknown")
                name = item.get("sheet_name", "Unknown")
                raw_fmt = item.get("format", "")
                mult = item.get("multiplicity", 1)
                sc = float(item.get("scale", 1.0))
                min_x = float(item.get("min_x", 0.0))
                min_y = float(item.get("min_y", 0.0))
                max_x = float(item.get("max_x", 0.0))
                max_y = float(item.get("max_y", 0.0))

                w = max_x - min_x
                h = max_y - min_y

                # 1. Формат из свойств СПДС (с учетом кратности AxN)
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

                # 2. Геометрическое определение формата с масштабом
                if not detected_fmt:
                    detected_fmt = detect_paper_format(w, h, scale=sc)

                frame = Frame(
                    object_id=0,
                    sheet_number=num,
                    sheet_name=name.replace("\r", " ").replace("\n", " ").strip(),
                    min_point=(min_x, min_y, 0.0),
                    max_point=(max_x, max_y, 0.0),
                    source_type="SPDS",
                    paper_format=detected_fmt,
                    handle=hdl
                )
                frames.append(frame)

            t_elapsed = time.perf_counter() - t_start
            print(f"[SPDSParser] LISP экспорт выполнен за {t_elapsed:.3f} сек (найдено {len(frames)} рамок)")
            return frames

        finally:
            if os.path.exists(temp_json):
                try:
                    os.remove(temp_json)
                except Exception:
                    pass

    def _find_frames_fallback_com(self, doc: Any) -> List[Frame]:
        """Резервный метод перебора через COM, если LISP недоступен"""
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
        # Основной быстрый путь через LISP-мост
        try:
            return self._find_frames_via_lisp(doc)
        except Exception as e:
            print(f"Предупреждение: LISP поиск СПДС не сработал ({e}), запуск резервного метода...")
            return self._find_frames_fallback_com(doc)
