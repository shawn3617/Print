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

    def test_explicit_spds_formats_survive_identical_frame_dimensions(self):
        from parsers.spds_parser import SPDSParser

        rows = [
            {"sheet_number": "2", "format": "A2", "scale": 100, "max_x": 42000, "max_y": 59400},
            {"sheet_number": "1", "format": "A4", "scale": 200, "min_x": 50000,
             "max_x": 92000, "max_y": 59400},
        ]
        with patch.object(SPDSParser, "_run_lisp_export", return_value=rows):
            frames = self.scanner.scan_document(MagicMock(), "spds")

        self.assertEqual(
            [(f.sheet_number, f.paper_format, f.scale, f.is_ambiguous) for f in frames],
            [("1", "A4", 200, False), ("2", "A2", 100, False)],
        )

    def test_explicit_block_format_survives_dominant_scale(self):
        from parsers.block_parser import BlockParser

        rows = [
            {"block_name": "SHT_A4P", "scale": 200, "max_x": 42000, "max_y": 59400,
             "attrs": {"FORMAT": "A4", "SHEET": "2"}},
            {"block_name": "SHT_A2L", "scale": 100, "min_x": 50000, "max_x": 109400,
             "max_y": 42000, "attrs": {"FORMAT": "A2", "SHEET": "1"}},
            {"block_name": "SHT_A4P", "scale": 200, "min_x": 120000, "max_x": 162000,
             "max_y": 59400, "attrs": {"FORMAT": "A4", "SHEET": "3"}},
        ]
        with patch.object(BlockParser, "_run_lisp_export", return_value=rows):
            frames = self.scanner.scan_document(MagicMock(), "all_blocks")

        self.assertEqual(
            [(f.sheet_number, f.paper_format, f.scale) for f in frames],
            [("1", "A2", 100), ("2", "A4", 200), ("3", "A4", 200)],
        )

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

    def test_get_parsers_for_mode(self):
        from parsers.spds_parser import SPDSParser
        from parsers.block_parser import BlockParser
        from parsers.polyline_parser import PolylineParser
        from core.scanner import (
            FRAME_TYPE_SPDS, FRAME_TYPE_ALL_BLOCKS,
            FRAME_TYPE_CUSTOM_BLOCK, FRAME_TYPE_POLYLINE, FRAME_TYPE_ALL
        )

        # 1. SPDS only
        p_spds = self.scanner.get_parsers_for_mode(FRAME_TYPE_SPDS)
        self.assertEqual(len(p_spds), 1)
        self.assertIsInstance(p_spds[0], SPDSParser)

        # 2. All blocks only
        p_blocks = self.scanner.get_parsers_for_mode(FRAME_TYPE_ALL_BLOCKS)
        self.assertEqual(len(p_blocks), 1)
        self.assertIsInstance(p_blocks[0], BlockParser)

        # 3. Custom block
        p_custom = self.scanner.get_parsers_for_mode(FRAME_TYPE_CUSTOM_BLOCK, "Рамка1, SHT_*")
        self.assertEqual(len(p_custom), 1)
        self.assertIsInstance(p_custom[0], BlockParser)
        self.assertIn("рамка1", p_custom[0].block_names)
        self.assertIn("*рамка1*", p_custom[0].block_names)
        self.assertIn("sht_*", p_custom[0].block_names)

        # 4. Polyline only
        p_poly = self.scanner.get_parsers_for_mode(FRAME_TYPE_POLYLINE)
        self.assertEqual(len(p_poly), 1)
        self.assertIsInstance(p_poly[0], PolylineParser)

        # 5. All parsers
        p_all = self.scanner.get_parsers_for_mode(FRAME_TYPE_ALL)
        self.assertEqual(len(p_all), 3)


if __name__ == "__main__":
    unittest.main()
