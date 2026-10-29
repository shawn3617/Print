import os
import re
import json
import time
import tempfile
from abc import ABC, abstractmethod
from typing import List, Any

from core.models import Frame
from core.com_utils import com_retry


def lisp_str(s: str) -> str:
    """Строка для вставки в LISP-выражение: прямые слэши, экранированные кавычки.
    Обратный слэш в строке AutoLISP — служебный символ: путь вида C:\\Users\\...\\_MEI123\\core
    (так выглядят пути внутри exe) ломается, и load не находит файл."""
    return str(s).replace("\\", "/").replace('"', '\\"')


class BaseParser(ABC):
    """
    Абстрактный базовый класс для всех парсеров рамок.
    Реализует паттерн Strategy для различных алгоритмов поиска.
    Общие помощники для LISP-экспорта: активация чертежа, ожидание AutoCAD, запуск и чтение JSON.
    """

    # Сколько ждать JSON от LISP. Обычно 0.05–0.5 сек, но первый запуск exe,
    # большой чертеж или антивирус могут растянуть это до нескольких секунд.
    LISP_TIMEOUT = 20.0

    @abstractmethod
    def find_frames(self, doc: Any) -> List[Frame]:
        """
        Ищет рамки в чертеже.

        :param doc: COM-объект документа AutoCAD
        :return: Список найденных рамок (объектов Frame)
        """
        pass

    # ------------------------------------------------------------------ помощники

    @staticmethod
    def _load_sanitized_json(filepath: str) -> list:
        """Считывает JSON (LISP пишет в ANSI/cp1251), заменяя спецсимволы AutoCAD \\U+XXXX
        на Unicode и экранируя одиночные обратные слэши."""
        with open(filepath, "r", encoding="cp1251") as f:
            text = f.read()
        clean = re.sub(r'\\U\+([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            clean = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu]|u[0-9a-fA-F]{4})', r'\\\\', clean)
            return json.loads(clean)

    @staticmethod
    def _wait_acad_idle(doc: Any, timeout: float = 10.0) -> bool:
        """Ждёт, пока AutoCAD освободится (нет активной команды, не открывается чертеж)."""
        try:
            app = doc.Application
        except Exception:
            return False
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            try:
                if app.GetAcadState().IsQuiescent:
                    return True
            except Exception:
                pass  # AutoCAD занят и отклоняет COM-вызов — ждём
            time.sleep(0.05)
        return False

    @staticmethod
    def _activate_doc(doc: Any) -> None:
        """Делает чертеж активным: команда из SendCommand выполняется в активном чертеже,
        а переключение после Documents.Open происходит не мгновенно."""
        def _do():
            app = doc.Application
            try:
                same = app.ActiveDocument.FullName.lower() == doc.FullName.lower()
            except Exception:
                same = False
            if not same:
                app.ActiveDocument = doc
        try:
            com_retry(_do, max_attempts=15, delay=0.2)
        except Exception as e:
            print(f"Предупреждение: не удалось активировать чертеж перед LISP-экспортом: {e}")

    def _run_lisp_export(self, doc: Any, lisp_path: str, func_name: str,
                         args: List[str] = None, prefix: str = "acad_export") -> list:
        """
        Загружает LISP-файл в чертеже doc, вызывает (func_name "файл.json" args...)
        и возвращает прочитанный JSON-список.
        Бросает исключение, если файл LISP не найден или ответ не пришёл за LISP_TIMEOUT.
        """
        if not os.path.exists(lisp_path):
            raise FileNotFoundError(
                f"LISP-скрипт не найден: {lisp_path} "
                f"(для exe папка core/lisp должна быть добавлена в сборку: --add-data \"core/lisp;core/lisp\")")

        temp_json = os.path.join(tempfile.gettempdir(),
                                 f"{prefix}_{os.getpid()}_{time.time_ns()}.json")
        if os.path.exists(temp_json):
            try:
                os.remove(temp_json)
            except Exception:
                pass

        call_args = " ".join(f'"{lisp_str(a)}"' for a in [temp_json] + list(args or []))
        lisp_cmd = f'(progn (load "{lisp_str(lisp_path)}") ({func_name} {call_args}) (princ))\n'

        try:
            self._activate_doc(doc)
            self._wait_acad_idle(doc)
            com_retry(lambda: doc.SendCommand(lisp_cmd), max_attempts=20, delay=0.25)

            end = time.perf_counter() + self.LISP_TIMEOUT
            while time.perf_counter() < end:
                time.sleep(0.05)
                if os.path.exists(temp_json) and os.path.getsize(temp_json) > 0:
                    try:
                        return self._load_sanitized_json(temp_json)
                    except (json.JSONDecodeError, PermissionError, UnicodeDecodeError):
                        pass  # файл ещё дописывается
            raise TimeoutError(
                f"AutoCAD не вернул данные ({func_name}) за {self.LISP_TIMEOUT:.0f} сек. "
                f"Посмотрите сообщение об ошибке в командной строке AutoCAD.")
        finally:
            if os.path.exists(temp_json):
                try:
                    os.remove(temp_json)
                except Exception:
                    pass
