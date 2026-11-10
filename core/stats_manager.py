"""
Модуль сбора и хранения локальной статистики стабильности и эффективности работы PrintPDF.
Все данные сохраняются исключительно локально в stats.json без отправки в сеть.
"""

from datetime import datetime
import json
import os
import shutil
import threading
import time
from typing import Any, Dict, Optional

from core.config_manager import ConfigManager, get_default_config_path
from core.logger import log_error, log_info, log_warn
from core.report_models import PrintReport, ScanReport

DEFAULT_STATS: Dict[str, Any] = {
    "total_app_launches": 0,
    "first_launch_date": "",
    "last_launch_date": "",
    "total_print_batches": 0,
    "total_sheets_printed": 0,
    "success_sheets_count": 0,
    "failed_sheets_count": 0,
    "fallback_format_count": 0,
    "total_print_duration_seconds": 0.0,
    "total_scan_batches": 0,
    "total_dwg_scanned": 0,
    "total_frames_found": 0,
}


def get_default_stats_path(config_manager: Optional[ConfigManager] = None) -> str:
    """
    Возвращает путь к stats.json в той же директории, где хранится config.json.
    """
    if config_manager and getattr(config_manager, "config_path", None):
        base_dir = os.path.dirname(os.path.abspath(config_manager.config_path))
    else:
        base_dir = os.path.dirname(os.path.abspath(get_default_config_path()))
    return os.path.join(base_dir, "stats.json")


class StatsManager:
    """
    Менеджер сбора и отображения локальной статистики стабильности и производительности.
    Обеспечивает атомарную запись через временный файл, потокобезопасность
    и автоматическое восстановление при повреждении файла.
    """

    MANUAL_SECONDS_PER_SHEET: float = 120.0  # ~2 минуты на лист при ручной печати в AutoCAD

    def __init__(self, stats_path: Optional[str] = None, config_manager: Optional[ConfigManager] = None):
        self._lock = threading.RLock()
        if stats_path:
            self.stats_path = os.path.abspath(stats_path)
        else:
            self.stats_path = get_default_stats_path(config_manager)

        self.total_app_launches: int = 0
        self.first_launch_date: str = ""
        self.last_launch_date: str = ""
        self.total_print_batches: int = 0
        self.total_sheets_printed: int = 0
        self.success_sheets_count: int = 0
        self.failed_sheets_count: int = 0
        self.fallback_format_count: int = 0
        self.total_print_duration_seconds: float = 0.0
        self.total_scan_batches: int = 0
        self.total_dwg_scanned: int = 0
        self.total_frames_found: int = 0

        self.load()

    # =========================================================================
    # Вычисляемые свойства
    # =========================================================================

    @property
    def success_rate(self) -> float:
        """
        Процент успешной печати (например, 99.4%).
        Если листы ещё не печатались, возвращает 0.0%.
        """
        with self._lock:
            total = self.total_sheets_printed
            if total <= 0:
                total = self.success_sheets_count + self.failed_sheets_count
            if total <= 0:
                return 0.0
            rate = (self.success_sheets_count / total) * 100.0
            return round(min(100.0, max(0.0, rate)), 1)

    @property
    def time_saved_seconds(self) -> float:
        """
        Расчёт сэкономленного времени: 120.0 сек (~2 минуты) на каждый успешно
        напечатанный лист вручную в AutoCAD.
        """
        with self._lock:
            return float(self.success_sheets_count * self.MANUAL_SECONDS_PER_SHEET)

    @property
    def time_saved_formatted(self) -> str:
        """
        Сэкономленное время в читаемом виде: '14 ч 35 мин' или '45 мин'.
        """
        with self._lock:
            total_seconds = int(self.time_saved_seconds)
            total_minutes = total_seconds // 60
            hours = total_minutes // 60
            minutes = total_minutes % 60
            if hours > 0:
                if minutes > 0:
                    return f"{hours} ч {minutes} мин"
                return f"{hours} ч"
            return f"{minutes} мин"

    @property
    def avg_seconds_per_sheet(self) -> float:
        """
        Средняя скорость печати одного листа (в секундах).
        """
        with self._lock:
            total = self.total_sheets_printed
            if total <= 0:
                total = self.success_sheets_count + self.failed_sheets_count
            if total <= 0 or self.total_print_duration_seconds <= 0.0:
                return 0.0
            return round(self.total_print_duration_seconds / total, 2)

    # =========================================================================
    # Регистрация событий
    # =========================================================================

    def record_launch(self) -> None:
        """
        Регистрирует факт запуска приложения.
        Увеличивает total_app_launches, устанавливает first_launch_date (при первом запуске)
        и обновляет last_launch_date в формате ISO 8601.
        """
        with self._lock:
            now_iso = datetime.now().isoformat(timespec="seconds")
            self.total_app_launches += 1
            if not self.first_launch_date:
                self.first_launch_date = now_iso
            self.last_launch_date = now_iso
            self._save_unlocked()
            log_info(
                f"Зафиксирован запуск программы (всего запусков: {self.total_app_launches})",
                module="StatsManager"
            )

    def record_print_batch(self, report: PrintReport) -> None:
        """
        Регистрирует результаты выполненной пакетной печати на основе PrintReport.
        """
        if not report:
            return
        with self._lock:
            self.total_print_batches += 1
            requested = getattr(report, "total_requested", 0)
            if requested <= 0 and hasattr(report, "items"):
                requested = len(report.items)
            self.total_sheets_printed += max(0, requested)
            self.success_sheets_count += max(0, getattr(report, "success_count", 0))
            self.failed_sheets_count += max(0, getattr(report, "failed_count", 0))
            self.fallback_format_count += max(0, getattr(report, "fallback_count", 0))
            self.total_print_duration_seconds += max(0.0, float(getattr(report, "duration_seconds", 0.0)))
            self._save_unlocked()
            log_info(
                f"Зафиксирована пакетная печать: +{requested} листов "
                f"(успешно: {getattr(report, 'success_count', 0)}, ошибок: {getattr(report, 'failed_count', 0)})",
                module="StatsManager"
            )

    def record_scan_batch(self, report: ScanReport) -> None:
        """
        Регистрирует результаты пакетного сканирования чертежей на основе ScanReport.
        """
        if not report:
            return
        with self._lock:
            self.total_scan_batches += 1
            files = getattr(report, "total_files", 0)
            if files <= 0 and hasattr(report, "file_results"):
                files = len(report.file_results)
            self.total_dwg_scanned += max(0, files)
            self.total_frames_found += max(0, getattr(report, "total_frames_found", 0))
            self._save_unlocked()
            log_info(
                f"Зафиксировано пакетное сканирование: +{files} DWG, "
                f"найдено рамок: {getattr(report, 'total_frames_found', 0)}",
                module="StatsManager"
            )

    def reset_stats(self) -> None:
        """
        Сбрасывает всю накопленную статистику к значениям по умолчанию.
        """
        with self._lock:
            self._reset_to_defaults()
            self._save_unlocked()
            log_info("Локальная статистика успешно сброшена", module="StatsManager")

    def get_summary(self) -> Dict[str, Any]:
        """
        Возвращает полную сводку всех метрик и вычисляемых показателей.
        """
        with self._lock:
            return {
                "total_app_launches": self.total_app_launches,
                "first_launch_date": self.first_launch_date,
                "last_launch_date": self.last_launch_date,
                "total_print_batches": self.total_print_batches,
                "total_sheets_printed": self.total_sheets_printed,
                "success_sheets_count": self.success_sheets_count,
                "failed_sheets_count": self.failed_sheets_count,
                "fallback_format_count": self.fallback_format_count,
                "total_print_duration_seconds": self.total_print_duration_seconds,
                "total_scan_batches": self.total_scan_batches,
                "total_dwg_scanned": self.total_dwg_scanned,
                "total_frames_found": self.total_frames_found,
                "success_rate": self.success_rate,
                "time_saved_seconds": self.time_saved_seconds,
                "time_saved_formatted": self.time_saved_formatted,
                "avg_seconds_per_sheet": self.avg_seconds_per_sheet,
            }

    def get_formatted_report(self) -> str:
        """
        Формирует форматированный текстовый отчёт со статистикой использования для отображения и буфера обмена.
        """
        with self._lock:
            first_date = self.first_launch_date.replace("T", " ") if self.first_launch_date else "—"
            last_date = self.last_launch_date.replace("T", " ") if self.last_launch_date else "—"
            lines = [
                "=" * 60,
                "СТАТИСТИКА ИСПОЛЬЗОВАНИЯ И ЭФФЕКТИВНОСТИ (PrintPDF)",
                "=" * 60,
                f"Запусков программы:          {self.total_app_launches}",
                f"Первый запуск:               {first_date}",
                f"Последний запуск:            {last_date}",
                "-" * 60,
                "ПАКЕТНАЯ ПЕЧАТЬ:",
                f"  Запусков пакетной печати:  {self.total_print_batches}",
                f"  Всего листов обработано:   {self.total_sheets_printed}",
                f"  Успешно напечатано:        {self.success_sheets_count}",
                f"  Ошибок печати:             {self.failed_sheets_count}",
                f"  С резервным форматом:      {self.fallback_format_count}",
                f"  Успешность (Success Rate): {self.success_rate:.1f}%",
                f"  Среднее время на лист:     {self.avg_seconds_per_sheet:.1f} сек",
                "-" * 60,
                "СКАНИРОВАНИЕ ЧЕРТЕЖЕЙ:",
                f"  Сессий сканирования:       {self.total_scan_batches}",
                f"  Обработано DWG-файлов:     {self.total_dwg_scanned}",
                f"  Всего рамок найдено:       {self.total_frames_found}",
                "-" * 60,
                "ЭКОНОМИЯ ВРЕМЕНИ:",
                f"  Сэкономлено времени:       {self.time_saved_formatted} (расчёт: ~2 мин/лист вручную)",
                "=" * 60,
            ]
            return "\n".join(lines)

    # =========================================================================
    # Работа с файловой системой (чтение, запись, восстановление)
    # =========================================================================

    def _reset_to_defaults(self) -> None:
        self.total_app_launches = int(DEFAULT_STATS["total_app_launches"])
        self.first_launch_date = str(DEFAULT_STATS["first_launch_date"])
        self.last_launch_date = str(DEFAULT_STATS["last_launch_date"])
        self.total_print_batches = int(DEFAULT_STATS["total_print_batches"])
        self.total_sheets_printed = int(DEFAULT_STATS["total_sheets_printed"])
        self.success_sheets_count = int(DEFAULT_STATS["success_sheets_count"])
        self.failed_sheets_count = int(DEFAULT_STATS["failed_sheets_count"])
        self.fallback_format_count = int(DEFAULT_STATS["fallback_format_count"])
        self.total_print_duration_seconds = float(DEFAULT_STATS["total_print_duration_seconds"])
        self.total_scan_batches = int(DEFAULT_STATS["total_scan_batches"])
        self.total_dwg_scanned = int(DEFAULT_STATS["total_dwg_scanned"])
        self.total_frames_found = int(DEFAULT_STATS["total_frames_found"])

    def _to_dict(self) -> Dict[str, Any]:
        return {
            "total_app_launches": self.total_app_launches,
            "first_launch_date": self.first_launch_date,
            "last_launch_date": self.last_launch_date,
            "total_print_batches": self.total_print_batches,
            "total_sheets_printed": self.total_sheets_printed,
            "success_sheets_count": self.success_sheets_count,
            "failed_sheets_count": self.failed_sheets_count,
            "fallback_format_count": self.fallback_format_count,
            "total_print_duration_seconds": self.total_print_duration_seconds,
            "total_scan_batches": self.total_scan_batches,
            "total_dwg_scanned": self.total_dwg_scanned,
            "total_frames_found": self.total_frames_found,
        }

    def _apply_dict(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            self._reset_to_defaults()
            return

        def _get_int(key: str, default: int = 0) -> int:
            try:
                val = data.get(key, default)
                return int(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def _get_float(key: str, default: float = 0.0) -> float:
            try:
                val = data.get(key, default)
                return float(val) if val is not None else default
            except (ValueError, TypeError):
                return default

        def _get_str(key: str, default: str = "") -> str:
            val = data.get(key, default)
            return str(val) if val is not None else default

        self.total_app_launches = _get_int("total_app_launches", DEFAULT_STATS["total_app_launches"])
        self.first_launch_date = _get_str("first_launch_date", DEFAULT_STATS["first_launch_date"])
        self.last_launch_date = _get_str("last_launch_date", DEFAULT_STATS["last_launch_date"])
        self.total_print_batches = _get_int("total_print_batches", DEFAULT_STATS["total_print_batches"])
        self.total_sheets_printed = _get_int("total_sheets_printed", DEFAULT_STATS["total_sheets_printed"])
        self.success_sheets_count = _get_int("success_sheets_count", DEFAULT_STATS["success_sheets_count"])
        self.failed_sheets_count = _get_int("failed_sheets_count", DEFAULT_STATS["failed_sheets_count"])
        self.fallback_format_count = _get_int("fallback_format_count", DEFAULT_STATS["fallback_format_count"])
        self.total_print_duration_seconds = _get_float("total_print_duration_seconds", DEFAULT_STATS["total_print_duration_seconds"])
        self.total_scan_batches = _get_int("total_scan_batches", DEFAULT_STATS["total_scan_batches"])
        self.total_dwg_scanned = _get_int("total_dwg_scanned", DEFAULT_STATS["total_dwg_scanned"])
        self.total_frames_found = _get_int("total_frames_found", DEFAULT_STATS["total_frames_found"])

    def load(self) -> bool:
        """
        Загружает данные из stats.json. При отсутствии файла инициализирует значения по умолчанию.
        При ошибке парсинга (повреждённый JSON) создаёт резервную копию .corrupted и сбрасывает данные.
        """
        with self._lock:
            if not os.path.exists(self.stats_path):
                self._reset_to_defaults()
                return True

            try:
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if not content:
                    raise ValueError("Файл stats.json пуст")
                raw_data = json.loads(content)
                if not isinstance(raw_data, dict):
                    raise ValueError("Данные stats.json не являются объектом")

                self._apply_dict(raw_data)
                return True
            except Exception as e:
                log_warn(
                    f"Файл статистики {self.stats_path} повреждён ({e}). "
                    f"Создаётся резервная копия и сбрасывается статистика.",
                    exc=e,
                    module="StatsManager"
                )
                self._backup_corrupted_file()
                self._reset_to_defaults()
                self._save_unlocked()
                return False

    def _backup_corrupted_file(self) -> None:
        """
        Создаёт резервную копию повреждённого файла stats.json.corrupted.
        """
        try:
            if os.path.exists(self.stats_path):
                corrupted_backup = f"{self.stats_path}.corrupted"
                shutil.copy2(self.stats_path, corrupted_backup)
                log_info(
                    f"Резервная копия повреждённого файла сохранена в {corrupted_backup}",
                    module="StatsManager"
                )
        except Exception as e:
            log_warn(f"Не удалось создать резервную копию повреждённого файла: {e}", exc=e, module="StatsManager")

    def save(self) -> bool:
        """
        Атомарно сохраняет текущие метрики в stats.json.
        """
        with self._lock:
            return self._save_unlocked()

    def _save_unlocked(self) -> bool:
        tmp_path = None
        try:
            dir_name = os.path.dirname(os.path.abspath(self.stats_path))
            os.makedirs(dir_name, exist_ok=True)

            data = self._to_dict()
            tmp_filename = f"{os.path.basename(self.stats_path)}.{os.getpid()}_{threading.get_ident()}_{int(time.time() * 1000)}.tmp"
            tmp_path = os.path.join(dir_name, tmp_filename)

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(tmp_path, self.stats_path)
            return True
        except Exception as e:
            log_error(f"Ошибка сохранения статистики в {self.stats_path}: {e}", exc=e, module="StatsManager")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False


# =============================================================================
# Глобальный доступ (Синглтон)
# =============================================================================

_global_stats_manager: Optional[StatsManager] = None
_instance_lock = threading.Lock()


def get_stats_manager(
    stats_path: Optional[str] = None,
    config_manager: Optional[ConfigManager] = None,
    reset_instance: bool = False
) -> StatsManager:
    """
    Возвращает глобальный экземпляр StatsManager.
    Если reset_instance=True или экземпляр ещё не был создан, создаёт новый.
    Если передан stats_path, создаёт независимый экземпляр StatsManager.
    """
    global _global_stats_manager
    with _instance_lock:
        if stats_path is not None:
            return StatsManager(stats_path=stats_path, config_manager=config_manager)
        if _global_stats_manager is None or reset_instance:
            _global_stats_manager = StatsManager(config_manager=config_manager)
        return _global_stats_manager
