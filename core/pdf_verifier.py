"""
Модуль валидации и проверки качества выходных PDF-файлов (core/pdf_verifier.py).

Проверяет реальные PDF, созданные AutoCAD (или сторонними плоттерами):
- Соответствие общего количества страниц количеству выбранных рамок;
- Физические размеры страниц в миллиметрах по ГОСТ 2.301-68 (A4..A0, кратные A4x3..A0x3);
- Ориентацию страниц (Альбомная / Книжная);
- Отсутствие пустых/поврежденных страниц (проверка векторных операторов и текста);
- Правильный порядок страниц в многостраничном томе;
- Соответствие номеров/названий листов при наличии текстового слоя.
"""

from dataclasses import dataclass, field
import os
import re
from typing import List, Optional, Tuple, Dict, Any

from pypdf import PdfReader
from core.models import ALL_FORMATS, Frame, natural_sheet_sort_key
from core.logger import get_logger

logger = get_logger("pdf_verifier")

# Регулярное выражение для поиска векторных операторов PDF в потоке содержимого:
# m/l/c/v/y/re - построение путей
# S/s/f/F/B/b - обводка и заливка
# Do - размещение XObject (растровые изображения, вложенные формы)
# sh - шейдинг
# BT/ET/Tj/TJ - текстовые операторы
DRAWING_OPS_PATTERN = re.compile(rb'(?:^|\s)(?:m|l|c|v|y|re|S|s|f|F|B|b|Do|sh|BT|Tj|TJ)(?:\s|$)')


@dataclass
class PageVerificationInfo:
    """Результаты проверки отдельной страницы PDF"""
    page_index: int                       # 0-based индекс страницы
    page_number: int                      # 1-based номер страницы в PDF
    width_mm: float                       # Ширина страницы в мм
    height_mm: float                      # Высота страницы в мм
    matched_format: Optional[str]         # Распознанный формат ГОСТ (напр. "A3", "A2", "A3x3") или None
    orientation: str                      # "Landscape" или "Portrait"
    is_blank: bool                        # True, если на странице нет видимой графики/текста
    stream_bytes_count: int = 0           # Объем байтов графического потока
    drawing_ops_count: int = 0            # Количество векторных операторов рисования
    text_content: str = ""                # Извлеченный текст страницы
    expected_sheet_number: str = ""       # Ожидаемый номер листа
    expected_sheet_name: str = ""         # Ожидаемое название листа
    expected_format: str = ""             # Ожидаемый формат
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0


@dataclass
class PdfVerificationReport:
    """Итоговый отчет проверки PDF-документа"""
    pdf_path: str
    total_pages: int = 0
    pages: List[PageVerificationInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    bookmarks: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0 and all(p.is_valid for p in self.pages)

    @property
    def blank_pages(self) -> List[int]:
        """Номера пустых страниц (1-based)"""
        return [p.page_number for p in self.pages if p.is_blank]

    @property
    def mismatched_formats(self) -> List[Tuple[int, str, str]]:
        """Список (номер страницы, факт_формат, ожид_формат) для несовпадений"""
        res = []
        for p in self.pages:
            if p.expected_format and p.matched_format != p.expected_format:
                res.append((p.page_number, p.matched_format or "Неизвестен", p.expected_format))
        return res

    def summary(self) -> str:
        """Формирует понятный текстовый отчет для пользователя или логов"""
        lines = [
            f"Отчет проверки PDF: {os.path.basename(self.pdf_path)}",
            f"Всего страниц: {self.total_pages}",
            f"Статус: {'ГОДЕН (ОК)' if self.is_valid else 'ЕСТЬ ОШИБКИ'}"
        ]
        if self.errors:
            lines.append("Критические ошибки:")
            for err in self.errors:
                lines.append(f"  ❌ {err}")
        if self.warnings:
            lines.append("Предупреждения:")
            for w in self.warnings:
                lines.append(f"  ⚠️ {w}")
        if self.bookmarks:
            bm_preview = ", ".join(f"«{b}»" for b in self.bookmarks[:4])
            if len(self.bookmarks) > 4:
                bm_preview += f" ... (еще {len(self.bookmarks) - 4})"
            lines.append(f"Закладки ({len(self.bookmarks)} шт.): {bm_preview}")
        if self.metadata:
            meta_parts = []
            for k in ("/Title", "/Author", "/Subject", "/Creator"):
                if k in self.metadata and self.metadata[k]:
                    meta_parts.append(f"{k.lstrip('/')}={self.metadata[k]}")
            if meta_parts:
                lines.append(f"Метаданные: {'; '.join(meta_parts)}")
        for p in self.pages:
            fmt_str = p.matched_format or f"Пользовательский ({p.width_mm:.1f}x{p.height_mm:.1f})"
            status_ico = "✅" if p.is_valid else "❌"
            line = f"  {status_ico} Стр. {p.page_number}: {fmt_str} ({p.orientation}, {p.width_mm:.1f}x{p.height_mm:.1f} мм)"
            if p.is_blank:
                line += " [ПУСТАЯ!]"
            lines.append(line)
            for pe in p.errors:
                lines.append(f"      - Ошибка: {pe}")
            for pw in p.warnings:
                lines.append(f"      - Предупреждение: {pw}")
        return "\n".join(lines)


def detect_page_format(width_mm: float, height_mm: float, tolerance_mm: float = 3.0) -> Optional[str]:
    """
    Определяет ГОСТ-формат бумаги по физическим размерам страницы в мм.
    Сравнивает длинную и короткую сторону с базой ALL_FORMATS.
    Возвращает имя формата (например 'A3', 'A4', 'A3x3') или None, если формат нестандартный.
    """
    long_side = max(width_mm, height_mm)
    short_side = min(width_mm, height_mm)

    best_match = None
    min_diff = float("inf")

    for fmt, (fw, fh) in ALL_FORMATS.items():
        diff_long = abs(long_side - fw)
        diff_short = abs(short_side - fh)
        if diff_long <= tolerance_mm and diff_short <= tolerance_mm:
            total_diff = diff_long + diff_short
            if total_diff < min_diff:
                min_diff = total_diff
                best_match = fmt

    return best_match


def extract_page_streams(page: Any) -> bytes:
    """Извлекает и объединяет декодированные байты всех потоков /Contents страницы"""
    contents = page.get('/Contents')
    if contents is None:
        return b""
    raw_streams = []
    if isinstance(contents, list):
        for item in contents:
            obj = item.get_object() if hasattr(item, 'get_object') else item
            if hasattr(obj, 'get_data'):
                try:
                    raw_streams.append(obj.get_data())
                except Exception as e:
                    logger.debug(f"Ошибка чтения потока /Contents: {e}")
    else:
        obj = contents.get_object() if hasattr(contents, 'get_object') else contents
        if hasattr(obj, 'get_data'):
            try:
                raw_streams.append(obj.get_data())
            except Exception as e:
                logger.debug(f"Ошибка чтения потока /Contents: {e}")
    return b"\n".join(raw_streams)


def is_page_blank(page: Any) -> Tuple[bool, int, int, str]:
    """
    Проверяет, является ли страница пустой.
    Возвращает (is_blank, stream_bytes_count, drawing_ops_count, extracted_text).
    """
    extracted_text = ""
    try:
        extracted_text = (page.extract_text() or "").strip()
    except Exception as e:
        logger.debug(f"Ошибка извлечения текста: {e}")

    # Если есть читаемый текст — страница гарантированно не пустая
    if len(extracted_text) > 0:
        return False, 0, 0, extracted_text

    # Извлекаем графический поток
    stream_bytes = extract_page_streams(page)
    stream_len = len(stream_bytes)

    if stream_len == 0:
        return True, 0, 0, ""

    # Подсчитываем количество векторных операторов рисования в потоке
    ops_matches = len(DRAWING_OPS_PATTERN.findall(stream_bytes))

    # Если операторов рисования нет (или только тривиальный блок состояния q Q), страница пустая
    is_blank = (ops_matches == 0)
    return is_blank, stream_len, ops_matches, extracted_text


def verify_pdf(
    pdf_path: str,
    expected_frames: Optional[List[Frame]] = None,
    tolerance_mm: float = 3.5
) -> PdfVerificationReport:
    """
    Выполняет полную проверку PDF-документа:
    - Проверка существования и целостности файла;
    - Проверка количества страниц против expected_frames;
    - Для каждой страницы: физический размер (мм), формат ГОСТ, ориентация, пустая ли страница;
    - Проверка порядка листов;
    - Поиск соответствия текстовых атрибутов (если в PDF есть векторный текст).
    """
    report = PdfVerificationReport(pdf_path=pdf_path)

    if not os.path.exists(pdf_path):
        report.errors.append(f"Файл не найден: {pdf_path}")
        return report

    if os.path.getsize(pdf_path) == 0:
        report.errors.append(f"Файл пуст (0 байт): {pdf_path}")
        return report

    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        report.errors.append(f"Не удалось открыть PDF-файл (файл поврежден): {e}")
        return report

    report.total_pages = len(reader.pages)

    try:
        report.metadata = {str(k): str(v) for k, v in (reader.metadata or {}).items()}
    except Exception:
        pass

    try:
        if reader.outline:
            def extract_outline(items):
                titles = []
                for it in items:
                    if isinstance(it, list):
                        titles.extend(extract_outline(it))
                    elif hasattr(it, "title"):
                        titles.append(str(it.title))
                return titles
            report.bookmarks = extract_outline(reader.outline)
    except Exception:
        pass

    if report.total_pages == 0:
        report.errors.append("В PDF-файле отсутствуют страницы (0 страниц)")
        return report

    # 1. Проверка общего количества страниц
    if expected_frames is not None:
        if report.total_pages != len(expected_frames):
            report.errors.append(
                f"Не совпадает количество страниц: ожидалось {len(expected_frames)}, в PDF {report.total_pages}"
            )

    # 2. Постраничная проверка
    for idx, page in enumerate(reader.pages):
        page_num = idx + 1
        box = page.mediabox if page.mediabox else page.cropbox
        width_pt = float(box.width)
        height_pt = float(box.height)
        if page.rotation % 180 == 90:
            width_pt, height_pt = height_pt, width_pt

        # 1 pt = 25.4 / 72.0 мм (~0.352778 мм)
        w_mm = round(width_pt * 25.4 / 72.0, 1)
        h_mm = round(height_pt * 25.4 / 72.0, 1)
        orientation = "Landscape" if w_mm >= h_mm else "Portrait"
        matched_format = detect_page_format(w_mm, h_mm, tolerance_mm=tolerance_mm)

        blank, stream_bytes, drawing_ops, text = is_page_blank(page)

        page_info = PageVerificationInfo(
            page_index=idx,
            page_number=page_num,
            width_mm=w_mm,
            height_mm=h_mm,
            matched_format=matched_format,
            orientation=orientation,
            is_blank=blank,
            stream_bytes_count=stream_bytes,
            drawing_ops_count=drawing_ops,
            text_content=text
        )

        if blank:
            page_info.errors.append(f"Страница {page_num} пустая (нет графики и текста)")

        # Проверка против ожидаемой рамки
        if expected_frames and idx < len(expected_frames):
            expected = expected_frames[idx]
            page_info.expected_sheet_number = expected.sheet_number
            page_info.expected_sheet_name = expected.sheet_name
            page_info.expected_format = expected.paper_format

            # Проверка формата
            if expected.paper_format:
                if matched_format != expected.paper_format:
                    page_info.errors.append(
                        f"Неверный формат: определен '{matched_format or 'Неизвестен'}', "
                        f"ожидался '{expected.paper_format}'"
                    )

            # Проверка ориентации по координатам рамки
            fw = abs(expected.max_point[0] - expected.min_point[0])
            fh = abs(expected.max_point[1] - expected.min_point[1])
            expected_orientation = "Landscape" if fw >= fh else "Portrait"
            if orientation != expected_orientation:
                page_info.errors.append(
                    f"Неверная ориентация: '{orientation}', ожидалась '{expected_orientation}'"
                )

            # Проверка наличия номера листа в тексте (если в PDF есть распознаваемый текст)
            if text and expected.sheet_number:
                # Ищем номер листа в тексте
                if expected.sheet_number not in text:
                    page_info.warnings.append(
                        f"Номер листа '{expected.sheet_number}' не найден в текстовом слое страницы"
                    )

        elif not matched_format:
            page_info.warnings.append(
                f"Размер страницы {w_mm:.1f}x{h_mm:.1f} мм не соответствует стандартным форматам ГОСТ"
            )

        report.pages.append(page_info)

    logger.info(f"Проверка PDF '{os.path.basename(pdf_path)}': валиден={report.is_valid}, страниц={report.total_pages}")
    return report
