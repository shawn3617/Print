import unittest
from core.models import Frame, natural_sheet_sort_key
from core.scanner import DocumentScanner


class TestNaturalSort(unittest.TestCase):
    def test_natural_sort_key_comparisons(self):
        k4 = natural_sheet_sort_key("4")
        k4_1 = natural_sheet_sort_key("4.1")
        k4_a = natural_sheet_sort_key("4а")
        k4_b = natural_sheet_sort_key("4б")
        k5 = natural_sheet_sort_key("5")
        k9 = natural_sheet_sort_key("9")
        k10 = natural_sheet_sort_key("10")

        self.assertLess(k4, k4_1)
        self.assertLess(k4_1, k4_a)
        self.assertLess(k4_a, k4_b)
        self.assertLess(k4_b, k5)
        self.assertLess(k5, k9)
        self.assertLess(k9, k10)

    def test_natural_sort_full_sequence(self):
        raw_numbers = ["10", "4б", "1", "4.1", "5", "4", "4а", "2", "4.2"]
        sorted_numbers = sorted(raw_numbers, key=natural_sheet_sort_key)
        expected = ["1", "2", "4", "4.1", "4.2", "4а", "4б", "5", "10"]
        self.assertEqual(sorted_numbers, expected)

    def test_natural_sort_prefix_sheets(self):
        raw = ["ПЗ-10", "1", "ПЗ-2", "ПЗ-1", "2"]
        sorted_sheets = sorted(raw, key=natural_sheet_sort_key)
        # Числовые листы (1, 2) идут первыми, затем листы с текстовым префиксом (ПЗ-1, ПЗ-2, ПЗ-10)
        expected = ["1", "2", "ПЗ-1", "ПЗ-2", "ПЗ-10"]
        self.assertEqual(sorted_sheets, expected)

    def test_multi_dwg_cross_file_natural_order(self):
        # Чертеж 1: листы 1, 4, 5
        # Чертеж 2: листы 4а, 4.1
        f1 = Frame(1, "1", "Лист 1", (0,0,0), (10,10,0), "Model", dwg_name="file1.dwg")
        f4 = Frame(4, "4", "Лист 4", (0,0,0), (10,10,0), "Model", dwg_name="file1.dwg")
        f5 = Frame(5, "5", "Лист 5", (0,0,0), (10,10,0), "Model", dwg_name="file1.dwg")
        f4_1 = Frame(41, "4.1", "Лист 4.1", (0,0,0), (10,10,0), "Model", dwg_name="file2.dwg")
        f4_a = Frame(42, "4а", "Лист 4а", (0,0,0), (10,10,0), "Model", dwg_name="file2.dwg")

        frames = [f5, f4_a, f1, f4_1, f4]
        frames.sort(key=lambda f: (natural_sheet_sort_key(f.sheet_number), f.dwg_name.lower()))

        order = [f.sheet_number for f in frames]
        self.assertEqual(order, ["1", "4", "4.1", "4а", "5"])


if __name__ == "__main__":
    unittest.main()
