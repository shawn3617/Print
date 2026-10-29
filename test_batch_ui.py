import os
import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication

from core.models import Frame
from ui.main_window import PrintManagerUI


class TestBatchUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.load.return_value = {}
        self.mock_config.get.side_effect = lambda k, d=None: d
        self.win = PrintManagerUI(config_manager=self.mock_config)

    def test_add_table_row_with_dwg(self):
        self.win.table.setRowCount(0)
        self.win.add_table_row(
            checked=True,
            num="1",
            name="План этажа",
            paper_format="A3",
            source="Model",
            dwg_name="plan_01.dwg"
        )
        self.assertEqual(self.win.table.rowCount(), 1)
        self.assertEqual(self.win.table.item(0, 1).text(), "1")
        self.assertEqual(self.win.table.item(0, 3).text(), "План этажа")
        self.assertEqual(self.win.table.item(0, 6).text(), "A3")
        self.assertEqual(self.win.table.item(0, 7).text(), "plan_01.dwg")
        self.assertEqual(self.win.table.item(0, 8).text(), "Model")

    def test_clear_frames(self):
        self.win.frames = [
            Frame(1, "1", "Лист 1", (0,0,0), (10,10,0), "Model", "A4", dwg_name="a.dwg")
        ]
        self.win.add_table_row(True, "1", "Лист 1", "A4", "Model", dwg_name="a.dwg")
        self.assertEqual(self.win.table.rowCount(), 1)

        self.win.clear_frames()
        self.assertEqual(len(self.win.frames), 0)
        self.assertEqual(self.win.table.rowCount(), 0)

    def test_sort_by_sheet_number_multi_dwg(self):
        # Файл 1 (открыт первым) содержит листы 6..10
        frames_file1 = [
            Frame(i, str(i), f"Лист {i}", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file_6_to_10.dwg")
            for i in range(6, 11)
        ]
        # Файл 2 (добавлен вторым) содержит листы 1..5
        frames_file2 = [
            Frame(i, str(i), f"Лист {i}", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file_1_to_5.dwg")
            for i in range(1, 6)
        ]

        # Имитируем добавление: сначала 6..10, затем 1..5
        self.win.frames = frames_file1 + frames_file2
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)

        self.win.sort_by_sheet_number()

        # Ожидаем сквозную последовательность 1..10
        sorted_nums = [f.sheet_number for f in self.win.frames]
        self.assertEqual(sorted_nums, ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        # Проверяем строки таблицы
        for row in range(10):
            self.assertEqual(self.win.table.item(row, 1).text(), str(row + 1))


    def test_handle_dropped_urls(self):
        url1 = QUrl.fromLocalFile(r"C:\Drawings\test1.dwg")
        url2 = QUrl.fromLocalFile(r"C:\Drawings\notes.txt") # Должен игнорироваться

        with patch("os.path.isfile") as mock_isfile, \
             patch.object(self.win, "process_batch_dwg_files") as mock_process:
            mock_isfile.side_effect = lambda p: p.endswith(".dwg") or p.endswith(".txt")
            self.win.handle_dropped_urls([url1, url2])
            mock_process.assert_called_once()
            args = mock_process.call_args[0][0]
            self.assertEqual(len(args), 1)
            self.assertTrue(args[0].endswith("test1.dwg"))

    def test_update_paper_sizes_picks_a3_fallback(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей B5 (250.00 x 176.00 мм)": "ISO_B5",
            "ISO A4 (210.00 x 297.00 мм)": "ISO_A4",
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
            "ISO A1 (594.00 x 841.00 мм)": "ISO_A1",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO без полей A3 (420.00 x 297.00 мм)")

    def test_update_paper_sizes_ignores_old_b5(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей B5 (250.00 x 176.00 мм)": "ISO_B5",
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "ISO без полей B5 (250.00 x 176.00 мм)" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO без полей A3 (420.00 x 297.00 мм)")

    def test_update_paper_sizes_restores_valid_custom(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
            "ISO A1 (594.00 x 841.00 мм)": "ISO_A1",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "ISO A1 (594.00 x 841.00 мм)" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO A1 (594.00 x 841.00 мм)")


if __name__ == "__main__":
    unittest.main()
