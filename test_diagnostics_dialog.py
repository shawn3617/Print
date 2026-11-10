"""
Тесты для диалогового окна диагностики (ui/diagnostics_dialog.py).
"""

import sys
import unittest
from PySide6.QtWidgets import QApplication

from core.logger import log_info, log_error, clear_log_buffer
from ui.diagnostics_dialog import DiagnosticsDialog


class TestDiagnosticsDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def setUp(self):
        clear_log_buffer()

    def test_dialog_init_and_refresh(self):
        log_info("Инфо для окна", module="UITest")
        log_error("Ошибка для окна", module="UITest")

        dlg = DiagnosticsDialog(
            current_theme_id="dark_catppuccin",
            extra_info={"acad_status": "AutoCAD 2024", "doc_name": "Test.dwg"}
        )

        self.assertIn("Диагностика", dlg.windowTitle())
        self.assertIn("Инфо для окна", dlg.txt_logs.toPlainText())
        self.assertIn("Ошибка для окна", dlg.txt_logs.toPlainText())

        # Проверка копирования в буфер
        dlg.on_copy_report_clicked()
        cb = QApplication.clipboard()
        self.assertIn("PrintPDF — Отчёт диагностики", cb.text())
        self.assertIn("AutoCAD 2024", cb.text())
        self.assertIn("Инфо для окна", cb.text())

        # Проверка очистки
        dlg.on_clear_clicked()
        self.assertEqual(dlg.txt_logs.toPlainText(), "")

        dlg.close()

    def test_filter_combobox(self):
        log_info("Информационное сообщение", module="UITest")
        log_error("Критическая ошибка", module="UITest")

        dlg = DiagnosticsDialog(current_theme_id="dark_catppuccin")
        
        # Фильтр "Только ошибки"
        idx_err = dlg.combo_level.findData("ERROR")
        dlg.combo_level.setCurrentIndex(idx_err)
        text = dlg.txt_logs.toPlainText()
        self.assertIn("Критическая ошибка", text)
        self.assertNotIn("Информационное сообщение", text)

        dlg.close()

    def test_main_window_fallback_warning_indicator(self):
        from ui.main_window import PrintManagerUI
        from core.models import Frame
        win = PrintManagerUI()
        f1 = Frame(
            object_id=1,
            sheet_number="1",
            sheet_name="План",
            min_point=(0, 0, 0),
            max_point=(420, 297, 0),
            source_type="SPDS",
            paper_format="A3"
        )
        f2 = Frame(
            object_id=2,
            sheet_number="2",
            sheet_name="Разрез",
            min_point=(0, 0, 0),
            max_point=(500, 300, 0),
            source_type="Block",
            paper_format="Нестандартный_500x300",
            fallback_warning="Применен резервный формат A3"
        )
        win.frames = [f1, f2]
        win.table.setRowCount(0)
        win.add_table_row(True, f1.sheet_number, f1.sheet_name, f1.paper_format, f1.source_type, fallback_warning=f1.fallback_warning)
        win.add_table_row(True, f2.sheet_number, f2.sheet_name, f2.paper_format, f2.source_type, fallback_warning=f2.fallback_warning)

        item_fmt1 = win.table.item(0, 6)
        item_fmt2 = win.table.item(1, 6)

        self.assertEqual(item_fmt1.text(), "A3")
        self.assertIn("⚠️", item_fmt2.text())
        self.assertIn("Применен резервный формат", item_fmt2.toolTip())

        win.close()


if __name__ == "__main__":
    unittest.main()
