import os
import tempfile
import unittest
import csv
import openpyxl

from core.models import Frame
from core.exporter import SheetExporter


class TestSheetExporter(unittest.TestCase):
    def setUp(self):
        self.frames = [
            Frame(1, "1", "Общие данные", (0, 0, 0), (10, 10, 0), "Model", "A4", dwg_name="01_plan.dwg"),
            Frame(2, "2", "План первого этажа", (10, 0, 0), (20, 10, 0), "Model", "A3", dwg_name="01_plan.dwg"),
            Frame(3, "3", "Спецификация пилонов", (20, 0, 0), (30, 10, 0), "Model", "A2", dwg_name="02_pilons.dwg"),
        ]

    def test_export_to_csv(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv", encoding="utf-8-sig") as f:
            temp_path = f.name

        try:
            SheetExporter.export_to_csv(self.frames, temp_path)
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 0)

            with open(temp_path, "r", encoding="utf-8-sig") as f:
                reader = list(csv.reader(f, delimiter=";"))
                self.assertEqual(len(reader), 4)  # 1 header + 3 rows
                header = reader[0]
                self.assertIn("Лист", header)
                self.assertIn("Наименование листа", header)
                self.assertIn("Формат", header)

                row1 = reader[1]
                self.assertEqual(row1[1], "1")
                self.assertEqual(row1[2], "Общие данные")
                self.assertEqual(row1[3], "A4")
                self.assertEqual(row1[4], "01_plan.dwg")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_export_to_xlsx(self):
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".xlsx") as f:
            temp_path = f.name

        try:
            SheetExporter.export_to_xlsx(self.frames, temp_path)
            self.assertTrue(os.path.exists(temp_path))
            self.assertGreater(os.path.getsize(temp_path), 0)

            wb = openpyxl.load_workbook(temp_path)
            ws = wb.active
            self.assertEqual(ws.max_row, 4)
            self.assertEqual(ws.cell(row=1, column=2).value, "Лист")
            self.assertEqual(ws.cell(row=2, column=2).value, "1")
            self.assertEqual(ws.cell(row=2, column=3).value, "Общие данные")
            self.assertEqual(ws.cell(row=2, column=4).value, "A4")
            wb.close()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


if __name__ == "__main__":
    unittest.main()
