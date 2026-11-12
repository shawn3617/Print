import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from PySide6.QtCore import QRect, QUrl
from PySide6.QtWidgets import QApplication

from core.config_manager import ConfigManager
from core.models import Frame
from ui.main_window import PrintManagerUI


class TestBatchUI(unittest.TestCase):
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

    def test_restores_window_geometry_and_fits_it_to_available_screen(self):
        with TemporaryDirectory() as folder, patch.object(PrintManagerUI, "refresh_document_status"), \
                patch("ui.main_window.get_stats_manager"):
            path = os.path.join(folder, "config.json")
            window = PrintManagerUI(ConfigManager(path))
            window.show()
            available = window.screen().availableGeometry()
            window.setGeometry(QRect(available.left() + 4, available.top() + 40, 790, 600))
            self.app.processEvents()
            expected = window.geometry()
            window.close()

            restored = PrintManagerUI(ConfigManager(path))
            restored.show()
            self.app.processEvents()
            self.assertEqual(restored.geometry(), expected)
            restored.setGeometry(available.right() + 4000, available.top(),
                                 available.width() + 900, available.height() + 500)
            restored.close()

            recovered = PrintManagerUI(ConfigManager(path))
            recovered.show()
            self.app.processEvents()
            self.assertTrue(available.contains(recovered.frameGeometry()))
            recovered.close()

    def test_polyline_layer_is_saved_and_available_for_both_model_modes(self):
        self.win.combo_source.setCurrentIndex(0)
        for mode in ("polyline", "all"):
            self.win.combo_frame_type.setCurrentIndex(self.win.combo_frame_type.findData(mode))
            self.assertFalse(self.win.polyline_layer_row.isHidden())

        self.win.edit_polyline_layer.setText(" Рамки.АР ")
        self.win.save_settings()
        self.assertEqual(self.mock_config.save.call_args.args[0]["polyline_layer"], "Рамки.АР")
        self.assertEqual(self.win.get_current_profile_settings()["polyline_layer"], "Рамки.АР")
        self.win.combo_source.setCurrentIndex(1)
        self.assertTrue(self.win.polyline_layer_row.isHidden())
        self.win.edit_polyline_layer.clear()
        self.assertEqual(self.win.selected_polyline_layer(), "0000_Формат")

    def test_empty_layout_warning_keeps_print_selection(self):
        frame = Frame(1, "1", "Лист1", (0, 0, 0), (0, 0, 0), "Layout", is_empty_layout=True)
        self.win.frames = [frame]
        self.win.add_table_row(True, "1", "Лист1", "A2", "Layout", frame=frame)

        name = self.win.table.item(0, 3)
        self.assertFalse(name.icon().isNull())
        self.assertIn("Пустой лист", name.toolTip())
        self.assertEqual(name.text(), "Лист1")
        self.assertTrue(self.win.is_row_checked(0))

    def test_add_table_row_with_dwg(self):
        self.win.table.setRowCount(0)
        self.win.add_table_row(
            checked=True,
            num="1",
            name="План этажа",
            paper_format="A3",
            source="Model",
            dwg_name="plan_01.dwg"
        )
        self.assertEqual(self.win.table.rowCount(), 1)
        self.assertEqual(self.win.table.item(0, 1).text(), "1")
        self.assertEqual(self.win.table.item(0, 3).text(), "План этажа")
        self.assertEqual(self.win.table.item(0, 6).text(), "A3")
        self.assertEqual(self.win.table.item(0, 7).text(), "plan_01.dwg")
        self.assertEqual(self.win.table.item(0, 8).text(), "Model")

    def test_clear_frames(self):
        self.win.frames = [
            Frame(1, "1", "Лист 1", (0,0,0), (10,10,0), "Model", "A4", dwg_name="a.dwg")
        ]
        self.win.add_table_row(True, "1", "Лист 1", "A4", "Model", dwg_name="a.dwg")
        self.assertEqual(self.win.table.rowCount(), 1)

        self.win.clear_frames()
        self.assertEqual(len(self.win.frames), 0)
        self.assertEqual(self.win.table.rowCount(), 0)

    def test_sort_by_sheet_number_multi_dwg(self):
        # Файл 1 (открыт первым) содержит листы 6..10
        frames_file1 = [
            Frame(i, str(i), f"Лист {i}", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file_6_to_10.dwg")
            for i in range(6, 11)
        ]
        # Файл 2 (добавлен вторым) содержит листы 1..5
        frames_file2 = [
            Frame(i, str(i), f"Лист {i}", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file_1_to_5.dwg")
            for i in range(1, 6)
        ]

        # Имитируем добавление: сначала 6..10, затем 1..5
        self.win.frames = frames_file1 + frames_file2
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)

        self.win.sort_by_sheet_number()

        # Ожидаем сквозную последовательность 1..10
        sorted_nums = [f.sheet_number for f in self.win.frames]
        self.assertEqual(sorted_nums, ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"])
        # Проверяем строки таблицы
        for row in range(10):
            self.assertEqual(self.win.table.item(row, 1).text(), str(row + 1))


    def test_handle_dropped_urls(self):
        url1 = QUrl.fromLocalFile(r"C:\Drawings\test1.dwg")
        url2 = QUrl.fromLocalFile(r"C:\Drawings\notes.txt") # Должен игнорироваться

        with patch("os.path.isfile") as mock_isfile, \
             patch.object(self.win, "process_batch_dwg_files") as mock_process:
            mock_isfile.side_effect = lambda p: p.endswith(".dwg") or p.endswith(".txt")
            self.win.handle_dropped_urls([url1, url2])
            mock_process.assert_called_once()
            args = mock_process.call_args[0][0]
            self.assertEqual(len(args), 1)
            self.assertTrue(args[0].endswith("test1.dwg"))

    def test_missing_paper_warning_follows_printer_and_fallback_selection(self):
        from core.printer import BatchPrinter

        self.win.printer = BatchPrinter(MagicMock())
        layout = self.win.printer.doc.ModelSpace.Layout
        layout.GetPlotDeviceNames.return_value = ["Обычный", "Расширенный"]
        names = {"a3": "ISO A3 (420.00 x 297.00 mm)",
                 "a1": "ISO A1 (841.00 x 594.00 mm)",
                 "a3x3": "A3x3 (891.00 x 420.00 mm)"}
        layout.GetLocaleMediaName.side_effect = names.__getitem__
        layout.GetCanonicalMediaNames.side_effect = lambda: (
            ["a3", "a1", "a3x3"] if layout.ConfigName == "Расширенный" else ["a3", "a1"]
        )
        self.win.combo_printers.clear()
        self.win.combo_printers.addItems(["Обычный", "Расширенный"])
        frame = Frame(1, "1", "Развёртка", (0, 0, 0), (891, 420, 0), "Polyline", "A3x3")
        self.win.frames = [frame]
        self.win.add_table_row(True, "1", "Развёртка", "A3x3", "Polyline", frame=frame)
        item = self.win.table.item(0, 6)
        self.assertTrue(item.text().startswith("⚠"))
        self.assertIn(names["a3"], item.toolTip())

        self.win.combo_papers.setCurrentText(names["a1"])
        self.assertIn(names["a1"], item.toolTip())
        self.win.combo_printers.setCurrentText("Расширенный")
        self.assertEqual(item.text(), "A3x3")

        layout.GetCanonicalMediaNames.side_effect = RuntimeError("Нет связи с плоттером")
        self.win.combo_printers.setCurrentText("Обычный")
        self.assertEqual(item.text(), "A3x3")

    def test_update_paper_sizes_picks_a3_fallback(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей B5 (250.00 x 176.00 мм)": "ISO_B5",
            "ISO A4 (210.00 x 297.00 мм)": "ISO_A4",
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
            "ISO A1 (594.00 x 841.00 мм)": "ISO_A1",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO без полей A3 (420.00 x 297.00 мм)")

    def test_update_paper_sizes_ignores_old_b5(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей B5 (250.00 x 176.00 мм)": "ISO_B5",
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "ISO без полей B5 (250.00 x 176.00 мм)" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO без полей A3 (420.00 x 297.00 мм)")

    def test_update_paper_sizes_restores_valid_custom(self):
        self.win.printer = MagicMock()
        self.win.printer.get_media_names.return_value = {
            "ISO без полей A3 (420.00 x 297.00 мм)": "ISO_A3_Bleed",
            "ISO A1 (594.00 x 841.00 мм)": "ISO_A1",
        }
        self.mock_config.get.side_effect = lambda k, d=None: "ISO A1 (594.00 x 841.00 мм)" if k == "fallback_paper" else d
        self.win.update_paper_sizes("DWG To PDF.pc3")
        self.assertEqual(self.win.combo_papers.currentText(), "ISO A1 (594.00 x 841.00 мм)")


    def test_table_column_widths_and_horizontal_scroll(self):
        from PySide6.QtWidgets import QHeaderView
        from PySide6.QtCore import Qt

        header = self.win.table.horizontalHeader()
        # Все колонки должны быть интерактивными (можно менять ширину)
        for i in range(self.win.table.columnCount()):
            self.assertEqual(header.sectionResizeMode(i), QHeaderView.ResizeMode.Interactive)

        # Проверка включения горизонтальной прокрутки
        self.assertEqual(self.win.table.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Проверка сохранения ширины колонок при изменении
        self.win._is_loading_config = False
        header.resizeSection(3, 350)
        self.mock_config.set.assert_called_with("table_column_widths", [header.sectionSize(i) for i in range(self.win.table.columnCount())])
        self.mock_config.save.assert_called()

    def test_responsive_bottom_buttons_layout(self):
        # При достаточной ширине (>= 1250) все кнопки выстраиваются в один ряд
        self.win.update_table_tools_layout(1300)
        self.assertTrue(self.win._is_single_row_tools)
        self.assertTrue(self.win.table_tools_row2_widget.isHidden())
        self.assertEqual(self.win.table_tools_row1.count(), 9)

        # При узком окне (< 1250) кнопки делятся на 2 ряда
        self.win.update_table_tools_layout(1000)
        self.assertFalse(self.win._is_single_row_tools)
        self.assertFalse(self.win.table_tools_row2_widget.isHidden())
        self.assertEqual(self.win.table_tools_row1.count(), 5)
        self.assertEqual(self.win.table_tools_row2.count(), 5)

    def test_theme_switching_and_persistence(self):
        # Проверяем наличие всех тем в combo_theme
        theme_keys = [self.win.combo_theme.itemData(i) for i in range(self.win.combo_theme.count())]
        self.assertIn("dark_catppuccin", theme_keys)
        self.assertIn("autocad_dark", theme_keys)
        self.assertIn("light", theme_keys)

        # Переключаем тему на autocad_dark
        self.win._is_loading_config = False
        idx_acad = self.win.combo_theme.findData("autocad_dark")
        self.win.combo_theme.setCurrentIndex(idx_acad)
        self.assertEqual(self.win.current_theme, "autocad_dark")
        self.assertIn("#212121", self.win.styleSheet())
        self.mock_config.save.assert_called()

        # Переключаем тему на light
        idx_light = self.win.combo_theme.findData("light")
        self.win.combo_theme.setCurrentIndex(idx_light)
        self.assertEqual(self.win.current_theme, "light")
        self.assertIn("#f0f2f5", self.win.styleSheet())
        self.mock_config.save.assert_called()

    def test_theme_restore_from_config(self):
        mock_cfg = MagicMock()
        mock_cfg.load.return_value = {"theme": "autocad_dark"}
        mock_cfg.get.side_effect = lambda k, d=None: "autocad_dark" if k == "theme" else d
        win2 = PrintManagerUI(config_manager=mock_cfg)
        self.assertEqual(win2.current_theme, "autocad_dark")
        self.assertEqual(win2.combo_theme.currentData(), "autocad_dark")

    def test_status_bar_summary(self):
        self.win.clear_frames()
        self.assertIn("Листов в очереди: <b>0</b>", self.win.lbl_status_left.text())
        self.assertIn("Добавьте чертежи", self.win.lbl_status_right.text())

        # Добавляем листы разных форматов и чертежей
        self.win.frames = [
            Frame(1, "1", "Лист 1", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file1.dwg"),
            Frame(2, "2", "Лист 2", (0,0,0), (10,10,0), "Model", "A3", dwg_name="file1.dwg"),
            Frame(3, "3", "Лист 3", (0,0,0), (10,10,0), "Model", "A3", dwg_name="file2.dwg"),
            Frame(4, "4", "Лист 4", (0,0,0), (10,10,0), "Model", "A2", dwg_name="file2.dwg"),
        ]
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)

        # Проверяем сводку в Status Bar
        left_text = self.win.lbl_status_left.text()
        self.assertIn("Всего листов: <b>4</b>", left_text)
        self.assertIn("К печати: <b", left_text)
        self.assertIn("4</b>", left_text)
        # Форматы: A4x1, A3x2, A2x1
        self.assertIn("A4x1", left_text)
        self.assertIn("A3x2", left_text)
        self.assertIn("A2x1", left_text)
        # Чертежей: 2
        self.assertIn("Чертежей: <b>2</b>", left_text)

    def test_status_bar_filter_and_uncheck(self):
        self.win.frames = [
            Frame(1, "1", "План", (0,0,0), (10,10,0), "Model", "A3", dwg_name="file1.dwg"),
            Frame(2, "2", "Схема", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file1.dwg"),
        ]
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type, dwg_name=f.dwg_name)

        # Снимаем галочки
        self.win.select_all_rows(False)
        left_text = self.win.lbl_status_left.text()
        self.assertIn("Всего листов: <b>2</b>", left_text)
        self.assertIn("К печати: <b", left_text)
        self.assertIn("0</b>", left_text)
        self.assertIn("Отметьте листы галочками", self.win.lbl_status_right.text())

        # Выбираем обратно
        self.win.select_all_rows(True)
        # Фильтруем по слову "План"
        self.win.txt_search.setText("План")
        self.assertTrue(self.win.is_filter_active())
        left_text = self.win.lbl_status_left.text()
        self.assertIn("Всего листов: <b>2</b>", left_text)
        self.assertIn("В фильтре: <b>1</b>", left_text)
        self.assertIn("К печати: <b", left_text)
        self.assertIn("1</b>", left_text)
        self.assertIn("Фильтр активен", self.win.lbl_status_right.text())

    def test_column_visibility_toggle_and_persistence(self):
        # По умолчанию колонки не скрыты
        self.assertFalse(self.win.table.isColumnHidden(4))
        self.assertFalse(self.win.table.isColumnHidden(5))

        # Скрываем колонку 4 ("Объект строительства")
        self.win.toggle_column_visibility(4, False)
        self.assertTrue(self.win.table.isColumnHidden(4))
        self.mock_config.set.assert_called_with("hidden_columns", [4])
        self.mock_config.save.assert_called()

        # Скрываем колонку 5 ("Здание / сооружение")
        self.win.toggle_column_visibility(5, False)
        self.assertTrue(self.win.table.isColumnHidden(5))
        self.mock_config.set.assert_called_with("hidden_columns", [4, 5])

        # Отображаем все колонки
        self.win.show_all_columns()
        self.assertFalse(self.win.table.isColumnHidden(4))
        self.assertFalse(self.win.table.isColumnHidden(5))
        self.mock_config.set.assert_called_with("hidden_columns", [])

        # Сброс ширины колонок
        self.win.reset_column_widths()
        header = self.win.table.horizontalHeader()
        self.assertEqual(header.sectionSize(0), 65)
        self.assertEqual(header.sectionSize(1), 60)
        self.assertEqual(header.sectionSize(2), 180)

    def test_context_menu_actions(self):
        from PySide6.QtGui import QGuiApplication
        self.win.frames = [
            Frame(1, "1", "Лист 1", (0,0,0), (10,10,0), "Model", "A4", dwg_name="file1.dwg", doc_code="2024-АР-1"),
            Frame(2, "2", "Лист 2", (0,0,0), (10,10,0), "Model", "A3", dwg_name="file1.dwg", doc_code="2024-АР-1"),
            Frame(3, "3", "Лист 3", (0,0,0), (10,10,0), "Model", "A3", dwg_name="file2.dwg", doc_code="2024-КЖ-1"),
        ]
        self.win.table.setRowCount(0)
        for f in self.win.frames:
            self.win.add_table_row(
                True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type,
                dwg_name=f.dwg_name, doc_code=f.doc_code
            )

        # 1. Печатать только этот лист (строка 1)
        self.win.print_only_this_row(1)
        self.assertFalse(self.win.is_row_checked(0))
        self.assertTrue(self.win.is_row_checked(1))
        self.assertFalse(self.win.is_row_checked(2))

        # 2. Инвертировать выбор
        self.win.invert_selection()
        self.assertTrue(self.win.is_row_checked(0))
        self.assertFalse(self.win.is_row_checked(1))
        self.assertTrue(self.win.is_row_checked(2))

        # 3. Печатать листы чертежа file2.dwg
        self.win.print_same_dwg_rows("file2.dwg")
        self.assertFalse(self.win.is_row_checked(0))
        self.assertFalse(self.win.is_row_checked(1))
        self.assertTrue(self.win.is_row_checked(2))

        # 4. Копировать строку в буфер обмена
        with patch.object(QGuiApplication.clipboard(), "setText") as mock_set:
            self.win.copy_full_row(0)
            mock_set.assert_called_once()
            copied_text = mock_set.call_args[0][0]
            self.assertIn("1", copied_text)
            self.assertIn("2024-АР-1", copied_text)
            self.assertIn("Лист 1", copied_text)
            self.assertIn("file1.dwg", copied_text)

    def test_frame_type_selection_and_ui_state(self):
        # Проверяем элементы группы "Поиск рамок"
        self.assertTrue(hasattr(self.win, "combo_frame_type"))
        self.assertTrue(hasattr(self.win, "edit_block_name"))
        self.assertTrue(hasattr(self.win, "lbl_frame_type_warning"))

        # Доступно 5 режимов
        self.assertEqual(self.win.combo_frame_type.count(), 5)
        codes = [self.win.combo_frame_type.itemData(i) for i in range(5)]
        self.assertEqual(codes, ["spds", "all_blocks", "custom_block", "polyline", "all"])

        # 1. Режим СПДС: скрыты поле ввода и предупреждение
        idx_spds = self.win.combo_frame_type.findData("spds")
        self.win.combo_frame_type.setCurrentIndex(idx_spds)
        self.assertTrue(self.win.edit_block_name.isHidden())
        self.assertTrue(self.win.lbl_frame_type_warning.isHidden())

        # 2. Режим "Конкретный блок": поле ввода отображается
        idx_custom = self.win.combo_frame_type.findData("custom_block")
        self.win.combo_frame_type.setCurrentIndex(idx_custom)
        self.assertFalse(self.win.edit_block_name.isHidden())
        self.assertTrue(self.win.lbl_frame_type_warning.isHidden())

        # 3. Режим "Все типы сразу": предупреждение отображается
        idx_all = self.win.combo_frame_type.findData("all")
        self.win.combo_frame_type.setCurrentIndex(idx_all)
        self.assertTrue(self.win.edit_block_name.isHidden())
        self.assertFalse(self.win.lbl_frame_type_warning.isHidden())


if __name__ == "__main__":
    unittest.main()
