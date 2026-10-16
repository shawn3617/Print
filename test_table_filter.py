import unittest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from core.models import Frame
from ui.main_window import PrintManagerUI


class TestTableFilter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        self.mock_config = MagicMock()
        self.mock_config.load.return_value = {}
        self.mock_config.get.side_effect = lambda k, d=None: d
        self.win = PrintManagerUI(config_manager=self.mock_config)

        # Создаем тестовый набор данных
        self.sample_frames = [
            Frame(1, "1", "Общие данные", (0, 0, 0), (10, 10, 0), "Model", "A4", dwg_name="01_plan.dwg"),
            Frame(2, "2", "План первого этажа", (10, 0, 0), (20, 10, 0), "Model", "A3", dwg_name="01_plan.dwg"),
            Frame(3, "3", "Спецификация пилонов", (20, 0, 0), (30, 10, 0), "Model", "A2", dwg_name="02_pilons.dwg"),
            Frame(4, "4", "Спецификация балок", (30, 0, 0), (40, 10, 0), "Model", "A3", dwg_name="02_pilons.dwg"),
            Frame(5, "5", "Разрез 1-1", (40, 0, 0), (50, 10, 0), "Model", "A4", dwg_name="03_sections.dwg"),
        ]
        self.win.frames = list(self.sample_frames)
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)
        self.win.update_format_filter_items()

    def test_format_filter_items_populated(self):
        # Проверяем, что в комбобоксе форматов есть "Все форматы", а также A2, A3, A4
        items = [self.win.combo_filter_format.itemText(i) for i in range(self.win.combo_filter_format.count())]
        self.assertTrue(any("Все форматы" in it for it in items))
        self.assertTrue(any("A2" in it for it in items))
        self.assertTrue(any("A3" in it for it in items))
        self.assertTrue(any("A4" in it for it in items))

    def test_filter_by_format_a3(self):
        # Выбираем формат A3
        idx = -1
        for i in range(self.win.combo_filter_format.count()):
            if "A3" in self.win.combo_filter_format.itemText(i):
                idx = i
                break
        self.assertGreaterEqual(idx, 0)
        self.win.combo_filter_format.setCurrentIndex(idx)

        # Строки 1 и 3 должны быть видимы (индексы 1 и 3 соответствуют листам 2 и 4 с форматом A3)
        self.assertTrue(self.win.table.isRowHidden(0))   # A4
        self.assertFalse(self.win.table.isRowHidden(1))  # A3
        self.assertTrue(self.win.table.isRowHidden(2))   # A2
        self.assertFalse(self.win.table.isRowHidden(3))  # A3
        self.assertTrue(self.win.table.isRowHidden(4))   # A4

    def test_filter_by_search_text_case_insensitive(self):
        # Ищем "спецификация" в нижнем регистре
        self.win.txt_search.setText("спецификация")

        # Строки 2 и 3 содержат "Спецификация" в названии
        self.assertTrue(self.win.table.isRowHidden(0))
        self.assertTrue(self.win.table.isRowHidden(1))
        self.assertFalse(self.win.table.isRowHidden(2))
        self.assertFalse(self.win.table.isRowHidden(3))
        self.assertTrue(self.win.table.isRowHidden(4))

    def test_filter_by_sheet_number(self):
        # Ищем по номеру листа "5"
        self.win.txt_search.setText("5")

        self.assertTrue(self.win.table.isRowHidden(0))
        self.assertTrue(self.win.table.isRowHidden(1))
        self.assertTrue(self.win.table.isRowHidden(2))
        self.assertTrue(self.win.table.isRowHidden(3))
        self.assertFalse(self.win.table.isRowHidden(4))

    def test_filter_by_dwg_name(self):
        # Ищем по имени файла чертежа "pilons"
        self.win.txt_search.setText("pilons")

        self.assertTrue(self.win.table.isRowHidden(0))
        self.assertTrue(self.win.table.isRowHidden(1))
        self.assertFalse(self.win.table.isRowHidden(2))
        self.assertFalse(self.win.table.isRowHidden(3))
        self.assertTrue(self.win.table.isRowHidden(4))

    def test_combined_search_and_format_filter(self):
        # Выбираем формат A3 и пишем "балок"
        idx = -1
        for i in range(self.win.combo_filter_format.count()):
            if "A3" in self.win.combo_filter_format.itemText(i):
                idx = i
                break
        self.win.combo_filter_format.setCurrentIndex(idx)
        self.win.txt_search.setText("балок")

        # Только строка 3 ("Спецификация балок", A3) должна остаться видимой
        for r in range(5):
            if r == 3:
                self.assertFalse(self.win.table.isRowHidden(r))
            else:
                self.assertTrue(self.win.table.isRowHidden(r))

    def test_reset_filter(self):
        # Задаем фильтр и затем сбрасываем
        self.win.txt_search.setText("балок")
        self.win.reset_filter()

        self.assertEqual(self.win.txt_search.text(), "")
        self.assertEqual(self.win.combo_filter_format.currentIndex(), 0)
        # Все строки должны стать видимыми
        for r in range(5):
            self.assertFalse(self.win.table.isRowHidden(r))

    def test_select_all_only_affects_visible_rows(self):
        # Отфильтруем A4 (строки 0 и 4)
        idx = -1
        for i in range(self.win.combo_filter_format.count()):
            if "A4" in self.win.combo_filter_format.itemText(i):
                idx = i
                break
        self.win.combo_filter_format.setCurrentIndex(idx)

        # Снимаем все галочки с видимых строк (A4)
        self.win.select_all_rows(False)

        # Проверяем: строки 0 и 4 сняты, а строки 1, 2, 3 (A3, A2) остались True
        self.assertFalse(self.win.is_row_checked(0))
        self.assertTrue(self.win.is_row_checked(1))
        self.assertTrue(self.win.is_row_checked(2))
        self.assertTrue(self.win.is_row_checked(3))
        self.assertFalse(self.win.is_row_checked(4))

        # Выбираем все галочки для видимых строк (A4)
        self.win.select_all_rows(True)
        self.assertTrue(self.win.is_row_checked(0))
        self.assertTrue(self.win.is_row_checked(4))

    def test_get_frames_to_print_excludes_hidden(self):
        # Отфильтруем A2 (только строка 2)
        idx = -1
        for i in range(self.win.combo_filter_format.count()):
            if "A2" in self.win.combo_filter_format.itemText(i):
                idx = i
                break
        self.win.combo_filter_format.setCurrentIndex(idx)

        frames_to_print = self.win.get_frames_to_print()
        self.assertEqual(len(frames_to_print), 1)
        self.assertEqual(frames_to_print[0].sheet_number, "3")

    def test_reorder_disabled_when_filtered(self):
        # Без фильтра кнопки Вверх/Вниз активны
        self.win.reset_filter()
        self.assertTrue(self.win.btn_move_up.isEnabled())
        self.assertTrue(self.win.btn_move_down.isEnabled())

        # При активном фильтре кнопки должны быть заблокированы
        self.win.txt_search.setText("разрез")
        self.assertFalse(self.win.btn_move_up.isEnabled())
        self.assertFalse(self.win.btn_move_down.isEnabled())

        # После сброса фильтра снова активны
        self.win.reset_filter()
        self.assertTrue(self.win.btn_move_up.isEnabled())
        self.assertTrue(self.win.btn_move_down.isEnabled())


if __name__ == "__main__":
    unittest.main()
