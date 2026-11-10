"""
Тесты для диалогового окна диагностики (ui/diagnostics_dialog.py).
"""

import sys
import unittest
from unittest.mock import patch
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
        with patch.object(QApplication.clipboard(), "setText") as mock_set:
            dlg.on_copy_report_clicked()
            mock_set.assert_called_once()
            copied_text = mock_set.call_args[0][0]
            self.assertIn("PrintPDF — Отчёт диагностики", copied_text)
            self.assertIn("AutoCAD 2024", copied_text)
            self.assertIn("Инфо для окна", copied_text)

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

    def test_stats_tab_and_copy_reset(self):
        from core.stats_manager import get_stats_manager
        from core.report_models import PrintReport, PrintItemResult
        from core.models import Frame
        from PySide6.QtWidgets import QMessageBox

        sm = get_stats_manager()
        sm.reset_stats()
        rep = PrintReport(
            total_requested=2,
            success_count=2,
            failed_count=0,
            fallback_count=1,
            duration_seconds=6.0,
            items=[
                PrintItemResult(frame=Frame(1, "1", "План", (0, 0, 0), (420, 297, 0), "SPDS", "A3"), success=True),
                PrintItemResult(frame=Frame(2, "2", "Разрез", (0, 0, 0), (420, 297, 0), "SPDS", "A3"), success=True, fallback_used=True)
            ]
        )
        sm.record_print_batch(rep)

        dlg = DiagnosticsDialog(current_theme_id="dark_catppuccin", initial_tab=1)
        self.assertEqual(dlg.tab_widget.currentIndex(), 1)
        self.assertEqual(dlg.lbl_card_sheets_val.text(), "2")
        self.assertIn("100.0%", dlg.lbl_card_rate_val.text())
        self.assertIn("4 мин", dlg.lbl_card_time_val.text())
        self.assertIn("СТАТИСТИКА ИСПОЛЬЗОВАНИЯ", dlg.txt_stats.toPlainText())

        # Копирование статистики
        with patch.object(QApplication.clipboard(), "setText") as mock_set:
            dlg.on_copy_stats_clicked()
            mock_set.assert_called_once()
            copied = mock_set.call_args[0][0]
            self.assertIn("СТАТИСТИКА ИСПОЛЬЗОВАНИЯ И ЭФФЕКТИВНОСТИ", copied)
            self.assertIn("Успешно напечатано:        2", copied)

        # Сброс статистики (пользователь соглашается)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            dlg.on_reset_stats_clicked()
            self.assertEqual(dlg.lbl_card_sheets_val.text(), "0")
            self.assertIn("0.0%", dlg.lbl_card_rate_val.text())
            self.assertIn("0 мин", dlg.lbl_card_time_val.text())

        dlg.close()


if __name__ == "__main__":
    unittest.main()
