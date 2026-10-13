import os
import unittest
from unittest.mock import MagicMock, patch

from core.models import Frame
from core.scanner import DocumentScanner


class TestBatchScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = DocumentScanner()
        self.connector = MagicMock()

    def test_scan_files_multiple(self):
        f1 = os.path.abspath("C:/Drawings/plan1.dwg")
        f2 = os.path.abspath("C:/Drawings/plan2.dwg")

        doc1 = MagicMock()
        doc1.FullName = f1
        doc1.Name = "plan1.dwg"

        doc2 = MagicMock()
        doc2.FullName = f2
        doc2.Name = "plan2.dwg"

        # connector.get_open_documents: изначально открыт только plan1
        self.connector.get_open_documents.return_value = [(f1, "plan1.dwg")]

        # connector.open_document возвращает (doc, was_opened)
        def mock_open(path, read_only=True):
            if os.path.abspath(path).lower() == f1.lower():
                return doc1, False
            return doc2, True

        self.connector.open_document.side_effect = mock_open

        frame1 = Frame(object_id=1, sheet_number="1", sheet_name="План 1", min_point=(0,0,0), max_point=(10,10,0), source_type="Model")
        frame2 = Frame(object_id=2, sheet_number="2", sheet_name="План 2", min_point=(0,0,0), max_point=(10,10,0), source_type="Model")

        with patch.object(self.scanner, "scan_document") as mock_scan:
            mock_scan.side_effect = [[frame1], [frame2]]

            frames = self.scanner.scan_files(self.connector, [f1, f2], source_mode="Модель")

            self.assertEqual(len(frames), 2)
            self.assertEqual(frames[0].dwg_name, "plan1.dwg")
            self.assertEqual(frames[0].dwg_path, f1)
            self.assertEqual(frames[1].dwg_name, "plan2.dwg")
            self.assertEqual(frames[1].dwg_path, f2)

            # doc1 был изначально открыт -> close_document НЕ должен вызываться для него
            # doc2 был открыт нами -> close_document ДОЛЖЕН вызваться для doc2
            self.connector.close_document.assert_called_once_with(doc2, save_changes=False)

    def test_scan_files_cancelled(self):
        f1 = os.path.abspath("C:/Drawings/plan1.dwg")
        f2 = os.path.abspath("C:/Drawings/plan2.dwg")

        self.connector.get_open_documents.return_value = []
        doc1 = MagicMock()
        self.connector.open_document.return_value = (doc1, True)

        frame1 = Frame(object_id=1, sheet_number="1", sheet_name="План 1", min_point=(0,0,0), max_point=(10,10,0), source_type="Model")

        cancelled_state = [False]
        def is_cancelled():
            return cancelled_state[0]

        with patch.object(self.scanner, "scan_document", return_value=[frame1]):
            # Отменяем после первого файла
            def prog_cb(idx, total, name, status):
                if idx == 0:
                    cancelled_state[0] = True

            frames = self.scanner.scan_files(self.connector, [f1, f2], source_mode="Модель", progress_callback=prog_cb, is_cancelled=is_cancelled)
            # Должен обработаться только 1 файл
            self.assertEqual(len(frames), 1)


if __name__ == "__main__":
    unittest.main()
