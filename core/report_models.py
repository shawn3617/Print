"""
Модели данных для итоговых отчётов сканирования и печати (PrintPDF).
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple
from core.models import Frame


@dataclass
class PrintItemResult:
    frame: Frame
    success: bool
    error: str = ""
    output_file: str = ""
    fallback_used: bool = False
    fallback_format: str = ""
    dwg_name: str = ""
    sheet_number: str = ""
    sheet_name: str = ""
    skipped: bool = False


@dataclass
class PrintReport:
    total_requested: int = 0
    success_count: int = 0
    failed_count: int = 0
    fallback_count: int = 0
    skipped_count: int = 0
    cancelled: bool = False
    duration_seconds: float = 0.0
    output_path: str = ""
    is_merged: bool = False
    printer_name: str = ""
    style_name: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    items: List[PrintItemResult] = field(default_factory=list)
    unopened_dwgs: List[Tuple[str, str]] = field(default_factory=list)

    @property
    def failed_frames(self) -> List[Frame]:
        return [it.frame for it in self.items if not it.success and not it.skipped]

    @property
    def skipped_frames(self) -> List[Frame]:
        return [it.frame for it in self.items if it.skipped]

    @property
    def repeatable_frames(self) -> List[Frame]:
        """Листы, которые можно повторить (с ошибкой или пропущенные/отмененные)."""
        return [it.frame for it in self.items if not it.success]

    @property
    def fallback_frames(self) -> List[Frame]:
        return [it.frame for it in self.items if it.fallback_used]

    def build_text_report(self) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("ОТЧЁТ О ПАКЕТНОЙ ПЕЧАТИ (PrintPDF)")
        lines.append("=" * 80)
        lines.append(f"Дата и время:     {self.timestamp}")
        lines.append(f"Длительность:     {self.duration_seconds:.1f} сек")
        mode_str = "Единый многостраничный PDF" if self.is_merged else "Отдельные PDF-файлы"
        lines.append(f"Режим печати:     {mode_str}")
        lines.append(f"Плоттер:          {self.printer_name or '—'}")
        lines.append(f"Стиль печати:     {self.style_name or '—'}")
        lines.append(f"Выходной путь:    {self.output_path or '—'}")
        if self.cancelled:
            lines.append("Статус:           ⚠️ ОСТАНОВЛЕНО ПОЛЬЗОВАТЕЛЕМ")
        elif self.failed_count > 0:
            lines.append("Статус:           ⚠️ ЗАВЕРШЕНО С ОШИБКАМИ")
        elif self.fallback_count > 0:
            lines.append("Статус:           ⚠️ ЗАВЕРШЕНО С ПРЕДУПРЕЖДЕНИЯМИ (применён резервный формат)")
        else:
            lines.append("Статус:           ✓ УСПЕШНО ЗАВЕРШЕНО")
        lines.append("-" * 80)
        lines.append("СВОДКА:")
        lines.append(f"• Всего запрошено листов: {self.total_requested}")
        lines.append(f"• Успешно напечатано:     {self.success_count}")
        lines.append(f"• Ошибок печати:          {self.failed_count}")
        lines.append(f"• С резервным форматом:   {self.fallback_count}")
        lines.append(f"• Пропущено / отменено:   {self.skipped_count}")
        if self.unopened_dwgs:
            lines.append(f"• Не удалось открыть DWG: {len(self.unopened_dwgs)}")
            for dwg, err in self.unopened_dwgs:
                lines.append(f"    - {dwg}: {err}")
        lines.append("-" * 80)
        lines.append("ДЕТАЛИЗАЦИЯ ПО ЛИСТАМ:")
        for idx, it in enumerate(self.items, 1):
            num = it.sheet_number or "б/н"
            name = it.sheet_name or "Без имени"
            dwg = it.dwg_name or ""
            dwg_str = f" [{dwg}]" if dwg else ""
            if it.skipped:
                status_icon = "[⚪ ПРОПУЩЕН]"
                extra = "Отменено пользователем"
            elif it.success:
                status_icon = "[✓ УСПЕХ]"
                if it.fallback_used:
                    extra = f"Формат {it.frame.paper_format} ➔ резервный {it.fallback_format}"
                else:
                    extra = f"Формат {it.frame.paper_format}"
            else:
                status_icon = "[✗ ОШИБКА]"
                extra = f"Ошибка: {it.error}"
            lines.append(f"{idx:03d}. {status_icon} Лист {num} — {name}{dwg_str} ({extra})")
        lines.append("=" * 80)
        return "\n".join(lines)


@dataclass
class ScanFileResult:
    file_path: str
    file_name: str
    success: bool
    error: str = ""
    frames_count: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class ScanReport:
    total_files: int = 0
    success_files_count: int = 0
    failed_files_count: int = 0
    empty_files_count: int = 0
    total_frames_found: int = 0
    duration_seconds: float = 0.0
    cancelled: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    file_results: List[ScanFileResult] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return any(result.warnings for result in self.file_results)

    def build_text_report(self) -> str:
        lines = []
        lines.append("=" * 80)
        lines.append("ОТЧЁТ О СКАНИРОВАНИИ ЧЕРТЕЖЕЙ (PrintPDF)")
        lines.append("=" * 80)
        lines.append(f"Дата и время:     {self.timestamp}")
        lines.append(f"Длительность:     {self.duration_seconds:.1f} сек")
        lines.append(f"Всего файлов DWG: {self.total_files}")
        lines.append(f"Успешно открыто:  {self.success_files_count}")
        lines.append(f"Ошибок открытия:  {self.failed_files_count}")
        lines.append(f"Файлов без рамок: {self.empty_files_count}")
        lines.append(f"Всего рамок найдено: {self.total_frames_found}")
        lines.append("-" * 80)
        lines.append("ДЕТАЛИЗАЦИЯ ПО ФАЙЛАМ:")
        for idx, fr in enumerate(self.file_results, 1):
            if fr.success:
                if fr.frames_count > 0:
                    status = f"[✓] Найдено рамок: {fr.frames_count}"
                else:
                    status = "[⚠️] Рамки не найдены"
            else:
                status = f"[✗] Ошибка: {fr.error}"
            lines.append(f"{idx:02d}. {status} — {fr.file_name} ({fr.file_path})")
            lines.extend(f"    {warning}" for warning in fr.warnings)
        lines.append("=" * 80)
        return "\n".join(lines)
