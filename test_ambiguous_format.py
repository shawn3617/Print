"""
Тесты для механизма выявления и ручного уточнения неоднозначных форматов (test_ambiguous_format.py).

Проверяет Пункт 4 плана улучшений:
- Обнаружение неоднозначных форматов (A2 М1:100 vs A4 М1:200);
- Сохранение основания выбора, масштаба и списка альтернатив в Frame;
- Работу диалога ручного выбора FormatSelectDialog;
- Отображение предупреждений и ручное переключение формата в интерфейсе.
"""

import unittest
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication

from core.models import (
    Frame,
    ALL_FORMATS,
    detect_paper_format,
    detect_paper_format_detailed,
    FormatDetectionResult
)
from ui.format_dialog import FormatSelectDialog

app = QApplication.instance() or QApplication([])


class TestAmbiguousFormatDetection(unittest.TestCase):
    def test_unambiguous_standard_sheet(self):
        """Однозначный лист A3 (420 x 297 мм в М1:1)"""
        res = detect_paper_format_detailed(420.0, 297.0)
        self.assertEqual(res.paper_format, "A3")
        self.assertEqual(res.scale, 1)
        self.assertFalse(res.is_ambiguous)
        self.assertIn("Геометрия М1:1", res.reason)

    def test_ambiguous_sheet_a2_100_vs_a4_200(self):
        """Неоднозначный лист 59400 x 42000 мм (A2 М1:100 или A4 М1:200)"""
        res = detect_paper_format_detailed(59400.0, 42000.0)
        # По приоритету выбирается масштаб 1:100 (A2)
        self.assertEqual(res.paper_format, "A2")
        self.assertEqual(res.scale, 100)
        self.assertTrue(res.is_ambiguous)

        # Проверяем наличие кандидатов A2 и A4
        cand_formats = [(c.paper_format, c.scale) for c in res.candidates]
        self.assertIn(("A2", 100), cand_formats)
        self.assertIn(("A4", 200), cand_formats)
        self.assertIn("альтернатива", res.reason.lower())

    def test_ambiguous_sheet_a4_100_vs_a2_50(self):
        """Неоднозначный лист 29700 x 21000 мм (A4 М1:100 или A2 М1:50)"""
        res = detect_paper_format_detailed(29700.0, 21000.0)
        # По приоритету 1:100 выбирается A4
        self.assertEqual(res.paper_format, "A4")
        self.assertEqual(res.scale, 100)
        self.assertTrue(res.is_ambiguous)

        cand_formats = [(c.paper_format, c.scale) for c in res.candidates]
        self.assertIn(("A4", 100), cand_formats)
        self.assertIn(("A2", 50), cand_formats)

    def test_block_name_resolves_ambiguity(self):
        """Если имя блока явно содержит A4, неоднозначность снимается в пользу A4"""
        res = detect_paper_format_detailed(59400.0, 42000.0, block_name="Формат_A4_альбом")
        self.assertEqual(res.paper_format, "A4")
        self.assertEqual(res.scale, 200)
        self.assertFalse(res.is_ambiguous)
        self.assertIn("Имя блока", res.reason)

    def test_explicit_spds_scale_resolves_ambiguity(self):
        """Если из свойств СПДС известен точный масштаб 1:200, выбирается A4 без неоднозначности"""
        res = detect_paper_format_detailed(59400.0, 42000.0, scale=200.0)
        self.assertEqual(res.paper_format, "A4")
        self.assertEqual(res.scale, 200)
        self.assertFalse(res.is_ambiguous)
        self.assertIn("СПДС", res.reason)

    def test_backward_compatibility_detect_paper_format(self):
        """Проверка работы старой функции detect_paper_format"""
        self.assertEqual(detect_paper_format(420.0, 297.0), "A3")
        self.assertEqual(detect_paper_format(59400.0, 42000.0), "A2")
        self.assertEqual(detect_paper_format(59400.0, 42000.0, block_name="A4"), "A4")


class TestFormatSelectDialog(unittest.TestCase):
    def test_dialog_initialization_with_ambiguous_frame(self):
        """Проверка инициализации диалога для неоднозначного листа"""
        frame = Frame(
            object_id=1,
            sheet_number="1",
            sheet_name="План этажа",
            min_point=(0, 0, 0),
            max_point=(59400, 42000, 0),
            source_type="Model",
            paper_format="A2",
            scale=100,
            format_reason="Геометрия М1:100 (альтернатива A4)",
            possible_formats=[("A2", 100), ("A4", 200)],
            is_ambiguous=True
        )

        dlg = FormatSelectDialog(frame=frame, selected_count=1)
        self.assertEqual(dlg.get_selected_format(), "A2")
        self.assertEqual(dlg.get_selected_scale(), 100)
        self.assertFalse(dlg.apply_to_selected_rows())

        # Переключаем на альтернативного кандидата A4 (200)
        dlg._on_candidate_toggled(True, "A4", 200)
        self.assertEqual(dlg.get_selected_format(), "A4")
        self.assertEqual(dlg.get_selected_scale(), 200)

    def test_dialog_manual_format_change(self):
        """Ручной выбор формата из выпадающего списка"""
        frame = Frame(
            object_id=2,
            sheet_number="2",
            sheet_name="Схема",
            min_point=(0, 0, 0),
            max_point=(420, 297, 0),
            source_type="Model",
            paper_format="A3",
            scale=1
        )

        dlg = FormatSelectDialog(frame=frame, selected_count=3)
        # Меняем на A1
        idx = dlg.combo_format.findData("A1")
        dlg.combo_format.setCurrentIndex(idx)
        dlg.combo_scale.setEditText("50")

        self.assertEqual(dlg.get_selected_format(), "A1")
        self.assertEqual(dlg.get_selected_scale(), 50)

        # Проверяем чекбокс "Применить ко всем"
        self.assertIsNotNone(dlg.chk_apply_all)
        dlg.chk_apply_all.setChecked(True)
        self.assertTrue(dlg.apply_to_selected_rows())


class TestMainWindowFormatClarification(unittest.TestCase):
    def test_table_format_item_ambiguity_warning(self):
        """В таблице неоднозначный лист отображается со значком ⚠️ и подробной подсказкой"""
        from ui.main_window import PrintManagerUI

        win = PrintManagerUI()
        frame = Frame(
            object_id=1,
            sheet_number="5",
            sheet_name="План",
            min_point=(0, 0, 0),
            max_point=(59400, 42000, 0),
            source_type="Model",
            paper_format="A2",
            scale=100,
            format_reason="Геометрия М1:100",
            possible_formats=[("A2", 100), ("A4", 200)],
            format_candidate_bounds={("A4", 200): (-4000, -1000, 60400, 43000)},
            is_ambiguous=True
        )

        win.frames = [frame]
        win.add_table_row(
            checked=True,
            num="5",
            name="План",
            paper_format="A2",
            source="Model",
            frame=frame
        )

        item = win.table.item(0, 6)
        self.assertIn("⚠️", item.text())
        self.assertIn("A2", item.text())
        self.assertIn("Неоднозначный формат", item.toolTip())
        self.assertIn("A4 (М1:200)", item.toolTip())

        # Выполняем быстрое переключение на A4
        win.quick_switch_format(0, "A4", 200)

        self.assertEqual(frame.paper_format, "A4")
        self.assertEqual(frame.scale, 200)
        self.assertEqual(frame.min_point, (-4000, -1000, 0))
        self.assertEqual(frame.max_point, (60400, 43000, 0))
        self.assertFalse(frame.is_ambiguous)
        self.assertTrue(frame.user_override)

        # Теперь значок ✏️ (ручное изменение) и нет предупреждения ⚠️
        item_updated = win.table.item(0, 6)
        self.assertIn("✏️", item_updated.text())
        self.assertIn("A4", item_updated.text())
        self.assertIn("задан вручную", item_updated.toolTip().lower())

        win.close()


if __name__ == "__main__":
    unittest.main()
