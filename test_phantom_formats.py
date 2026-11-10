"""
Тесты исключения фантомных форматов (A4x2, A3x2, A2x2, A1x2) и корректного
определения листа A3 в масштабе 1:20 (8400x5940 мм) по ГОСТ 2.301-68.
"""
import unittest
from collections import Counter
from core.models import detect_paper_format, Frame, ALL_FORMATS, GOST_FORMATS, GOST_EXTENDED
from core.scanner import DocumentScanner


class TestPhantomFormats(unittest.TestCase):
    def test_no_phantom_x2_formats(self):
        """По ГОСТ 2.301 кратность x2 существует только у A0 (A0x2). Для A4..A1 кратные начинаются с x3."""
        self.assertIn("A0x2", ALL_FORMATS)
        self.assertNotIn("A4x2", ALL_FORMATS)
        self.assertNotIn("A3x2", ALL_FORMATS)
        self.assertNotIn("A2x2", ALL_FORMATS)
        self.assertNotIn("A1x2", ALL_FORMATS)

    def test_a3_scale_20_detection(self):
        """Рамка 8400x5940 мм должна определяться как A3 (масштаб 1:20), а не как A2x2 или A1."""
        fmt_no_scale = detect_paper_format(8400, 5940)
        self.assertEqual(fmt_no_scale, "A3")

        fmt_scale_20 = detect_paper_format(8400, 5940, scale=20.0)
        self.assertEqual(fmt_scale_20, "A3")

    def test_scanner_scale_reconciliation_preserves_valid_a3_m20(self):
        """
        Согласование масштабов чертежа не должно ломать лист A3 в М1:20 (8400x5940),
        если в том же чертеже присутствуют листы A2 в М1:10 (5940x4200).
        """
        mock_frames = []
        # 9 листов A2 в масштабе 1:10
        for i in range(1, 10):
            mock_frames.append(Frame(
                object_id=i,
                sheet_number=str(i),
                sheet_name=f"Пилон {i}",
                min_point=(0, 0, 0),
                max_point=(5940, 4200, 0),
                source_type="Polyline",
                paper_format="A2"
            ))
        # 1 лист A3 в масштабе 1:20
        sheet_10 = Frame(
            object_id=10,
            sheet_number="10",
            sheet_name="План",
            min_point=(0, 0, 0),
            max_point=(8400, 5940, 0),
            source_type="Polyline",
            paper_format="A3"
        )
        mock_frames.append(sheet_10)

        # Выполняем логику согласования масштабов из scanner.py
        scales = []
        for f in mock_frames:
            fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
            w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
            sc = round(w / fw)
            if sc > 0:
                scales.append(sc)

        common_scale, count = Counter(scales).most_common(1)[0]
        self.assertEqual(common_scale, 10)

        for f in mock_frames:
            fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
            w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
            h = min(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
            curr_sc = round(w / fw) if fw > 0 else 1
            if curr_sc != common_scale:
                corrected_fmt = detect_paper_format(w, h, scale=common_scale)
                if corrected_fmt in ALL_FORMATS:
                    cfw, cfh = ALL_FORMATS[corrected_fmt]
                    err_curr = abs(w - fw * curr_sc) + abs(h - fh * curr_sc)
                    err_corr = abs(w - cfw * common_scale) + abs(h - cfh * common_scale)
                    if err_corr <= err_curr + 1.0:
                        f.paper_format = corrected_fmt

        self.assertEqual(sheet_10.paper_format, "A3")


if __name__ == "__main__":
    unittest.main()
