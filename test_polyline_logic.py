import unittest
from parsers.polyline_parser import analyze

class TestPolylineLogic(unittest.TestCase):
    def test_form_4_detection(self):
        # Рамка A4 (масштаб 1:100, внешняя 21000x29700, внутренняя 18500x28700)
        polys = [
            {"bbox": (424.5, 419.0, 21424.5, 30119.0), "ref": None, "ltscale": 100.0},
            {"bbox": (2424.5, 919.0, 20924.5, 29619.0), "ref": None, "ltscale": 100.0},
        ]
        # Правый нижний угол внутренней рамки: (20924.5, 919.0), масштаб 100
        # Тексты штампа формы 4
        texts = [
            (20924.5 - 34.7 * 100, 919.0 + 17.5 * 100, "1"),
            (20924.5 - 44.7 * 100, 919.0 + 17.4 * 100, "Лист"),
            (20924.5 - 22.5 * 100, 919.0 + 17.5 * 100, "Листов"),
            (20924.5 - 85.0 * 100, 919.0 + 27.5 * 100, "Изделие закладное Зд3"),
            (20924.5 - 28.5 * 100, 919.0 + 37.2 * 100, "Масса"),
            (20924.5 - 10.3 * 100, 919.0 + 37.2 * 100, "Масштаб"),
            (20924.5 - 60.0 * 100, 919.0 + 47.2 * 100, "09-23-4-КЖ.НЦ1.И-Зд3"),
            (20924.5 - 125.0 * 100, 919.0 + 32.4 * 100, "Дата"),
        ]

        frames = analyze(polys, texts)
        self.assertEqual(len(frames), 1)
        f = frames[0]
        self.assertEqual(f["format"], "A4")
        self.assertEqual(f["scale"], 100.0)
        self.assertEqual(f["sheet_number"], "1")
        self.assertEqual(f["sheet_name"], "Изделие закладное Зд3")

    def test_form_3_detection(self):
        # Рамка A2 (масштаб 1:10, внешняя 5940x4200, внутренняя 5690x4100)
        polys = [
            {"bbox": (274.4, 164.0, 6214.4, 4364.0), "ref": None, "ltscale": 10.0},
            {"bbox": (474.4, 214.0, 6164.4, 4314.0), "ref": None, "ltscale": 10.0},
        ]
        # Правый нижний угол: (6164.4, 214.0), масштаб 10
        texts = [
            (6164.4 - 27.5 * 10, 214.0 + 27.4 * 10, "Лист"),
            (6164.4 - 27.5 * 10, 214.0 + 19.9 * 10, "9"),
            (6164.4 - 10.0 * 10, 214.0 + 27.5 * 10, "Листов"),
            (6164.4 - 42.5 * 10, 214.0 + 27.5 * 10, "Стадия"),
            (6164.4 - 85.0 * 10, 214.0 + 7.5 * 10, "Пилон R90 12.30.26-22∅25-П5"),
            (6164.4 - 60.0 * 10, 214.0 + 49.7 * 10, "09-23-4-КЖ.НЦ1"),
        ]

        frames = analyze(polys, texts)
        self.assertEqual(len(frames), 1)
        f = frames[0]
        self.assertEqual(f["format"], "A2")
        self.assertEqual(f["scale"], 10.0)
        self.assertEqual(f["sheet_number"], "9")
        self.assertEqual(f["sheet_name"], "Пилон R90 12.30.26-22∅25-П5")

if __name__ == "__main__":
    unittest.main()
