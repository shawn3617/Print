import unittest
from unittest.mock import MagicMock, patch

from core.models import Frame, detect_format_from_media_name
from core.scanner import DocumentScanner
from core.printer import BatchPrinter
from core.autocad_connector import AutoCADConnector


class TestLayoutsSupport(unittest.TestCase):
    def test_detect_format_from_media_name(self):
        self.assertEqual(detect_format_from_media_name("ISO_full_bleed_A3_(420.00_x_297.00_MM)"), "A3")
        self.assertEqual(detect_format_from_media_name("ISO_A4_(210.00_x_297.00_MM)"), "A4")
        self.assertEqual(detect_format_from_media_name("ISO_full_bleed_A2_(594.00_x_420.00_MM)"), "A2")
        self.assertEqual(detect_format_from_media_name("ISO_full_bleed_A1_(841.00_x_594.00_MM)"), "A1")
        self.assertEqual(detect_format_from_media_name("ISO_full_bleed_A0_(1189.00_x_841.00_MM)"), "A0")
        self.assertEqual(detect_format_from_media_name("Custom_1485_x_420_MM"), "A3x5")

    def test_scanner_scan_layouts(self):
        scanner = DocumentScanner()

        mock_doc = MagicMock()
        # Создаем макеты: Model (должен быть пропущен) и 3 листа с разным TabOrder
        m_model = MagicMock()
        m_model.Name = "Model"
        m_model.ModelType = True
        m_model.TabOrder = 0

        m_sheet2 = MagicMock()
        m_sheet2.Name = "Лист 2 - Разрез 1-1"
        m_sheet2.ModelType = False
        m_sheet2.TabOrder = 2
        m_sheet2.CanonicalMediaName = "ISO_full_bleed_A2_(594.00_x_420.00_MM)"
        m_sheet2.Handle = "H2"
        m_sheet2.ObjectID = 202

        m_sheet1 = MagicMock()
        m_sheet1.Name = "Лист 1 - План этажа"
        m_sheet1.ModelType = False
        m_sheet1.TabOrder = 1
        m_sheet1.CanonicalMediaName = "ISO_full_bleed_A3_(420.00_x_297.00_MM)"
        m_sheet1.Handle = "H1"
        m_sheet1.ObjectID = 101

        layouts_list = [m_model, m_sheet2, m_sheet1]

        mock_layouts = MagicMock()
        mock_layouts.Count = len(layouts_list)
        mock_layouts.Item.side_effect = lambda idx: layouts_list[idx]
        mock_doc.Layouts = mock_layouts

        frames = scanner.scan_layouts(mock_doc)

        # Должно быть ровно 2 листа, Model отфильтрован
        self.assertEqual(len(frames), 2)

        # Отсортированы по TabOrder: сначала Лист 1, затем Лист 2
        self.assertEqual(frames[0].sheet_number, "1")
        self.assertEqual(frames[0].sheet_name, "Лист 1 - План этажа")
        self.assertEqual(frames[0].paper_format, "A3")
        self.assertEqual(frames[0].source_type, "Layout")
        self.assertEqual(frames[0].handle, "H1")

        self.assertEqual(frames[1].sheet_number, "2")
        self.assertEqual(frames[1].sheet_name, "Лист 2 - Разрез 1-1")
        self.assertEqual(frames[1].paper_format, "A2")
        self.assertEqual(frames[1].source_type, "Layout")

    def test_printer_plots_layouts_with_acLayout(self):
        mock_doc = MagicMock()
        mock_active_layout = MagicMock()
        mock_active_layout.Name = "Model"
        mock_doc.ActiveLayout = mock_active_layout

        mock_layout1 = MagicMock()
        mock_layout1.Name = "Лист 1"

        mock_layout2 = MagicMock()
        mock_layout2.Name = "Лист 2"

        def get_layout_item(name):
            if name == "Лист 1": return mock_layout1
            if name == "Лист 2": return mock_layout2
            return mock_active_layout

        mock_doc.Layouts.Item.side_effect = get_layout_item

        printer = BatchPrinter(mock_doc)

        frames = [
            Frame(101, "1", "Лист 1", (0, 0, 0), (0, 0, 0), "Layout", "A3"),
            Frame(102, "2", "Лист 2", (0, 0, 0), (0, 0, 0), "Layout", "A2"),
        ]

        with patch.object(printer, "_disable_pc3_view_file", return_value=False):
            with patch.object(printer, "_build_media_map", return_value={"A3": "sys_A3", "A2": "sys_A2"}):
                printer.print_frames(
                    frames=frames,
                    printer_name="DWG To PDF.pc3",
                    canonical_media_name="sys_A3",
                    style_name="monochrome.ctb",
                    output_path="C:/dummy/output",
                    merge_pdf=False
                )

        # Проверяем, что для Layout листов был выставлен PlotType = 5 (acLayout)
        self.assertEqual(mock_layout1.PlotType, 5)
        self.assertEqual(mock_layout2.PlotType, 5)
        self.assertEqual(mock_layout1.ConfigName, "DWG To PDF.pc3")
        self.assertEqual(mock_layout2.ConfigName, "DWG To PDF.pc3")
        self.assertEqual(mock_layout1.CanonicalMediaName, "sys_A3")
        self.assertEqual(mock_layout2.CanonicalMediaName, "sys_A2")

        # PlotToFile вызван для каждого листа
        self.assertEqual(mock_doc.Plot.PlotToFile.call_count, 2)

        # Исходный ActiveLayout восстановлен в finally
        self.assertEqual(mock_doc.ActiveLayout.Name, "Model")

    def test_connector_show_frame_activates_layout(self):
        connector = AutoCADConnector()
        connector.doc = MagicMock()
        connector.app = MagicMock()

        frame = Frame(101, "1", "Лист 1", (0, 0, 0), (0, 0, 0), "Layout", "A3")

        with patch.object(connector, "activate_layout") as mock_activate:
            connector.show_frame(frame)
            mock_activate.assert_called_once_with("Лист 1")


if __name__ == "__main__":
    unittest.main()
