import os
import json
import tempfile
import unittest
from unittest.mock import MagicMock

from core.config_manager import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self.temp_dir.name, "test_config.json")
        self.manager = ConfigManager(self.config_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config_when_file_not_found(self):
        cfg = self.manager.load()
        self.assertEqual(cfg, DEFAULT_CONFIG)
        self.assertEqual(self.manager.get("printer"), "DWG To PDF.pc3")
        self.assertTrue(self.manager.get("sync_autocad"))

    def test_save_and_load_config(self):
        custom = {
            "printer": "AutoCAD PDF (General Documentation).pc3",
            "plot_style": "acad.ctb",
            "fallback_paper": "ISO_A3",
            "merge_mode": "В отдельные файлы",
            "open_after_print": False,
            "sync_autocad": False,
            "source_mode": "Листы (Layouts)",
        }
        success = self.manager.save(custom)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.config_file))

        # Создаем новый экземпляр и считываем из файла
        new_manager = ConfigManager(self.config_file)
        loaded = new_manager.load()
        self.assertEqual(loaded["printer"], "AutoCAD PDF (General Documentation).pc3")
        self.assertEqual(loaded["plot_style"], "acad.ctb")
        self.assertEqual(loaded["fallback_paper"], "ISO_A3")
        self.assertEqual(loaded["merge_mode"], "В отдельные файлы")
        self.assertFalse(loaded["open_after_print"])
        self.assertFalse(loaded["sync_autocad"])
        self.assertEqual(loaded["source_mode"], "Листы (Layouts)")

    def test_partial_config_fallback(self):
        # Если в файле записана только часть настроек
        partial = {"printer": "Custom.pc3"}
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(partial, f)

        loaded = self.manager.load()
        self.assertEqual(loaded["printer"], "Custom.pc3")
        # Остальные поля должны взяться из дефолтных
        self.assertEqual(loaded["plot_style"], DEFAULT_CONFIG["plot_style"])
        self.assertEqual(loaded["sync_autocad"], DEFAULT_CONFIG["sync_autocad"])
        self.assertEqual(loaded["source_mode"], DEFAULT_CONFIG["source_mode"])

    def test_corrupted_json_handling(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            f.write("{invalid json content!!!")

        loaded = self.manager.load()
        self.assertEqual(loaded, DEFAULT_CONFIG)


class TestUIConfigIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PySide6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_file = os.path.join(self.temp_dir.name, "ui_config.json")
        self.manager = ConfigManager(self.config_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_ui_loads_and_saves_settings(self):
        from ui.main_window import PrintManagerUI

        # 1. Задаем начальные кастомные настройки в конфиге
        self.manager.save({
            "printer": "MyPrinter.pc3",
            "plot_style": "grayscale.ctb",
            "fallback_paper": "A3_Custom",
            "merge_mode": "В отдельные файлы",
            "open_after_print": False,
            "sync_autocad": False,
            "source_mode": "Листы (Layouts)",
        })

        win = PrintManagerUI(config_manager=self.manager)

        # Проверяем, что элементы UI приняли значения из config
        self.assertFalse(win.chk_sync_acad.isChecked())
        self.assertFalse(win.chk_open_after.isChecked())
        self.assertEqual(win.combo_mode.currentText(), "В отдельные файлы")
        self.assertEqual(win.combo_source.currentText(), "Листы (Layouts)")
        self.assertEqual(win.btn_scan.text(), "Загрузить листы")

        # 2. Мокаем BatchPrinter для эмуляции принтера AutoCAD
        mock_printer = MagicMock()
        mock_printer.get_printers.return_value = ["DWG To PDF.pc3", "MyPrinter.pc3", "Other.pc3"]
        mock_printer.get_plot_styles.return_value = ["monochrome.ctb", "grayscale.ctb", "acad.ctb"]
        mock_printer.get_media_names.return_value = {"A4_Custom": "sys_a4", "A3_Custom": "sys_a3"}
        win.printer = mock_printer

        # Загружаем настройки принтера в UI
        win.load_printer_settings()

        # Должен быть выбран именно MyPrinter.pc3, grayscale.ctb и A3_Custom из конфига
        self.assertEqual(win.combo_printers.currentText(), "MyPrinter.pc3")
        self.assertEqual(win.combo_style.currentText(), "grayscale.ctb")
        self.assertEqual(win.combo_papers.currentText(), "A3_Custom")

        # 3. Меняем чекбоксы и комбобоксы в интерфейсе
        win.chk_sync_acad.setChecked(True)
        win.chk_open_after.setChecked(True)
        win.combo_mode.setCurrentIndex(1)  # "В один файл (PDF)"
        win.combo_source.setCurrentIndex(0) # "Модель (Model Space)"
        win.combo_printers.setCurrentText("DWG To PDF.pc3")
        win.combo_style.setCurrentText("monochrome.ctb")

        # Проверяем, что config_manager сохранился на диск
        saved_cfg = self.manager.load()
        self.assertTrue(saved_cfg["sync_autocad"])
        self.assertTrue(saved_cfg["open_after_print"])
        self.assertEqual(saved_cfg["merge_mode"], "В один файл (PDF)")
        self.assertEqual(saved_cfg["source_mode"], "Модель (Model Space)")
        self.assertEqual(saved_cfg["printer"], "DWG To PDF.pc3")
        self.assertEqual(saved_cfg["plot_style"], "monochrome.ctb")


if __name__ == "__main__":
    unittest.main()
