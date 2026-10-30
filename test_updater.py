"""
Тесты для модуля автоматического обновления (core/updater.py и ui/update_dialog.py).
"""

import unittest
from unittest.mock import patch, MagicMock
import io
import json
import urllib.error

from core.updater import (
    parse_version,
    is_newer_version,
    UpdateInfo,
    check_for_updates,
    download_file
)


class TestUpdater(unittest.TestCase):

    def test_parse_version(self):
        self.assertEqual(parse_version("1.3.0"), (1, 3, 0))
        self.assertEqual(parse_version("v1.3.1"), (1, 3, 1))
        self.assertEqual(parse_version("V2.0"), (2, 0))
        self.assertEqual(parse_version("1.10.2"), (1, 10, 2))
        self.assertEqual(parse_version(""), (0,))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("1.3.1", "1.3.0"))
        self.assertTrue(is_newer_version("v1.4.0", "1.3.9"))
        self.assertTrue(is_newer_version("2.0.0", "1.99.99"))
        self.assertFalse(is_newer_version("1.3.0", "1.3.0"))
        self.assertFalse(is_newer_version("1.2.9", "1.3.0"))
        self.assertFalse(is_newer_version("v1.3.0", "1.3.1"))

    @patch("urllib.request.urlopen")
    def test_check_for_updates_new_version_available(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        payload = {
            "tag_name": "v1.4.0",
            "name": "PrintPDF Релиз 1.4.0",
            "body": "- Добавлена новая функция\n- Исправлена ошибка",
            "published_at": "2026-11-01T12:00:00Z",
            "html_url": "https://github.com/shawn3617/Print/releases/tag/v1.4.0",
            "assets": [
                {
                    "name": "PrintPDF_Setup_v1.4.0.exe",
                    "browser_download_url": "https://github.com/.../PrintPDF_Setup_v1.4.0.exe",
                    "size": 38500000
                },
                {
                    "name": "PrintPDF_v1.4.0_Portable.zip",
                    "browser_download_url": "https://github.com/.../PrintPDF_v1.4.0_Portable.zip",
                    "size": 54000000
                }
            ]
        }
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = check_for_updates(current_version="1.3.0")
        self.assertIsNotNone(info)
        self.assertEqual(info.version, "1.4.0")
        self.assertEqual(info.title, "PrintPDF Релиз 1.4.0")
        self.assertEqual(info.installer_name, "PrintPDF_Setup_v1.4.0.exe")
        self.assertIn("PrintPDF_Setup_v1.4.0.exe", info.installer_url)
        self.assertEqual(info.installer_size, 38500000)
        self.assertIn("36.7 МБ", info.formatted_size_mb)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_already_latest(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        payload = {
            "tag_name": "v1.3.0",
            "name": "PrintPDF 1.3.0",
            "assets": []
        }
        mock_response.read.return_value = json.dumps(payload).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        info = check_for_updates(current_version="1.3.0")
        self.assertIsNone(info)

    @patch("urllib.request.urlopen")
    def test_check_for_updates_network_error(self, mock_urlopen):
        # При сетевой ошибке или таймауте не должно быть падений
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        info = check_for_updates(current_version="1.3.0")
        self.assertIsNone(info)

    @patch("urllib.request.urlopen")
    def test_download_file_success(self, mock_urlopen):
        import tempfile
        import os

        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": "12"}
        mock_response.read.side_effect = [b"Hello ", b"World!", b""]
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with tempfile.NamedTemporaryFile(delete=False) as tf:
            target_file = tf.name

        try:
            progress_calls = []
            def on_progress(d, t):
                progress_calls.append((d, t))

            ok = download_file("http://example.com/test.exe", target_file, progress_callback=on_progress)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(target_file))
            with open(target_file, "rb") as f:
                self.assertEqual(f.read(), b"Hello World!")
            self.assertGreater(len(progress_calls), 0)
        finally:
            if os.path.exists(target_file):
                os.remove(target_file)


class TestUpdateDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        import sys
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_update_dialog_init(self):
        from ui.update_dialog import UpdateDialog

        info = UpdateInfo(
            version="1.4.0",
            title="Тестовый релиз 1.4.0",
            changelog="* Новая версия 1.4.0\n* Исправление ошибки",
            published_at="2026-10-30",
            html_url="https://github.com/shawn3617/Print/releases",
            installer_url="https://example.com/setup.exe",
            installer_name="PrintPDF_Setup_v1.4.0.exe",
            installer_size=36000000
        )

        dlg = UpdateDialog(info, current_version="1.3.0", current_theme_id="dark_graphite")
        self.assertIn("1.4.0", dlg.windowTitle())
        self.assertIn("1.4.0", dlg.txt_changelog.toPlainText())
        self.assertTrue(dlg.btn_update.isEnabled())
        dlg.close()


if __name__ == "__main__":
    unittest.main()
