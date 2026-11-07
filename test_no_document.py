"""
Запуск без открытых чертежей (стартовая вкладка AutoCAD):
подключение без ошибок, поля печати заполнены из config.json, резервный формат находится по имени.
"""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication

from core.autocad_connector import AutoCADConnector
from core.printer import BatchPrinter


class TestConnectWithoutDocuments(unittest.TestCase):
    @patch.object(AutoCADConnector, "_ensure_trusted_paths", return_value=None)
    @patch("core.autocad_connector.win32com.client.GetActiveObject")
    def test_connect_without_documents_is_quiet(self, mock_get, _trusted):
        app = MagicMock()
        app.Documents.Count = 0
        type(app).ActiveDocument = property(lambda self: (_ for _ in ()).throw(
            AssertionError("ActiveDocument не должен вызываться, когда чертежей нет")))
        mock_get.return_value = app

        conn = AutoCADConnector()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertTrue(conn.connect())
        self.assertIsNone(conn.doc)
        self.assertNotIn("COM-ошибка", out.getvalue())
        self.assertEqual(conn.get_active_document_name(), "Нет открытого чертежа")


class TestResolveFallbackMedia(unittest.TestCase):
    def setUp(self):
        self.doc = MagicMock()
        layout = self.doc.ModelSpace.Layout
        layout.GetCanonicalMediaNames.return_value = ["ISO_full_bleed_A3_(420.00_x_297.00_MM)", "ISO_A1"]
        layout.GetLocaleMediaName.side_effect = lambda s: {
            "ISO_full_bleed_A3_(420.00_x_297.00_MM)": "ISO без полей A3 (420.00 x 297.00 мм)",
            "ISO_A1": "ISO A1 (841.00 x 594.00 мм)",
        }[s]
        self.printer = BatchPrinter(self.doc)

    def test_local_name_is_converted(self):
        self.assertEqual(
            self.printer._resolve_media_name("ISO без полей A3 (420.00 x 297.00 мм)", {}),
            "ISO_full_bleed_A3_(420.00_x_297.00_MM)")

    def test_canonical_name_kept(self):
        self.assertEqual(self.printer._resolve_media_name("ISO_A1", {}), "ISO_A1")

    def test_empty_name_uses_a3(self):
        media_map = {"A3": "ISO_full_bleed_A3_(420.00_x_297.00_MM)", "A1": "ISO_A1"}
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.printer._resolve_media_name("", media_map),
                             "ISO_full_bleed_A3_(420.00_x_297.00_MM)")


class TestPrintSettingsFromConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _window(self, cfg: dict):
        from ui.main_window import PrintManagerUI
        mock_config = MagicMock()
        mock_config.load.return_value = dict(cfg)
        mock_config.get.side_effect = lambda k, d=None: cfg.get(k, d)
        return PrintManagerUI(config_manager=mock_config)

    def test_fields_filled_from_config(self):
        cfg = {
            "printer": "PDF_ГОСТ.pc3",
            "plot_style": "monochrome.ctb",
            "fallback_paper": "ISO без полей A3 (420.00 x 297.00 мм)",
            "fallback_paper_canonical": "ISO_full_bleed_A3_(420.00_x_297.00_MM)",
        }
        win = self._window(cfg)
        win.load_printer_settings_from_config()
        self.assertEqual(win.combo_printers.currentText(), "PDF_ГОСТ.pc3")
        self.assertEqual(win.combo_style.currentText(), "monochrome.ctb")
        self.assertEqual(win.combo_papers.currentText(), "ISO без полей A3 (420.00 x 297.00 мм)")
        self.assertEqual(win.paper_dict[win.combo_papers.currentText()],
                         "ISO_full_bleed_A3_(420.00_x_297.00_MM)")
        win.close()

    def test_defaults_when_config_empty(self):
        win = self._window({})
        win.load_printer_settings_from_config()
        self.assertEqual(win.combo_printers.currentText(), "DWG To PDF.pc3")
        self.assertEqual(win.combo_style.currentText(), "monochrome.ctb")
        win.close()


if __name__ == "__main__":
    unittest.main()
