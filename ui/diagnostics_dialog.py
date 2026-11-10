"""
Диалоговое окно «Диагностика» PrintPDF.
Отображает журнал событий в реальном времени, позволяет скопировать полный отчёт
для разработчика и быстро открыть папку с логами на диске.
"""

import os
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QFrame, QApplication, QPlainTextEdit,
    QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QFont, QTextCharFormat, QColor

from core.resource_utils import get_resource_path
from core.version import APP_VERSION
from core.logger import (
    get_recent_logs,
    get_log_file_path,
    clear_log_buffer,
    build_diagnostic_report
)
from ui.themes import THEMES, build_theme_qss, apply_title_bar_theme


class DiagnosticsDialog(QDialog):
    def __init__(self, current_theme_id: str = "dark_catppuccin", connector=None, parent=None, extra_info: dict = None):
        super().__init__(parent)
        self.current_theme_id = current_theme_id
        self.connector = connector
        self.extra_info = extra_info or {}

        self.setWindowTitle("Диагностика и журнал событий — PrintPDF")
        self.resize(760, 560)
        self.setMinimumSize(600, 420)
        self.setModal(False)

        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(build_theme_qss(self.current_theme_id))
        self.init_ui()
        self.refresh_logs()

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

    def init_ui(self):
        theme = self._get_theme()
        accent = theme.get("accent_color", "#89b4fa")
        text_primary = theme.get("text_primary", "#cdd6f4")
        text_muted = theme.get("text_muted", "#a6adc8")
        bg_card = theme.get("bg_card", "#181825")
        border_color = theme.get("border_color", "#45475a")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Шапка
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        lbl_icon = QLabel("🐞")
        lbl_icon.setStyleSheet("font-size: 26px;")
        header_layout.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)
        lbl_title = QLabel("Журнал диагностики и событий")
        lbl_title.setStyleSheet(f"font-size: 15px; font-weight: bold; color: {accent};")
        title_vbox.addWidget(lbl_title)

        log_path = get_log_file_path()
        lbl_subtitle = QLabel(f"Файл лога: {log_path}")
        lbl_subtitle.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        lbl_subtitle.setWordWrap(True)
        title_vbox.addWidget(lbl_subtitle)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # 2. Панель фильтров и управления
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

        # 3. Текстовое поле для логов
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

        # 4. Нижняя панель кнопок
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(10)

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
        bottom_layout.addWidget(self.btn_copy_report)

        self.btn_open_folder = QPushButton("📂 Открыть папку с логами")
        self.btn_open_folder.setProperty("cssClass", "btn_tool")
        self.btn_open_folder.clicked.connect(self.on_open_folder_clicked)
        bottom_layout.addWidget(self.btn_open_folder)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet(f"color: #a6e3a1; font-weight: bold; font-size: 11px;")
        bottom_layout.addWidget(self.lbl_status)

        bottom_layout.addStretch()

        self.btn_close = QPushButton("Закрыть")
        self.btn_close.setProperty("cssClass", "btn_tool")
        self.btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(self.btn_close)

        layout.addLayout(bottom_layout)

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
            self.refresh_logs()

    def refresh_logs(self):
        level_filter = self._get_filter_level()
        logs = get_recent_logs(max_lines=300, level_filter=level_filter or None)

        # Сохраняем позицию курсора если автопрокрутка выключена
        current_text = "\n".join(logs)
        if self.txt_logs.toPlainText() != current_text:
            self.txt_logs.setPlainText(current_text)
            if self.chk_autoscroll.isChecked():
                self.txt_logs.verticalScrollBar().setValue(
                    self.txt_logs.verticalScrollBar().maximum()
                )

    def on_clear_clicked(self):
        clear_log_buffer()
        self.txt_logs.clear()
        self.lbl_status.setText("Журнал очищен")
        QTimer.singleShot(2000, lambda: self.lbl_status.setText(""))

    def on_copy_report_clicked(self):
        # Собираем свежие диагностические данные
        report = build_diagnostic_report(self.extra_info)
        clipboard = QApplication.clipboard()
        clipboard.setText(report)

        self.lbl_status.setText("✓ Отчёт скопирован в буфер обмена!")
        QTimer.singleShot(3000, lambda: self.lbl_status.setText(""))

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
