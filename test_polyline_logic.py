import unittest
from parsers.polyline_parser import analyze
from core.models import Frame, frame_natural_sort_key

class TestPolylineLogic(unittest.TestCase):
    def test_identical_outer_sizes_use_each_frames_own_evidence(self):
        polys = [
            {"bbox": (0, 0, 59400, 42000), "ref": "A2"},
            {"bbox": (2000, 500, 58900, 41500), "ref": None},
            {"bbox": (70000, 0, 129400, 42000), "ref": "A4"},
            {"bbox": (74000, 1000, 128400, 41000), "ref": None},
            {"bbox": (140000, 0, 199400, 42000), "ref": "unknown", "ltscale": 1},
        ]
        by_ref = {f["ref"]: f for f in analyze(polys, [])}
        self.assertEqual(set(by_ref), {"A2", "A4", "unknown"})
        self.assertEqual(list(by_ref["A2"]["candidate_bounds"]), [("A2", 100)])
        self.assertEqual(list(by_ref["A4"]["candidate_bounds"]), [("A4", 200)])
        options = by_ref["unknown"]["candidate_bounds"]
        self.assertIn(("A2", 100), options)
        self.assertIn(("A4", 200), options)
        self.assertEqual(options[("A4", 200)], polys[-1]["bbox"])

    def test_stamp_position_takes_precedence_over_linetype_scale(self):
        poly = {"bbox": (0, 0, 59400, 42000), "ref": None, "ltscale": 100}
        texts = [(58400 - 27.5 * 200, 1000 + 27.5 * 200, "Лист")]
        frame, = analyze([poly], texts)
        self.assertEqual(list(frame["candidate_bounds"]), [("A4", 200)])
        self.assertEqual(frame["format_reason"], "Расположение заголовков штампа")

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
        self.assertEqual(f["doc_code"], "09-23-4-КЖ.НЦ1.И-Зд3")
        self.assertEqual(f["object_name"], "")
        self.assertEqual(f["building_name"], "")

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
            (6164.4 - 85.0 * 10, 214.0 + 22.0 * 10, "Позиция 4.1"),
            (6164.4 - 60.0 * 10, 214.0 + 38.0 * 10, "Жилой комплекс"),
            (6164.4 - 60.0 * 10, 214.0 + 49.7 * 10, "09-23-4-КЖ.НЦ1"),
        ]

        frames = analyze(polys, texts)
        self.assertEqual(len(frames), 1)
        f = frames[0]
        self.assertEqual(f["format"], "A2")
        self.assertEqual(f["scale"], 10.0)
        self.assertEqual(f["sheet_number"], "9")
        self.assertEqual(f["sheet_name"], "Пилон R90 12.30.26-22∅25-П5")
        self.assertEqual(f["doc_code"], "09-23-4-КЖ.НЦ1")
        self.assertEqual(f["object_name"], "Жилой комплекс")
        self.assertEqual(f["building_name"], "Позиция 4.1")

    def test_title_page_detection_and_ordering(self):
        # Лист 1: Форма 4 (A4, 1:100)
        p1_out = {"bbox": (0, 0, 21000, 29700), "ref": None, "ltscale": 100.0}
        p1_in = {"bbox": (2000, 500, 20500, 29200), "ref": None, "ltscale": 100.0}
        texts1 = [
            (20500 - 34.7 * 100, 500 + 17.5 * 100, "1"),
            (20500 - 44.7 * 100, 500 + 17.4 * 100, "Лист"),
            (20500 - 85.0 * 100, 500 + 27.5 * 100, "Изделие Зд3"),
            (20500 - 28.5 * 100, 500 + 37.2 * 100, "Масса"),
            (20500 - 60.0 * 100, 500 + 47.2 * 100, "09-23-4-КЖ.НЦ1.И-Зд3"),
        ]

        # Лист Титульный: внешняя и внутренняя рамка A4, но штамп пустой
        p_title_out = {"bbox": (50000, 0, 71000, 29700), "ref": None, "ltscale": 100.0}
        p_title_in = {"bbox": (52000, 500, 70500, 29200), "ref": None, "ltscale": 100.0}
        # Только текст под рамкой ("Формат A4")
        texts_title = [
            (70500 - 32.5 * 100, 500 - 2.8 * 100, "Формат"),
            (70500 - 12.2 * 100, 500 - 2.5 * 100, "A4"),
        ]

        all_polys = [p1_out, p1_in, p_title_out, p_title_in]
        all_texts = texts1 + texts_title

        frames = analyze(all_polys, all_texts)
        self.assertEqual(len(frames), 2)
        # Титульный лист ВСЕГДА должен идти первым!
        self.assertEqual(frames[0]["sheet_name"], "Титульный лист")
        self.assertEqual(frames[0]["sheet_number"], "")
        self.assertEqual(frames[0]["format"], "A4")
        self.assertEqual(frames[0]["doc_code"], "")
        self.assertEqual(frames[0]["object_name"], "")
        self.assertEqual(frames[0]["building_name"], "")

        self.assertEqual(frames[1]["sheet_name"], "Изделие Зд3")
        self.assertEqual(frames[1]["sheet_number"], "1")
        self.assertEqual(frames[1]["format"], "A4")
        self.assertEqual(frames[1]["doc_code"], "09-23-4-КЖ.НЦ1.И-Зд3")

    def test_frame_natural_sort_key_title_priority(self):
        f_title = Frame(1, "", "Титульный лист", (0,0,0), (10,10,0), "Polyline")
        f1 = Frame(2, "1", "План 1", (0,0,0), (10,10,0), "Polyline")
        f2 = Frame(3, "2", "План 2", (0,0,0), (10,10,0), "Polyline")

        raw_list = [f2, f1, f_title]
        raw_list.sort(key=frame_natural_sort_key)
        self.assertEqual(raw_list, [f_title, f1, f2])

if __name__ == "__main__":
    unittest.main()
