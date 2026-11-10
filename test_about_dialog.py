"""
Unit-тесты для диалогового окна «О программе» (AboutDialog).
"""

import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from ui.about_dialog import AboutDialog, APP_NAME, APP_VERSION


class TestAboutDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def test_init_about_dialog_all_themes(self):
        for theme_id in ["dark_catppuccin", "autocad_dark", "light"]:
            dlg = AboutDialog(current_theme_id=theme_id)
            self.assertEqual(dlg.current_theme_id, theme_id)
            self.assertIn("О программе", dlg.windowTitle())
            self.assertIsNotNone(dlg.diag_text)
            self.assertIn(APP_NAME, dlg.diag_text)
            self.assertIn(APP_VERSION, dlg.diag_text)

    def test_about_dialog_with_mock_connector(self):
        mock_connector = MagicMock()
        mock_connector.app.Caption = "Autodesk AutoCAD 2024 - [01-АР.dwg]"
        mock_connector.app.Version = "24.3s (LMS Tech)"
        mock_connector.get_active_document_name.return_value = "01-АР.dwg"

        dlg = AboutDialog(current_theme_id="dark_catppuccin", connector=mock_connector)
        self.assertIn("AutoCAD 2024", dlg.diag_text)
        self.assertIn("01-АР.dwg", dlg.diag_text)

        # Тест копирования в буфер обмена
        dlg.copy_diagnostics()
        QApplication.processEvents()
        clipboard_text = QApplication.clipboard().text()
        self.assertEqual(clipboard_text, dlg.diag_text)

    def test_about_dialog_stats_card_and_open_diagnostics(self):
        from unittest.mock import patch
        from core.stats_manager import get_stats_manager

        sm = get_stats_manager()
        sm.reset_stats()

        dlg = AboutDialog(current_theme_id="dark_catppuccin")
        self.assertIn("Листов напечатано: 0", dlg.lbl_stats_body.text())

        # Проверка вызова open_diagnostics с tab_index=1
        with patch.object(dlg, "open_diagnostics") as mock_open:
            dlg.btn_open_stats.click()
            mock_open.assert_called_once_with(tab_index=1)

        dlg.close()


if __name__ == "__main__":
    unittest.main()
