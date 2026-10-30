import unittest
import sys
import os

from PySide6.QtWidgets import QApplication

# Ensure QApplication exists for UI tests
app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui.help_dialog import HelpDialog, _get_help_html


class TestHelpDialog(unittest.TestCase):
    def test_help_dialog_creation_and_tabs(self):
        dlg = HelpDialog(current_theme_id="dark_catppuccin")
        self.assertEqual(dlg.tabs.count(), 5)
        self.assertIn("quickstart", dlg.browsers)
        self.assertIn("faq", dlg.browsers)

        # Проверяем, что HTML содержит ключевые разделы
        html_qs = dlg.browsers["quickstart"].toHtml()
        self.assertIn("Быстрый старт", html_qs)

        html_frames = dlg.browsers["frames"].toHtml()
        self.assertIn("СПДС", html_frames)

        html_faq = dlg.browsers["faq"].toHtml()
        self.assertIn("F1", html_faq)

    def test_theme_update(self):
        dlg = HelpDialog(current_theme_id="dark_catppuccin")
        dlg.update_theme("light")
        self.assertEqual(dlg.current_theme_id, "light")
        dlg.update_theme("autocad_dark")
        self.assertEqual(dlg.current_theme_id, "autocad_dark")


if __name__ == "__main__":
    unittest.main()
