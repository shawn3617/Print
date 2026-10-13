import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from core.models import Frame
from core.printer import BatchPrinter, PrintCancelledError


class TestBatchPrinterProgress(unittest.TestCase):
    def setUp(self):
        self.mock_doc = MagicMock()
        self.mock_layout = MagicMock()
        self.mock_doc.ModelSpace.Layout = self.mock_layout
        self.mock_doc.GetVariable.return_value = 0

        self.printer = BatchPrinter(self.mock_doc)

        # Подготовим 3 тестовые рамки
        self.frames = [
            Frame(1, "1", "Общие данные", (0, 0, 0), (29700, 21000, 0), "SPDS", "A4"),
            Frame(2, "2", "План 1 этажа", (0, 0, 0), (59400, 42000, 0), "SPDS", "A2"),
            Frame(3, "3", "Фасад", (0, 0, 0), (59400, 42000, 0), "SPDS", "A2"),
        ]

    def test_print_frames_progress_without_merge(self):
        progress_calls = []

        def callback(current_step, total_steps, status_text):
            progress_calls.append((current_step, total_steps, status_text))

        with patch.object(self.printer, "_disable_pc3_view_file", return_value=False):
            with patch.object(self.printer, "_build_media_map", return_value={}):
                self.printer.print_frames(
                    frames=self.frames,
                    printer_name="DWG To PDF.pc3",
                    canonical_media_name="ISO_A2",
                    style_name="monochrome.ctb",
                    output_path="C:/dummy/output",
                    merge_pdf=False,
                    progress_callback=callback
                )

        # Должно быть 3 вызова для 3 листов + 1 финальный "Готово!"
        self.assertEqual(len(progress_calls), 4)
        self.assertEqual(progress_calls[0][0], 0)
        self.assertEqual(progress_calls[0][1], 3)
        self.assertIn("Лист 1", progress_calls[0][2])

        self.assertEqual(progress_calls[1][0], 1)
        self.assertEqual(progress_calls[1][1], 3)
        self.assertIn("Лист 2", progress_calls[1][2])

        self.assertEqual(progress_calls[2][0], 2)
        self.assertEqual(progress_calls[2][1], 3)
        self.assertIn("Лист 3", progress_calls[2][2])

        self.assertEqual(progress_calls[3][0], 3)
        self.assertEqual(progress_calls[3][1], 3)
        self.assertEqual(progress_calls[3][2], "Готово!")

        # PlotToFile должен быть вызван 3 раза
        self.assertEqual(self.mock_doc.Plot.PlotToFile.call_count, 3)

    def test_print_frames_cancellation_mid_process(self):
        progress_calls = []

        # Отменяем после 1-го листа
        call_count = [0]
        def is_cancelled():
            return call_count[0] >= 1

        def callback(current_step, total_steps, status_text):
            progress_calls.append((current_step, total_steps, status_text))
            call_count[0] += 1

        with patch.object(self.printer, "_disable_pc3_view_file", return_value=False):
            with patch.object(self.printer, "_build_media_map", return_value={}):
                with self.assertRaises(PrintCancelledError):
                    self.printer.print_frames(
                        frames=self.frames,
                        printer_name="DWG To PDF.pc3",
                        canonical_media_name="ISO_A2",
                        style_name="monochrome.ctb",
                        output_path="C:/dummy/output",
                        merge_pdf=False,
                        progress_callback=callback,
                        is_cancelled=is_cancelled
                    )

        # PlotToFile должен был выполниться только для 1 листа, а перед вторым сработала отмена
        self.assertEqual(self.mock_doc.Plot.PlotToFile.call_count, 1)

    def test_print_frames_progress_with_merge(self):
        progress_calls = []

        def callback(current_step, total_steps, status_text):
            progress_calls.append((current_step, total_steps, status_text))

        # Создаем фиктивные файлы в temp_dir при вызове PlotToFile
        def fake_plot_to_file(filepath, printer_name):
            with open(filepath, "w") as f:
                f.write("fake pdf content")

        self.mock_doc.Plot.PlotToFile.side_effect = fake_plot_to_file

        with patch.object(self.printer, "_disable_pc3_view_file", return_value=False):
            with patch.object(self.printer, "_build_media_map", return_value={}):
                with patch("pypdf.PdfWriter") as mock_writer_cls:
                    mock_writer = MagicMock()
                    mock_writer_cls.return_value = mock_writer

                    self.printer.print_frames(
                        frames=self.frames,
                        printer_name="DWG To PDF.pc3",
                        canonical_media_name="ISO_A2",
                        style_name="monochrome.ctb",
                        output_path="C:/dummy/merged.pdf",
                        merge_pdf=True,
                        progress_callback=callback
                    )

        # total_steps для merge = len(frames) + 1 = 4
        # Шаги: 0 (Лист 1), 1 (Лист 2), 2 (Лист 3), 3 (Объединение), 4 (Готово)
        self.assertEqual(len(progress_calls), 5)
        self.assertEqual(progress_calls[3][0], 3)
        self.assertEqual(progress_calls[3][1], 4)
        self.assertIn("Объединение", progress_calls[3][2])

        self.assertEqual(progress_calls[4][0], 4)
        self.assertEqual(progress_calls[4][1], 4)
        self.assertEqual(progress_calls[4][2], "Готово!")


class TestUIPrintProgressDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_lifecycle_and_updates(self):
        from ui.main_window import PrintProgressDialog

        dlg = PrintProgressDialog(total_steps=10)
        self.assertEqual(dlg.progress_bar.maximum(), 10)
        self.assertEqual(dlg.progress_bar.value(), 0)
        self.assertFalse(dlg.is_cancelled)

        # Обновление прогресса
        dlg.set_progress(5, "Печать листа 6 из 10...")
        self.assertEqual(dlg.progress_bar.value(), 5)
        self.assertEqual(dlg.lbl_status.text(), "Печать листа 6 из 10...")

        # Нажатие "Отмена"
        dlg.btn_cancel.click()
        self.assertTrue(dlg.is_cancelled)
        self.assertFalse(dlg.btn_cancel.isEnabled())
        self.assertIn("Отмена", dlg.lbl_status.text())

    def test_dialog_close_sets_cancelled(self):
        from ui.main_window import PrintProgressDialog

        dlg = PrintProgressDialog(total_steps=5)
        self.assertFalse(dlg.is_cancelled)
        dlg.close()
        self.assertTrue(dlg.is_cancelled)


if __name__ == "__main__":
    unittest.main()
