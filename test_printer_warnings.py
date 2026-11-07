"""Ошибки в печати не глотаются молча: запасной вариант срабатывает, но причина видна в консоли."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock

from core.printer import BatchPrinter


class TestPrinterWarnings(unittest.TestCase):
    def _printer(self):
        doc = MagicMock()
        printer = BatchPrinter(doc)
        printer._plotters_checked = True  # не трогаем установку плоттеров
        return printer, doc.ModelSpace.Layout

    def test_printers_fallback_is_reported(self):
        printer, layout = self._printer()
        layout.GetPlotDeviceNames.side_effect = RuntimeError("COM недоступен")
        out = io.StringIO()
        with redirect_stdout(out):
            names = printer.get_printers()
        self.assertIn("DWG To PDF.pc3", names)
        self.assertIn("[Печать] Предупреждение", out.getvalue())
        self.assertIn("COM недоступен", out.getvalue())

    def test_media_fallback_is_reported(self):
        printer, layout = self._printer()
        layout.GetCanonicalMediaNames.side_effect = RuntimeError("нет форматов")
        out = io.StringIO()
        with redirect_stdout(out):
            media = printer.get_media_names("PDF_ГОСТ.pc3")
        self.assertTrue(media)
        self.assertIn("PDF_ГОСТ.pc3", out.getvalue())
        self.assertIn("нет форматов", out.getvalue())

    def test_plot_styles_fallback_is_reported(self):
        printer, layout = self._printer()
        layout.GetPlotStyleTableNames.side_effect = RuntimeError("нет стилей")
        out = io.StringIO()
        with redirect_stdout(out):
            styles = printer.get_plot_styles()
        self.assertIn("monochrome.ctb", styles)
        self.assertIn("нет стилей", out.getvalue())


if __name__ == "__main__":
    unittest.main()
