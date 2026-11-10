import os
import unittest
from unittest.mock import MagicMock, patch

from core.models import Frame
from core.printer import BatchPrinter


class TestBatchPrinter(unittest.TestCase):
    def test_multi_dwg_print(self):
        f1 = os.path.abspath("C:/Drawings/plan1.dwg")
        f2 = os.path.abspath("C:/Drawings/plan2.dwg")

        doc1 = MagicMock()
        doc1.FullName = f1
        doc1.Name = "plan1.dwg"
        doc1.ModelSpace.Layout.GetCanonicalMediaNames.return_value = ["ISO_A4"]
        doc1.ModelSpace.Layout.GetLocaleMediaName.return_value = "ISO A4 (210 x 297)"

        doc2 = MagicMock()
        doc2.FullName = f2
        doc2.Name = "plan2.dwg"
        doc2.ModelSpace.Layout.GetCanonicalMediaNames.return_value = ["ISO_A4"]
        doc2.ModelSpace.Layout.GetLocaleMediaName.return_value = "ISO A4 (210 x 297)"

        mock_connector = MagicMock()
        mock_connector.get_open_documents.return_value = [(f1, "plan1.dwg")]

        def mock_open(path, read_only=True):
            if os.path.abspath(path).lower() == f1.lower():
                return doc1, False
            return doc2, True

        mock_connector.open_document.side_effect = mock_open

        frame1 = Frame(
            object_id=1, sheet_number="1", sheet_name="План 1",
            min_point=(0, 0, 0), max_point=(297, 210, 0),
            source_type="Model", paper_format="A4",
            dwg_path=f1, dwg_name="plan1.dwg"
        )
        frame2 = Frame(
            object_id=2, sheet_number="1", sheet_name="План 2",
            min_point=(0, 0, 0), max_point=(297, 210, 0),
            source_type="Model", paper_format="A4",
            dwg_path=f2, dwg_name="plan2.dwg"
        )

        printer = BatchPrinter(doc=doc1, connector=mock_connector)

        printed_files = []
        doc1.Plot.PlotToFile.side_effect = lambda f, p: printed_files.append(f)
        doc2.Plot.PlotToFile.side_effect = lambda f, p: printed_files.append(f)

        printer.print_frames(
            frames=[frame1, frame2],
            printer_name="DWG To PDF.pc3",
            canonical_media_name="ISO_A4",
            style_name="monochrome.ctb",
            output_path=os.path.abspath("C:/Out"),
            merge_pdf=False
        )

        # Проверяем, что напечатаны 2 файла с префиксом чертежей, чтобы не затереть друг друга
        self.assertEqual(len(printed_files), 2)
        self.assertIn("[plan1] Лист 1 - План 1.pdf", printed_files[0])
        self.assertIn("[plan2] Лист 1 - План 2.pdf", printed_files[1])

        # По принятому решению чертежи, открытые программой, по умолчанию не закрываются
        mock_connector.close_document.assert_not_called()

        # Если явно передан флаг close_opened_docs=True — чертежи закрываются
        printer.print_frames(
            frames=[frame1, frame2],
            printer_name="DWG To PDF.pc3",
            canonical_media_name="ISO_A4",
            style_name="monochrome.ctb",
            output_path=os.path.abspath("C:/Out"),
            merge_pdf=False,
            close_opened_docs=True
        )
        mock_connector.close_document.assert_called_once_with(doc2, save_changes=False)

    def test_custom_filename_template_and_deduplication(self):
        f1 = os.path.abspath("C:/Drawings/plan1.dwg")
        doc1 = MagicMock()
        doc1.FullName = f1
        doc1.Name = "plan1.dwg"
        doc1.ModelSpace.Layout.GetCanonicalMediaNames.return_value = ["ISO_A4"]
        doc1.ModelSpace.Layout.GetLocaleMediaName.return_value = "ISO A4 (210 x 297)"

        mock_connector = MagicMock()
        mock_connector.get_open_documents.return_value = [(f1, "plan1.dwg")]
        mock_connector.open_document.side_effect = lambda p, read_only=True: (doc1, False)

        # Два листа с одинаковым номером и именем в одном файле
        frame1 = Frame(
            object_id=1, sheet_number="1", sheet_name="План",
            min_point=(0, 0, 0), max_point=(297, 210, 0),
            source_type="Model", paper_format="A4",
            dwg_path=f1, dwg_name="plan1.dwg", doc_code="ПР-01"
        )
        frame2 = Frame(
            object_id=2, sheet_number="1", sheet_name="План",
            min_point=(0, 0, 0), max_point=(297, 210, 0),
            source_type="Model", paper_format="A4",
            dwg_path=f1, dwg_name="plan1.dwg", doc_code="ПР-01"
        )

        printed_files = []
        doc1.Plot.PlotToFile.side_effect = lambda f, p: printed_files.append(f)

        printer = BatchPrinter(doc=doc1, connector=mock_connector)
        printer.print_frames(
            frames=[frame1, frame2],
            printer_name="DWG To PDF.pc3",
            canonical_media_name="ISO_A4",
            style_name="monochrome.ctb",
            output_path=os.path.abspath("C:/Out"),
            merge_pdf=False,
            filename_template="{Шифр}_{Номер}_{Наименование}"
        )

        self.assertEqual(len(printed_files), 2)
        # Первый дубликат получает _1, второй _2
        self.assertTrue(printed_files[0].endswith("ПР-01_1_План_1.pdf"))
        self.assertTrue(printed_files[1].endswith("ПР-01_1_План_2.pdf"))


if __name__ == "__main__":
    unittest.main()
