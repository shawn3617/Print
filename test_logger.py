"""
Тесты для модуля логирования и диагностики (core/logger.py).
"""

import os
import unittest
from unittest.mock import patch

from core.logger import (
    init_logging,
    get_logger,
    log_info,
    log_warn,
    log_error,
    get_recent_logs,
    clear_log_buffer,
    get_log_file_path,
    build_diagnostic_report,
)


class TestLogger(unittest.TestCase):
    def setUp(self):
        clear_log_buffer()

    def test_init_and_get_log_file_path(self):
        path = get_log_file_path()
        self.assertTrue(path.endswith("app.log"))
        self.assertTrue(os.path.exists(os.path.dirname(path)))

    def test_memory_buffer_captures_logs(self):
        clear_log_buffer()
        log_info("Тестовое информационное сообщение", module="TestMod")
        log_warn("Предупреждение проверки", exc=ValueError("ошибка теста"), module="TestMod")
        log_error("Критический сбой", module="TestMod")

        logs = get_recent_logs()
        self.assertGreaterEqual(len(logs), 3)

        text_dump = "\n".join(logs)
        self.assertIn("Тестовое информационное сообщение", text_dump)
        self.assertIn("Предупреждение проверки", text_dump)
        self.assertIn("ValueError: ошибка теста", text_dump)
        self.assertIn("Критический сбой", text_dump)
        self.assertIn("PrintPDF.TestMod", text_dump)

    def test_level_filter(self):
        clear_log_buffer()
        log_info("Инфо для фильтра", module="Filt")
        log_warn("Варнинг для фильтра", module="Filt")
        log_error("Эррор для фильтра", module="Filt")

        warns = get_recent_logs(level_filter="WARNING")
        self.assertEqual(len(warns), 1)
        self.assertIn("Варнинг для фильтра", warns[0])

        errors = get_recent_logs(level_filter="ERROR")
        self.assertEqual(len(errors), 1)
        self.assertIn("Эррор для фильтра", errors[0])

    def test_build_diagnostic_report(self):
        clear_log_buffer()
        log_info("Старт тестовой сессии", module="ReportTest")
        log_warn("Внимание: тестовый сбой", module="ReportTest")

        report = build_diagnostic_report(extra_info={
            "acad_status": "AutoCAD 2024",
            "doc_name": "ТестЧертеж.dwg",
            "printer": "DWG To PDF.pc3",
            "plot_style": "monochrome.ctb",
            "fallback_paper": "ISO A3"
        })

        self.assertIn("PrintPDF — Отчёт диагностики для разработчика", report)
        self.assertIn("AutoCAD 2024", report)
        self.assertIn("ТестЧертеж.dwg", report)
        self.assertIn("DWG To PDF.pc3", report)
        self.assertIn("Старт тестовой сессии", report)
        self.assertIn("Внимание: тестовый сбой", report)
        self.assertIn("КОНЕЦ ОТЧЁТА", report)


if __name__ == "__main__":
    unittest.main()
