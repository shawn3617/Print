import unittest
import json
import re
from core.models import Frame, detect_paper_format, ALL_FORMATS


def simulate_lisp_spds_extraction(dxf_pairs: list) -> dict:
    """
    Точная симуляция логики AutoLISP из spds_export.lsp для извлечения данных
    из пар DXF (301 . ключ) и (код . значение).
    """
    # 1. Построение dat
    dat = []
    current_key = None
    for code, val in dxf_pairs:
        if code == 301:
            current_key = val
        elif current_key is not None and code in (1, 40, 70, 90, 290, 300):
            dat.append((current_key, val))
            current_key = None

    # Вспомогательная функция проверки непустоты
    def nonempty_str(v):
        if v is None:
            return None
        s = str(v).strip()
        if s != "" and s != "nil":
            return s
        return None

    # Поиск значения по ключу (без учета регистра)
    def get_val(target_key):
        t_up = target_key.upper()
        for k, v in dat:
            if k == target_key or k.upper() == t_up:
                val = nonempty_str(v)
                if val is not None:
                    return val
        return None

    # Поиск первого непустого значения
    def find_first(keys):
        for k in keys:
            v = get_val(k)
            if v is not None:
                return v
        return None

    # Сборка многострочного наименования
    def collect_multiline(prefix_list, max_lines):
        full = ""
        for p in prefix_list:
            if full == "":
                for i in range(1, max_lines + 1):
                    k = f"{p}{i}"
                    val = get_val(k)
                    if val is not None:
                        if full == "":
                            full = val
                        else:
                            full = f"{full} {val}"
        return full if full != "" else None

    # Извлечение полей
    sh_num = find_first(
        ["Лист", "Sheet", "PageNumber", "Page", "Номер листа", "НомерЛиста", "SH_NUM", "NUM", "Number", "Лист1", "Sheet1"]
    )
    if not sh_num:
        sh_num = "Unknown"

    sh_name = collect_multiline(
        ["DrawingName", "Name ", "Name", "Наименование ", "Наименование", "Название ", "Название"],
        9
    )
    if not sh_name:
        sh_name = find_first(
            ["Drawing type", "DrawingName", "ComplexName", "TITLE", "Title", "Наименование", "Название", "Name", "Description", "Subject"]
        )
    if not sh_name:
        sh_name = ""

    shifr = find_first(["Designation", "Обозначение", "Шифр", "Code", "DocCode"]) or ""
    fmt = find_first(["Format", "Формат"]) or ""
    
    mult_raw = find_first(["Multiplicity", "Кратность"])
    try:
        mult = int(mult_raw) if mult_raw else 1
    except (ValueError, TypeError):
        mult = 1
    if mult < 1:
        mult = 1

    sc_raw = find_first(["Scale", "Масштаб"])
    try:
        sc = float(sc_raw) if sc_raw else 1.0
    except (ValueError, TypeError):
        sc = 1.0
    if sc <= 0:
        sc = 1.0

    ori = find_first(["Orientation", "Ориентация"]) or ""

    return {
        "sheet_number": sh_num,
        "sheet_name": sh_name,
        "shifr": shifr,
        "format": fmt,
        "multiplicity": mult,
        "scale": sc,
        "orientation": ori
    }


def parse_spds_json_data(items) -> list:
    """Парсинг списка словарей JSON в объекты Frame (как в parsers/spds_parser.py)"""
    fmt_map = {k.upper(): k for k in ALL_FORMATS.keys()}
    frames = []
    for item in items:
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
    def test_user_spds_stamp_dxf_extraction(self):
        """Тест на реальном объекте пользователя с пустыми Sheet/Drawing type и заполненными Лист/DrawingName1"""
        user_dxf = [
            (0, "SPDSFORMAT"),
            (5, "2C0"),
            (301, "Name"), (300, ""),
            (301, "Info"), (300, "Обозначение\t\nФормат\tA4\nЛист\t"),
            (301, "Scale"), (40, 100.0),
            (301, "Designation"), (300, ""),
            (301, "Drawing type"), (300, ""),  # Пустой Drawing type
            (301, "DrawingName1"), (300, "увацуаыаыуаыаываываыва"),  # Реальное имя листа!
            (301, "PageNumber"), (300, ""),
            (301, "Лист"), (300, "1"),  # Реальный номер листа!
            (301, "Sheet"), (300, ""),  # Пустой Sheet
            (301, "Format"), (300, "A4"),
            (301, "Orientation"), (300, "Вертикальный"),
            (301, "Multiplicity"), (90, 1),
            (301, "OriginX"), (40, 20090.1),
            (301, "OriginY"), (40, 20939.3),
        ]

        result = simulate_lisp_spds_extraction(user_dxf)

        # Проверяем номер и название
        self.assertEqual(result["sheet_number"], "1")
        self.assertEqual(result["sheet_name"], "увацуаыаыуаыаываываыва")
        self.assertEqual(result["format"], "A4")
        self.assertEqual(result["orientation"], "Вертикальный")
        self.assertEqual(result["scale"], 100.0)

    def test_multiline_drawing_name_extraction(self):
        """Тест многострочного названия листа (DrawingName1 + DrawingName2)"""
        dxf = [
            (301, "DrawingName1"), (300, "План расположения фундаментов"),
            (301, "DrawingName2"), (300, "на отм. 0.000"),
            (301, "Лист"), (300, "12"),
            (301, "Format"), (300, "A2"),
        ]
        result = simulate_lisp_spds_extraction(dxf)
        self.assertEqual(result["sheet_number"], "12")
        self.assertEqual(result["sheet_name"], "План расположения фундаментов на отм. 0.000")

    def test_parse_sample_spds_json(self):
        sample_json = """
        [
          {
            "handle": "2C0",
            "sheet_number": "1",
            "sheet_name": "увацуаыаыуаыаываываыва",
            "shifr": "",
            "format": "A4",
            "multiplicity": 1,
            "scale": 100.0,
            "orientation": "Вертикальный",
            "min_x": 20090.089,
            "min_y": 20939.269,
            "max_x": 41090.089,
            "max_y": 50639.269
          }
        ]
        """
        items = json.loads(sample_json)
        frames = parse_spds_json_data(items)

        self.assertEqual(len(frames), 1)
        f = frames[0]
        self.assertEqual(f.handle, "2C0")
        self.assertEqual(f.sheet_number, "1")
        self.assertEqual(f.sheet_name, "увацуаыаыуаыаываываыва")
        self.assertEqual(f.paper_format, "A4")
        self.assertEqual(f.source_type, "SPDS")

    def test_empty_json(self):
        frames = parse_spds_json_data([])
        self.assertEqual(len(frames), 0)


    def test_spds_title_page_and_rtf_detection(self):
        from parsers.spds_parser import SPDSParser, clean_rtf
        
        # Тест clean_rtf
        rtf_num = '{\\rtf1\\ansi\\deff0{\\fonttbl{\\f0\\fnil\\fcharset0 CS Standard;}}  \\fs17  \\v\\embo\\impr <ref id="2094871149">\\v0\\embo0 1\\v\\embo </ref>\\v0\\embo0\\impr0  \\par  }'
        self.assertEqual(clean_rtf(rtf_num), "1")

        # Тест титульного листа SPDS (idTemplate = -3)
        parser = SPDSParser()
        raw_items = [
            {
                "handle": "48F",
                "form": "6",
                "sheet_number": rtf_num,
                "sheet_name": "",
                "shifr": "",
                "format": "A4",
                "multiplicity": 1,
                "scale": 100.0,
                "orientation": "Вертикальный",
                "min_x": 112739.0,
                "min_y": 6752.0,
                "max_x": 133739.0,
                "max_y": 36452.0,
                "fields": {
                    "idTemplate": "-3"
                }
            },
            {
                "handle": "490",
                "form": "3",
                "sheet_number": "2",
                "sheet_name": "План перекрытия",
                "shifr": "01-24",
                "format": "A3",
                "scale": 100.0,
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 42000.0,
                "max_y": 29700.0,
                "fields": {
                    "idTemplate": "3"
                }
            }
        ]
        frames = parser._convert_items_to_frames(raw_items)
        self.assertEqual(len(frames), 2)
        
        # Титульник должен иметь пустой номер и имя "Титульный лист"
        self.assertEqual(frames[0].sheet_number, "")
        self.assertEqual(frames[0].sheet_name, "Титульный лист")
        self.assertEqual(frames[0].paper_format, "A4")
        
        # Обычный лист
        self.assertEqual(frames[1].sheet_number, "2")
        self.assertEqual(frames[1].sheet_name, "План перекрытия")

        # Проверка сортировки: титульник всегда первый
        from core.models import frame_natural_sort_key
        sorted_frames = sorted(frames, key=frame_natural_sort_key)
        self.assertEqual(sorted_frames[0].sheet_name, "Титульный лист")
        self.assertEqual(sorted_frames[1].sheet_number, "2")


if __name__ == "__main__":
    unittest.main()
