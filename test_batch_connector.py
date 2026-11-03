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

    @patch("time.sleep", return_value=None)
    @patch("os.path.exists", return_value=True)
    def test_open_document_retries_when_busy(self, mock_exists, mock_sleep):
        """AutoCAD занят: в exe это AttributeError 'Open.X' — открытие повторяется."""
        mock_docs = MagicMock()
        mock_docs.Count = 0
        new_doc = MagicMock()
        mock_docs.Open.side_effect = [AttributeError("Open.ModelSpace"), new_doc]
        self.mock_app.Documents = mock_docs

        doc, was_opened = self.connector.open_document(r"C:\Drawings\busy.dwg", read_only=True)
        self.assertEqual(doc, new_doc)
        self.assertTrue(was_opened)
        self.assertEqual(mock_docs.Open.call_count, 2)

    @patch("time.sleep", return_value=None)
    @patch("os.path.exists", return_value=True)
    def test_open_document_no_second_copy_after_failed_attempt(self, mock_exists, mock_sleep):
        """Попытка упала, но AutoCAD всё же открыл чертеж — второй раз не открываем."""
        path = os.path.abspath(r"C:\Drawings\late.dwg")
        late_doc = MagicMock()
        late_doc.FullName = path
        late_doc.Name = "late.dwg"
        state = {"opened": False}

        mock_docs = MagicMock()
        type(mock_docs).Count = property(lambda self: 1 if state["opened"] else 0)
        mock_docs.Item.side_effect = lambda i: late_doc

        def _open(*args):
            state["opened"] = True
            raise AttributeError("Open.ModelSpace")

        mock_docs.Open.side_effect = _open
        self.mock_app.Documents = mock_docs

        doc, was_opened = self.connector.open_document(path, read_only=True)
        self.assertEqual(doc, late_doc)
        self.assertTrue(was_opened)
        mock_docs.Open.assert_called_once()

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

    @patch("os.path.exists", return_value=True)
    def test_opened_by_us_tracking(self, mock_exists):
        # 1. Открытие нового файла должно добавить его в _opened_by_us
        mock_docs = MagicMock()
        mock_docs.Count = 0
        new_doc = MagicMock()
        mock_docs.Open.return_value = new_doc
        self.mock_app.Documents = mock_docs

        p_new = os.path.abspath(r"C:\Drawings\new_dwg.dwg")
        doc, was_opened = self.connector.open_document(p_new, read_only=True)
        self.assertTrue(was_opened)
        self.assertIn(p_new.lower(), self.connector._opened_by_us)

        # 2. Открытие уже открытого чертежа не должно помечать его как opened_by_us
        doc_existing = MagicMock()
        doc_existing.FullName = os.path.abspath(r"C:\Drawings\user_dwg.dwg")
        doc_existing.Name = "user_dwg.dwg"
        mock_docs.Count = 1
        mock_docs.Item.side_effect = lambda i: [doc_existing][i]

        p_existing = os.path.abspath(r"C:\Drawings\user_dwg.dwg")
        doc2, was_opened2 = self.connector.open_document(p_existing, read_only=True)
        self.assertFalse(was_opened2)
        self.assertNotIn(p_existing.lower(), self.connector._opened_by_us)

    def test_close_opened_documents_only_closes_program_files(self):
        # Пользовательский файл (открыт до программы)
        user_doc = MagicMock()
        user_doc.FullName = os.path.abspath(r"C:\Drawings\user.dwg")
        user_doc.Name = "user.dwg"

        # Файл, открытый программой
        prog_doc = MagicMock()
        prog_doc.FullName = os.path.abspath(r"C:\Drawings\prog.dwg")
        prog_doc.Name = "prog.dwg"

        all_docs = [user_doc, prog_doc]
        mock_docs = MagicMock()
        mock_docs.Count = len(all_docs)
        mock_docs.Item.side_effect = lambda i: all_docs[i]
        self.mock_app.Documents = mock_docs

        # Симулируем, что prog.dwg был открыт нашей программой
        self.connector._opened_by_us.add(os.path.abspath(r"C:\Drawings\prog.dwg").lower())

        closed_count = self.connector.close_opened_documents()

        self.assertEqual(closed_count, 1)
        prog_doc.Close.assert_called_once_with(False)
        user_doc.Close.assert_not_called()
        self.assertEqual(len(self.connector._opened_by_us), 0)

    def test_get_opened_by_us_count_prunes_closed(self):
        # Если чертеж числился в _opened_by_us, но пользователь закрыл его в AutoCAD вручную
        self.connector._opened_by_us.add(os.path.abspath(r"C:\Drawings\already_closed.dwg").lower())
        
        mock_docs = MagicMock()
        mock_docs.Count = 0
        self.mock_app.Documents = mock_docs

        count = self.connector.get_opened_by_us_count()
        self.assertEqual(count, 0)
        self.assertEqual(len(self.connector._opened_by_us), 0)


if __name__ == "__main__":
    unittest.main()
