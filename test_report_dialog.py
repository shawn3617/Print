"""
Тесты диалогового окна итогового отчёта (ui/report_dialog.py).
"""

import sys
import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from core.models import Frame
from core.report_models import PrintReport, PrintItemResult, ScanReport, ScanFileResult
from ui.report_dialog import ReportDialog


class TestReportDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_print_report_dialog_display_and_repeat_signal(self):
        f1 = Frame(1, "1", "План", (0, 0, 0), (420, 297, 0), "SPDS", "A3", dwg_name="plan.dwg")
        f2 = Frame(2, "2", "Разрез", (0, 0, 0), (420, 297, 0), "SPDS", "A3", dwg_name="plan.dwg")

        rep = PrintReport(
            total_requested=2,
            success_count=1,
            failed_count=1,
            duration_seconds=3.2,
            output_path="C:/dummy/out.pdf",
            items=[
                PrintItemResult(frame=f1, success=True, output_file="C:/dummy/1.pdf", dwg_name="plan.dwg", sheet_number="1", sheet_name="План"),
                PrintItemResult(frame=f2, success=False, error="Ошибка AutoCAD", dwg_name="plan.dwg", sheet_number="2", sheet_name="Разрез")
            ]
        )

        dlg = ReportDialog(report=rep, current_theme_id="dark_catppuccin")

        self.assertIn("Итоги пакетной печати", dlg.windowTitle())
        self.assertEqual(dlg.table.rowCount(), 2)

        # Проверяем видимость кнопки повтора
        self.assertFalse(dlg.btn_repeat.isHidden())
        self.assertIn("Повторить неудачные (1)", dlg.btn_repeat.text())

        # Проверяем сигнал repeat_requested
        emitted_frames = []
        dlg.repeat_requested.connect(lambda frames: emitted_frames.extend(frames))

        dlg.on_repeat_clicked()
        self.assertEqual(len(emitted_frames), 1)
        self.assertEqual(emitted_frames[0].sheet_number, "2")

        # Проверяем копирование
        dlg.on_copy_clicked()
        cb = QApplication.clipboard()
        self.assertIn("ОТЧЁТ О ПАКЕТНОЙ ПЕЧАТИ", cb.text())
        self.assertIn("Разрез", cb.text())

        dlg.close()

    def test_scan_report_dialog_display(self):
        scan_rep = ScanReport(
            total_files=2,
            success_files_count=1,
            failed_files_count=1,
            total_frames_found=10,
            duration_seconds=1.5,
            file_results=[
                ScanFileResult(file_path="C:/Drawings/good.dwg", file_name="good.dwg", success=True, frames_count=10),
                ScanFileResult(file_path="C:/Drawings/bad.dwg", file_name="bad.dwg", success=False, error="Ошибка COM", frames_count=0)
            ]
        )

        dlg = ReportDialog(report=scan_rep, current_theme_id="dark_catppuccin")
        self.assertIn("Итоги сканирования чертежей", dlg.windowTitle())
        self.assertEqual(dlg.table.rowCount(), 2)
        self.assertFalse(dlg.btn_repeat.isVisible())
        dlg.close()

    def test_main_window_repeat_failed_frames(self):
        from ui.main_window import PrintManagerUI
        win = PrintManagerUI()
        f1 = Frame(1, "1", "План", (0, 0, 0), (420, 297, 0), "SPDS", "A3", handle="H1")
        f2 = Frame(2, "2", "Разрез", (0, 0, 0), (420, 297, 0), "SPDS", "A3", handle="H2")
        f3 = Frame(3, "3", "Схема", (0, 0, 0), (420, 297, 0), "SPDS", "A3", handle="H3")
        win.frames = [f1, f2, f3]
        win.table.setRowCount(0)
        win.add_table_row(True, f1.sheet_number, f1.sheet_name, f1.paper_format, f1.source_type)
        win.add_table_row(True, f2.sheet_number, f2.sheet_name, f2.paper_format, f2.source_type)
        win.add_table_row(True, f3.sheet_number, f3.sheet_name, f3.paper_format, f3.source_type)

        # Все три выбраны изначально
        self.assertTrue(win.is_row_checked(0))
        self.assertTrue(win.is_row_checked(1))
        self.assertTrue(win.is_row_checked(2))

        # Вызываем повтор только для f2
        win.on_repeat_failed_frames([f2])

        self.assertFalse(win.is_row_checked(0))
        self.assertTrue(win.is_row_checked(1))
        self.assertFalse(win.is_row_checked(2))
        win.close()


if __name__ == "__main__":
    unittest.main()
