"""
Диалоговое окно обновления программы PrintPDF.
Позволяет просмотреть список изменений, скачать обновление и выполнить установку в 1 клик.
"""

import os
import sys
import webbrowser
import tempfile
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTextEdit, QProgressBar, QFrame, QApplication, QMessageBox, QWidget
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QIcon, QFont

from core.resource_utils import get_resource_path
from core.updater import UpdateInfo, download_file, apply_update_and_restart, is_running_as_installed_app
from ui.themes import THEMES, build_theme_qss, apply_title_bar_theme


class DownloadWorker(QThread):
    """Фоновый поток для скачивания файла установщика без зависания интерфейса."""
    progress = Signal(int, int)  # downloaded, total
    finished = Signal(bool, str)  # success, file_path

    def __init__(self, url: str, target_path: str):
        super().__init__()
        self.url = url
        self.target_path = target_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        def on_prog(down, total):
            self.progress.emit(down, total)

        def is_canc():
            return self._is_cancelled

        ok = download_file(
            url=self.url,
            target_path=self.target_path,
            progress_callback=on_prog,
            is_cancelled_callback=is_canc
        )
        self.finished.emit(ok and not self._is_cancelled, self.target_path)


class UpdateDialog(QDialog):
    def __init__(self, update_info: UpdateInfo, current_version: str, current_theme_id: str = "dark_catppuccin", parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.current_version = current_version
        self.current_theme_id = current_theme_id
        self.download_worker: DownloadWorker = None

        self.setWindowTitle(f"Доступно обновление — PrintPDF v{self.update_info.version}")
        self.setFixedSize(560, 480)
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Шапка с акцентом
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        lbl_icon = QLabel("🚀")
        lbl_icon.setStyleSheet("font-size: 32px;")
        header_layout.addWidget(lbl_icon)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(3)

        lbl_title = QLabel("Доступна новая версия PrintPDF!")
        lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {theme.get('accent', '#89b4fa')};")
        title_vbox.addWidget(lbl_title)

        ver_text = f"Текущая: <b>v{self.current_version}</b>  ➔  Новая: <b style='color: #a6e3a1;'>v{self.update_info.version}</b>"
        if self.update_info.formatted_size_mb:
            ver_text += f" &nbsp;•&nbsp; Размер: {self.update_info.formatted_size_mb}"
        lbl_ver = QLabel(ver_text)
        lbl_ver.setStyleSheet("font-size: 13px; color: #a6adc8;")
        title_vbox.addWidget(lbl_ver)

        header_layout.addLayout(title_vbox)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Разделитель
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #45475a; margin: 4px 0;")
        layout.addWidget(sep)

        # Блок "Что нового"
        lbl_changelog_title = QLabel("Что нового в этом выпуске:")
        lbl_changelog_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(lbl_changelog_title)

        self.txt_changelog = QTextEdit()
        self.txt_changelog.setReadOnly(True)
        changelog_content = self.update_info.changelog or "Официальный релиз с исправлениями и улучшениями производительности."
        self.txt_changelog.setPlainText(changelog_content)
        self.txt_changelog.setStyleSheet("""
            QTextEdit {
                font-size: 12px;
                line-height: 1.4;
                border-radius: 6px;
                padding: 8px;
            }
        """)
        layout.addWidget(self.txt_changelog)

        # Блок прогресса скачивания (скрыт по умолчанию)
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(6)

        self.lbl_progress_status = QLabel("Скачивание обновления...")
        self.lbl_progress_status.setStyleSheet("font-size: 12px; color: #cdd6f4;")
        self.progress_layout.addWidget(self.lbl_progress_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_layout.addWidget(self.progress_bar)

        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)

        # Нижняя панель кнопок
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_open_web = QPushButton("Страница на GitHub ↗")
        self.btn_open_web.setProperty("cssClass", "btn_tool")
        self.btn_open_web.clicked.connect(self.on_open_web_clicked)
        btn_layout.addWidget(self.btn_open_web)

        btn_layout.addStretch()

        self.btn_remind_later = QPushButton("Напомнить позже")
        self.btn_remind_later.setProperty("cssClass", "btn_tool")
        self.btn_remind_later.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_remind_later)

        self.btn_update = QPushButton("🚀 Обновить сейчас")
        self.btn_update.setObjectName("btn_do_update")
        self.btn_update.setStyleSheet(f"""
            QPushButton#btn_do_update {{
                background-color: {theme.get('accent', '#89b4fa')};
                color: #11111b;
                font-weight: bold;
                font-size: 13px;
                padding: 7px 18px;
                border-radius: 6px;
            }}
            QPushButton#btn_do_update:hover {{
                opacity: 0.9;
                background-color: #b4befe;
            }}
            QPushButton#btn_do_update:disabled {{
                background-color: #585b70;
                color: #a6adc8;
            }}
        """)
        self.btn_update.clicked.connect(self.on_update_clicked)
        btn_layout.addWidget(self.btn_update)

        layout.addLayout(btn_layout)

    def showEvent(self, event):
        super().showEvent(event)
        apply_title_bar_theme(self, self.current_theme_id)

    def on_open_web_clicked(self):
        webbrowser.open(self.update_info.html_url)

    def on_update_clicked(self):
        if not self.update_info.installer_url:
            # Если прямой ссылки на установщик нет в релизе, открываем браузер
            webbrowser.open(self.update_info.html_url)
            self.accept()
            return

        # Показываем прогресс-бар и блокируем кнопку
        self.progress_container.setVisible(True)
        self.btn_update.setEnabled(False)
        self.btn_remind_later.setText("Отмена")
        self.btn_remind_later.clicked.disconnect()
        self.btn_remind_later.clicked.connect(self.on_cancel_download)

        temp_dir = tempfile.gettempdir()
        file_name = self.update_info.installer_name or f"PrintPDF_Setup_v{self.update_info.version}.exe"
        target_path = os.path.join(temp_dir, file_name)

        self.download_worker = DownloadWorker(self.update_info.installer_url, target_path)
        self.download_worker.progress.connect(self.on_download_progress)
        self.download_worker.finished.connect(self.on_download_finished)
        self.download_worker.start()

    def on_download_progress(self, downloaded: int, total: int):
        if total > 0:
            percent = int((downloaded / total) * 100)
            self.progress_bar.setValue(percent)
            down_mb = downloaded / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            self.lbl_progress_status.setText(f"Скачивание установщика: {down_mb:.1f} МБ из {tot_mb:.1f} МБ ({percent}%)")
        else:
            down_mb = downloaded / (1024 * 1024)
            self.lbl_progress_status.setText(f"Скачано: {down_mb:.1f} МБ...")

    def on_download_finished(self, success: bool, installer_path: str):
        if not success:
            self.lbl_progress_status.setText("❌ Ошибка при скачивании обновления.")
            self.btn_update.setEnabled(True)
            self.btn_update.setText("Повторить скачивание")
            self.btn_remind_later.setText("Закрыть")
            return

        self.lbl_progress_status.setText("✅ Установщик загружен. Запуск обновления...")
        self.progress_bar.setValue(100)

        # Если запущено из исходного кода Python (режим разработки)
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                "Обновление загружено",
                f"Установщик сохранён:\n{installer_path}\n\n"
                "Так как вы запускаете программу из исходного кода Python,\n"
                "для обновления достаточно выполнить 'git pull' в терминале."
            )
            self.accept()
            return

        # Запускаем фоновую установку и закрываем приложение
        ok = apply_update_and_restart(installer_path, silent=True)
        if ok:
            QApplication.quit()
        else:
            QMessageBox.warning(
                self,
                "Ошибка запуска",
                f"Не удалось запустить автоматический установщик.\nВы можете запустить его вручную:\n{installer_path}"
            )
            self.accept()

    def on_cancel_download(self):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait()
        self.reject()

    def closeEvent(self, event):
        if self.download_worker and self.download_worker.isRunning():
            self.download_worker.cancel()
            self.download_worker.wait()
        super().closeEvent(event)
