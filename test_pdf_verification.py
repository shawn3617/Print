"""
Модульные и интеграционные тесты для валидатора выходных PDF и тестовых чертежей (test_pdf_verification.py).

Проверяет требования Этапа 1 (Пункт 3):
- Количество страниц;
- Размеры страниц по ГОСТ 2.301-68 (A4..A0, кратные форматы);
- Правильный порядок листов;
- Отсутствие пустых страниц (детекция пустого потока векторных команд);
- Ориентацию (Альбомная / Книжная);
- Проверку реальных чертежей AutoCAD (Многостраничный_чертеж.pdf и отдельные листы);
- Наличие и корректность эталонных DWG-файлов в tests/samples.
"""

import os
import unittest
import tempfile
import io
from typing import List

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from core.models import Frame, ALL_FORMATS
from core.pdf_verifier import (
    verify_pdf,
    detect_page_format,
    is_page_blank,
    PageVerificationInfo,
    PdfVerificationReport
)


def create_test_pdf_stream(commands: bytes = b"20 20 200 200 re S\n") -> bytes:
    """Создает байты потока содержимого с графическими операторами"""
    return b"q\n1 0 0 1 0 0 cm\n" + commands + b"Q\n"


def create_synthetic_pdf(
    pages_spec: List[dict],
    output_path: str
) -> str:
    """
    Создает синтетический PDF с заданными параметрами страниц:
    pages_spec: список словарей вида:
      {"width_mm": 420.0, "height_mm": 297.0, "is_blank": False, "text": "Лист 1"}
    """
    writer = PdfWriter()
    for spec in pages_spec:
        w_mm = spec.get("width_mm", 420.0)
        h_mm = spec.get("height_mm", 297.0)
        w_pt = w_mm * 72.0 / 25.4
        h_pt = h_mm * 72.0 / 25.4

        page = writer.add_blank_page(width=w_pt, height=h_pt)

        if not spec.get("is_blank", False):
            text = spec.get("text", "")
            stream_body = b"0.5 w\n10 10 100 100 re S\n"
            if text:
                text_bytes = text.encode("latin-1", errors="replace")
                stream_body += b"BT\n/F1 12 Tf\n20 20 Td\n(" + text_bytes + b") Tj\nET\n"
            stream_content = create_test_pdf_stream(stream_body)
            stream_obj = DecodedStreamObject()
            stream_obj.set_data(stream_content)
            page[NameObject('/Contents')] = writer._add_object(stream_obj)

    with open(output_path, "wb") as f:
        writer.write(f)
    return output_path


class TestPdfVerification(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_detect_page_format_standard_and_extended(self):
        """Проверка распознавания стандартных и кратных форматов ГОСТ по размерам в мм"""
        # A4 (книжный и альбомный)
        self.assertEqual(detect_page_format(210.0, 297.0), "A4")
        self.assertEqual(detect_page_format(297.0, 210.0), "A4")

        # A3
        self.assertEqual(detect_page_format(420.0, 297.0), "A3")
        self.assertEqual(detect_page_format(420.2, 297.1), "A3")  # с погрешностью плоттера

        # A2
        self.assertEqual(detect_page_format(594.0, 420.0), "A2")

        # A1
        self.assertEqual(detect_page_format(841.0, 594.0), "A1")

        # A0
        self.assertEqual(detect_page_format(1189.0, 841.0), "A0")

        # Кратные форматы: A3x3 (891 x 420), A4x3 (630 x 297)
        self.assertEqual(detect_page_format(891.0, 420.0), "A3x3")
        self.assertEqual(detect_page_format(630.0, 297.0), "A4x3")

        # Нестандартный формат (например 100x100 мм)
        self.assertIsNone(detect_page_format(100.0, 100.0))

    def test_verify_pdf_page_count_match_and_mismatch(self):
        """Проверка соответствия количества страниц в PDF и списка рамок"""
        pdf_path = os.path.join(self.temp_dir, "test_count.pdf")
        create_synthetic_pdf([
            {"width_mm": 420.0, "height_mm": 297.0},
            {"width_mm": 594.0, "height_mm": 420.0}
        ], pdf_path)

        f1 = Frame(1, "1", "Лист 1", (0, 0, 0), (420, 297, 0), "Model", "A3")
        f2 = Frame(2, "2", "Лист 2", (0, 0, 0), (594, 420, 0), "Model", "A2")

        # Совпадает (2 страницы = 2 рамки)
        report = verify_pdf(pdf_path, [f1, f2])
        self.assertTrue(report.is_valid)
        self.assertEqual(report.total_pages, 2)
        self.assertEqual(len(report.errors), 0)

        # Не совпадает (ожидалось 3 рамки)
        f3 = Frame(3, "3", "Лист 3", (0, 0, 0), (210, 297, 0), "Model", "A4")
        report_bad = verify_pdf(pdf_path, [f1, f2, f3])
        self.assertFalse(report_bad.is_valid)
        self.assertIn("Не совпадает количество страниц", report_bad.errors[0])

    def test_blank_page_detection(self):
        """Детекция пустой страницы (отсутствие векторной графики и текста)"""
        pdf_path = os.path.join(self.temp_dir, "test_blank.pdf")
        create_synthetic_pdf([
            {"width_mm": 420.0, "height_mm": 297.0, "is_blank": False},
            {"width_mm": 420.0, "height_mm": 297.0, "is_blank": True}  # Пустая
        ], pdf_path)

        report = verify_pdf(pdf_path)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.blank_pages, [2])
        self.assertTrue(report.pages[1].is_blank)
        self.assertFalse(report.pages[0].is_blank)
        self.assertIn("пустая", report.pages[1].errors[0])

    def test_orientation_verification(self):
        """Проверка соответствия ориентации листа (Альбомная / Книжная)"""
        pdf_path = os.path.join(self.temp_dir, "test_orient.pdf")
        # Создаем PDF со страницей A4 альбомной (297 x 210)
        create_synthetic_pdf([
            {"width_mm": 297.0, "height_mm": 210.0, "is_blank": False}
        ], pdf_path)

        # Ожидаем книжный A4 (210 x 297)
        frame_portrait = Frame(1, "1", "Лист 1", (0, 0, 0), (210, 297, 0), "Model", "A4")
        report = verify_pdf(pdf_path, [frame_portrait])

        self.assertFalse(report.is_valid)
        self.assertTrue(any("ориентация" in err.lower() for err in report.pages[0].errors))

    def test_format_mismatch_detection(self):
        """Детекция несовпадения формата бумаги между чертежом и PDF"""
        pdf_path = os.path.join(self.temp_dir, "test_mismatch.pdf")
        create_synthetic_pdf([
            {"width_mm": 420.0, "height_mm": 297.0, "is_blank": False}  # Это A3
        ], pdf_path)

        # Ожидаем A1
        frame_a1 = Frame(1, "1", "Лист 1", (0, 0, 0), (841, 594, 0), "Model", "A1")
        report = verify_pdf(pdf_path, [frame_a1])

        self.assertFalse(report.is_valid)
        self.assertEqual(len(report.mismatched_formats), 1)
        page_num, actual_fmt, exp_fmt = report.mismatched_formats[0]
        self.assertEqual(page_num, 1)
        self.assertEqual(actual_fmt, "A3")
        self.assertEqual(exp_fmt, "A1")

    def test_orientation_with_pdf_page_rotation(self):
        frame = Frame(1, "1", "Лист 1", (0, 0, 0), (420, 297, 0), "Model", "A3")
        source = create_synthetic_pdf(
            [{"width_mm": 297.0, "height_mm": 420.0}],
            os.path.join(self.temp_dir, "portrait.pdf"),
        )
        for angle in (90, 270):
            with self.subTest(angle=angle):
                output = os.path.join(self.temp_dir, f"rotated_{angle}.pdf")
                writer = PdfWriter(clone_from=source)
                writer.pages[0].rotate(angle)
                writer.write(output)
                report = verify_pdf(output, [frame])
                self.assertTrue(report.is_valid, report.summary())
                page = report.pages[0]
                self.assertEqual((page.width_mm, page.height_mm), (420.0, 297.0))

    def test_real_autocad_multipage_pdf_verification(self):
        """Проверка реального многостраничного PDF, выведенного из AutoCAD"""
        pdf_path = os.path.abspath("tests/samples/pdf/Многостраничный_чертеж.pdf")
        if not os.path.exists(pdf_path):
            self.skipTest(f"Файл {pdf_path} не найден")

        report = verify_pdf(pdf_path)
        self.assertTrue(report.is_valid)
        self.assertEqual(report.total_pages, 6)
        self.assertEqual(len(report.blank_pages), 0)

        # Проверяем форматы страниц реального тома:
        # P1..P3: A2, P4: A1, P5..P6: A3x3
        expected_formats = ["A2", "A2", "A2", "A1", "A3x3", "A3x3"]
        actual_formats = [p.matched_format for p in report.pages]
        self.assertEqual(actual_formats, expected_formats)

        # Проверяем наличие векторных операторов в каждом листе
        for p in report.pages:
            self.assertGreater(p.drawing_ops_count, 1000)
            self.assertFalse(p.is_blank)

    def test_real_autocad_single_sheet_pdf(self):
        """Проверка отдельных реальных листов AutoCAD (A2, A1, A3x3)"""
        samples_dir = os.path.abspath("tests/samples/pdf")
        if not os.path.exists(samples_dir):
            self.skipTest("Папка samples/pdf не найдена")

        # Лист 1 (A2)
        p1 = os.path.join(samples_dir, "Лист 1 - амываываыаыва.pdf")
        if os.path.exists(p1):
            r1 = verify_pdf(p1)
            self.assertTrue(r1.is_valid)
            self.assertEqual(r1.pages[0].matched_format, "A2")

        # Лист 4 (A1)
        p4 = os.path.join(samples_dir, "Лист 4 - амываываыаыва.pdf")
        if os.path.exists(p4):
            r4 = verify_pdf(p4)
            self.assertTrue(r4.is_valid)
            self.assertEqual(r4.pages[0].matched_format, "A1")

        # Лист 5 (A3x3)
        p5 = os.path.join(samples_dir, "Лист 5 - амываываыаыва.pdf")
        if os.path.exists(p5):
            r5 = verify_pdf(p5)
            self.assertTrue(r5.is_valid)
            self.assertEqual(r5.pages[0].matched_format, "A3x3")

    def test_sample_dwg_files_exist_and_non_empty(self):
        """Проверка наличия сгенерированных эталонных чертежей DWG в tests/samples"""
        samples_dir = os.path.abspath("tests/samples")
        model_dwg = os.path.join(samples_dir, "sample_model_sheets.dwg")
        layouts_dwg = os.path.join(samples_dir, "sample_layouts_tabs.dwg")

        self.assertTrue(os.path.exists(model_dwg), f"Чертеж модели не найден: {model_dwg}")
        self.assertGreater(os.path.getsize(model_dwg), 10000, "Размер DWG модели подозрительно мал")

        self.assertTrue(os.path.exists(layouts_dwg), f"Чертеж макетов не найден: {layouts_dwg}")
        self.assertGreater(os.path.getsize(layouts_dwg), 10000, "Размер DWG макетов подозрительно мал")

    def test_corrupted_or_missing_file_handling(self):
        """Проверка корректной обработки несуществующего или поврежденного файла"""
        # Несуществующий файл
        r_missing = verify_pdf(os.path.join(self.temp_dir, "non_existent.pdf"))
        self.assertFalse(r_missing.is_valid)
        self.assertIn("Файл не найден", r_missing.errors[0])

        # Пустой файл (0 байт)
        empty_pdf = os.path.join(self.temp_dir, "empty.pdf")
        with open(empty_pdf, "wb") as f:
            pass
        r_empty = verify_pdf(empty_pdf)
        self.assertFalse(r_empty.is_valid)
        self.assertIn("пуст", r_empty.errors[0])

        # Битый файл с невалидным содержимым
        corrupt_pdf = os.path.join(self.temp_dir, "corrupt.pdf")
        with open(corrupt_pdf, "wb") as f:
            f.write(b"NOT A VALID PDF FILE CONTENT")
        r_corrupt = verify_pdf(corrupt_pdf)
        self.assertFalse(r_corrupt.is_valid)
        self.assertTrue(any("поврежден" in err.lower() or "не удалось" in err.lower() for err in r_corrupt.errors))

    def test_report_summary_formatting(self):
        """Проверка генерации читаемой сводки отчета (summary)"""
        pdf_path = os.path.join(self.temp_dir, "test_summary.pdf")
        create_synthetic_pdf([
            {"width_mm": 420.0, "height_mm": 297.0, "is_blank": False}
        ], pdf_path)

        report = verify_pdf(pdf_path)
        summary = report.summary()
        self.assertIn("Отчет проверки PDF", summary)
        self.assertIn("Всего страниц: 1", summary)
        self.assertIn("ГОДЕН (ОК)", summary)
        self.assertIn("A3 (Landscape", summary)

    def test_batch_printer_end_to_end_verification(self):
        """Интеграционный тест: печать и слияние через BatchPrinter с валидацией через verify_pdf"""
        from unittest.mock import MagicMock
        from core.printer import BatchPrinter

        merged_pdf = os.path.join(self.temp_dir, "volume_merged.pdf")
        f1 = Frame(1, "1", "План этажа", (0, 0, 0), (420, 297, 0), "Model", "A3")
        f2 = Frame(2, "2", "Разрез 1-1", (0, 0, 0), (594, 420, 0), "Model", "A2")

        mock_doc = MagicMock()
        mock_doc.FullName = "C:/Drawings/test.dwg"
        mock_doc.Name = "test.dwg"
        mock_doc.ModelSpace.Layout.GetCanonicalMediaNames.return_value = ["ISO_A3", "ISO_A2"]
        mock_doc.ModelSpace.Layout.GetLocaleMediaName.return_value = "ISO A3"

        def mock_plot_to_file(filepath, plotter):
            # Создаем реальные одностраничные PDF для каждого листа
            basename = os.path.basename(filepath)
            if "Лист 1" in basename:
                create_synthetic_pdf([{"width_mm": 420.0, "height_mm": 297.0}], filepath)
            else:
                create_synthetic_pdf([{"width_mm": 594.0, "height_mm": 420.0}], filepath)

        mock_doc.Plot.PlotToFile.side_effect = mock_plot_to_file

        printer = BatchPrinter(mock_doc)
        print_report = printer.print_frames(
            frames=[f1, f2],
            printer_name="DWG To PDF.pc3",
            canonical_media_name="ISO_A3",
            style_name="monochrome.ctb",
            output_path=merged_pdf,
            merge_pdf=True
        )

        self.assertEqual(print_report.success_count, 2)
        self.assertTrue(os.path.exists(merged_pdf))

        # Валидируем результирующий объединенный PDF
        verification_report = verify_pdf(merged_pdf, [f1, f2])
        self.assertTrue(verification_report.is_valid, verification_report.summary())
        self.assertEqual(verification_report.total_pages, 2)
        self.assertEqual(verification_report.pages[0].matched_format, "A3")
        self.assertEqual(verification_report.pages[1].matched_format, "A2")


if __name__ == "__main__":
    unittest.main()
