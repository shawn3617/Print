"""Ошибки в печати не глотаются молча: запасной вариант срабатывает, но причина видна в консоли."""
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import MagicMock

from core.printer import BatchPrinter, _safe_file_part


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


class TestSafeFilePart(unittest.TestCase):
    def test_forbidden_characters_removed(self):
        self.assertEqual(_safe_file_part('1/2: "План" *эт.*', 50), "12 План эт")  # точка в конце имени Windows не допускает

    def test_length_limited(self):
        long_name = "Схема расположения элементов " * 10
        self.assertLessEqual(len(_safe_file_part(long_name, 80)), 80)

    def test_empty(self):
        self.assertEqual(_safe_file_part(None, 20), "")
        self.assertEqual(_safe_file_part("///", 20), "")

if __name__ == "__main__":
    unittest.main()
