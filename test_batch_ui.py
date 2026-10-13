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
        self.assertEqual(self.win.table.item(0, 2).text(), "План этажа")
        self.assertEqual(self.win.table.item(0, 3).text(), "A3")
        self.assertEqual(self.win.table.item(0, 4).text(), "plan_01.dwg")
        self.assertEqual(self.win.table.item(0, 5).text(), "Model")

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
        f1 = Frame(1, "2", "Лист 2", (0,0,0), (10,10,0), "Model", "A4", dwg_name="B_file.dwg")
        f2 = Frame(2, "1", "Лист 1", (0,0,0), (10,10,0), "Model", "A4", dwg_name="B_file.dwg")
        f3 = Frame(3, "5", "Лист 5", (0,0,0), (10,10,0), "Model", "A4", dwg_name="A_file.dwg")

        self.win.frames = [f1, f2, f3]
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)

        self.win.sort_by_sheet_number()

        # Ожидаем группировку: сначала A_file (Лист 5), затем B_file (Лист 1, Лист 2)
        sorted_dwgs = [f.dwg_name for f in self.win.frames]
        sorted_nums = [f.sheet_number for f in self.win.frames]
        self.assertEqual(sorted_dwgs, ["A_file.dwg", "B_file.dwg", "B_file.dwg"])
        self.assertEqual(sorted_nums, ["5", "1", "2"])

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


if __name__ == "__main__":
    unittest.main()
