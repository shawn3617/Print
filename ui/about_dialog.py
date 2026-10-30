"""
Диалоговое окно «О программе» PrintPDF.
Содержит сведения о версии, возможностях, системную диагностику,
информацию о лицензии и обратной связи.
"""

import os
import platform
import sys
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QWidget, QFrame, QApplication
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon, QPixmap, QFont

from core.resource_utils import get_resource_path
from ui.themes import THEMES, build_theme_qss, apply_title_bar_theme

APP_NAME = "AutoCAD Batch PDF Plotter"
APP_SUBTITLE = "PrintPDF"
APP_VERSION = "1.3.0"
APP_RELEASE_DATE = "30 октября 2026"


class AboutDialog(QDialog):
    def __init__(self, current_theme_id: str = "dark_catppuccin", connector=None, parent=None):
        super().__init__(parent)
        self.current_theme_id = current_theme_id
        self.connector = connector

        self.setWindowTitle(f"О программе — {APP_SUBTITLE}")
        self.setFixedSize(540, 530)
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
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # 1. Шапка: Иконка + Название + Версия
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)

        icon_lbl = QLabel()
        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if os.path.exists(icon_path):
            pix = QPixmap(icon_path).scaled(54, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            icon_lbl.setPixmap(pix)
        else:
            icon_lbl.setText("🖨️")
            icon_lbl.setStyleSheet(f"font-size: 40px; color: {accent};")
        header_layout.addWidget(icon_lbl)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(2)

        lbl_app = QLabel(APP_NAME)
        lbl_app.setStyleSheet(f"font-size: 17px; font-weight: bold; color: {accent};")
        title_vbox.addWidget(lbl_app)

        lbl_ver = QLabel(f"{APP_SUBTITLE} • Версия {APP_VERSION}")
        lbl_ver.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {text_primary};")
        title_vbox.addWidget(lbl_ver)

        lbl_date = QLabel(f"Дата релиза: {APP_RELEASE_DATE}")
        lbl_date.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        title_vbox.addWidget(lbl_date)

        header_layout.addLayout(title_vbox, stretch=1)
        layout.addLayout(header_layout)

        # 2. Карточка описания программы
        desc_frame = QFrame()
        desc_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_card}; border: 1px solid {border}; border-radius: 8px; padding: 6px; }}"
        )
        desc_layout = QVBoxLayout(desc_frame)
        desc_layout.setContentsMargins(12, 10, 12, 10)
        desc_layout.setSpacing(6)

        lbl_desc_title = QLabel("Назначение:")
        lbl_desc_title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        desc_layout.addWidget(lbl_desc_title)

        desc_text = (
            "Пакетная автоматизированная печать проектных чертежей в PDF напрямую из AutoCAD.\n"
            "• Быстрое распознавание рамок СПДС GraphiCS, произвольных блоков и полилиний по ГОСТ 2.301-68;\n"
            "• Автоматический подбор форматов бумаги (A4..A0x9) и ориентации;\n"
            "• Сбор атрибутов штампа (номер листа, наименование, шифр проекта, объект строительства)."
        )
        lbl_desc = QLabel(desc_text)
        lbl_desc.setWordWrap(True)
        lbl_desc.setStyleSheet(f"font-size: 12px; color: {text_primary}; line-height: 1.4;")
        desc_layout.addWidget(lbl_desc)

        layout.addWidget(desc_frame)

        # 3. Карточка сведений о системе (диагностика)
        diag_frame = QFrame()
        diag_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_card}; border: 1px solid {border}; border-radius: 8px; padding: 6px; }}"
        )
        diag_layout = QVBoxLayout(diag_frame)
        diag_layout.setContentsMargins(12, 10, 12, 10)
        diag_layout.setSpacing(6)

        diag_hdr = QHBoxLayout()
        lbl_diag_title = QLabel("Сведения о системе:")
        lbl_diag_title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        diag_hdr.addWidget(lbl_diag_title)
        diag_hdr.addStretch()

        self.btn_copy_info = QPushButton("📋 Скопировать")
        self.btn_copy_info.setProperty("cssClass", "btn_tool")
        self.btn_copy_info.setToolTip("Скопировать сведения о системе и версии в буфер обмена")
        self.btn_copy_info.setStyleSheet("padding: 2px 8px; font-size: 11px;")
        self.btn_copy_info.clicked.connect(self.copy_diagnostics)
        diag_hdr.addWidget(self.btn_copy_info)
        diag_layout.addLayout(diag_hdr)

        self.diag_text = self._build_diagnostics_text()
        lbl_diag_body = QLabel(self._build_display_diagnostics())
        lbl_diag_body.setWordWrap(True)
        lbl_diag_body.setStyleSheet(f"font-size: 11px; color: {text_muted};")
        diag_layout.addWidget(lbl_diag_body)

        layout.addWidget(diag_frame)

        # 4. Блок обратной связи (заготовка)
        fb_frame = QFrame()
        fb_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_card}; border: 1px solid {border}; border-radius: 8px; padding: 6px; }}"
        )
        fb_layout = QVBoxLayout(fb_frame)
        fb_layout.setContentsMargins(12, 8, 12, 8)
        fb_layout.setSpacing(4)

        lbl_fb_title = QLabel("Обратная связь и предложения:")
        lbl_fb_title.setStyleSheet(f"font-weight: bold; font-size: 12px; color: {accent};")
        fb_layout.addWidget(lbl_fb_title)

        lbl_fb_desc = QLabel("Канал связи и поддержка будут открыты после завершения закрытого тестирования.")
        lbl_fb_desc.setStyleSheet(f"font-size: 11px; font-style: italic; color: {text_muted};")
        fb_layout.addWidget(lbl_fb_desc)

        layout.addWidget(fb_frame)

        # 5. Лицензия
        lbl_lic = QLabel("Лицензия: Freeware — бесплатно для внутреннего использования и проектных работ.")
        lbl_lic.setStyleSheet(f"font-size: 10px; color: {text_muted};")
        layout.addWidget(lbl_lic)

        # 6. Кнопка закрытия
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_close = QPushButton("Закрыть")
        btn_close.setProperty("cssClass", "btn_tool")
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def _build_display_diagnostics(self) -> str:
        acad_status = "Не подключено"
        doc_name = "—"
        if self.connector:
            try:
                if getattr(self.connector, "app", None):
                    ver = getattr(self.connector.app, "Version", "")
                    caption = getattr(self.connector.app, "Caption", "")
                    acad_status = caption if caption else (f"AutoCAD v{ver}" if ver else "Подключено")
                    doc = self.connector.get_active_document_name()
                    if doc and "не открыт" not in doc.lower():
                        doc_name = doc
            except Exception:
                acad_status = "Ошибка связи"

        os_info = f"Windows {platform.release()} ({platform.architecture()[0]})"
        return (
            f"AutoCAD: {acad_status}\n"
            f"Чертеж: {doc_name}\n"
            f"Платформа: {os_info} • Python {platform.python_version()}"
        )

    def _build_diagnostics_text(self) -> str:
        lines = [
            f"=== {APP_NAME} ({APP_SUBTITLE}) ===",
            f"Версия: {APP_VERSION} ({APP_RELEASE_DATE})",
            f"ОС: {platform.platform()} ({platform.architecture()[0]})",
            f"Python: {platform.python_version()} ({sys.executable})",
        ]
        try:
            import PySide6
            lines.append(f"PySide6 (Qt): {PySide6.__version__}")
        except Exception:
            pass

        if self.connector:
            try:
                if getattr(self.connector, "app", None):
                    caption = getattr(self.connector.app, "Caption", "AutoCAD")
                    ver = getattr(self.connector.app, "Version", "?")
                    lines.append(f"AutoCAD: {caption} (v{ver})")
                    doc = self.connector.get_active_document_name()
                    lines.append(f"Активный чертеж: {doc}")
                else:
                    lines.append("AutoCAD: не подключен")
            except Exception as e:
                lines.append(f"AutoCAD: ошибка ({e})")
        else:
            lines.append("AutoCAD: нет коннектора")

        return "\n".join(lines)

    def copy_diagnostics(self):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(self.diag_text)
            self.btn_copy_info.setText("✓ Скопировано")
            QTimer.singleShot(2000, lambda: self.btn_copy_info.setText("📋 Скопировать"))

    def showEvent(self, event):
        super().showEvent(event)
        apply_title_bar_theme(self, getattr(self, "current_theme_id", "dark_catppuccin"))
