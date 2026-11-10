"""
Тесты для моделей итоговых отчётов (core/report_models.py).
"""

import unittest
from core.models import Frame
from core.report_models import PrintReport, PrintItemResult, ScanReport, ScanFileResult


class TestReportModels(unittest.TestCase):
    def test_print_report_metrics_and_properties(self):
        f1 = Frame(1, "1", "План", (0, 0, 0), (420, 297, 0), "SPDS", "A3", dwg_name="file1.dwg")
        f2 = Frame(2, "2", "Разрез", (0, 0, 0), (500, 300, 0), "Block", "A2x3", dwg_name="file1.dwg")
        f3 = Frame(3, "3", "Узел", (0, 0, 0), (297, 210, 0), "Polyline", "A4", dwg_name="file2.dwg")
        f4 = Frame(4, "4", "Схема", (0, 0, 0), (297, 210, 0), "Model", "A4", dwg_name="file2.dwg")

        it1 = PrintItemResult(frame=f1, success=True, output_file="C:/out/1.pdf", dwg_name="file1.dwg", sheet_number="1", sheet_name="План")
        it2 = PrintItemResult(frame=f2, success=True, output_file="C:/out/2.pdf", fallback_used=True, fallback_format="A1", dwg_name="file1.dwg", sheet_number="2", sheet_name="Разрез")
        it3 = PrintItemResult(frame=f3, success=False, error="AutoCAD error 0x80010001", dwg_name="file2.dwg", sheet_number="3", sheet_name="Узел")
        it4 = PrintItemResult(frame=f4, success=False, skipped=True, dwg_name="file2.dwg", sheet_number="4", sheet_name="Схема")

        rep = PrintReport(
            total_requested=4,
            success_count=2,
            failed_count=1,
            fallback_count=1,
            skipped_count=1,
            output_path="C:/out/batch.pdf",
            is_merged=True,
            printer_name="PDF_ГОСТ.pc3",
            style_name="monochrome.ctb",
            duration_seconds=5.4,
            items=[it1, it2, it3, it4],
            unopened_dwgs=[("C:/broken.dwg", "Файл поврежден")]
        )

        self.assertEqual(len(rep.failed_frames), 1)
        self.assertEqual(rep.failed_frames[0].sheet_number, "3")

        self.assertEqual(len(rep.skipped_frames), 1)
        self.assertEqual(rep.skipped_frames[0].sheet_number, "4")

        # repeatable_frames содержит как сбойные, так и пропущенные (3 и 4)
        self.assertEqual(len(rep.repeatable_frames), 2)
        self.assertEqual([f.sheet_number for f in rep.repeatable_frames], ["3", "4"])

        self.assertEqual(len(rep.fallback_frames), 1)
        self.assertEqual(rep.fallback_frames[0].sheet_number, "2")

        text = rep.build_text_report()
        self.assertIn("ОТЧЁТ О ПАКЕТНОЙ ПЕЧАТИ", text)
        self.assertIn("5.4 сек", text)
        self.assertIn("PDF_ГОСТ.pc3", text)
        self.assertIn("C:/broken.dwg", text)
        self.assertIn("[✓ УСПЕХ] Лист 1", text)
        self.assertIn("резервный A1", text)
        self.assertIn("[✗ ОШИБКА] Лист 3", text)
        self.assertIn("[⚪ ПРОПУЩЕН] Лист 4", text)

    def test_scan_report_text(self):
        rep = ScanReport(
            total_files=2,
            success_files_count=1,
            failed_files_count=1,
            empty_files_count=0,
            total_frames_found=5,
            duration_seconds=2.1,
            file_results=[
                ScanFileResult(file_path="C:/Drawings/p1.dwg", file_name="p1.dwg", success=True, frames_count=5),
                ScanFileResult(file_path="C:/Drawings/bad.dwg", file_name="bad.dwg", success=False, error="Файл заблокирован")
            ]
        )

        text = rep.build_text_report()
        self.assertIn("ОТЧЁТ О СКАНИРОВАНИИ ЧЕРТЕЖЕЙ", text)
        self.assertIn("Всего файлов DWG: 2", text)
        self.assertIn("p1.dwg", text)
        self.assertIn("bad.dwg", text)
        self.assertIn("Файл заблокирован", text)


if __name__ == "__main__":
    unittest.main()
