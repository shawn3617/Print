import unittest
import json
from core.models import Frame, detect_paper_format, ALL_FORMATS

def parse_spds_json_data(items) -> list:
    """Функция преобразования словарей из JSON в объекты Frame"""
    frames = []
    for item in items:
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
        
        # 1. Попытка определить по строке формата СПДС (например "A3", "A4x3")
        detected_fmt = None
        if raw_fmt:
            import re
            clean_fmt = raw_fmt.strip().upper().replace('А', 'A').replace('Х', 'X')
            if mult > 1 and "X" not in clean_fmt:
                clean_fmt = f"{clean_fmt}X{mult}"
            m_fmt = re.search(r'\b(A[0-4](?:X\d+)?)\b', clean_fmt)
            if m_fmt:
                fmt_key_upper = m_fmt.group(1).upper()
                fmt_map = {k.upper(): k for k in ALL_FORMATS.keys()}
                if fmt_key_upper in fmt_map:
                    detected_fmt = fmt_map[fmt_key_upper]
                
        # 2. Если по строке не вышло, определяем геометрически с масштабом
        if not detected_fmt:
            detected_fmt = detect_paper_format(w, h, scale=sc)
            
        frame = Frame(
            object_id=0,
            sheet_number=num,
            sheet_name=name,
            min_point=(min_x, min_y, 0.0),
            max_point=(max_x, max_y, 0.0),
            source_type="SPDS",
            paper_format=detected_fmt,
            handle=hdl
        )
        frames.append(frame)
    return frames

class TestSPDSExportLogic(unittest.TestCase):
    def test_parse_sample_spds_json(self):
        sample_json = """
        [
          {
            "handle": "2E8",
            "sheet_number": "1",
            "sheet_name": "План 1 этажа",
            "shifr": "01-2026-АР",
            "format": "A3",
            "multiplicity": 1,
            "scale": 100.0,
            "orientation": "L",
            "min_x": 0.0,
            "min_y": 0.0,
            "max_x": 42000.0,
            "max_y": 29700.0
          },
          {
            "handle": "2E9",
            "sheet_number": "2",
            "sheet_name": "План 2 этажа",
            "shifr": "01-2026-АР",
            "format": "A4",
            "multiplicity": 3,
            "scale": 50.0,
            "orientation": "L",
            "min_x": 50000.0,
            "min_y": 0.0,
            "max_x": 81500.0,
            "max_y": 14850.0
          }
        ]
        """
        items = json.loads(sample_json)
        frames = parse_spds_json_data(items)
        
        self.assertEqual(len(frames), 2)
        
        # Проверяем первый лист
        f1 = frames[0]
        self.assertEqual(f1.handle, "2E8")
        self.assertEqual(f1.sheet_number, "1")
        self.assertEqual(f1.sheet_name, "План 1 этажа")
        self.assertEqual(f1.paper_format, "A3")
        self.assertEqual(f1.source_type, "SPDS")
        self.assertEqual(f1.min_point, (0.0, 0.0, 0.0))
        self.assertEqual(f1.max_point, (42000.0, 29700.0, 0.0))
        
        # Проверяем второй лист (A4x3)
        f2 = frames[1]
        self.assertEqual(f2.handle, "2E9")
        self.assertEqual(f2.sheet_number, "2")
        self.assertEqual(f2.paper_format, "A4x3")
        
    def test_empty_json(self):
        frames = parse_spds_json_data([])
        self.assertEqual(len(frames), 0)

if __name__ == "__main__":
    unittest.main()
