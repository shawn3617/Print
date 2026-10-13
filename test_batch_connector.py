import os
import unittest
from unittest.mock import MagicMock, patch

from core.autocad_connector import AutoCADConnector
from core.models import Frame


class TestBatchConnector(unittest.TestCase):
    def setUp(self):
        self.connector = AutoCADConnector()
        self.mock_app = MagicMock()
        self.connector.app = self.mock_app

    def test_find_open_document_by_fullname(self):
        doc1 = MagicMock()
        doc1.FullName = r"C:\Drawings\plan1.dwg"
        doc1.Name = "plan1.dwg"

        doc2 = MagicMock()
        doc2.FullName = r"C:\Drawings\plan2.dwg"
        doc2.Name = "plan2.dwg"

        mock_docs = MagicMock()
        mock_docs.Count = 2
        mock_docs.Item.side_effect = lambda i: [doc1, doc2][i]
        self.mock_app.Documents = mock_docs

        found = self.connector.find_open_document(r"C:\Drawings\plan2.dwg")
        self.assertEqual(found, doc2)

        # Поиск по имени файла (basename)
        found_by_name = self.connector.find_open_document("plan1.dwg")
        self.assertEqual(found_by_name, doc1)

        # Несуществующий
        not_found = self.connector.find_open_document("other.dwg")
        self.assertIsNone(not_found)

    def test_get_open_documents(self):
        doc1 = MagicMock()
        doc1.FullName = r"C:\Drawings\p1.dwg"
        doc1.Name = "p1.dwg"

        mock_docs = MagicMock()
        mock_docs.Count = 1
        mock_docs.Item.side_effect = lambda i: [doc1][i]
        self.mock_app.Documents = mock_docs

        docs = self.connector.get_open_documents()
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0], (r"C:\Drawings\p1.dwg", "p1.dwg"))

    @patch("os.path.exists", return_value=True)
    def test_open_document_already_open(self, mock_exists):
        doc1 = MagicMock()
        doc1.FullName = os.path.abspath(r"C:\Drawings\p1.dwg")
        doc1.Name = "p1.dwg"

        mock_docs = MagicMock()
        mock_docs.Count = 1
        mock_docs.Item.side_effect = lambda i: [doc1][i]
        self.mock_app.Documents = mock_docs

        doc, was_opened = self.connector.open_document(r"C:\Drawings\p1.dwg", read_only=True)
        self.assertEqual(doc, doc1)
        self.assertFalse(was_opened)
        self.assertEqual(self.connector.doc, doc1)
        mock_docs.Open.assert_not_called()

    @patch("os.path.exists", return_value=True)
    def test_open_document_not_yet_open(self, mock_exists):
        mock_docs = MagicMock()
        mock_docs.Count = 0
        new_doc = MagicMock()
        mock_docs.Open.return_value = new_doc
        self.mock_app.Documents = mock_docs

        doc, was_opened = self.connector.open_document(r"C:\Drawings\new.dwg", read_only=True)
        self.assertEqual(doc, new_doc)
        self.assertTrue(was_opened)
        self.assertEqual(self.connector.doc, new_doc)
        mock_docs.Open.assert_called_once_with(os.path.abspath(r"C:\Drawings\new.dwg"), True)

    def test_close_document(self):
        doc = MagicMock()
        self.connector.doc = doc
        active_remaining = MagicMock()
        self.mock_app.ActiveDocument = active_remaining

        self.connector.close_document(doc, save_changes=False)
        doc.Close.assert_called_once_with(False)
        self.assertEqual(self.connector.doc, active_remaining)

    @patch("os.path.exists", return_value=True)
    def test_show_frame_switches_document_if_different(self, mock_exists):
        cur_doc = MagicMock()
        cur_doc.FullName = os.path.abspath(r"C:\Drawings\doc1.dwg")
        self.connector.doc = cur_doc

        target_doc = MagicMock()
        target_doc.FullName = os.path.abspath(r"C:\Drawings\doc2.dwg")

        mock_docs = MagicMock()
        mock_docs.Count = 0
        mock_docs.Open.return_value = target_doc
        self.mock_app.Documents = mock_docs

        frame = Frame(
            object_id=1,
            sheet_number="1",
            sheet_name="Лист 1",
            min_point=(0, 0, 0),
            max_point=(100, 100, 0),
            source_type="Model",
            dwg_path=r"C:\Drawings\doc2.dwg"
        )

        with patch.object(self.connector, "zoom_window") as mock_zoom, \
             patch.object(self.connector, "highlight_object") as mock_hl:
            self.connector.show_frame(frame)
            mock_docs.Open.assert_called_once()
            self.assertEqual(self.mock_app.ActiveDocument, target_doc)
            mock_zoom.assert_called_once()
            mock_hl.assert_called_once()


if __name__ == "__main__":
    unittest.main()
