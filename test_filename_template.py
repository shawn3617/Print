"""
Юнит-тесты для движка шаблонов имён файлов (core/filename_template.py).
"""

import unittest
from typing import List, Tuple
from dataclasses import dataclass, field

from core.filename_template import (
    sanitize_filename,
    render_filename,
    resolve_duplicates,
    get_default_template,
    preview_filename,
    PRESET_TEMPLATES,
    TEMPLATE_VARIABLES,
)
from core.models import Frame


def _make_frame(**overrides) -> Frame:
    """Создаёт тестовый Frame с заполненными полями по умолчанию."""
    defaults = dict(
        object_id=1,
        sheet_number="5",
        sheet_name="План на отм. 0.000",
        min_point=(0.0, 0.0, 0.0),
        max_point=(100.0, 100.0, 0.0),
        source_type="block",
        paper_format="A3",
        handle="ABC",
        dwg_path=r"C:\Projects\ПР-01-АР.dwg",
        dwg_name="ПР-01-АР",
        doc_code="ПР-01-АР",
        object_name="Жилой дом",
        building_name="Корпус 1",
        layout_name="Model",
        fallback_warning="",
        scale=100,
        format_reason="",
        possible_formats=[],
        is_ambiguous=False,
        user_override=False,
    )
    defaults.update(overrides)
    return Frame(**defaults)


class TestSanitizeFilename(unittest.TestCase):
    """Тесты очистки имени файла от недопустимых символов."""

    def test_removes_illegal_characters(self):
        """Удаляет \\ / : * ? \" < > | из имени файла."""
        result = sanitize_filename('file\\name/with:illegal*chars?"<>|end')
        for ch in r'\/:*?"<>|':
            self.assertNotIn(ch, result)

    def test_preserves_valid_characters(self):
        """Сохраняет кириллицу, латиницу, цифры, пробелы, дефисы, подчёркивания, точки, скобки."""
        valid = "Файл file-01_v2.3 (копия)"
        result = sanitize_filename(valid)
        self.assertEqual(result, valid)

    def test_collapses_multiple_spaces(self):
        """Схлопывает множественные пробелы в один."""
        result = sanitize_filename("Лист   5  -  План")
        self.assertNotIn("  ", result)

    def test_collapses_multiple_underscores(self):
        """Схлопывает множественные подчёркивания в одно."""
        result = sanitize_filename("name___value")
        self.assertNotIn("__", result)

    def test_strips_leading_trailing_dots_and_spaces(self):
        """Убирает точки и пробелы по краям имени."""
        result = sanitize_filename("  ..name.. ")
        self.assertFalse(result.startswith("."))
        self.assertFalse(result.startswith(" "))
        self.assertFalse(result.endswith("."))
        self.assertFalse(result.endswith(" "))

    def test_truncates_to_max_len(self):
        """Обрезает имя до указанной максимальной длины."""
        long_name = "А" * 300
        result = sanitize_filename(long_name, max_len=50)
        self.assertLessEqual(len(result), 50)

    def test_truncates_to_default_max_len(self):
        """Обрезает имя до 200 символов по умолчанию."""
        long_name = "Б" * 250
        result = sanitize_filename(long_name)
        self.assertLessEqual(len(result), 200)

    def test_empty_string(self):
        """Пустая строка → пустой результат."""
        result = sanitize_filename("")
        self.assertEqual(result, "")

    def test_all_illegal_chars(self):
        """Строка только из недопустимых символов → пустая строка."""
        result = sanitize_filename(r'\/:*?"<>|')
        self.assertEqual(result.strip(), "")


class TestRenderFilename(unittest.TestCase):
    """Тесты рендера имени файла по шаблону."""

    def test_default_template_with_real_frame(self):
        """Шаблон по умолчанию с реальными данными Frame даёт ожидаемый результат."""
        frame = _make_frame()
        template = get_default_template()
        result = render_filename(template, frame, dwg_name="ПР-01-АР")
        self.assertTrue(result.endswith(".pdf"))
        self.assertTrue(len(result) > len(".pdf"))

    def test_all_variables_substitute(self):
        """Все переменные шаблона подставляются корректно."""
        frame = _make_frame()
        template = "{Шифр}_{Номер}_{Наименование}_{Формат}_{DWG}_{Объект}_{Здание}_{Масштаб}"
        result = render_filename(template, frame, dwg_name="ПР-01-АР")
        base = result.replace(".pdf", "")
        self.assertIn("ПР-01-АР", base)
        self.assertIn("5", base)
        self.assertIn("План на отм. 0.000", base)
        self.assertIn("A3", base)
        self.assertIn("Жилой дом", base)
        self.assertIn("Корпус 1", base)
        self.assertIn("100", base)

    def test_zero_padded_numeric(self):
        """Форматирование {Номер:02d} с числовым значением → 01, 05 и т.д."""
        frame = _make_frame(sheet_number="1")
        template = "{Номер:02d}"
        result = render_filename(template, frame)
        base = result.replace(".pdf", "")
        self.assertIn("01", base)

    def test_zero_padded_three_digits(self):
        """Форматирование {Номер:03d} с числовым значением → 005."""
        frame = _make_frame(sheet_number="5")
        template = "{Номер:03d}"
        result = render_filename(template, frame)
        base = result.replace(".pdf", "")
        self.assertIn("005", base)

    def test_zero_padded_non_numeric(self):
        """Форматирование {Номер:03d} с нечисловым значением '4а' → оставляет как есть."""
        frame = _make_frame(sheet_number="4а")
        template = "{Номер:03d}"
        result = render_filename(template, frame)
        base = result.replace(".pdf", "")
        self.assertIn("4а", base)

    def test_empty_fields_use_fallback(self):
        """Пустые поля Frame → используются значения-заглушки."""
        frame = _make_frame(
            sheet_number="",
            sheet_name="",
            doc_code="",
            object_name="",
            building_name="",
        )
        template = "{Шифр}_{Номер}_{Наименование}"
        result = render_filename(template, frame)
        self.assertTrue(result.endswith(".pdf"))
        self.assertTrue(len(result) > len(".pdf"))

    def test_dwg_extension_stripped(self):
        """Расширение .dwg удаляется из имени DWG-файла."""
        frame = _make_frame()
        template = "{DWG}"
        result = render_filename(template, frame, dwg_name="Проект.dwg")
        base = result.replace(".pdf", "")
        self.assertNotIn(".dwg", base.lower())

    def test_result_ends_with_pdf(self):
        """Результат всегда заканчивается на .pdf."""
        frame = _make_frame()
        template = "{Шифр}_{Номер}"
        result = render_filename(template, frame)
        self.assertTrue(result.endswith(".pdf"))

    def test_result_is_sanitized(self):
        """Результат проходит через sanitize_filename — без недопустимых символов."""
        frame = _make_frame(sheet_name='Лист "главный" / план')
        template = "{Наименование}"
        result = render_filename(template, frame)
        for ch in r'\/:*?"<>|':
            self.assertNotIn(ch, result)

    def test_index_parameter_accepted(self):
        """Параметр index передаётся без ошибок."""
        frame = _make_frame()
        template = "{Шифр}_{Номер}"
        result = render_filename(template, frame, index=3)
        self.assertTrue(result.endswith(".pdf"))


class TestResolveDuplicates(unittest.TestCase):
    """Тесты разрешения дубликатов имён файлов."""

    def test_no_duplicates_unchanged(self):
        """Список без дубликатов → без изменений."""
        filenames = ["file_a.pdf", "file_b.pdf", "file_c.pdf"]
        result = resolve_duplicates(filenames)
        self.assertEqual(result, filenames)

    def test_all_same_get_suffixes(self):
        """Все одинаковые имена получают суффиксы _1, _2, _3."""
        filenames = ["plan.pdf", "plan.pdf", "plan.pdf"]
        result = resolve_duplicates(filenames)
        self.assertEqual(len(result), 3)
        self.assertEqual(len(set(result)), 3)
        for name in result:
            self.assertTrue(name.endswith(".pdf"))

    def test_mixed_duplicates_and_unique(self):
        """Смешанный список дубликатов и уникальных имён."""
        filenames = ["plan.pdf", "facade.pdf", "plan.pdf", "section.pdf", "facade.pdf"]
        result = resolve_duplicates(filenames)
        self.assertEqual(len(result), 5)
        self.assertEqual(len(set(result)), 5)

    def test_single_file_unchanged(self):
        """Один файл → без изменений."""
        filenames = ["single.pdf"]
        result = resolve_duplicates(filenames)
        self.assertEqual(result, ["single.pdf"])

    def test_empty_list(self):
        """Пустой список → пустой результат."""
        result = resolve_duplicates([])
        self.assertEqual(result, [])


class TestPresetTemplates(unittest.TestCase):
    """Тесты предустановленных шаблонов."""

    def test_all_presets_render_without_errors(self):
        """Все предустановленные шаблоны рендерятся без ошибок с реальным Frame."""
        frame = _make_frame()
        for label, template in PRESET_TEMPLATES:
            with self.subTest(label=label):
                result = render_filename(template, frame, dwg_name="ПР-01-АР")
                self.assertIsInstance(result, str)

    def test_all_presets_produce_non_empty(self):
        """Все предустановленные шаблоны дают непустые имена файлов."""
        frame = _make_frame()
        for label, template in PRESET_TEMPLATES:
            with self.subTest(label=label):
                result = render_filename(template, frame, dwg_name="ПР-01-АР")
                base = result.replace(".pdf", "")
                self.assertTrue(len(base) > 0, f"Пресет '{label}' дал пустое имя")

    def test_get_default_template_returns_first_preset(self):
        """get_default_template возвращает шаблон первого пресета."""
        default = get_default_template()
        _, first_template = PRESET_TEMPLATES[0]
        self.assertEqual(default, first_template)


class TestPreviewFilename(unittest.TestCase):
    """Тесты предпросмотра имени файла."""

    def test_preview_with_real_frame(self):
        """Предпросмотр с реальным Frame → рендерит с данными фрейма."""
        frame = _make_frame()
        template = "{Шифр}_{Номер}_{Наименование}"
        result = preview_filename(template, frame)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)
        self.assertIn("ПР-01-АР", result)
        self.assertIn("5", result)

    def test_preview_without_frame(self):
        """Предпросмотр без Frame (None) → рендерит с примерными данными-заглушками."""
        template = "{Шифр}_{Номер}_{Наименование}"
        result = preview_filename(template, None)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)

    def test_preview_result_is_valid_filename(self):
        """Результат предпросмотра — валидное имя файла (без недопустимых символов)."""
        frame = _make_frame()
        template = "{Шифр}_{Номер}_{Наименование}"
        result = preview_filename(template, frame)
        for ch in r'\/:*?"<>|':
            self.assertNotIn(ch, result)

    def test_preview_without_frame_default_template(self):
        """Предпросмотр шаблона по умолчанию без Frame."""
        template = get_default_template()
        result = preview_filename(template, None)
        self.assertIsInstance(result, str)
        self.assertTrue(len(result) > 0)


class TestFilenameTemplateUI(unittest.TestCase):
    """Интеграционные тесты шаблонов имён файлов в интерфейсе (MainWindow)."""

    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication([])

    def setUp(self):
        from unittest.mock import MagicMock
        from ui.main_window import PrintManagerUI
        self.mock_config = MagicMock()
        self.mock_config.load.return_value = {
            "filename_template": "Лист {Номер} - {Наименование}"
        }
        self.mock_config.get.side_effect = lambda k, d=None: (
            "Лист {Номер} - {Наименование}" if k == "filename_template" else d
        )
        self.win = PrintManagerUI(config_manager=self.mock_config)

    def test_combo_template_initialized_with_presets(self):
        """Выпадающий список шаблонов содержит все пресеты."""
        self.assertTrue(hasattr(self.win, "combo_template"))
        items = [self.win.combo_template.itemText(i) for i in range(self.win.combo_template.count())]
        for _, tpl in PRESET_TEMPLATES:
            self.assertIn(tpl, items)

    def test_preview_label_updates_on_template_change(self):
        """Изменение шаблона обновляет текст предпросмотра."""
        self.win.combo_template.setEditText("{Шифр}_{Номер}")
        preview_text = self.win.lbl_template_preview.text()
        self.assertIn("Пример:", preview_text)
        self.assertIn(".pdf", preview_text)

    def test_preview_label_updates_with_loaded_frame(self):
        """Предпросмотр отображает реальные данные первого фрейма."""
        frame = _make_frame(sheet_number="42", doc_code="ПР-42")
        self.win.frames = [frame]
        self.win.combo_template.setEditText("{Шифр}_Л{Номер}")
        self.win.update_template_preview()
        preview_text = self.win.lbl_template_preview.text()
        self.assertIn("ПР-42_Л42.pdf", preview_text)

    def test_save_settings_includes_filename_template(self):
        """save_settings сохраняет выбранный шаблон в конфигурацию."""
        self.win.combo_template.setEditText("{DWG}_{Номер}")
        self.win.save_settings()
        self.mock_config.save.assert_called()
        saved_dict = self.mock_config.save.call_args[0][0]
        self.assertEqual(saved_dict.get("filename_template"), "{DWG}_{Номер}")


if __name__ == "__main__":
    unittest.main()
