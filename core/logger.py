"""
Модуль логирования и диагностики PrintPDF.
Обеспечивает:
1. Запись журнала в файл с автоматической ротацией (app.log, до 5 МБ, 3 копии).
2. Хранение последних сообщений в памяти для окна «Диагностика».
3. Формирование отчёта для разработчика (версии, окружение, последние ошибки).
"""

import collections
import logging
from logging.handlers import RotatingFileHandler
import os
import platform
import sys
import tempfile
import threading
from typing import Any, Dict, List, Optional


LOG_BUFFER_SIZE = 1000
_log_buffer = collections.deque(maxlen=LOG_BUFFER_SIZE)
_buffer_lock = threading.Lock()
_root_logger_initialized = False
_log_file_path: Optional[str] = None


class MemoryBufferHandler(logging.Handler):
    """Хендлер для сохранения логов в кольцевой буфер памяти (для окна Диагностика)."""

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            with _buffer_lock:
                _log_buffer.append({
                    "time": record.created,
                    "level": record.levelname,
                    "name": record.name,
                    "text": msg
                })
        except Exception:
            self.handleError(record)


def _determine_log_dir() -> str:
    """Определяет подходящую папку для хранения логов с проверкой прав на запись."""
    # 1. Если установлено стандартно через Inno Setup
    local_appdata = os.environ.get("LOCALAPPDATA", "")
    if local_appdata:
        appdata_log_dir = os.path.join(local_appdata, "PrintPDF", "logs")
        try:
            os.makedirs(appdata_log_dir, exist_ok=True)
            test_file = os.path.join(appdata_log_dir, ".perm_test")
            with open(test_file, "w") as f:
                f.write("1")
            os.remove(test_file)
            return appdata_log_dir
        except Exception:
            pass

    # 2. Портативная версия или режим разработки — папка logs рядом с exe/проектом
    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    portable_log_dir = os.path.join(base_dir, "logs")
    try:
        os.makedirs(portable_log_dir, exist_ok=True)
        test_file = os.path.join(portable_log_dir, ".perm_test")
        with open(test_file, "w") as f:
            f.write("1")
        os.remove(test_file)
        return portable_log_dir
    except Exception:
        pass

    # 3. Резервный вариант — системная временная папка
    temp_log_dir = os.path.join(tempfile.gettempdir(), "PrintPDF", "logs")
    os.makedirs(temp_log_dir, exist_ok=True)
    return temp_log_dir


def init_logging(log_level: int = logging.INFO) -> str:
    """
    Инициализирует глобальную систему логирования:
    - Консольный вывод (если есть консоль);
    - Файловый логгер с ротацией (app.log);
    - Буфер в оперативной памяти.
    Возвращает абсолютный путь к активному файлу лога.
    """
    global _root_logger_initialized, _log_file_path
    if _root_logger_initialized and _log_file_path:
        return _log_file_path

    log_dir = _determine_log_dir()
    _log_file_path = os.path.join(log_dir, "app.log")

    logger = logging.getLogger("PrintPDF")
    logger.setLevel(log_level)
    logger.propagate = False

    # Форматтер: [2026-11-10 11:35:00] [INFO] [Module] Сообщение
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Файловый хэндлер с ротацией (5 МБ на файл, храним до 3 архивных копий)
    try:
        file_handler = RotatingFileHandler(
            _log_file_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"[Logger] Не удалось создать файловый лог {_log_file_path}: {e}")

    # 2. Консольный хэндлер (stdout)
    if sys.stdout is not None:
        try:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.setLevel(log_level)
            stream_handler.setFormatter(formatter)
            logger.addHandler(stream_handler)
        except Exception:
            pass

    # 3. Хэндлер оперативной памяти (для окна диагностики)
    memory_handler = MemoryBufferHandler()
    memory_handler.setLevel(log_level)
    memory_handler.setFormatter(formatter)
    logger.addHandler(memory_handler)

    _root_logger_initialized = True
    return _log_file_path


def get_logger(name: str = "") -> logging.Logger:
    """Возвращает дочерний или корневой логгер приложения PrintPDF."""
    if not _root_logger_initialized:
        init_logging()
    if not name or name == "PrintPDF":
        return logging.getLogger("PrintPDF")
    return logging.getLogger(f"PrintPDF.{name}")


def log_info(msg: str, module: str = "App") -> None:
    """Записывает информационное сообщение."""
    get_logger(module).info(msg)


def log_warn(msg: str, exc: Optional[Exception] = None, module: str = "App") -> None:
    """Записывает предупреждение, опционально с объектом исключения."""
    if exc:
        get_logger(module).warning(f"{msg}: {type(exc).__name__}: {exc}")
    else:
        get_logger(module).warning(msg)


def log_error(msg: str, exc: Optional[Exception] = None, module: str = "App") -> None:
    """Записывает ошибку, опционально с объектом исключения."""
    if exc:
        get_logger(module).error(f"{msg}: {type(exc).__name__}: {exc}")
    else:
        get_logger(module).error(msg)


def get_recent_logs(max_lines: int = 200, level_filter: Optional[str] = None) -> List[str]:
    """Возвращает список последних отформатированных строк журнала."""
    with _buffer_lock:
        items = list(_log_buffer)

    if level_filter:
        level_filter = level_filter.upper()
        items = [x for x in items if x["level"] == level_filter]

    if max_lines and len(items) > max_lines:
        items = items[-max_lines:]

    return [x["text"] for x in items]


def get_log_file_path() -> str:
    """Возвращает путь к активному файлу лога."""
    if not _log_file_path:
        init_logging()
    return _log_file_path or ""


def clear_log_buffer() -> None:
    """Очищает буфер журнала в оперативной памяти."""
    with _buffer_lock:
        _log_buffer.clear()


def build_diagnostic_report(extra_info: Optional[Dict[str, Any]] = None) -> str:
    """
    Формирует полный отчёт о системе, программе и последних событиях для разработчика.
    """
    from core.version import APP_VERSION, APP_RELEASE_DATE

    extra = extra_info or {}
    lines = [
        "=======================================================",
        f"PrintPDF — Отчёт диагностики для разработчика",
        f"Дата и время: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', (), None), '%Y-%m-%d %H:%M:%S')}",
        "=======================================================",
        f"Версия программы:  v{APP_VERSION} ({APP_RELEASE_DATE})",
        f"Операционная система: Windows {platform.release()} ({platform.architecture()[0]}, сборка {platform.version()})",
        f"Интерпретатор:     Python {platform.python_version()}",
        f"Режим запуска:     {'Скомпилированный (EXE)' if getattr(sys, 'frozen', False) else 'Исходный код (Python)'}",
        f"Файл лога:         {get_log_file_path()}",
    ]

    # Данные об AutoCAD
    acad_status = extra.get("acad_status", "Не подключено")
    doc_name = extra.get("doc_name", "—")
    lines.extend([
        f"Статус AutoCAD:    {acad_status}",
        f"Активный чертёж:   {doc_name}",
        f"Выбранный принтер: {extra.get('printer', '—')}",
        f"Стиль печати:      {extra.get('plot_style', '—')}",
        f"Резервный формат:  {extra.get('fallback_paper', '—')}",
    ])

    lines.append("=======================================================")
    lines.append("ПОСЛЕДНИЕ СОБЫТИЯ ЖУРНАЛА (до 150 строк):")
    lines.append("=======================================================")

    recent = get_recent_logs(max_lines=150)
    if recent:
        lines.extend(recent)
    else:
        lines.append("(Журнал пуст)")

    lines.append("=======================================================")
    lines.append("КОНЕЦ ОТЧЁТА")
    lines.append("=======================================================")

    return "\n".join(lines)
