"""
Модульные тесты для менеджера локальной статистики стабильности (core/stats_manager.py).
"""

from datetime import datetime
import json
import os
import shutil
import tempfile
import threading
import time
import unittest

from core.config_manager import ConfigManager
from core.report_models import PrintItemResult, PrintReport, ScanFileResult, ScanReport
from core.stats_manager import StatsManager, get_default_stats_path, get_stats_manager


class TestStatsManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.stats_file = os.path.join(self.temp_dir.name, "stats.json")
        self.manager = StatsManager(self.stats_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_values_on_initialization(self):
        """Проверка дефолтных значений метрик и вычисляемых свойств."""
        summary = self.manager.get_summary()

        self.assertEqual(summary["total_app_launches"], 0)
        self.assertEqual(summary["first_launch_date"], "")
        self.assertEqual(summary["last_launch_date"], "")
        self.assertEqual(summary["total_print_batches"], 0)
        self.assertEqual(summary["total_sheets_printed"], 0)
        self.assertEqual(summary["success_sheets_count"], 0)
        self.assertEqual(summary["failed_sheets_count"], 0)
        self.assertEqual(summary["fallback_format_count"], 0)
        self.assertEqual(summary["total_print_duration_seconds"], 0.0)
        self.assertEqual(summary["total_scan_batches"], 0)
        self.assertEqual(summary["total_dwg_scanned"], 0)
        self.assertEqual(summary["total_frames_found"], 0)

        # Вычисляемые свойства при пустой статистике
        self.assertEqual(self.manager.success_rate, 0.0)
        self.assertEqual(self.manager.time_saved_seconds, 0.0)
        self.assertEqual(self.manager.time_saved_formatted, "0 мин")
        self.assertEqual(self.manager.avg_seconds_per_sheet, 0.0)

    def test_path_resolution_with_config_manager(self):
        """Проверка размещения stats.json рядом с config.json."""
        config_path = os.path.join(self.temp_dir.name, "subdir", "config.json")
        cfg_mgr = ConfigManager(config_path)
        resolved_path = get_default_stats_path(cfg_mgr)
        expected_path = os.path.join(self.temp_dir.name, "subdir", "stats.json")
        self.assertEqual(os.path.normpath(resolved_path), os.path.normpath(expected_path))

    def test_singleton_get_stats_manager(self):
        """Проверка синглтона get_stats_manager()."""
        m1 = get_stats_manager(reset_instance=True)
        m2 = get_stats_manager()
        self.assertIs(m1, m2)

        # Независимый экземпляр при явном указании stats_path
        custom_file = os.path.join(self.temp_dir.name, "custom_stats.json")
        m_custom = get_stats_manager(stats_path=custom_file)
        self.assertIsNot(m1, m_custom)
        self.assertEqual(m_custom.stats_path, custom_file)

    def test_record_launch(self):
        """Проверка фиксации запусков приложения и обновления дат ISO 8601."""
        self.manager.record_launch()
        self.assertEqual(self.manager.total_app_launches, 1)
        first_launch = self.manager.first_launch_date
        self.assertTrue(len(first_launch) > 0)
        self.assertEqual(self.manager.last_launch_date, first_launch)

        # Проверяем формат ISO 8601
        dt = datetime.fromisoformat(first_launch)
        self.assertIsInstance(dt, datetime)

        time.sleep(0.01)
        self.manager.record_launch()
        self.assertEqual(self.manager.total_app_launches, 2)
        # first_launch_date не должна измениться
        self.assertEqual(self.manager.first_launch_date, first_launch)
        # last_launch_date должна быть установлена
        self.assertTrue(self.manager.last_launch_date >= first_launch)

        # Проверяем сохранность на диске
        reloaded = StatsManager(self.stats_file)
        self.assertEqual(reloaded.total_app_launches, 2)
        self.assertEqual(reloaded.first_launch_date, first_launch)

    def test_record_print_batch(self):
        """Проверка фиксации пакетной печати."""
        report1 = PrintReport(
            total_requested=10,
            success_count=9,
            failed_count=1,
            fallback_count=2,
            duration_seconds=25.5,
        )
        self.manager.record_print_batch(report1)

        self.assertEqual(self.manager.total_print_batches, 1)
        self.assertEqual(self.manager.total_sheets_printed, 10)
        self.assertEqual(self.manager.success_sheets_count, 9)
        self.assertEqual(self.manager.failed_sheets_count, 1)
        self.assertEqual(self.manager.fallback_format_count, 2)
        self.assertAlmostEqual(self.manager.total_print_duration_seconds, 25.5)

        # Вторая пачка печати суммируется
        report2 = PrintReport(
            total_requested=5,
            success_count=5,
            failed_count=0,
            fallback_count=0,
            duration_seconds=12.5,
        )
        self.manager.record_print_batch(report2)

        self.assertEqual(self.manager.total_print_batches, 2)
        self.assertEqual(self.manager.total_sheets_printed, 15)
        self.assertEqual(self.manager.success_sheets_count, 14)
        self.assertEqual(self.manager.failed_sheets_count, 1)
        self.assertEqual(self.manager.fallback_format_count, 2)
        self.assertAlmostEqual(self.manager.total_print_duration_seconds, 38.0)

        # Перезагрузка с диска
        reloaded = StatsManager(self.stats_file)
        self.assertEqual(reloaded.total_sheets_printed, 15)
        self.assertEqual(reloaded.success_sheets_count, 14)

    def test_record_print_batch_with_fallback_items_length(self):
        """Проверка фиксации печати, если total_requested не заполнен, но есть items."""
        mock_item = PrintItemResult(frame=None, success=True)
        report = PrintReport(
            total_requested=0,
            success_count=2,
            failed_count=0,
            items=[mock_item, mock_item],
            duration_seconds=5.0
        )
        self.manager.record_print_batch(report)
        self.assertEqual(self.manager.total_sheets_printed, 2)
        self.assertEqual(self.manager.success_sheets_count, 2)

    def test_record_scan_batch(self):
        """Проверка фиксации пакетного сканирования."""
        report1 = ScanReport(
            total_files=4,
            success_files_count=4,
            failed_files_count=0,
            total_frames_found=24,
            duration_seconds=8.0,
        )
        self.manager.record_scan_batch(report1)

        self.assertEqual(self.manager.total_scan_batches, 1)
        self.assertEqual(self.manager.total_dwg_scanned, 4)
        self.assertEqual(self.manager.total_frames_found, 24)

        # Второе сканирование
        mock_file_res = ScanFileResult("test.dwg", "test.dwg", True, frames_count=3)
        report2 = ScanReport(
            total_files=0,
            file_results=[mock_file_res],
            total_frames_found=3,
        )
        self.manager.record_scan_batch(report2)

        self.assertEqual(self.manager.total_scan_batches, 2)
        self.assertEqual(self.manager.total_dwg_scanned, 5)
        self.assertEqual(self.manager.total_frames_found, 27)

    def test_calculated_properties(self):
        """Проверка расчёта success_rate, time_saved и avg_seconds_per_sheet."""
        # Пример из ТЗ: успешность печати 99.4%
        report = PrintReport(
            total_requested=1000,
            success_count=994,
            failed_count=6,
            duration_seconds=2500.0,
        )
        self.manager.record_print_batch(report)

        self.assertEqual(self.manager.success_rate, 99.4)
        # Сэкономленное время: 994 листа * 120 сек = 119280 сек
        self.assertEqual(self.manager.time_saved_seconds, 119280.0)
        # 119280 сек = 1988 мин = 33 ч 8 мин
        self.assertEqual(self.manager.time_saved_formatted, "33 ч 8 мин")
        # Средняя скорость: 2500 / 1000 = 2.5 сек/лист
        self.assertEqual(self.manager.avg_seconds_per_sheet, 2.5)

    def test_time_saved_formatting(self):
        """Проверка вариантов форматирования сэкономленного времени."""
        # 0 секунд
        self.assertEqual(self.manager.time_saved_formatted, "0 мин")

        # 1 лист = 120 сек = 2 мин
        self.manager.success_sheets_count = 1
        self.assertEqual(self.manager.time_saved_formatted, "2 мин")

        # 45 минут (45 * 60 / 120 = 22.5 листа)
        # Зададим напрямую для тестирования форматирования
        self.manager.success_sheets_count = 22  # 44 мин
        self.assertEqual(self.manager.time_saved_formatted, "44 мин")

        # Ровно 1 час (30 листов * 120 сек = 3600 сек)
        self.manager.success_sheets_count = 30
        self.assertEqual(self.manager.time_saved_formatted, "1 ч")

        # Пример из ТЗ: "14 ч 35 мин" -> 14 * 60 + 35 = 875 мин -> 875 * 60 = 52500 сек
        # 52500 / 120 = 437.5. Проверим логику свойства:
        self.manager.success_sheets_count = 437  # 874 мин = 14 ч 34 мин
        self.assertEqual(self.manager.time_saved_formatted, "14 ч 34 мин")

    def test_reset_stats(self):
        """Проверка сброса статистики."""
        self.manager.record_launch()
        self.manager.record_print_batch(PrintReport(total_requested=10, success_count=10, duration_seconds=15.0))
        self.manager.record_scan_batch(ScanReport(total_files=2, total_frames_found=8))

        self.assertGreater(self.manager.total_app_launches, 0)
        self.assertGreater(self.manager.total_sheets_printed, 0)
        self.assertGreater(self.manager.total_dwg_scanned, 0)

        self.manager.reset_stats()

        self.assertEqual(self.manager.total_app_launches, 0)
        self.assertEqual(self.manager.first_launch_date, "")
        self.assertEqual(self.manager.last_launch_date, "")
        self.assertEqual(self.manager.total_print_batches, 0)
        self.assertEqual(self.manager.total_sheets_printed, 0)
        self.assertEqual(self.manager.success_sheets_count, 0)
        self.assertEqual(self.manager.failed_sheets_count, 0)
        self.assertEqual(self.manager.fallback_format_count, 0)
        self.assertEqual(self.manager.total_print_duration_seconds, 0.0)
        self.assertEqual(self.manager.total_scan_batches, 0)
        self.assertEqual(self.manager.total_dwg_scanned, 0)
        self.assertEqual(self.manager.total_frames_found, 0)

        # Проверяем, что файл на диске тоже обновился
        reloaded = StatsManager(self.stats_file)
        self.assertEqual(reloaded.total_app_launches, 0)
        self.assertEqual(reloaded.total_sheets_printed, 0)

    def test_corrupted_json_recovery(self):
        """Проверка безопасного восстановления и создания бэкапа при повреждённом json."""
        # 1. Записываем повреждённый JSON
        with open(self.stats_file, "w", encoding="utf-8") as f:
            f.write("{this is not a valid json syntax: 1234")

        # 2. Инициализируем StatsManager поверх повреждённого файла
        corrupted_mgr = StatsManager(self.stats_file)

        # Данные должны быть сброшены к дефолтным без падения с исключением
        self.assertEqual(corrupted_mgr.total_app_launches, 0)
        self.assertEqual(corrupted_mgr.total_sheets_printed, 0)

        # Должна быть создана резервная копия .corrupted
        backup_file = f"{self.stats_file}.corrupted"
        self.assertTrue(os.path.exists(backup_file))
        with open(backup_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("this is not a valid json", content)

        # Исходный файл должен быть перезаписан корректным JSON
        with open(self.stats_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict)
        self.assertEqual(data["total_app_launches"], 0)

    def test_non_dict_json_recovery(self):
        """Проверка восстановления, когда JSON корректен, но является списком или примитивом."""
        with open(self.stats_file, "w", encoding="utf-8") as f:
            json.dump([1, 2, 3], f)

        mgr = StatsManager(self.stats_file)
        self.assertEqual(mgr.total_app_launches, 0)
        self.assertTrue(os.path.exists(f"{self.stats_file}.corrupted"))

    def test_atomic_save_tmp_file(self):
        """Проверка атомарности: после сохранения временных файлов .tmp не остаётся."""
        self.manager.record_launch()
        self.manager.record_print_batch(PrintReport(total_requested=5, success_count=5))

        tmp_files = [f for f in os.listdir(self.temp_dir.name) if f.endswith(".tmp")]
        self.assertEqual(len(tmp_files), 0, f"Остались временные файлы: {tmp_files}")
        self.assertTrue(os.path.exists(self.stats_file))

    def test_thread_safety(self):
        """Проверка потокобезопасности при одновременных записях из разных потоков."""
        num_threads = 10
        records_per_thread = 20

        def worker():
            for _ in range(records_per_thread):
                self.manager.record_launch()
                self.manager.record_print_batch(PrintReport(total_requested=2, success_count=2, duration_seconds=1.0))
                self.manager.record_scan_batch(ScanReport(total_files=1, total_frames_found=2))
                _ = self.manager.get_summary()

        threads = [threading.Thread(target=worker) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        expected_launches = num_threads * records_per_thread
        expected_sheets = expected_launches * 2
        expected_dwg = expected_launches * 1
        expected_frames = expected_launches * 2

        self.assertEqual(self.manager.total_app_launches, expected_launches)
        self.assertEqual(self.manager.total_sheets_printed, expected_sheets)
        self.assertEqual(self.manager.success_sheets_count, expected_sheets)
        self.assertEqual(self.manager.total_dwg_scanned, expected_dwg)
        self.assertEqual(self.manager.total_frames_found, expected_frames)

        # Перезагрузка с диска для проверки целостности сохранённого файла
        reloaded = StatsManager(self.stats_file)
        self.assertEqual(reloaded.total_app_launches, expected_launches)
        self.assertEqual(reloaded.total_sheets_printed, expected_sheets)


if __name__ == "__main__":
    unittest.main()
