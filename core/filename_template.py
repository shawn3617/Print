"""
Шаблонизатор имён выходных PDF-файлов.

Позволяет пользователю задавать шаблон имени файла с подстановкой переменных
из данных рамки (Frame), поддерживает форматирование с нулевым дополнением,
очистку от недопустимых символов и разрешение дубликатов.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields as dc_fields
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. Словарь переменных шаблона
# ---------------------------------------------------------------------------

TEMPLATE_VARIABLES: Dict[str, str] = {
    "Шифр": "doc_code",
    "Номер": "sheet_number",
    "Наименование": "sheet_name",
    "Формат": "paper_format",
    "DWG": "dwg_name",          # без расширения
    "Объект": "object_name",
    "Здание": "building_name",
    "Масштаб": "scale",
}

# ---------------------------------------------------------------------------
# 2. Предустановленные шаблоны
# ---------------------------------------------------------------------------

PRESET_TEMPLATES: List[Tuple[str, str]] = [
    ("Лист №_Наименование",          "Лист {Номер} - {Наименование}"),
    ("Шифр_Лист №",                  "{Шифр}_Лист {Номер}"),
    ("Шифр_Номер_Наименование",      "{Шифр}_{Номер}_{Наименование}"),
    ("DWG_Лист №_Наименование",      "{DWG}_Лист {Номер} - {Наименование}"),
    ("Номер. Наименование (Формат)", "{Номер}. {Наименование} ({Формат})"),
]

# Значения-заглушки, используемые когда реальное значение пустое / None
_FALLBACKS: Dict[str, str] = {
    "Шифр": "Без_шифра",
    "Номер": "б-н",
    "Наименование": "Без_имени",
    "Формат": "A3",
    "DWG": "Чертёж",
    "Объект": "Без_объекта",
    "Здание": "Без_здания",
    "Масштаб": "100",
}

# Демо-данные для предпросмотра в UI (preview_filename без frame)
_EXAMPLE_DATA: Dict[str, str] = {
    "Шифр": "1234-АР",
    "Номер": "1",
    "Наименование": "План 1 этажа",
    "Формат": "A3",
    "DWG": "Plans",
    "Объект": "Жилой дом",
    "Здание": "Корпус 1",
    "Масштаб": "100",
}

# Регулярное выражение для разбора плейсхолдеров вида {Имя} или {Имя:02d}
_PLACEHOLDER_RE = re.compile(r"\{(\w+)(?::(\d+)d)?\}")

# Символы, запрещённые в именах файлов Windows
_ILLEGAL_CHARS_RE = re.compile(r'[\\/:*?"<>|]')


# ---------------------------------------------------------------------------
# 3. sanitize_filename
# ---------------------------------------------------------------------------

def sanitize_filename(name: str, max_len: int = 200) -> str:
    """Очистка строки для безопасного использования в качестве имени файла.

    - Удаляет/заменяет недопустимые символы файловой системы
      (``\\ / : * ? " < > |``).
    - Схлопывает множественные пробелы и подчёркивания.
    - Убирает ведущие/завершающие точки и пробелы.
    - Обрезает до *max_len* символов.
    - Допускает кириллицу, латиницу, цифры, пробелы, дефисы, подчёркивания,
      точки и круглые скобки.
    """
    # Убираем запрещённые символы
    name = _ILLEGAL_CHARS_RE.sub("", name)

    # Схлопываем множественные пробелы
    name = re.sub(r" {2,}", " ", name)

    # Схлопываем множественные подчёркивания
    name = re.sub(r"_{2,}", "_", name)

    # Убираем ведущие/завершающие точки и пробелы
    name = name.strip(". ")

    # Обрезаем до max_len
    if len(name) > max_len:
        name = name[:max_len].rstrip(". ")

    return name


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _strip_dwg_extension(dwg_name: str) -> str:
    """Убирает расширение ``.dwg`` (без учёта регистра) из имени файла."""
    if dwg_name.lower().endswith(".dwg"):
        return dwg_name[:-4]
    return dwg_name


def _get_frame_value(var_name: str, frame: Any, dwg_name: str = "") -> str:
    """Извлекает значение переменной из объекта *frame*.

    Для переменной ``DWG`` дополнительно убирает расширение.
    Если значение пустое или ``None`` — возвращает заглушку из ``_FALLBACKS``.
    """
    attr = TEMPLATE_VARIABLES.get(var_name)
    if attr is None:
        return var_name  # неизвестная переменная — оставляем как есть

    raw: Any = None
    if frame is not None:
        raw = getattr(frame, attr, None)

    # Для DWG: приоритет — frame.dwg_name, затем переданный dwg_name
    if var_name == "DWG":
        if not raw and dwg_name:
            raw = dwg_name
        if raw:
            raw = _strip_dwg_extension(str(raw))

    # Преобразуем в строку
    value = "" if raw is None else str(raw)

    if not value.strip():
        value = _FALLBACKS.get(var_name, "")

    return value


def _substitute(template: str, value_getter) -> str:  # noqa: ANN001
    """Подставляет значения в шаблон, поддерживая формат ``{Имя:02d}``.

    *value_getter* — callable(var_name) -> str.
    """

    def _replace(match: re.Match) -> str:
        var_name: str = match.group(1)
        pad_width: Optional[str] = match.group(2)  # e.g. "02" из "{Номер:02d}"

        value = value_getter(var_name)

        if pad_width is not None:
            width = int(pad_width)
            # Пытаемся отформатировать числовое значение с нулевым дополнением
            try:
                numeric = int(value)
                return str(numeric).zfill(width)
            except (ValueError, TypeError):
                # Не число — возвращаем как есть
                return value

        return value

    return _PLACEHOLDER_RE.sub(_replace, template)


# ---------------------------------------------------------------------------
# 4. render_filename
# ---------------------------------------------------------------------------

def render_filename(
    template: str,
    frame: Any,
    dwg_name: str = "",
    index: int = 0,
) -> str:
    """Формирует имя PDF-файла по шаблону и данным рамки.

    Параметры
    ---------
    template : str
        Строка-шаблон с плейсхолдерами ``{Переменная}``
        или ``{Переменная:02d}``.
    frame : Any
        Объект рамки (``Frame`` dataclass) с атрибутами листа.
    dwg_name : str, optional
        Имя DWG-файла (используется, если ``frame.dwg_name`` пусто).
    index : int, optional
        Порядковый индекс листа (зарезервировано для будущего использования).

    Возвращает
    ----------
    str
        Готовое имя файла с расширением ``.pdf``.
    """

    def getter(var_name: str) -> str:
        return _get_frame_value(var_name, frame, dwg_name)

    result = _substitute(template, getter)
    result = sanitize_filename(result)

    if not result:
        result = f"Лист_{index}"

    return result + ".pdf"


# ---------------------------------------------------------------------------
# 5. resolve_duplicates
# ---------------------------------------------------------------------------

def resolve_duplicates(filenames: List[str]) -> List[str]:
    """Разрешает дубликаты имён файлов добавлением суффикса ``_N``.

    Если имя встречается более одного раза, все вхождения получают
    суффикс ``_1``, ``_2``, … перед расширением ``.pdf``.
    Уникальные имена остаются без изменений.

    Пример::

        ["a.pdf", "a.pdf", "b.pdf"]  →  ["a_1.pdf", "a_2.pdf", "b.pdf"]
    """
    # Считаем, сколько раз встречается каждое имя
    count: Dict[str, int] = {}
    for fn in filenames:
        count[fn] = count.get(fn, 0) + 1

    # Определяем имена-дубликаты
    duplicates: Dict[str, int] = {}  # текущий счётчик для каждого дубликата

    result: List[str] = []
    for fn in filenames:
        if count[fn] > 1:
            # Увеличиваем счётчик для этого имени
            idx = duplicates.get(fn, 0) + 1
            duplicates[fn] = idx

            # Вставляем суффикс перед .pdf
            if fn.lower().endswith(".pdf"):
                base = fn[:-4]
                result.append(f"{base}_{idx}.pdf")
            else:
                result.append(f"{fn}_{idx}")
        else:
            result.append(fn)

    return result


# ---------------------------------------------------------------------------
# 6. get_default_template
# ---------------------------------------------------------------------------

def get_default_template() -> str:
    """Возвращает строку шаблона первого (по умолчанию) пресета."""
    return PRESET_TEMPLATES[0][1]


# ---------------------------------------------------------------------------
# 7. preview_filename
# ---------------------------------------------------------------------------

def preview_filename(template: str, frame: Optional[Any] = None) -> str:
    """Предпросмотр имени файла по шаблону.

    Если *frame* передан — используются реальные данные рамки.
    Если ``None`` — подставляются демонстрационные значения для отображения
    в пользовательском интерфейсе.

    Возвращает
    ----------
    str
        Отрендеренное имя файла (с расширением ``.pdf``).
    """
    if frame is not None:
        return render_filename(template, frame)

    # Рендерим с примерными данными
    def example_getter(var_name: str) -> str:
        return _EXAMPLE_DATA.get(var_name, _FALLBACKS.get(var_name, var_name))

    result = _substitute(template, example_getter)
    result = sanitize_filename(result)

    if not result:
        result = "Пример"

    return result + ".pdf"
