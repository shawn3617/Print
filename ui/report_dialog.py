"""
Диалоговое окно итогового отчёта после сканирования и печати (PrintPDF).
Отображает развёрнутую сводку: количество успешных листов, ошибки,
применение резервного формата, кнопки «Повторить неудачные» и «Сохранить отчёт».
"""

import os
from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QFileDialog, QApplication, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QIcon, QFont, QColor

from core.report_models import PrintReport, ScanReport, PrintItemResult, ScanFileResult
from core.resource_utils import get_resource_path
from ui.themes import THEMES, build_theme_qss, apply_title_bar_theme


class ReportDialog(QDialog):
    """
    Диалоговое окно подробного отчёта о результатах печати или сканирования.
    """
    repeat_requested = Signal(list)  # Передаёт список Frame для повторной печати

    def __init__(self, report, current_theme_id: str = "dark_catppuccin", parent=None):
        super().__init__(parent)
        self.report = report
        self.current_theme_id = current_theme_id

        is_print = isinstance(self.report, PrintReport)
        title = "Итоги пакетной печати — PrintPDF" if is_print else "Итоги сканирования чертежей — PrintPDF"
        self.setWindowTitle(title)
        self.resize(860, 580)
        self.setMinimumSize(680, 420)
        self.setModal(True)

        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(build_theme_qss(self.current_theme_id))
        self.init_ui()

    def _get_theme(self):
        return THEMES.get(self.current_theme_id, THEMES["dark_catppuccin"])

    def init_ui(self):
        theme = self._get_theme()
        accent = theme.get("accent_color", "#89b4fa")
        text_primary = theme.get("text_primary", "#cdd6f4")
        text_muted = theme.get("text_muted", "#a6adc8")
        bg_card = theme.get("bg_card", "#181825")
        border = theme.get("border", "#45475a")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Шапка (Заголовок и статус)
        header_frame = QFrame()
        header_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_card}; border: 1px solid {border}; border-radius: 8px; padding: 6px; }}"
        )
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 10, 12, 10)
        header_layout.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)

        lbl_title = QLabel()
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_vbox.addWidget(lbl_title)

        lbl_subtitle = QLabel()
        lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        lbl_subtitle.setWordWrap(True)
        title_vbox.addWidget(lbl_subtitle)

        header_layout.addLayout(title_vbox, stretch=1)
        layout.addWidget(header_frame)

        # 2. Карточки сводной статистики
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(10)
        layout.addLayout(stats_layout)

        # 3. Детализированная таблица
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {bg_card};
                border: 1px solid {border};
                border-radius: 6px;
                gridline-color: {border};
            }}
            QHeaderView::section {{
                background-color: {theme.get('bg_surface', '#313244')};
                color: {text_primary};
                padding: 4px;
                font-weight: bold;
                border: none;
            }}
        """)
        layout.addWidget(self.table, stretch=1)

        # 4. Нижняя панель действий
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.btn_repeat = QPushButton("🔁 Повторить неудачные")
        self.btn_repeat.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #11111b;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
            }}
            QPushButton:hover {{
                background-color: #b4befe;
            }}
        """)
        self.btn_repeat.clicked.connect(self.on_repeat_clicked)
        bottom_layout.addWidget(self.btn_repeat)

        self.btn_save = QPushButton("💾 Сохранить отчёт...")
        self.btn_save.setProperty("cssClass", "btn_tool")
        self.btn_save.clicked.connect(self.on_save_clicked)
        bottom_layout.addWidget(self.btn_save)

        self.btn_copy = QPushButton("📋 Скопировать")
        self.btn_copy.setProperty("cssClass", "btn_tool")
        self.btn_copy.clicked.connect(self.on_copy_clicked)
        bottom_layout.addWidget(self.btn_copy)

        self.btn_open = QPushButton("📂 Открыть результат")
        self.btn_open.setProperty("cssClass", "btn_tool")
        self.btn_open.clicked.connect(self.on_open_output_clicked)
        bottom_layout.addWidget(self.btn_open)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)

        bottom_layout.addStretch()

        btn_close = QPushButton("Закрыть")
        btn_close.setProperty("cssClass", "btn_tool")
        btn_close.setMinimumWidth(90)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        layout.addLayout(bottom_layout)

        # Заполнение данными в зависимости от типа отчета
        if isinstance(self.report, PrintReport):
            self._fill_print_report(icon_lbl, lbl_title, lbl_subtitle, stats_layout, theme)
        elif isinstance(self.report, ScanReport):
            self._fill_scan_report(icon_lbl, lbl_title, lbl_subtitle, stats_layout, theme)

    def _create_badge(self, title: str, value: int, color: str, theme: dict) -> QFrame:
        badge = QFrame()
        bg = theme.get("bg_surface", "#1e1e2e")
        badge.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid {theme.get('border', '#45475a')};
                border-radius: 6px;
                padding: 4px;
            }}
        """)
        vbox = QVBoxLayout(badge)
        vbox.setContentsMargins(10, 6, 10, 6)
        vbox.setSpacing(1)

        lbl_t = QLabel(title)
        lbl_t.setStyleSheet(f"font-size: 11px; color: {theme.get('text_muted', '#a6adc8')};")
        vbox.addWidget(lbl_t)

        lbl_v = QLabel(str(value))
        lbl_v.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {color};")
        vbox.addWidget(lbl_v)
        return badge

    def _fill_print_report(self, icon_lbl: QLabel, lbl_title: QLabel, lbl_subtitle: QLabel, stats_layout: QHBoxLayout, theme: dict):
        rep: PrintReport = self.report
        accent = theme.get("accent_color", "#89b4fa")
        text_primary = theme.get("text_primary", "#cdd6f4")

        # Настройка шапки
        if rep.cancelled:
            icon_lbl.setText("⏹️")
            lbl_title.setText("Печать остановлена пользователем")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f9e2af;")
        elif rep.failed_count > 0:
            icon_lbl.setText("⚠️")
            lbl_title.setText("Печать завершена с ошибками")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f38ba8;")
        elif rep.fallback_count > 0:
            icon_lbl.setText("ℹ️")
            lbl_title.setText("Печать завершена с предупреждениями")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f9e2af;")
        else:
            icon_lbl.setText("✅")
            lbl_title.setText("Все листы успешно напечатаны!")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #a6e3a1;")

        sub_parts = [
            f"Время: {rep.timestamp}",
            f"Длительность: {rep.duration_seconds:.1f} сек",
            f"Плоттер: {rep.printer_name or '—'}"
        ]
        if rep.output_path:
            sub_parts.append(f"Выход: {rep.output_path}")
        lbl_subtitle.setText(" • ".join(sub_parts))

        # Карточки статистики
        stats_layout.addWidget(self._create_badge("Успешно", rep.success_count, "#a6e3a1", theme))
        if rep.failed_count > 0:
            stats_layout.addWidget(self._create_badge("Ошибок", rep.failed_count, "#f38ba8", theme))
        if rep.fallback_count > 0:
            stats_layout.addWidget(self._create_badge("Резервный формат", rep.fallback_count, "#f9e2af", theme))
        if rep.skipped_count > 0:
            stats_layout.addWidget(self._create_badge("Пропущено", rep.skipped_count, "#a6adc8", theme))
        stats_layout.addStretch()

        # Таблица листов
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Статус", "Лист", "Формат", "Чертеж", "Детали / Результат"])
        self.table.setRowCount(len(rep.items))

        for row, it in enumerate(rep.items):
            # 0. Статус
            if it.skipped:
                st_text = "⚪ Пропущен"
                st_color = "#a6adc8"
            elif it.success:
                if it.fallback_used:
                    st_text = "⚠️ Резервный"
                    st_color = "#f9e2af"
                else:
                    st_text = "✓ Напечатан"
                    st_color = "#a6e3a1"
            else:
                st_text = "✗ Ошибка"
                st_color = "#f38ba8"

            item_st = QTableWidgetItem(st_text)
            item_st.setForeground(QColor(st_color))
            item_st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            # 1. Лист
            num = it.sheet_number or "б/н"
            name = it.sheet_name or ""
            sheet_title = f"{num} — {name}" if name else num
            item_sheet = QTableWidgetItem(sheet_title)
            item_sheet.setToolTip(sheet_title)

            # 2. Формат
            if it.fallback_used:
                fmt_str = f"{it.frame.paper_format} ➔ {it.fallback_format}"
            else:
                fmt_str = it.frame.paper_format or "—"
            item_fmt = QTableWidgetItem(fmt_str)
            item_fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if it.fallback_used:
                item_fmt.setToolTip(f"Применен резервный формат плоттера: {it.fallback_format}")

            # 3. Чертеж
            dwg = it.dwg_name or ""
            item_dwg = QTableWidgetItem(dwg)
            item_dwg.setToolTip(getattr(it.frame, "dwg_path", "") or dwg)

            # 4. Детали
            if it.skipped:
                detail = "Отменено пользователем"
            elif it.success:
                detail = os.path.basename(it.output_file) if it.output_file else "Готово"
            else:
                detail = it.error or "Неизвестная ошибка печати"
            item_det = QTableWidgetItem(detail)
            item_det.setToolTip(detail)

            for col_idx, item in enumerate((item_st, item_sheet, item_fmt, item_dwg, item_det)):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, col_idx, item)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Кнопка повтора
        repeatable = rep.repeatable_frames
        if repeatable:
            self.btn_repeat.setVisible(True)
            self.btn_repeat.setText(f"🔁 Повторить неудачные ({len(repeatable)})")
        else:
            self.btn_repeat.setVisible(False)

        # Кнопка открытия
        if rep.output_path and os.path.exists(rep.output_path):
            self.btn_open.setVisible(True)
        else:
            self.btn_open.setVisible(False)

    def _fill_scan_report(self, icon_lbl: QLabel, lbl_title: QLabel, lbl_subtitle: QLabel, stats_layout: QHBoxLayout, theme: dict):
        rep: ScanReport = self.report

        if rep.cancelled:
            icon_lbl.setText("⏹️")
            lbl_title.setText("Сканирование остановлено пользователем")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f9e2af;")
        elif rep.failed_files_count > 0:
            icon_lbl.setText("⚠️")
            lbl_title.setText("Сканирование завершено с предупреждениями")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #f9e2af;")
        else:
            icon_lbl.setText("✅")
            lbl_title.setText("Сканирование файлов успешно завершено")
            lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #a6e3a1;")

        lbl_subtitle.setText(f"Время: {rep.timestamp} • Длительность: {rep.duration_seconds:.1f} сек • Обработано файлов: {rep.total_files}")

        stats_layout.addWidget(self._create_badge("Файлов открыто", rep.success_files_count, "#a6e3a1", theme))
        if rep.failed_files_count > 0:
            stats_layout.addWidget(self._create_badge("Ошибок открытия", rep.failed_files_count, "#f38ba8", theme))
        if rep.empty_files_count > 0:
            stats_layout.addWidget(self._create_badge("Без рамок", rep.empty_files_count, "#f9e2af", theme))
        stats_layout.addWidget(self._create_badge("Найдено рамок", rep.total_frames_found, "#89b4fa", theme))
        stats_layout.addStretch()

        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Статус", "Файл чертежа", "Рамок найдено", "Путь к файлу / Ошибка"])
        self.table.setRowCount(len(rep.file_results))

        for row, fr in enumerate(rep.file_results):
            if not fr.success:
                st_text = "✗ Ошибка"
                st_color = "#f38ba8"
                detail = fr.error
            elif fr.frames_count == 0:
                st_text = "⚠️ Рамки не найдены"
                st_color = "#f9e2af"
                detail = fr.file_path
            else:
                st_text = "✓ Успешно"
                st_color = "#a6e3a1"
                detail = fr.file_path

            item_st = QTableWidgetItem(st_text)
            item_st.setForeground(QColor(st_color))
            item_st.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_name = QTableWidgetItem(fr.file_name)
            item_name.setToolTip(fr.file_path)

            item_cnt = QTableWidgetItem(str(fr.frames_count))
            item_cnt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            item_det = QTableWidgetItem(detail)
            item_det.setToolTip(detail)

            for col_idx, item in enumerate((item_st, item_name, item_cnt, item_det)):
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.table.setItem(row, col_idx, item)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        self.btn_repeat.setVisible(False)
        self.btn_open.setVisible(False)

    def on_repeat_clicked(self):
        if isinstance(self.report, PrintReport):
            repeatable = self.report.repeatable_frames
            if repeatable:
                self.repeat_requested.emit(repeatable)
                self.accept()

    def on_save_clicked(self):
        default_name = "PrintPDF_Отчёт_Печати.txt" if isinstance(self.report, PrintReport) else "PrintPDF_Отчёт_Сканирования.txt"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить отчёт в файл",
            default_name,
            "Текстовые файлы (*.txt);;Все файлы (*.*)"
        )
        if not file_path:
            return

        try:
            text = self.report.build_text_report()
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(text)
            self.lbl_status.setText(f"✓ Отчёт сохранён в {os.path.basename(file_path)}")
            QTimer.singleShot(3000, lambda: self.lbl_status.setText(""))
        except Exception as e:
            QMessageBox.critical(self, "Ошибка сохранения", f"Не удалось записать файл:\n{e}")

    def on_copy_clicked(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            text = self.report.build_text_report()
            clipboard.setText(text)
            self.btn_copy.setText("✓ Скопировано")
            self.lbl_status.setText("✓ Отчёт скопирован в буфер обмена!")
            QTimer.singleShot(2500, lambda: (self.btn_copy.setText("📋 Скопировать"), self.lbl_status.setText("")))

    def on_open_output_clicked(self):
        if isinstance(self.report, PrintReport) and self.report.output_path:
            path = self.report.output_path
            if os.path.exists(path):
                try:
                    os.startfile(path)
                except Exception as e:
                    QMessageBox.warning(self, "Ошибка", f"Не удалось открыть:\n{e}")

    def showEvent(self, event):
        super().showEvent(event)
        apply_title_bar_theme(self, getattr(self, "current_theme_id", "dark_catppuccin"))
