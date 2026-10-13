import unittest
from unittest.mock import MagicMock
from core.models import Frame
from core.autocad_connector import AutoCADConnector

class TestHighlightLogic(unittest.TestCase):
    def test_frame_handle_default(self):
        f = Frame(1, "1", "Лист 1", (0, 0, 0), (297, 210, 0), "SPDS", "A4")
        self.assertEqual(f.handle, "")
        
        f2 = Frame(2, "2", "Лист 2", (0, 0, 0), (420, 297, 0), "Block", "A3", handle="2F8")
        self.assertEqual(f2.handle, "2F8")

    def test_zoom_window_coordinate_margins(self):
        connector = AutoCADConnector()
        connector.app = MagicMock()
        connector.doc = MagicMock()
        connector.doc.ActiveSpace = 1

        # Вызываем zoom_window
        min_pt = (100.0, 200.0, 0.0)
        max_pt = (500.0, 600.0, 0.0)
        # dx = 400, dy = 400, margin = 20
        connector.zoom_window(min_pt, max_pt, margin_percent=0.05)

        connector.app.ZoomWindow.assert_called_once()
        args, _ = connector.app.ZoomWindow.call_args
        self.assertEqual(len(args), 2)
        # Проверяем, что переданы VARIANT-объекты
        self.assertTrue(args[0] is not None)
        self.assertTrue(args[1] is not None)

    def test_highlight_object_and_clear(self):
        connector = AutoCADConnector()
        connector.app = MagicMock()
        connector.doc = MagicMock()

        mock_obj = MagicMock()
        mock_obj.Handle = "3AB"
        connector.doc.HandleToObject.return_value = mock_obj

        # Подсвечиваем первый объект
        connector.highlight_object(handle="3AB")
        mock_obj.Highlight.assert_called_with(True)
        self.assertEqual(connector._last_highlighted_handle, "3AB")

        # Подсвечиваем второй объект - первый должен быть снят
        mock_obj2 = MagicMock()
        mock_obj2.Handle = "3AC"
        connector.doc.HandleToObject.side_effect = lambda h: mock_obj if h == "3AB" else mock_obj2

        connector.highlight_object(handle="3AC")
        mock_obj.Highlight.assert_called_with(False)
        mock_obj2.Highlight.assert_called_with(True)
        self.assertEqual(connector._last_highlighted_handle, "3AC")

        # Очистка
        connector.clear_highlight()
        mock_obj2.Highlight.assert_called_with(False)
        self.assertIsNone(connector._last_highlighted_handle)

    def test_show_frame_integration(self):
        connector = AutoCADConnector()
        connector.app = MagicMock()
        connector.doc = MagicMock()
        connector.app.ActiveDocument = connector.doc
        mock_obj = MagicMock()
        connector.doc.HandleToObject.return_value = mock_obj

        frame = Frame(
            object_id=999,
            sheet_number="5",
            sheet_name="План кровли",
            min_point=(0.0, 0.0, 0.0),
            max_point=(1000.0, 500.0, 0.0),
            source_type="Polyline",
            paper_format="A1",
            handle="4D1"
        )

        connector.show_frame(frame, zoom=True, highlight=True)
        connector.app.ZoomWindow.assert_called_once()
        mock_obj.Highlight.assert_called_with(True)

    def test_ui_highlight_on_cell_change(self):
        import os
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        from PySide6.QtWidgets import QApplication
        from ui.main_window import PrintManagerUI

        app = QApplication.instance() or QApplication([])
        win = PrintManagerUI(config_manager=MagicMock())
        win.connector = MagicMock()
        frame = Frame(1, "1", "Лист 1", (0, 0, 0), (297, 210, 0), "SPDS", "A4", handle="1A")
        win.frames = [frame]
        win.add_table_row(True, "1", "Лист 1", "A4", "SPDS")

        # 1. При включенном чекбоксе выбор ячейки вызывает show_frame
        win.chk_sync_acad.setChecked(True)
        win.table.setCurrentCell(0, 1)
        win.connector.show_frame.assert_called_with(frame, zoom=True, highlight=True)

        # 2. При выключенном чекбоксе show_frame не вызывается
        win.connector.show_frame.reset_mock()
        win.chk_sync_acad.setChecked(False)
        win.table.setCurrentCell(0, 2)
        win.connector.show_frame.assert_not_called()

        # 3. Кнопка "В AutoCAD" вызывает show_frame и activate_autocad_window
        win.show_current_frame_in_autocad()
        win.connector.show_frame.assert_called_with(frame, zoom=True, highlight=True)
        win.connector.activate_autocad_window.assert_called_once()

if __name__ == "__main__":
    unittest.main()
