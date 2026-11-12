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

    def test_marks_empty_layout_only_if_model_is_empty(self):
        doc = MagicMock()
        doc.ModelSpace.Count = 0
        doc.Layouts.Count = 3
        blank = MagicMock(Name="Лист1", ModelType=False, TabOrder=1)
        blank.Block.Count = 0
        viewport = MagicMock(Name="Лист2", ModelType=False, TabOrder=2)
        viewport.Block.Count = 1
        viewport.Block.Item.return_value.ObjectName = "AcDbViewport"
        drawing = MagicMock(Name="План", ModelType=False, TabOrder=3)
        drawing.Block.Count = 1
        drawing.Block.Item.return_value.ObjectName = "AcDbLine"
        doc.Layouts.Item.side_effect = [blank, viewport, drawing] * 2
        scanner = DocumentScanner()

        frames = scanner.scan_layouts(doc, "polyline")
        self.assertEqual([f.is_empty_layout for f in frames], [True, True, False])

        doc.ModelSpace.Count = 1
        frames = scanner.scan_layouts(doc, "polyline")
        self.assertEqual([f.is_empty_layout for f in frames], [False, False, False])

    def test_printer_plots_layouts_with_acLayout(self):
        mock_doc = MagicMock()
        mock_active_layout = MagicMock()
        mock_active_layout.Name = "Model"
        mock_doc.ActiveLayout = mock_active_layout

        mock_layout1 = MagicMock()
        mock_layout1.Name = "Лист 1"
        mock_layout1.GetPaperSize.side_effect = [(420, 297), (297, 420)]
        mock_layout1.PlotRotation = 0

        mock_layout2 = MagicMock()
        mock_layout2.Name = "Лист 2"
        mock_layout2.GetPaperSize.return_value = (420, 594)
        mock_layout2.PlotRotation = 0

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
        self.assertEqual(mock_layout1.PlotRotation, 1)
        self.assertEqual(mock_layout2.PlotRotation, 0)

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

    def test_block_parser_converts_paper_space_blocks_and_stamps(self):
        from parsers.block_parser import BlockParser
        parser = BlockParser()

        raw_items = [
            # Формат на Листе 1
            {
                "handle": "H_FMT1",
                "layout": "Лист 1",
                "block_name": "Формат_А3",
                "min_x": 0.0, "min_y": 0.0, "max_x": 420.0, "max_y": 297.0,
                "scale": 1.0,
                "attrs": {"SHEET": "1", "TITLE": "План 1 этажа"}
            },
            # Штамп на Листе 1 (внутри формата 1)
            {
                "handle": "H_STMP1",
                "layout": "Лист 1",
                "block_name": "Штамп_Форма3",
                "min_x": 235.0, "min_y": 5.0, "max_x": 420.0, "max_y": 60.0,
                "scale": 1.0,
                "attrs": {"DOC_CODE": "01-2026-АР", "OBJECT_NAME": "Жилой комплекс"}
            },
            # Формат на Листе 2 (без штампа)
            {
                "handle": "H_FMT2",
                "layout": "Лист 2",
                "block_name": "Формат_А2",
                "min_x": 0.0, "min_y": 0.0, "max_x": 594.0, "max_y": 420.0,
                "scale": 1.0,
                "attrs": {"SHEET": "2", "TITLE": "Разрез 1-1"}
            },
            # Формат в Пространстве Модели
            {
                "handle": "H_FMT_MOD",
                "layout": "Model",
                "block_name": "Формат_А1",
                "min_x": 1000.0, "min_y": 1000.0, "max_x": 1841.0, "max_y": 1594.0,
                "scale": 1.0,
                "attrs": {"SHEET": "3", "TITLE": "Фасад"}
            }
        ]

        frames = parser._convert_items_to_frames(raw_items)
        self.assertEqual(len(frames), 3)

        # 1. Лист 1: штамп с того же листа должен объединиться с форматом
        f1 = [f for f in frames if f.layout_name == "Лист 1"][0]
        self.assertEqual(f1.source_type, "Block (Лист)")
        self.assertEqual(f1.sheet_number, "1")
        self.assertEqual(f1.sheet_name, "План 1 этажа")
        self.assertEqual(f1.doc_code, "01-2026-АР")
        self.assertEqual(f1.object_name, "Жилой комплекс")
        self.assertEqual(f1.paper_format, "A3")

        # 2. Лист 2: не должен случайно получить атрибуты штампа с Листа 1
        f2 = [f for f in frames if f.layout_name == "Лист 2"][0]
        self.assertEqual(f2.source_type, "Block (Лист)")
        self.assertEqual(f2.sheet_number, "2")
        self.assertEqual(f2.doc_code, "")
        self.assertEqual(f2.paper_format, "A2")

        # 3. Model: source_type="Block"
        f_mod = [f for f in frames if f.layout_name == "Model"][0]
        self.assertEqual(f_mod.source_type, "Block")
        self.assertEqual(f_mod.sheet_number, "3")

    def test_spds_parser_converts_paper_space_spds(self):
        from parsers.spds_parser import SPDSParser
        parser = SPDSParser()

        raw_items = [
            {
                "handle": "H_SPDS_L1",
                "layout": "Лист 1",
                "sheet_number": "1",
                "sheet_name": "План кровли",
                "format": "A3",
                "multiplicity": 1,
                "min_x": 0.0, "min_y": 0.0, "max_x": 420.0, "max_y": 297.0
            },
            {
                "handle": "H_SPDS_MOD",
                "layout": "Model",
                "sheet_number": "2",
                "sheet_name": "Схема",
                "format": "A2",
                "multiplicity": 1,
                "min_x": 0.0, "min_y": 0.0, "max_x": 594.0, "max_y": 420.0
            }
        ]

        frames = parser._convert_items_to_frames(raw_items)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0].source_type, "SPDS (Лист)")
        self.assertEqual(frames[0].layout_name, "Лист 1")
        self.assertEqual(frames[1].source_type, "SPDS")
        self.assertEqual(frames[1].layout_name, "Model")

    def test_scanner_scan_layouts_with_mixed_block_and_fallback(self):
        scanner = DocumentScanner()
        mock_doc = MagicMock()

        m_sheet1 = MagicMock()
        m_sheet1.Name = "Лист 1"
        m_sheet1.ModelType = False
        m_sheet1.TabOrder = 1

        m_sheet2 = MagicMock()
        m_sheet2.Name = "Лист 2"
        m_sheet2.ModelType = False
        m_sheet2.TabOrder = 2
        m_sheet2.CanonicalMediaName = "ISO_A4_(210.00_x_297.00_MM)"
        m_sheet2.Handle = "H_FALLBACK_2"
        m_sheet2.ObjectID = 202

        layouts_list = [m_sheet1, m_sheet2]
        mock_layouts = MagicMock()
        mock_layouts.Count = len(layouts_list)
        mock_layouts.Item.side_effect = lambda idx: layouts_list[idx]
        mock_doc.Layouts = mock_layouts

        # Имитируем, что BlockParser нашел рамку на Листе 1
        block_frame_l1 = Frame(
            object_id=0,
            sheet_number="1",
            sheet_name="План фундамента",
            min_point=(0.0, 0.0, 0.0),
            max_point=(420.0, 297.0, 0.0),
            source_type="Block (Лист)",
            paper_format="A3",
            handle="H_BLK_L1",
            layout_name="Лист 1"
        )

        with patch("parsers.block_parser.BlockParser.find_frames", return_value=[block_frame_l1]), \
             patch("parsers.spds_parser.SPDSParser.find_frames", return_value=[]):
            frames = scanner.scan_layouts(mock_doc)

        self.assertEqual(len(frames), 2)
        # Лист 1 взят из блока рамок с его атрибутами
        self.assertEqual(frames[0].sheet_number, "1")
        self.assertEqual(frames[0].sheet_name, "План фундамента")
        self.assertEqual(frames[0].source_type, "Block (Лист)")
        self.assertEqual(frames[0].layout_name, "Лист 1")

        # Лист 2 не содержит блоков — резервная рамка Layout
        self.assertEqual(frames[1].sheet_number, "2")
        self.assertEqual(frames[1].sheet_name, "Лист 2")
        self.assertEqual(frames[1].source_type, "Layout")
        self.assertEqual(frames[1].paper_format, "A4")

    def test_printer_plots_paper_space_blocks_with_acWindow(self):
        mock_doc = MagicMock()
        mock_layout1 = MagicMock()
        mock_layout1.Name = "Лист 1"
        mock_layout1.PlotType = 0
        mock_layout1.GetLocaleMediaName.return_value = "A3 420 x 297 mm"

        mock_doc.Layouts.Item.return_value = mock_layout1
        mock_doc.ActiveLayout = mock_layout1

        printer = BatchPrinter(mock_doc)

        # Рамка-блок в пространстве листа (Paper Space)
        frame = Frame(
            object_id=101,
            sheet_number="1",
            sheet_name="План 1 этажа",
            min_point=(0.0, 0.0, 0.0),
            max_point=(420.0, 297.0, 0.0),
            source_type="Block (Лист)",
            paper_format="A3",
            layout_name="Лист 1"
        )

        with patch.object(printer, "_disable_pc3_view_file", return_value=False):
            with patch.object(printer, "_build_media_map", return_value={"A3": "sys_A3"}):
                printer.print_frames(
                    frames=[frame],
                    printer_name="DWG To PDF.pc3",
                    canonical_media_name="sys_A3",
                    style_name="monochrome.ctb",
                    output_path="C:/dummy/output",
                    merge_pdf=False
                )

        # Для блока на листе должен быть выставлен PlotType = 4 (acWindow), центрирование и SetWindowToPlot
        self.assertEqual(mock_layout1.PlotType, 4)
        self.assertTrue(mock_layout1.CenterPlot)
        self.assertEqual(mock_layout1.StandardScale, 0)
        self.assertEqual(mock_layout1.ConfigName, "DWG To PDF.pc3")
        self.assertEqual(mock_layout1.CanonicalMediaName, "sys_A3")
        self.assertTrue(mock_layout1.SetWindowToPlot.called)
        self.assertEqual(mock_doc.Plot.PlotToFile.call_count, 1)

    def test_connector_show_frame_for_paper_space_block(self):
        connector = AutoCADConnector()
        connector.doc = MagicMock()
        connector.app = MagicMock()

        frame = Frame(
            object_id=505,
            sheet_number="1",
            sheet_name="План 1 этажа",
            min_point=(0.0, 0.0, 0.0),
            max_point=(420.0, 297.0, 0.0),
            source_type="Block (Лист)",
            paper_format="A3",
            handle="H_BLK_1",
            layout_name="Лист 1"
        )

        with patch.object(connector, "activate_layout") as mock_activate, \
             patch.object(connector, "zoom_window") as mock_zoom, \
             patch.object(connector, "highlight_object") as mock_highlight:
            connector.show_frame(frame)
            mock_activate.assert_called_once_with("Лист 1")
            mock_zoom.assert_called_once_with((0.0, 0.0, 0.0), (420.0, 297.0, 0.0))
            mock_highlight.assert_called_once_with(handle="H_BLK_1", object_id=505)

    def test_paper_space_block_enriched_with_free_texts(self):
        from parsers.block_parser import BlockParser
        parser = BlockParser()

        # Рамка блока на листе "Лист 1" без заполненных атрибутов
        frame = Frame(
            object_id=101,
            sheet_number="Unknown",
            sheet_name="Unknown",
            min_point=(0.0, 0.0, 0.0),
            max_point=(420.0, 297.0, 0.0),
            source_type="Block (Лист)",
            paper_format="A3",
            layout_name="Лист 1"
        )

        # Свободные надписи на Листе 1 в зоне штампа (A3: правый нижний угол 420, 0)
        # Отступ 5 мм: угол (415, 5)
        # Наименование листа: x = 415 - 85 = 330, y = 5 + 10 = 15
        # Номер листа: x = 415 - 28 = 387, y = 5 + 20 = 25
        mock_texts = [
            (387.0, 25.0, "12", "12", (385.0, 23.0, 389.0, 27.0)),
            (330.0, 15.0, "План на отм. 0.000", "План на отм. 0.000", (300.0, 10.0, 360.0, 20.0)),
        ]

        parser._enrich_single_frame(frame, mock_texts)
        self.assertEqual(frame.sheet_number, "12")
        self.assertEqual(frame.sheet_name, "План на отм. 0.000")

    def test_paper_space_block_multiline_mtext_title(self):
        from parsers.block_parser import BlockParser
        parser = BlockParser()

        frame = Frame(
            object_id=102,
            sheet_number="5", # номер уже известен из атрибута блока
            sheet_name="Unknown",
            min_point=(0.0, 0.0, 0.0),
            max_point=(420.0, 297.0, 0.0),
            source_type="Block (Лист)",
            paper_format="A3",
            layout_name="Лист 2"
        )

        # Многострочный MTEXT со штампом в средней колонке (x = 335, y = 20)
        raw_mtext = "Многоквартирный жилой дом\\PСхема расположения колонн"
        mock_texts = [
            (335.0, 20.0, "Многоквартирный жилой дом Схема расположения колонн", raw_mtext, (300.0, 10.0, 370.0, 30.0)),
        ]

        parser._enrich_single_frame(frame, mock_texts)
        self.assertEqual(frame.sheet_number, "5")
        self.assertEqual(frame.sheet_name, "Схема расположения колонн")


if __name__ == "__main__":
    unittest.main()
