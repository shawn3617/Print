"""
Тесты для механизма закладок (оглавления) и метаданных в многостраничном PDF (test_bookmarks_metadata.py).

Проверяет Пункт 5 плана улучшений:
- Формирование названий закладок вида '03 — Ведомость марок';
- Генерацию метаданных документа (Title, Author, Subject, Creator, Producer);
- Сквозное слияние через BatchPrinter с созданием закладок и метаданных;
- Проверку наличия закладок и метаданных через pdf_verifier.
"""

import os
import unittest
import tempfile
from unittest.mock import MagicMock
from pypdf import PdfReader

from core.models import Frame
from core.printer import BatchPrinter, format_bookmark_title, build_pdf_metadata
from core.pdf_verifier import verify_pdf
from test_pdf_verification import create_synthetic_pdf


class TestBookmarksAndMetadata(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_format_bookmark_title(self):
        """Проверка форматирования названий закладок по ГОСТ"""
        # 1. Цифровой номер дополняется нулем до двух цифр
        self.assertEqual(
            format_bookmark_title("3", "Ведомость марок"),
            "03 — Ведомость марок"
        )
        self.assertEqual(
            format_bookmark_title("1", "План первого этажа"),
            "01 — План первого этажа"
        )
        self.assertEqual(
            format_bookmark_title("12", "План кровли"),
            "12 — План кровли"
        )

        # 2. Нечисловой номер (буквенный/составной)
        self.assertEqual(
            format_bookmark_title("4а", "Разрез 1-1"),
            "4а — Разрез 1-1"
        )
        self.assertEqual(
            format_bookmark_title("ПЗ-1", "Пояснительная записка"),
            "ПЗ-1 — Пояснительная записка"
        )

        # 3. Лист без номера (титульный лист / обложка)
        self.assertEqual(
            format_bookmark_title("", "Титульный лист"),
            "Титульный лист"
        )

        # 4. Лист без названия или Unknown
        self.assertEqual(
            format_bookmark_title("5", "Unknown"),
            "Лист 05"
        )
        self.assertEqual(
            format_bookmark_title("7", ""),
            "Лист 07"
        )

        # 5. Без номера и названия
        self.assertEqual(
            format_bookmark_title("", "", page_index=2),
            "Лист 3"
        )

    def test_build_pdf_metadata(self):
        """Проверка формирования словаря метаданных PDF"""
        f1 = Frame(
            object_id=1, sheet_number="1", sheet_name="Титульный лист",
            min_point=(0, 0, 0), max_point=(420, 297, 0), source_type="Model",
            doc_code="001-2026-АР", object_name="ЖК Северный", building_name="Корпус 1"
        )
        f2 = Frame(
            object_id=2, sheet_number="2", sheet_name="План",
            min_point=(0, 0, 0), max_point=(420, 297, 0), source_type="Model",
            doc_code="001-2026-АР", object_name="ЖК Северный", building_name="Корпус 1"
        )

        meta = build_pdf_metadata([f1, f2], doc_name="Архитектура.dwg")
        self.assertIn("/Title", meta)
        self.assertIn("ЖК Северный", meta["/Title"])
        self.assertIn("001-2026-АР", meta["/Title"])
        self.assertEqual(meta.get("/Author"), "001-2026-АР")
        self.assertEqual(meta.get("/Subject"), "Корпус 1")
        self.assertIn("PrintPDF", meta.get("/Creator", ""))

    def test_merged_pdf_contains_bookmarks_and_metadata(self):
        """Сквозной тест: печать тома в один PDF с закладками и метаданными"""
        merged_pdf = os.path.join(self.temp_dir, "volume_bookmarked.pdf")

        f1 = Frame(
            object_id=1, sheet_number="1", sheet_name="Титульный лист",
            min_point=(0, 0, 0), max_point=(210, 297, 0), source_type="Model",
            paper_format="A4", doc_code="2026-АР", object_name="Административное здание"
        )
        f2 = Frame(
            object_id=2, sheet_number="2", sheet_name="План 1 этажа",
            min_point=(0, 0, 0), max_point=(420, 297, 0), source_type="Model",
            paper_format="A3", doc_code="2026-АР", object_name="Административное здание"
        )
        f3 = Frame(
            object_id=3, sheet_number="3", sheet_name="Ведомость марок",
            min_point=(0, 0, 0), max_point=(594, 420, 0), source_type="Model",
            paper_format="A2", doc_code="2026-АР", object_name="Административное здание"
        )

        mock_doc = MagicMock()
        mock_doc.FullName = "C:/Drawings/Building.dwg"
        mock_doc.Name = "Building.dwg"
        mock_doc.ModelSpace.Layout.GetCanonicalMediaNames.return_value = ["ISO_A4", "ISO_A3", "ISO_A2"]
        mock_doc.ModelSpace.Layout.GetLocaleMediaName.return_value = "Media"

        def mock_plot(fpath, plotter):
            basename = os.path.basename(fpath)
            if "Лист 1" in basename:
                create_synthetic_pdf([{"width_mm": 210.0, "height_mm": 297.0}], fpath)
            elif "Лист 2" in basename:
                create_synthetic_pdf([{"width_mm": 420.0, "height_mm": 297.0}], fpath)
            else:
                create_synthetic_pdf([{"width_mm": 594.0, "height_mm": 420.0}], fpath)

        mock_doc.Plot.PlotToFile.side_effect = mock_plot

        printer = BatchPrinter(mock_doc)
        report = printer.print_frames(
            frames=[f1, f2, f3],
            printer_name="DWG To PDF.pc3",
            canonical_media_name="ISO_A3",
            style_name="monochrome.ctb",
            output_path=merged_pdf,
            merge_pdf=True
        )

        self.assertEqual(report.success_count, 3)
        self.assertTrue(os.path.exists(merged_pdf))

        # 1. Проверяем через PdfReader
        reader = PdfReader(merged_pdf)
        self.assertEqual(len(reader.pages), 3)

        # Проверяем закладки
        self.assertIsNotNone(reader.outline)
        self.assertEqual(len(reader.outline), 3)
        bookmark_titles = [str(getattr(item, "title", item)) for item in reader.outline]
        self.assertEqual(bookmark_titles[0], "01 — Титульный лист")
        self.assertEqual(bookmark_titles[1], "02 — План 1 этажа")
        self.assertEqual(bookmark_titles[2], "03 — Ведомость марок")

        # Проверяем метаданные
        meta = reader.metadata
        self.assertIn("Административное здание", meta.get("/Title", ""))
        self.assertEqual(meta.get("/Author"), "2026-АР")
        self.assertIn("PrintPDF", meta.get("/Creator", ""))

        # 2. Проверяем через verify_pdf
        v_report = verify_pdf(merged_pdf, [f1, f2, f3])
        self.assertTrue(v_report.is_valid)
        self.assertEqual(len(v_report.bookmarks), 3)
        self.assertIn("03 — Ведомость марок", v_report.bookmarks)
        summary = v_report.summary()
        self.assertIn("Закладки (3 шт.)", summary)
        self.assertIn("03 — Ведомость марок", summary)


if __name__ == "__main__":
    unittest.main()
