import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock

from core.models import Frame
from parsers.block_parser import BlockParser


class TestBlockExportLogic(unittest.TestCase):
    def setUp(self):
        self.parser = BlockParser(block_names=["SHT_*", "Формат*"], sheet_attr_tags=["SHEET", "ЛИСТ"])

    def test_load_sanitized_json(self):
        sample_json = (
            '[\n'
            '  {\n'
            '    "handle": "1A2B",\n'
            '    "block_name": "Формат А3",\n'
            '    "sheet_number": "1",\n'
            '    "sheet_name": "План \\U+220512 арматуры",\n'
            '    "scale": 100.0,\n'
            '    "min_x": 0.0,\n'
            '    "min_y": 0.0,\n'
            '    "max_x": 42000.0,\n'
            '    "max_y": 29700.0\n'
            '  }\n'
            ']\n'
        )
        with tempfile.NamedTemporaryFile("w", encoding="cp1251", delete=False, suffix=".json") as f:
            f.write(sample_json)
            temp_path = f.name

        try:
            data = self.parser._load_sanitized_json(temp_path)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["handle"], "1A2B")
            self.assertEqual(data[0]["sheet_number"], "1")
            self.assertIn("\u220512", data[0]["sheet_name"])
            self.assertEqual(data[0]["scale"], 100.0)
            self.assertEqual(data[0]["max_x"], 42000.0)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_parse_json_to_frames(self):
        items = [
            {
                "handle": "100A",
                "block_name": "Формат А3",
                "sheet_number": "5",
                "sheet_name": "Схема расположения колонн",
                "scale": 100.0,
                "min_x": 1000.0,
                "min_y": 2000.0,
                "max_x": 43000.0,
                "max_y": 31700.0,
                "attrs": {
                    "SHIFR": "09-23-КЖ",
                    "OBJECT": "Жилой комплекс",
                    "BUILDING": "Поз. 1"
                }
            },
            {
                "handle": "100B",
                "block_name": "SHT_A4",
                "sheet_number": "6",
                "sheet_name": "Ведомость расхода стали",
                "scale": 1.0,
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 210.0,
                "max_y": 297.0
            }
        ]

        frames = self.parser._convert_items_to_frames(items)
        self.assertEqual(len(frames), 2)

        # Первый лист: А3 (42000 x 29700 при масштабе 1:100)
        f1 = frames[0]
        self.assertEqual(f1.handle, "100A")
        self.assertEqual(f1.sheet_number, "5")
        self.assertEqual(f1.sheet_name, "Схема расположения колонн")
        self.assertEqual(f1.paper_format, "A3")
        self.assertEqual(f1.source_type, "Block")
        self.assertEqual(f1.doc_code, "09-23-КЖ")
        self.assertEqual(f1.object_name, "Жилой комплекс")
        self.assertEqual(f1.building_name, "Поз. 1")

        # Второй лист: А4 (210 x 297 при масштабе 1:1)
        f2 = frames[1]
        self.assertEqual(f2.handle, "100B")
        self.assertEqual(f2.sheet_number, "6")
        self.assertEqual(f2.paper_format, "A4")
        self.assertEqual(f2.source_type, "Block")

    def test_find_frames_fallback_on_lisp_failure(self):
        # Если LISP завершается ошибкой, должен вызываться резервный метод COM
        mock_doc = MagicMock()
        mock_doc.Blocks.Count = 0 # Быстрая проверка
        mock_doc.SendCommand.side_effect = Exception("AutoCAD busy")

        frames = self.parser.find_frames(mock_doc)
        self.assertEqual(frames, [])


    def test_block_title_page_detection(self):
        from core.models import frame_natural_sort_key

        raw_items = [
            {
                "handle": "200A",
                "block_name": "SHT_A3",
                "sheet_number": "1",
                "sheet_name": "План этажа",
                "scale": 1.0,
                "min_x": 0.0,
                "min_y": 0.0,
                "max_x": 420.0,
                "max_y": 297.0
            },
            {
                "handle": "200B",
                "block_name": "SHT_A4",
                "sheet_number": "Unknown",
                "sheet_name": "Титульный лист",
                "scale": 1.0,
                "min_x": 1000.0,
                "min_y": 0.0,
                "max_x": 1210.0,
                "max_y": 297.0
            },
            {
                "handle": "200C",
                "block_name": "SHT_TITLE_A4",
                "sheet_number": "",
                "sheet_name": "",
                "scale": 1.0,
                "min_x": 2000.0,
                "min_y": 0.0,
                "max_x": 2210.0,
                "max_y": 297.0
            },
            {
                "handle": "200D",
                "block_name": "SHT_A4P_T",
                "sheet_number": "Unknown",
                "sheet_name": "",
                "scale": 100.0,
                "min_x": 4140.0,
                "min_y": 3870.0,
                "max_x": 25140.0,
                "max_y": 33570.0,
                "attrs": {
                    "FORMAT": "A4",
                    "ORIENT": "вертикальная"
                }
            }
        ]
        frames = self.parser._convert_items_to_frames(raw_items)
        self.assertEqual(len(frames), 4)

        # Обычный лист
        self.assertEqual(frames[0].sheet_number, "1")
        self.assertEqual(frames[0].sheet_name, "План этажа")

        # Титульник по атрибуту TITLE
        self.assertEqual(frames[1].sheet_number, "")
        self.assertEqual(frames[1].sheet_name, "Титульный лист")

        # Титульник по имени блока SHT_TITLE_A4
        self.assertEqual(frames[2].sheet_number, "")
        self.assertEqual(frames[2].sheet_name, "Титульный лист")

        # Титульник по суффиксу _T (пользовательский блок SHT_A4P_T)
        self.assertEqual(frames[3].sheet_number, "")
        self.assertEqual(frames[3].sheet_name, "Титульный лист")
        self.assertEqual(frames[3].paper_format, "A4")

        # Сортировка: все титульники должны оказаться перед листом 1
        sorted_frames = sorted(frames, key=frame_natural_sort_key)
        self.assertEqual(sorted_frames[0].sheet_name, "Титульный лист")
        self.assertEqual(sorted_frames[1].sheet_name, "Титульный лист")
        self.assertEqual(sorted_frames[2].sheet_name, "Титульный лист")
        self.assertEqual(sorted_frames[3].sheet_number, "1")


if __name__ == "__main__":
    unittest.main()
