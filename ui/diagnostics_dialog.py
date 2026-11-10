"""
Диалоговое окно «Диагностика и статистика» PrintPDF.
Отображает журнал событий в реальном времени, локальную статистику стабильности
и эффективности, позволяет скопировать полный отчёт для разработчика
и быстро открыть папку с логами на диске.
"""

import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QFrame, QApplication, QPlainTextEdit,
    QComboBox, QCheckBox, QMessageBox, QTabWidget, QGridLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont

from core.resource_utils import get_resource_path
from core.version import APP_VERSION
from core.logger import (
    get_recent_logs,
    get_log_file_path,
    clear_log_buffer,
    build_diagnostic_report
)
from core.stats_manager import get_stats_manager
from ui.themes import THEMES, build_theme_qss, apply_title_bar_theme


class DiagnosticsDialog(QDialog):
    def __init__(
        self,
        current_theme_id: str = "dark_catppuccin",
        connector=None,
        parent=None,
        extra_info: dict = None,
        initial_tab: int = 0
    ):
        super().__init__(parent)
        self.current_theme_id = current_theme_id
        self.connector = connector
        self.extra_info = extra_info or {}
        self.stats_manager = get_stats_manager()

        self.setWindowTitle("Диагностика и статистика — PrintPDF")
        self.resize(780, 580)
        self.setMinimumSize(640, 440)
        self.setModal(False)

        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(build_theme_qss(self.current_theme_id))
        self.init_ui()

        if 0 <= initial_tab < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(initial_tab)

        self.refresh_logs()
        self.refresh_stats()

        # Таймер для автообновления списка событий каждые 1.5 сек
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._on_timer_refresh)
        self.refresh_timer.start(1500)

    def _get_theme(self):
        return THEMES.get(self.current_theme_id, THEMES["dark_catppuccin"])

    def showEvent(self, event):
        super().showEvent(event)
        apply_title_bar_theme(self, self.current_theme_id)
        self.refresh_logs()
        self.refresh_stats()

    def closeEvent(self, event):
        if hasattr(self, "refresh_timer") and self.refresh_timer and self.refresh_timer.isActive():
            self.refresh_timer.stop()
        if hasattr(self, "_status_timer") and self._status_timer and self._status_timer.isActive():
            self._status_timer.stop()
        super().closeEvent(event)

    def init_ui(self):
        theme = self._get_theme()
        accent = theme.get("accent_color", "#89b4fa")
        text_primary = theme.get("text_primary", "#cdd6f4")
        text_muted = theme.get("text_muted", "#a6adc8")
        bg_card = theme.get("bg_card", "#181825")
        border_color = theme.get("border", theme.get("border_color", "#45475a"))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Шапка
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        lbl_icon = QLabel("📊")
        lbl_icon.setStyleSheet("font-size: 26px;")
        header_layout.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Диагностика и статистика работы")
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {accent};")
        title_vbox.addWidget(lbl_title)

        log_path = get_log_file_path()
        lbl_subtitle = QLabel(f"Журнал: {log_path}")
        lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        lbl_subtitle.setWordWrap(True)
        title_vbox.addWidget(lbl_subtitle)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 2. Вкладки: Журнал событий | Статистика использования
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget, stretch=1)

        # Вкладка 1: Журнал событий
        tab_logs = QWidget()
        self._init_logs_tab(tab_logs, theme)
        self.tab_widget.addTab(tab_logs, "📋 Журнал событий")

        # Вкладка 2: Статистика использования
        tab_stats = QWidget()
        self._init_stats_tab(tab_stats, theme)
        self.tab_widget.addTab(tab_stats, "📊 Статистика использования")

        # 3. Нижняя общая полоса кнопок
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)

        bottom_layout.addStretch()

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.setProperty("cssClass", "btn_tool")
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        layout.addLayout(bottom_layout)

    def _init_logs_tab(self, tab: QWidget, theme: dict):
        text_primary = theme.get("text_primary", "#cdd6f4")
        accent = theme.get("accent_color", "#89b4fa")
        bg_card = theme.get("bg_card", "#181825")
        border_color = theme.get("border", theme.get("border_color", "#45475a"))

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Панель фильтров
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        lbl_filter = QLabel("Фильтр:")
        lbl_filter.setStyleSheet(f"color: {text_primary}; font-size: 12px;")
        filter_layout.addWidget(lbl_filter)

        self.combo_level = QComboBox()
        self.combo_level.addItem("Все события", "")
        self.combo_level.addItem("Только ошибки (ERROR)", "ERROR")
        self.combo_level.addItem("Предупреждения (WARNING)", "WARNING")
        self.combo_level.addItem("Инфо (INFO)", "INFO")
        self.combo_level.currentIndexChanged.connect(self.refresh_logs)
        filter_layout.addWidget(self.combo_level)

        self.chk_autoscroll = QCheckBox("Автопрокрутка вниз")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet(f"color: {text_primary}; font-size: 12px;")
        filter_layout.addWidget(self.chk_autoscroll)

        filter_layout.addStretch()

        self.btn_refresh = QPushButton("🔄 Обновить")
        self.btn_refresh.setProperty("cssClass", "btn_tool")
        self.btn_refresh.clicked.connect(self.refresh_logs)
        filter_layout.addWidget(self.btn_refresh)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setProperty("cssClass", "btn_tool")
        self.btn_clear.clicked.connect(self.on_clear_clicked)
        filter_layout.addWidget(self.btn_clear)

        layout.addLayout(filter_layout)

        # Поле для логов
        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.txt_logs.setFont(font)
        self.txt_logs.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_card};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
                line-height: 1.3;
            }}
        """)
        layout.addWidget(self.txt_logs, stretch=1)

        # Нижние кнопки вкладки логов
        btns_layout = QHBoxLayout()
        btns_layout.setSpacing(10)

        self.btn_copy_report = QPushButton("📋 Скопировать отчёт для разработчика")
        self.btn_copy_report.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: #11111b;
                font-weight: bold;
                font-size: 12px;
                padding: 7px 14px;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        self.btn_copy_report.clicked.connect(self.on_copy_report_clicked)
        btns_layout.addWidget(self.btn_copy_report)

        self.btn_open_folder = QPushButton("📂 Открыть папку с логами")
        self.btn_open_folder.setProperty("cssClass", "btn_tool")
        self.btn_open_folder.clicked.connect(self.on_open_folder_clicked)
        btns_layout.addWidget(self.btn_open_folder)

        btns_layout.addStretch()
        layout.addLayout(btns_layout)

    def _init_stats_tab(self, tab: QWidget, theme: dict):
        text_primary = theme.get("text_primary", "#cdd6f4")
        text_muted = theme.get("text_muted", "#a6adc8")
        accent = theme.get("accent_color", "#89b4fa")
        bg_card = theme.get("bg_card", "#181825")
        border_color = theme.get("border", theme.get("border_color", "#45475a"))

        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Сетка карточек-метрик
        cards_layout = QGridLayout()
        cards_layout.setSpacing(8)

        def _create_stat_card(title: str, val_text: str, sub_text: str) -> tuple:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background-color: {bg_card};
                    border: 1px solid {border_color};
                    border-radius: 6px;
                    padding: 4px;
                }}
            """)
            card_vbox = QVBoxLayout(card)
            card_vbox.setContentsMargins(8, 6, 8, 6)
            card_vbox.setSpacing(2)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet(f"font-size: 11px; color: {text_muted}; font-weight: 500;")
            card_vbox.addWidget(lbl_t)

            lbl_v = QLabel(val_text)
            lbl_v.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {accent};")
            card_vbox.addWidget(lbl_v)

            lbl_s = QLabel(sub_text)
            lbl_s.setStyleSheet(f"font-size: 10px; color: {text_muted};")
            card_vbox.addWidget(lbl_s)

            return card, lbl_v, lbl_s

        card1, self.lbl_card_sheets_val, self.lbl_card_sheets_sub = _create_stat_card(
            "🖨️ Листов напечатано", "0", "Успешно: 0 • Ошибок: 0"
        )
        card2, self.lbl_card_rate_val, self.lbl_card_rate_sub = _create_stat_card(
            "🎯 Успешность печати", "0.0%", "Среднее время: 0.0 сек/лист"
        )
        card3, self.lbl_card_time_val, self.lbl_card_time_sub = _create_stat_card(
            "⏱️ Сэкономлено времени", "0 мин", "~2 мин на лист вручную"
        )
        card4, self.lbl_card_scan_val, self.lbl_card_scan_sub = _create_stat_card(
            "🔍 Чертежей обработано", "0 DWG", "Рамок найдено: 0"
        )

        cards_layout.addWidget(card1, 0, 0)
        cards_layout.addWidget(card2, 0, 1)
        cards_layout.addWidget(card3, 0, 2)
        cards_layout.addWidget(card4, 0, 3)

        layout.addLayout(cards_layout)

        # Текстовое поле детализированного отчета
        self.txt_stats = QPlainTextEdit()
        self.txt_stats.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.txt_stats.setFont(font)
        self.txt_stats.setStyleSheet(f"""
            QPlainTextEdit {{
                background-color: {bg_card};
                color: {text_primary};
                border: 1px solid {border_color};
                border-radius: 6px;
                padding: 6px;
                line-height: 1.3;
            }}
        """)
        layout.addWidget(self.txt_stats, stretch=1)

        # Кнопки вкладки статистики
        stats_btns_layout = QHBoxLayout()
        stats_btns_layout.setSpacing(10)

        self.btn_copy_stats = QPushButton("📋 Скопировать статистику")
        self.btn_copy_stats.setProperty("cssClass", "btn_tool")
        self.btn_copy_stats.clicked.connect(self.on_copy_stats_clicked)
        stats_btns_layout.addWidget(self.btn_copy_stats)

        self.btn_refresh_stats = QPushButton("🔄 Обновить")
        self.btn_refresh_stats.setProperty("cssClass", "btn_tool")
        self.btn_refresh_stats.clicked.connect(self.refresh_stats)
        stats_btns_layout.addWidget(self.btn_refresh_stats)

        self.btn_reset_stats = QPushButton("🗑️ Сбросить статистику")
        self.btn_reset_stats.setProperty("cssClass", "btn_tool")
        self.btn_reset_stats.setToolTip("Сбросить накопленные локальные счетчики")
        self.btn_reset_stats.clicked.connect(self.on_reset_stats_clicked)
        stats_btns_layout.addWidget(self.btn_reset_stats)

        stats_btns_layout.addStretch()
        layout.addLayout(stats_btns_layout)

    def _get_filter_level(self) -> str:
        data = self.combo_level.currentData()
        if data is not None and str(data) != "":
            return str(data)
        idx = self.combo_level.currentIndex()
        if idx == 1:
            return "ERROR"
        if idx == 2:
            return "WARNING"
        if idx == 3:
            return "INFO"
        return ""

    def _on_timer_refresh(self):
        if self.isVisible():
            if self.tab_widget.currentIndex() == 0:
                self.refresh_logs()
            else:
                self.refresh_stats()

    def refresh_logs(self):
        level_filter = self._get_filter_level()
        logs = get_recent_logs(max_lines=300, level_filter=level_filter or None)

        current_text = "\n".join(logs)
        if self.txt_logs.toPlainText() != current_text:
            self.txt_logs.setPlainText(current_text)
            if self.chk_autoscroll.isChecked():
                self.txt_logs.verticalScrollBar().setValue(
                    self.txt_logs.verticalScrollBar().maximum()
                )

    def refresh_stats(self):
        sm = self.stats_manager
        summary = sm.get_summary()

        total_sheets = summary["total_sheets_printed"]
        succ_sheets = summary["success_sheets_count"]
        fail_sheets = summary["failed_sheets_count"]
        fb_sheets = summary["fallback_format_count"]

        self.lbl_card_sheets_val.setText(str(total_sheets))
        self.lbl_card_sheets_sub.setText(f"Успешно: {succ_sheets} • Ошибок: {fail_sheets}")

        rate = summary["success_rate"]
        avg_sec = summary["avg_seconds_per_sheet"]
        self.lbl_card_rate_val.setText(f"{rate:.1f}%")
        self.lbl_card_rate_sub.setText(f"Резервных: {fb_sheets} • {avg_sec:.1f} сек/лист")

        time_saved = summary["time_saved_formatted"]
        self.lbl_card_time_val.setText(time_saved)

        dwg_scanned = summary["total_dwg_scanned"]
        frames_found = summary["total_frames_found"]
        self.lbl_card_scan_val.setText(f"{dwg_scanned} DWG")
        self.lbl_card_scan_sub.setText(f"Рамок найдено: {frames_found}")

        rep_text = sm.get_formatted_report()
        if self.txt_stats.toPlainText() != rep_text:
            self.txt_stats.setPlainText(rep_text)

    def _on_status_timeout(self):
        if hasattr(self, "lbl_status"):
            self.lbl_status.setText("")

    def _set_status_with_timeout(self, text: str, timeout_ms: int = 2000):
        self.lbl_status.setText(text)
        if hasattr(self, "_status_timer") and self._status_timer:
            self._status_timer.stop()
        self._status_timer = QTimer(self)
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(self._on_status_timeout)
        self._status_timer.start(timeout_ms)

    def on_clear_clicked(self):
        clear_log_buffer()
        self.txt_logs.clear()
        self._set_status_with_timeout("Журнал очищен", 2000)

    def on_copy_report_clicked(self):
        report = build_diagnostic_report(self.extra_info)
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(report)
        self._set_status_with_timeout("✓ Отчёт скопирован в буфер обмена!", 3000)

    def on_copy_stats_clicked(self):
        report = self.stats_manager.get_formatted_report()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(report)
        self._set_status_with_timeout("✓ Статистика скопирована в буфер обмена!", 3000)

    def on_reset_stats_clicked(self):
        res = QMessageBox.question(
            self,
            "Сброс статистики",
            "Вы действительно хотите сбросить накопленную локальную статистику стабильности и эффективности?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if res == QMessageBox.StandardButton.Yes:
            self.stats_manager.reset_stats()
            self.refresh_stats()
            self._set_status_with_timeout("Статистика сброшена", 2000)

    def on_open_folder_clicked(self):
        path = get_log_file_path()
        log_dir = os.path.dirname(path)
        if os.path.exists(log_dir):
            try:
                os.startfile(log_dir)
            except Exception as e:
                QMessageBox.warning(self, "Ошибка", f"Не удалось открыть папку:\n{e}")
        else:
            QMessageBox.information(self, "Папка логов", f"Папка ещё не создана:\n{log_dir}")
