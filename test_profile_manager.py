"""
Юнит-тесты для менеджера профилей проектов (core/profile_manager.py).
"""

import json
import os
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

from core.config_manager import ConfigManager
from core.profile_manager import (
    BUILTIN_PROFILES,
    DEFAULT_PROFILE_NAME,
    PROFILE_KEYS,
    ProfileManager,
)


class TestProfileManagerBuiltins(unittest.TestCase):
    """
    1. Тестирование встроенных (базовых) профилей:
       - get_profile_names() содержит 'По умолчанию' и другие встроенные пресеты.
       - is_builtin('По умолчанию') -> True, is_builtin('Custom') -> False.
       - get_profile('По умолчанию') возвращает все PROFILE_KEYS.
       - Нельзя удалить 'По умолчанию' (возвращает (False, ...)).
       - Нельзя переименовать 'По умолчанию' (возвращает (False, ...)).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_path)
        self.manager = ProfileManager(self.config_manager)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_profile_names_contains_default_and_builtins(self):
        """get_profile_names() содержит 'По умолчанию' и другие встроенные пресеты."""
        names = self.manager.get_profile_names()
        self.assertIn(DEFAULT_PROFILE_NAME, names)
        for builtin_name in BUILTIN_PROFILES.keys():
            self.assertIn(builtin_name, names)

        # Встроенные профили должны располагаться первыми в списке
        builtin_keys = list(BUILTIN_PROFILES.keys())
        self.assertEqual(names[:len(builtin_keys)], builtin_keys)

    def test_is_builtin(self):
        """is_builtin('По умолчанию') -> True, is_builtin('Custom') -> False."""
        self.assertTrue(self.manager.is_builtin(DEFAULT_PROFILE_NAME))
        self.assertTrue(self.manager.is_builtin("СПДС — В один том"))
        self.assertTrue(self.manager.is_builtin("Отдельные листы (Шифр_Номер_Имя)"))
        self.assertTrue(self.manager.is_builtin("Пространство Листов (Layouts)"))
        self.assertFalse(self.manager.is_builtin("Custom"))
        self.assertFalse(self.manager.is_builtin("Мой Проект"))
        self.assertFalse(self.manager.is_builtin(""))

    def test_get_profile_default_has_all_profile_keys(self):
        """get_profile('По умолчанию') возвращает все PROFILE_KEYS."""
        profile = self.manager.get_profile(DEFAULT_PROFILE_NAME)
        self.assertIsNotNone(profile)
        self.assertIsInstance(profile, dict)

        for key in PROFILE_KEYS:
            self.assertIn(key, profile, f"Ключ {key} отсутствует в профиле {DEFAULT_PROFILE_NAME}")

        # Проверка ключевых настроек по умолчанию
        self.assertEqual(profile["printer"], "DWG To PDF.pc3")
        self.assertEqual(profile["plot_style"], "monochrome.ctb")
        self.assertEqual(profile["merge_mode"], "В один файл (PDF)")
        self.assertTrue(profile["open_after_print"])
        self.assertTrue(profile["sync_autocad"])
        self.assertEqual(profile["source_mode"], "Модель (Model Space)")
        self.assertEqual(profile["frame_type"], "spds")

    def test_get_profile_all_builtins_have_all_keys(self):
        """Все встроенные профили содержат полный набор ключей PROFILE_KEYS."""
        for name in BUILTIN_PROFILES.keys():
            prof = self.manager.get_profile(name)
            self.assertIsNotNone(prof, f"Профиль {name} не найден")
            for key in PROFILE_KEYS:
                self.assertIn(key, prof, f"Ключ {key} отсутствует во встроенном профиле {name}")

    def test_cannot_delete_default_profile(self):
        """Нельзя удалить 'По умолчанию' (возвращает (False, ...))."""
        success, msg = self.manager.delete_profile(DEFAULT_PROFILE_NAME)
        self.assertFalse(success)
        self.assertTrue(len(msg) > 0)
        self.assertIn("Нельзя удалить", msg)
        self.assertIn(DEFAULT_PROFILE_NAME, self.manager.get_profile_names())

    def test_cannot_rename_default_profile(self):
        """Нельзя переименовать 'По умолчанию' (возвращает (False, ...))."""
        success, msg = self.manager.rename_profile(DEFAULT_PROFILE_NAME, "Новое Имя")
        self.assertFalse(success)
        self.assertTrue(len(msg) > 0)
        self.assertIn("Нельзя переименовать", msg)
        self.assertIn(DEFAULT_PROFILE_NAME, self.manager.get_profile_names())

    def test_get_profile_returns_copy(self):
        """get_profile возвращает копию, модификация которой не меняет исходный профиль."""
        prof = self.manager.get_profile(DEFAULT_PROFILE_NAME)
        self.assertIsNotNone(prof)
        prof["printer"] = "Corrupted.pc3"

        fresh = self.manager.get_profile(DEFAULT_PROFILE_NAME)
        self.assertEqual(fresh["printer"], "DWG To PDF.pc3")

    def test_get_profile_non_existent_returns_none(self):
        """get_profile для несуществующего имени возвращает None."""
        self.assertIsNone(self.manager.get_profile("Несуществующий"))
        self.assertIsNone(self.manager.get_profile(""))
        self.assertIsNone(self.manager.get_profile(None))  # type: ignore


class TestProfileManagerCRUD(unittest.TestCase):
    """
    2. Тестирование операций создания, чтения, обновления, переименования и удаления:
       - create_profile('Мой Проект', settings) завершается успехом.
       - get_profile_names() теперь содержит 'Мой Проект'.
       - create_profile с дублирующимся именем завершается понятной ошибкой.
       - create_profile с пустым именем завершается ошибкой.
       - save_profile обновляет настройки существующего профиля.
       - rename_profile('Мой Проект', 'Новое Имя') обновляет имя.
       - delete_profile('Новое Имя') удаляет профиль из списка.
       - Удаление активного профиля сбрасывает активный профиль на 'По умолчанию'.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_path)
        self.manager = ProfileManager(self.config_manager)

        self.sample_settings = {
            "printer": "AutoCAD PDF (High Quality Print).pc3",
            "plot_style": "acad.ctb",
            "fallback_paper": "A3",
            "fallback_paper_canonical": "ISO_A3",
            "merge_mode": "В отдельные файлы",
            "filename_template": "{Шифр}_{Номер}",
            "open_after_print": False,
            "sync_autocad": True,
            "source_mode": "Модель (Model Space)",
            "frame_type": "spds",
            "custom_block_name": "",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_profile_success_and_appears_in_names(self):
        """create_profile('Мой Проект', settings) успешен, и get_profile_names() теперь содержит 'Мой Проект'."""
        success, msg = self.manager.create_profile("Мой Проект", self.sample_settings)
        self.assertTrue(success)
        self.assertEqual(msg, "")
        self.assertIn("Мой Проект", self.manager.get_profile_names())

        # Проверяем заполненные значения
        loaded = self.manager.get_profile("Мой Проект")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["printer"], "AutoCAD PDF (High Quality Print).pc3")
        self.assertEqual(loaded["plot_style"], "acad.ctb")
        self.assertEqual(loaded["merge_mode"], "В отдельные файлы")
        self.assertEqual(loaded["filename_template"], "{Шифр}_{Номер}")
        self.assertFalse(loaded["open_after_print"])

    def test_create_profile_duplicate_name_fails(self):
        """create_profile с дублирующимся именем возвращает понятную ошибку."""
        success1, _ = self.manager.create_profile("Мой Проект", self.sample_settings)
        self.assertTrue(success1)

        success2, msg = self.manager.create_profile("Мой Проект", self.sample_settings)
        self.assertFalse(success2)
        self.assertIn("уже существует", msg)

        # Проверка создания с именем встроенного профиля
        success3, msg3 = self.manager.create_profile(DEFAULT_PROFILE_NAME, self.sample_settings)
        self.assertFalse(success3)
        self.assertIn("уже существует", msg3)

    def test_create_profile_empty_name_fails(self):
        """create_profile с пустым именем или состоящим только из пробелов завершается ошибкой."""
        success_empty, msg_empty = self.manager.create_profile("", self.sample_settings)
        self.assertFalse(success_empty)
        self.assertTrue(len(msg_empty) > 0)

        success_spaces, msg_spaces = self.manager.create_profile("   ", self.sample_settings)
        self.assertFalse(success_spaces)
        self.assertTrue(len(msg_spaces) > 0)

    def test_save_profile_updates_existing_profile(self):
        """save_profile обновляет настройки существующего профиля."""
        self.manager.create_profile("Мой Проект", self.sample_settings)

        updated = {
            "printer": "AutoCAD PDF (General Documentation).pc3",
            "plot_style": "grayscale.ctb",
            "open_after_print": True,
        }
        res = self.manager.save_profile("Мой Проект", updated)
        self.assertTrue(res)

        loaded = self.manager.get_profile("Мой Проект")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["printer"], "AutoCAD PDF (General Documentation).pc3")
        self.assertEqual(loaded["plot_style"], "grayscale.ctb")
        self.assertTrue(loaded["open_after_print"])
        # Прежние ключи сохранились
        self.assertEqual(loaded["merge_mode"], "В отдельные файлы")

    def test_save_profile_cannot_overwrite_default_with_empty(self):
        """Нельзя сохранить 'По умолчанию' с пустым словарем настроек."""
        res = self.manager.save_profile(DEFAULT_PROFILE_NAME, {})
        self.assertFalse(res)

    def test_rename_profile_success(self):
        """rename_profile('Мой Проект', 'Новое Имя') переименовывает профиль."""
        self.manager.create_profile("Мой Проект", self.sample_settings)
        self.assertIn("Мой Проект", self.manager.get_profile_names())

        success, msg = self.manager.rename_profile("Мой Проект", "Новое Имя")
        self.assertTrue(success)
        self.assertEqual(msg, "")

        self.assertNotIn("Мой Проект", self.manager.get_profile_names())
        self.assertIn("Новое Имя", self.manager.get_profile_names())

        loaded = self.manager.get_profile("Новое Имя")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["printer"], self.sample_settings["printer"])

    def test_rename_profile_validation(self):
        """Проверка валидации при переименовании."""
        self.manager.create_profile("Проект 1", self.sample_settings)
        self.manager.create_profile("Проект 2", self.sample_settings)

        # Переименование в уже существующее имя
        ok, err = self.manager.rename_profile("Проект 1", "Проект 2")
        self.assertFalse(ok)
        self.assertIn("уже существует", err)

        # Переименование в пустое имя
        ok, err = self.manager.rename_profile("Проект 1", "   ")
        self.assertFalse(ok)
        self.assertTrue(len(err) > 0)

        # Переименование несуществующего профиля
        ok, err = self.manager.rename_profile("Несуществующий", "Другое")
        self.assertFalse(ok)
        self.assertIn("не найден", err)

        # Переименование в то же самое имя
        ok, err = self.manager.rename_profile("Проект 1", "Проект 1")
        self.assertTrue(ok)

    def test_delete_profile_success(self):
        """delete_profile('Новое Имя') удаляет профиль из списка."""
        self.manager.create_profile("Новое Имя", self.sample_settings)
        self.assertIn("Новое Имя", self.manager.get_profile_names())

        success, msg = self.manager.delete_profile("Новое Имя")
        self.assertTrue(success)
        self.assertEqual(msg, "")
        self.assertNotIn("Новое Имя", self.manager.get_profile_names())
        self.assertIsNone(self.manager.get_profile("Новое Имя"))

    def test_delete_non_existent_profile_fails(self):
        """Попытка удалить несуществующий профиль возвращает ошибку."""
        success, msg = self.manager.delete_profile("Несуществующий")
        self.assertFalse(success)
        self.assertIn("не найден", msg)

    def test_delete_active_profile_resets_to_default(self):
        """Удаление активного профиля сбрасывает активный профиль на 'По умолчанию'."""
        self.manager.create_profile("Временный Активный", self.sample_settings)
        self.manager.set_active_profile_name("Временный Активный")
        self.assertEqual(self.manager.get_active_profile_name(), "Временный Активный")

        success, msg = self.manager.delete_profile("Временный Активный")
        self.assertTrue(success)
        self.assertEqual(self.manager.get_active_profile_name(), DEFAULT_PROFILE_NAME)

    def test_rename_active_profile_updates_active_name(self):
        """Переименование активного профиля обновляет имя активного профиля."""
        self.manager.create_profile("Старое Имя", self.sample_settings)
        self.manager.set_active_profile_name("Старое Имя")
        self.assertEqual(self.manager.get_active_profile_name(), "Старое Имя")

        success, msg = self.manager.rename_profile("Старое Имя", "Новое Имя")
        self.assertTrue(success)
        self.assertEqual(self.manager.get_active_profile_name(), "Новое Имя")

    def test_user_profiles_alphabetical_order(self):
        """Пользовательские профили отображаются в алфавитном порядке после встроенных."""
        self.manager.create_profile("Яблоко", self.sample_settings)
        self.manager.create_profile("Абрикос", self.sample_settings)
        self.manager.create_profile("Вишня", self.sample_settings)

        names = self.manager.get_profile_names()
        builtin_count = len(BUILTIN_PROFILES)
        self.assertEqual(names[builtin_count:], ["Абрикос", "Вишня", "Яблоко"])


class TestProfileManagerActiveProfile(unittest.TestCase):
    """
    3. Тестирование активного профиля:
       - get_active_profile_name() возвращает 'По умолчанию' изначально.
       - set_active_profile_name('СПДС — В один том') переключает активный профиль.
       - set_active_profile_name с несуществующим профилем возвращает False.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_path)
        self.manager = ProfileManager(self.config_manager)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_active_profile_name_default_initially(self):
        """get_active_profile_name() возвращает дефолтный профиль 'По умолчанию' изначально."""
        self.assertEqual(self.manager.get_active_profile_name(), DEFAULT_PROFILE_NAME)

    def test_set_active_profile_name_switches_active_profile(self):
        """set_active_profile_name('СПДС — В один том') успешно переключает активный профиль."""
        target_name = "СПДС — В один том"
        success = self.manager.set_active_profile_name(target_name)
        self.assertTrue(success)
        self.assertEqual(self.manager.get_active_profile_name(), target_name)

        # Проверяем персистентность при повторном чтении из конфигурации
        reloaded = ProfileManager(ConfigManager(self.config_path))
        self.assertEqual(reloaded.get_active_profile_name(), target_name)

    def test_set_active_profile_name_non_existent_returns_false(self):
        """set_active_profile_name с несуществующим профилем возвращает False и оставляет прежний активный профиль."""
        initial = self.manager.get_active_profile_name()
        success = self.manager.set_active_profile_name("Несуществующий Пресет")
        self.assertFalse(success)
        self.assertEqual(self.manager.get_active_profile_name(), initial)

        # Некорректные типы и пустые строки
        self.assertFalse(self.manager.set_active_profile_name(""))
        self.assertFalse(self.manager.set_active_profile_name(None))  # type: ignore

    def test_apply_profile_to_config(self):
        """apply_profile_to_config применяет настройки профиля в ConfigManager и устанавливает active_profile."""
        success = self.manager.apply_profile_to_config("Отдельные листы (Шифр_Номер_Имя)")
        self.assertTrue(success)
        self.assertEqual(self.manager.get_active_profile_name(), "Отдельные листы (Шифр_Номер_Имя)")

        cfg = self.config_manager.load()
        self.assertEqual(cfg.get("active_profile"), "Отдельные листы (Шифр_Номер_Имя)")
        self.assertEqual(cfg.get("merge_mode"), "В отдельные файлы")
        self.assertEqual(cfg.get("filename_template"), "{Шифр}_{Номер}_{Наименование}")

    def test_apply_non_existent_profile_returns_false(self):
        """Попытка применить несуществующий профиль возвращает False."""
        self.assertFalse(self.manager.apply_profile_to_config("Призрачный профиль"))


class TestProfileManagerExportImport(unittest.TestCase):
    """
    4. Тестирование экспорта и импорта профилей:
       - export_profile записывает валидный JSON-файл.
       - import_profile из экспортированного файла восстанавливает настройки.
       - Импорт при уже существующем имени генерирует уникальное имя (например, '... (импорт)' или '... (копия)').
       - Импорт поврежденного/невалидного файла возвращает (False, error, None).
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_path)
        self.manager = ProfileManager(self.config_manager)

        self.custom_settings = {
            "printer": "AutoCAD PDF (High Quality Print).pc3",
            "plot_style": "acad.ctb",
            "fallback_paper": "A4",
            "fallback_paper_canonical": "ISO_A4",
            "merge_mode": "В отдельные файлы",
            "filename_template": "{DWG}_{Номер}_{Наименование}",
            "open_after_print": False,
            "sync_autocad": False,
            "source_mode": "Листы (Layouts)",
            "frame_type": "all_blocks",
            "custom_block_name": "Штамп_Формат",
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_export_profile_writes_valid_json(self):
        """export_profile записывает валидный JSON-файл с корректными полями."""
        export_file = os.path.join(self.temp_dir.name, "default_export.json")
        success, msg = self.manager.export_profile(DEFAULT_PROFILE_NAME, export_file)
        self.assertTrue(success)
        self.assertEqual(msg, "")
        self.assertTrue(os.path.exists(export_file))

        with open(export_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("profile_name", data)
        self.assertEqual(data["profile_name"], DEFAULT_PROFILE_NAME)
        self.assertIn("settings", data)
        for key in PROFILE_KEYS:
            self.assertIn(key, data["settings"])

    def test_export_non_existent_profile_fails(self):
        """Экспорт несуществующего профиля возвращает ошибку и не создает файл."""
        export_file = os.path.join(self.temp_dir.name, "missing.json")
        success, msg = self.manager.export_profile("Несуществующий", export_file)
        self.assertFalse(success)
        self.assertIn("не найден", msg)
        self.assertFalse(os.path.exists(export_file))

    def test_import_profile_restores_settings(self):
        """import_profile из экспортированного файла корректно восстанавливает настройки."""
        self.manager.create_profile("Проект Экспорт", self.custom_settings)
        export_file = os.path.join(self.temp_dir.name, "project_export.json")
        self.manager.export_profile("Проект Экспорт", export_file)

        # Импортируем во второй менеджер с чистой конфигурацией
        second_config_path = os.path.join(self.temp_dir.name, "second_config.json")
        second_manager = ProfileManager(ConfigManager(second_config_path))

        self.assertNotIn("Проект Экспорт", second_manager.get_profile_names())
        imp_success, imp_msg, imp_name = second_manager.import_profile(export_file)

        self.assertTrue(imp_success)
        self.assertEqual(imp_msg, "")
        self.assertEqual(imp_name, "Проект Экспорт")
        self.assertIn("Проект Экспорт", second_manager.get_profile_names())

        restored = second_manager.get_profile("Проект Экспорт")
        self.assertIsNotNone(restored)
        self.assertEqual(restored["printer"], "AutoCAD PDF (High Quality Print).pc3")
        self.assertEqual(restored["custom_block_name"], "Штамп_Формат")
        self.assertEqual(restored["source_mode"], "Листы (Layouts)")
        self.assertFalse(restored["open_after_print"])

    def test_import_profile_duplicate_generates_unique_name(self):
        """При импорте, если профиль с таким именем уже существует, генерируется уникальное имя."""
        export_file = os.path.join(self.temp_dir.name, "spds_export.json")
        self.manager.export_profile("СПДС — В один том", export_file)

        # Импортируем в тот же менеджер, где 'СПДС — В один том' уже присутствует
        success1, msg1, new_name1 = self.manager.import_profile(export_file)
        self.assertTrue(success1)
        self.assertEqual(msg1, "")
        self.assertIsNotNone(new_name1)
        self.assertNotEqual(new_name1, "СПДС — В один том")
        self.assertIn("СПДС — В один том", new_name1)
        self.assertIn(new_name1, self.manager.get_profile_names())

        # Повторный импорт должен сгенерировать другое уникальное имя
        success2, msg2, new_name2 = self.manager.import_profile(export_file)
        self.assertTrue(success2)
        self.assertNotEqual(new_name2, new_name1)
        self.assertIn(new_name2, self.manager.get_profile_names())

    def test_import_profile_corrupted_file_returns_error(self):
        """Импорт поврежденного/невалидного JSON возвращает (False, error, None)."""
        corrupted_file = os.path.join(self.temp_dir.name, "corrupted.json")
        with open(corrupted_file, "w", encoding="utf-8") as f:
            f.write("{invalid_json_data:")

        success, msg, name = self.manager.import_profile(corrupted_file)
        self.assertFalse(success)
        self.assertTrue(len(msg) > 0)
        self.assertIsNone(name)

    def test_import_profile_missing_file_returns_error(self):
        """Импорт из несуществующего пути возвращает (False, error, None)."""
        missing_file = os.path.join(self.temp_dir.name, "missing.json")
        success, msg, name = self.manager.import_profile(missing_file)
        self.assertFalse(success)
        self.assertIn("не найден", msg)
        self.assertIsNone(name)

    def test_import_profile_non_dict_or_no_settings_returns_error(self):
        """Импорт файла с не-словарем или без допустимых настроек возвращает ошибку."""
        list_file = os.path.join(self.temp_dir.name, "array.json")
        with open(list_file, "w", encoding="utf-8") as f:
            f.write("[1, 2, 3]")

        ok1, msg1, name1 = self.manager.import_profile(list_file)
        self.assertFalse(ok1)
        self.assertIsNone(name1)

        empty_keys_file = os.path.join(self.temp_dir.name, "no_keys.json")
        with open(empty_keys_file, "w", encoding="utf-8") as f:
            json.dump({"settings": {"irrelevant": "data"}}, f)

        ok2, msg2, name2 = self.manager.import_profile(empty_keys_file)
        self.assertFalse(ok2)
        self.assertIn("не содержит допустимых настроек", msg2)
        self.assertIsNone(name2)


class TestExtractProfileSettings(unittest.TestCase):
    """
    5. Тестирование extract_profile_settings:
       - Отфильтровывает сторонние ключи (например, 'theme', 'unknown_key', 'table_column_widths'),
         сохраняя все PROFILE_KEYS.
    """

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")
        self.config_manager = ConfigManager(self.config_path)
        self.manager = ProfileManager(self.config_manager)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_filters_extraneous_keys_while_keeping_profile_keys(self):
        """Отфильтровывает сторонние ключи ('theme', 'unknown_key', 'table_column_widths'), сохраняя все PROFILE_KEYS."""
        full_dict = {
            "printer": "DWG To PDF.pc3",
            "plot_style": "monochrome.ctb",
            "fallback_paper": "ISO_A3",
            "fallback_paper_canonical": "ISO_A3",
            "merge_mode": "В один файл (PDF)",
            "filename_template": "Шаблон {Номер}",
            "open_after_print": True,
            "sync_autocad": True,
            "source_mode": "Модель (Model Space)",
            "frame_type": "spds",
            "custom_block_name": "Штамп",
            # Сторонние ключи, не относящиеся к профилю печати:
            "theme": "dark",
            "unknown_key": "some_value",
            "table_column_widths": [65, 60, 180, 260],
            "auto_check_updates": False,
            "hidden_columns": ["col1", "col2"],
        }

        extracted = self.manager.extract_profile_settings(full_dict)

        # Все PROFILE_KEYS из full_dict присутствуют в результате
        for k in PROFILE_KEYS:
            self.assertIn(k, extracted)
            self.assertEqual(extracted[k], full_dict[k])

        # Сторонние ключи должны быть отфильтрованы
        self.assertNotIn("theme", extracted)
        self.assertNotIn("unknown_key", extracted)
        self.assertNotIn("table_column_widths", extracted)
        self.assertNotIn("auto_check_updates", extracted)
        self.assertNotIn("hidden_columns", extracted)

    def test_extract_handles_empty_and_non_dict_input(self):
        """extract_profile_settings возвращает пустой словарь для пустых или некорректных входных данных."""
        self.assertEqual(self.manager.extract_profile_settings({}), {})
        self.assertEqual(self.manager.extract_profile_settings(None), {})  # type: ignore
        self.assertEqual(self.manager.extract_profile_settings("string"), {})  # type: ignore
        self.assertEqual(self.manager.extract_profile_settings([1, 2, 3]), {})  # type: ignore


class TestProfileManagerConfigIntegration(unittest.TestCase):
    """Дополнительные тесты интеграции с ConfigManager и персистентности."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = os.path.join(self.temp_dir.name, "test_config.json")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config_manager_creation(self):
        """При вызове ProfileManager() без параметров создается ConfigManager по умолчанию."""
        with patch("core.profile_manager.ConfigManager") as mock_cm_cls:
            mock_cm_instance = MagicMock()
            mock_cm_instance.load.return_value = {}
            mock_cm_instance.get.return_value = None
            mock_cm_cls.return_value = mock_cm_instance

            pm = ProfileManager()
            self.assertIsNotNone(pm.config_manager)
            mock_cm_cls.assert_called_once()

    def test_loads_saved_profiles_from_file_on_init(self):
        """Считывает ранее сохраненные профили из config.json при инициализации."""
        saved_data = {
            "profiles": {
                "Сохраненный Проект": {
                    "printer": "Existing.pc3",
                    "plot_style": "monochrome.ctb",
                    "merge_mode": "В отдельные файлы",
                }
            },
            "active_profile": "Сохраненный Проект",
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(saved_data, f)

        cm = ConfigManager(self.config_path)
        pm = ProfileManager(cm)

        self.assertIn("Сохраненный Проект", pm.get_profile_names())
        self.assertEqual(pm.get_active_profile_name(), "Сохраненный Проект")
        loaded = pm.get_profile("Сохраненный Проект")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["printer"], "Existing.pc3")


class TestProfileManagerUI(unittest.TestCase):
    """Интеграционные тесты управления профилями в интерфейсе (MainWindow)."""

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
            "active_profile": "По умолчанию",
            "profiles": {}
        }
        self.mock_config.get.side_effect = lambda k, d=None: (
            "По умолчанию" if k == "active_profile" else ({} if k == "profiles" else d)
        )
        self.win = PrintManagerUI(config_manager=self.mock_config)

    def test_combo_profile_initialized_with_builtins(self):
        """Выпадающий список профилей содержит все встроенные пресеты."""
        self.assertTrue(hasattr(self.win, "combo_profile"))
        items = [self.win.combo_profile.itemText(i) for i in range(self.win.combo_profile.count())]
        self.assertIn("По умолчанию", items)
        self.assertIn("СПДС — В один том", items)
        self.assertIn("Отдельные листы (Шифр_Номер_Имя)", items)
        self.assertIn("Пространство Листов (Layouts)", items)

    def test_selecting_profile_updates_ui_widgets(self):
        """Выбор профиля в комбобоксе обновляет элементы интерфейса."""
        self.win.combo_profile.setCurrentText("Отдельные листы (Шифр_Номер_Имя)")
        self.assertEqual(self.win.combo_mode.currentText(), "В отдельные файлы")
        self.assertEqual(self.win.combo_template.currentText(), "{Шифр}_{Номер}_{Наименование}")

    def test_selecting_layouts_profile_updates_source_mode(self):
        """Выбор профиля пространств листов переключает режим на Layouts."""
        self.win.combo_profile.setCurrentText("Пространство Листов (Layouts)")
        self.assertEqual(self.win.combo_source.currentText(), "Листы (Layouts)")

    def test_save_current_profile_updates_storage(self):
        """on_save_current_profile сохраняет текущие параметры в профиль."""
        with patch.object(self.win.profile_manager, "save_profile") as mock_save:
            with patch("PySide6.QtWidgets.QMessageBox.information"):
                self.win.on_save_current_profile()
                mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
