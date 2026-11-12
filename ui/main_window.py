import os
import sys
from typing import Any, Optional, List, Dict

# Гарантируем корректный импорт модулей core/parsers даже при прямом запуске скрипта
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QLabel, QHeaderView, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog, QAbstractItemView, QDialog, QProgressBar,
    QLineEdit, QSizePolicy, QListView, QFrame, QMenu, QInputDialog, QStyle
)
from PySide6.QtCore import QByteArray, Qt, Signal, QMimeData, QTimer
from PySide6.QtGui import QDrag, QAction, QGuiApplication, QShortcut, QKeySequence, QIcon

from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
from core.printer import BatchPrinter, PrintCancelledError
from core.config_manager import ConfigManager
from core.models import DEFAULT_POLYLINE_LAYER, natural_sheet_sort_key, frame_natural_sort_key, ALL_FORMATS
from core.exporter import SheetExporter
from core.resource_utils import get_resource_path
from core.logger import init_logging, log_info, log_warn, log_error
from core.filename_template import (
    PRESET_TEMPLATES,
    TEMPLATE_VARIABLES,
    get_default_template,
    preview_filename,
    render_filename,
)
from core.profile_manager import ProfileManager, DEFAULT_PROFILE_NAME
from core.stats_manager import get_stats_manager
from ui.themes import THEMES, build_theme_qss, get_theme_status_colors, apply_title_bar_theme
from ui.help_dialog import HelpDialog
from ui.about_dialog import AboutDialog, APP_VERSION
from ui.diagnostics_dialog import DiagnosticsDialog
from ui.report_dialog import ReportDialog
from ui.format_dialog import FormatSelectDialog


class PrintSettingComboBox(QComboBox):
    def __init__(self):
        super().__init__()
        self.currentTextChanged.connect(self.setToolTip)

    def showPopup(self):
        view = self.view()
        content_width = view.sizeHintForColumn(0) + view.verticalScrollBar().sizeHint().width() + 8
        view.setMinimumWidth(min(content_width, self.screen().availableGeometry().width()))
        super().showPopup()


class ReorderableTableWidget(QTableWidget):
    row_moved = Signal(int, int) # from_row, to_row
    key_move_requested = Signal(int) # -1: up, 1: down

    def __init__(self, rows=0, cols=0, parent=None):
        super().__init__(rows, cols, parent)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def startDrag(self, supportedActions):
        row = self.currentRow()
        if row < 0:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-print-row", str(row).encode())
        drag.setMimeData(mime)
        # CopyAction гарантирует, что Qt не удалит строки сам при завершении drag
        drag.exec(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-print-row"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        elif event.mimeData().hasFormat("application/x-print-row"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            win = self.window()
            if hasattr(win, "handle_dropped_urls"):
                event.acceptProposedAction()
                win.handle_dropped_urls(event.mimeData().urls())
                return
        if event.mimeData().hasFormat("application/x-print-row"):
            try:
                src_row = int(event.mimeData().data("application/x-print-row").data().decode())
                pos = event.position().toPoint()
                drop_row = self.rowAt(pos.y())
                if drop_row == -1:
                    drop_row = self.rowCount() - 1
                if 0 <= src_row < self.rowCount() and 0 <= drop_row < self.rowCount() and src_row != drop_row:
                    event.acceptProposedAction()
                    self.row_moved.emit(src_row, drop_row)
                    return
            except Exception as e:
                print(f"Drop error: {e}")
        event.ignore()


    def keyPressEvent(self, event):
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            if event.key() == Qt.Key.Key_Up:
                self.key_move_requested.emit(-1)
                event.accept()
                return
            elif event.key() == Qt.Key.Key_Down:
                self.key_move_requested.emit(1)
                event.accept()
                return
        super().keyPressEvent(event)

class PrintProgressDialog(QDialog):
    def __init__(
        self,
        total_steps: int,
        parent=None,
        title: str = "Пакетная печать PDF",
        title_text: str = "Идет печать чертежей...",
        cancel_status: str = "Отмена печати, завершение текущей операции..."
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(500, 170)
        self.is_cancelled = False
        self.cancel_status_msg = cancel_status
        
        # Убираем кнопку контекстной справки (?) в Windows
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        self.lbl_title = QLabel(title_text)
        self.lbl_title.setProperty("cssClass", "header_accent")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(self.lbl_title)
        
        self.lbl_status = QLabel("Подготовка к операции...")
        self.lbl_status.setStyleSheet("font-size: 13px;")
        self.lbl_status.setWordWrap(True)
        layout.addWidget(self.lbl_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, max(1, total_steps))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%v / %m (%p%)")
        self.progress_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_bar)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel = QPushButton("Отмена")
        self.btn_cancel.setObjectName("btn_cancel_progress")
        self.btn_cancel.setStyleSheet("""
            QPushButton#btn_cancel_progress {
                background-color: #f38ba8;
                color: #11111b;
                font-size: 13px;
                font-weight: bold;
                padding: 6px 20px;
                border-radius: 6px;
            }
            QPushButton#btn_cancel_progress:hover {
                background-color: #eba0ac;
            }
            QPushButton#btn_cancel_progress:pressed {
                background-color: #f5c2e7;
            }
            QPushButton#btn_cancel_progress:disabled {
                background-color: #585b70;
                color: #a6adc8;
            }
        """)
        self.btn_cancel.clicked.connect(self.request_cancel)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)
        
    def request_cancel(self):
        self.is_cancelled = True
        self.lbl_status.setText(self.cancel_status_msg)
        self.btn_cancel.setEnabled(False)
        QApplication.processEvents()
        
    def closeEvent(self, event):
        self.is_cancelled = True
        event.accept()
        
    def reject(self):
        self.request_cancel()
        
    def set_progress(self, value: int, status_text: str):
        self.progress_bar.setValue(value)
        self.lbl_status.setText(status_text)
        QApplication.processEvents()

class PrintManagerUI(QMainWindow):
    update_check_finished = Signal(object, float)

    def __init__(self, config_manager=None):
        super().__init__()
        self.config_manager = config_manager or ConfigManager()
        init_logging()
        log_info(f"Запуск PrintPDF v{APP_VERSION}", module="App")
        get_stats_manager(config_manager=self.config_manager).record_launch()
        self.setWindowTitle(f"PrintPDF v{APP_VERSION} — AutoCAD Batch PDF Plotter")
        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        self.resize(1100, 650)
        self.setMinimumSize(780, 480)
        self.setAcceptDrops(True)
        self.profile_manager = ProfileManager(self.config_manager)
        self._is_loading_config = True
        self.connector = AutoCADConnector()
        self.scanner = DocumentScanner()
        self.printer = None
        self.frames = []
        self.paper_dict = {} # Словарь {Локальное_Имя: Системное_Имя}
        self._is_updating_table = False
        
        saved_theme = self.config_manager.get("theme", "dark_catppuccin")
        self.current_theme = saved_theme if saved_theme in THEMES else "dark_catppuccin"
        self.setup_theme(self.current_theme)
        self.init_ui()
        self.apply_initial_config()
        saved_geometry = self.config_manager.get("window_geometry")
        self._check_restored_geometry = (
            isinstance(saved_geometry, str)
            and saved_geometry.isascii()
            and self.restoreGeometry(QByteArray.fromBase64(saved_geometry.encode("ascii")))
        )
        self.refresh_document_status()
        self._is_loading_config = False
        self.available_update = None
        self.update_check_finished.connect(self._finish_background_update_check, Qt.ConnectionType.QueuedConnection)
        QTimer.singleShot(2500, self.start_background_update_check)

    def setup_theme(self, theme_id: str = "dark_catppuccin"):
        if theme_id not in THEMES:
            theme_id = "dark_catppuccin"
        self.current_theme = theme_id
        self.setStyleSheet(build_theme_qss(theme_id))

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        window_layout = QVBoxLayout(central_widget)
        window_layout.setContentsMargins(20, 20, 20, 20)
        window_layout.setSpacing(8)
        main_layout = QHBoxLayout()
        main_layout.setSpacing(20)
        window_layout.addLayout(main_layout, stretch=1)

        # ЛЕВАЯ ЧАСТЬ
        left_layout = QVBoxLayout()
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Чертеж:"))
        self.lbl_document = QLabel("Не подключено")
        self.lbl_document.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.lbl_document.setMinimumWidth(30)
        self.lbl_document.setSizePolicy(self.lbl_document.sizePolicy().Policy.Expanding, self.lbl_document.sizePolicy().Policy.Fixed)
        top_bar.addWidget(self.lbl_document)
        btn_refresh = QPushButton("Обновить связь")
        btn_refresh.setProperty("cssClass", "btn_tool")
        btn_refresh.setToolTip("Обновить связь с активным чертежом AutoCAD")
        btn_refresh.clicked.connect(self.refresh_document_status)
        top_bar.addWidget(btn_refresh)
        
        top_bar.addWidget(QLabel("Источник:"))
        self.combo_source = PrintSettingComboBox()
        self.combo_source.setView(QListView())
        self.combo_source.addItems(["Модель (Model Space)", "Листы (Layouts)"])
        self.combo_source.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_source.setMinimumContentsLength(12)
        self.combo_source.currentTextChanged.connect(self.on_source_mode_changed)
        top_bar.addWidget(self.combo_source)
        
        self.btn_scan = QPushButton("Найти рамки")
        self.btn_scan.clicked.connect(self.scan_frames)
        top_bar.addWidget(self.btn_scan)
        left_layout.addLayout(top_bar)

        # Панель пакетной обработки чертежей
        batch_bar = QHBoxLayout()
        batch_bar.setSpacing(8)

        btn_batch = QPushButton("Пакет чертежей")
        btn_batch.setProperty("cssClass", "btn_tool")
        batch_menu = QMenu(btn_batch)
        batch_menu.addAction("Закрыть чертежи программы", self.close_opened_documents_dialog)
        btn_batch.setMenu(batch_menu)
        batch_bar.addWidget(btn_batch)

        btn_add_dwg = QPushButton("+ DWG...")
        btn_add_dwg.setProperty("cssClass", "btn_tool")
        btn_add_dwg.setToolTip("Выбрать один или несколько DWG-файлов для сканирования и печати")
        btn_add_dwg.clicked.connect(self.add_dwg_files_dialog)
        batch_bar.addWidget(btn_add_dwg)

        btn_add_folder = QPushButton("+ Папка...")
        btn_add_folder.setProperty("cssClass", "btn_tool")
        btn_add_folder.setToolTip("Выбрать папку для добавления всех чертежей .dwg")
        btn_add_folder.clicked.connect(self.add_dwg_folder_dialog)
        batch_bar.addWidget(btn_add_folder)

        btn_clear = QPushButton("Очистить")
        btn_clear.setProperty("cssClass", "btn_tool")
        btn_clear.setToolTip("Очистить таблицу найденных листов")
        btn_clear.clicked.connect(self.clear_frames)
        batch_bar.addWidget(btn_clear)

        batch_bar.addStretch()

        btn_help = QPushButton("Справка")
        btn_help.setProperty("cssClass", "btn_tool")
        help_menu = QMenu(btn_help)
        help_menu.addAction("Инструкция (F1)", self.show_help_dialog)
        help_menu.addAction("Диагностика (F2)", self.show_diagnostics_dialog)
        help_menu.addAction("О программе", self.show_about_dialog)
        btn_help.setMenu(help_menu)
        batch_bar.addWidget(btn_help)

        self.btn_update_alert = QPushButton("✨ Обновление")
        self.btn_update_alert.setObjectName("btn_update_alert")
        self.btn_update_alert.setToolTip("Нажмите, чтобы посмотреть список изменений и обновить программу")
        self.btn_update_alert.setStyleSheet("""
            QPushButton#btn_update_alert {
                background-color: #a6e3a1;
                color: #11111b;
                font-weight: bold;
                border-radius: 6px;
                padding: 5px 12px;
            }
            QPushButton#btn_update_alert:hover {
                background-color: #94e2d5;
            }
        """)
        self.btn_update_alert.setVisible(False)
        self.btn_update_alert.clicked.connect(self.show_update_dialog)
        batch_bar.addWidget(self.btn_update_alert)

        left_layout.addLayout(batch_bar)

        # Панель фильтрации и быстрого поиска
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        lbl_filter = QLabel("Поиск:")
        lbl_filter.setProperty("cssClass", "header_accent")
        filter_bar.addWidget(lbl_filter)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Номер, название или чертеж...")
        self.txt_search.setMinimumWidth(60)
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.txt_search, stretch=3)

        lbl_fmt = QLabel("Формат:")
        lbl_fmt.setProperty("cssClass", "header_accent")
        filter_bar.addWidget(lbl_fmt)

        self.combo_filter_format = QComboBox()
        self.combo_filter_format.setView(QListView())
        self.combo_filter_format.addItem("Все форматы")
        self.combo_filter_format.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_filter_format.setMinimumContentsLength(8)
        self.combo_filter_format.currentIndexChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.combo_filter_format, stretch=1)

        self.btn_reset_filter = QPushButton("✕ Сброс")
        self.btn_reset_filter.setProperty("cssClass", "btn_tool")
        self.btn_reset_filter.setToolTip("Сбросить поиск и фильтр по форматам")
        self.btn_reset_filter.clicked.connect(self.reset_filter)
        filter_bar.addWidget(self.btn_reset_filter)

        left_layout.addLayout(filter_bar)

        self.table = ReorderableTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels([
            "Печать",
            "Лист",
            "Обозначение документа",
            "Название листа",
            "Объект строительства",
            "Здание / сооружение",
            "Формат",
            "Чертеж",
            "Источник"
        ])
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        default_widths = [65, 60, 180, 260, 220, 200, 75, 140, 90]
        saved_widths = self.config_manager.get("table_column_widths", default_widths)
        if not isinstance(saved_widths, list) or len(saved_widths) != 9:
            saved_widths = default_widths

        for col_idx, width in enumerate(saved_widths):
            header.resizeSection(col_idx, width)

        header.sectionResized.connect(self.on_column_resized)
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_context_menu)

        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setToolTip("Листы можно перетаскивать мышкой или перемещать кнопками «Вверх» / «Вниз» (Ctrl+↑ / Ctrl+↓).\nМожно перетаскивать файлы DWG из проводника прямо в окно программы.\nПравый клик по строке или шапке открывает контекстное меню.")
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.table.row_moved.connect(self.on_row_drag_moved)
        self.table.key_move_requested.connect(self.on_key_move_requested)
        self.table.currentCellChanged.connect(self.on_table_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        left_layout.addWidget(self.table)

        # Информационная строка со сводкой по форматам листов (Status Bar)
        self.status_bar_frame = QFrame()
        self.status_bar_frame.setObjectName("status_bar_container")
        status_bar_layout = QHBoxLayout(self.status_bar_frame)
        status_bar_layout.setContentsMargins(12, 6, 12, 6)
        status_bar_layout.setSpacing(10)

        self.lbl_status_left = QLabel("Листов в очереди: <b>0</b>")
        self.lbl_status_left.setObjectName("status_bar_left")
        status_bar_layout.addWidget(self.lbl_status_left)

        status_bar_layout.addStretch()

        self.lbl_status_right = QLabel("F1 — Инструкция | F2 — Диагностика")
        self.lbl_status_right.setObjectName("status_bar_right")
        status_bar_layout.addWidget(self.lbl_status_right)

        left_layout.addWidget(self.status_bar_frame)


        # Панель управления порядком и выбором листов (адаптивная: 1 ряд при широком окне, 2 при узком)
        self.table_tools_container = QWidget()
        self.table_tools_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.table_tools_vbox = QVBoxLayout(self.table_tools_container)
        self.table_tools_vbox.setContentsMargins(0, 0, 0, 0)
        self.table_tools_vbox.setSpacing(8)

        self.table_tools_row1_widget = QWidget()
        self.table_tools_row1 = QHBoxLayout(self.table_tools_row1_widget)
        self.table_tools_row1.setContentsMargins(0, 0, 0, 0)
        self.table_tools_row1.setSpacing(8)

        self.table_tools_row2_widget = QWidget()
        self.table_tools_row2 = QHBoxLayout(self.table_tools_row2_widget)
        self.table_tools_row2.setContentsMargins(0, 0, 0, 0)
        self.table_tools_row2.setSpacing(8)

        self.table_tools_vbox.addWidget(self.table_tools_row1_widget)
        self.table_tools_vbox.addWidget(self.table_tools_row2_widget)

        self.btn_select_all = QPushButton("Выбрать все")
        self.btn_select_all.setProperty("cssClass", "btn_tool")
        self.btn_select_all.clicked.connect(lambda: self.select_all_rows(True))

        self.btn_deselect_all = QPushButton("Снять все")
        self.btn_deselect_all.setProperty("cssClass", "btn_tool")
        self.btn_deselect_all.clicked.connect(lambda: self.select_all_rows(False))

        self.btn_sort_num = QPushButton("По номерам")
        self.btn_sort_num.setProperty("cssClass", "btn_tool")
        self.btn_sort_num.setToolTip("Сбросить ручной порядок и отсортировать по возрастанию номеров листов")
        self.btn_sort_num.clicked.connect(self.sort_by_sheet_number)

        self.btn_export = QPushButton("В Excel / CSV...")
        self.btn_export.setProperty("cssClass", "btn_tool")
        self.btn_export.setToolTip("Экспортировать ведомость листов таблицы в Excel (.xlsx) или CSV")
        self.btn_export.clicked.connect(self.export_sheet_list_dialog)

        self.btn_move_up = QPushButton("▲ Вверх (Ctrl+↑)")
        self.btn_move_up.setProperty("cssClass", "btn_tool")
        self.btn_move_up.setToolTip("Поднять выбранный лист выше в очереди печати")
        self.btn_move_up.clicked.connect(self.move_row_up)

        self.btn_move_down = QPushButton("▼ Вниз (Ctrl+↓)")
        self.btn_move_down.setProperty("cssClass", "btn_tool")
        self.btn_move_down.setToolTip("Опустить выбранный лист ниже в очереди печати")
        self.btn_move_down.clicked.connect(self.move_row_down)

        self.chk_sync_acad = QCheckBox("Подсветка в AutoCAD")
        self.chk_sync_acad.setChecked(True)
        self.chk_sync_acad.setToolTip("Автоматически центрировать и подсвечивать выбранную рамку в AutoCAD при клике или переходе стрелками")
        self.chk_sync_acad.toggled.connect(lambda _: self.save_settings())

        self.btn_show_acad = QPushButton("В AutoCAD")
        self.btn_show_acad.setProperty("cssClass", "btn_tool")
        self.btn_show_acad.setToolTip("Центрировать выбранную рамку в окне AutoCAD и развернуть окно")
        self.btn_show_acad.clicked.connect(self.show_current_frame_in_autocad)

        self._is_single_row_tools = None
        self.update_table_tools_layout(self.width())

        left_layout.addWidget(self.table_tools_container)
        main_layout.addLayout(left_layout, stretch=1)

        # ПРАВАЯ ЧАСТЬ (настройки печати, расширенная панель)
        right_widget = QWidget()
        self.settings_panel = right_widget
        right_widget.setMinimumWidth(300)
        right_widget.setMaximumWidth(360)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Выбор темы оформления
        theme_layout = QHBoxLayout()
        theme_layout.setSpacing(10)
        lbl_theme = QLabel("Оформление:")
        lbl_theme.setProperty("cssClass", "header_accent")
        self.combo_theme = QComboBox()
        self.combo_theme.setView(QListView())
        for tid, tmeta in THEMES.items():
            self.combo_theme.addItem(tmeta["name"], tid)
        self.combo_theme.currentIndexChanged.connect(self.on_theme_changed)
        theme_layout.addWidget(lbl_theme)
        theme_layout.addWidget(self.combo_theme, stretch=1)
        right_layout.addLayout(theme_layout)

        # Профиль проекта
        group_profile = QGroupBox("Профиль проекта")
        profile_layout = QVBoxLayout(group_profile)
        profile_layout.setSpacing(6)

        self.combo_profile = QComboBox()
        self.combo_profile.setView(QListView())
        self.combo_profile.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_profile.setMinimumContentsLength(8)
        self.combo_profile.setToolTip("Выберите сохранённый профиль настроек для проекта или задачи")
        self.combo_profile.currentTextChanged.connect(self.on_profile_selected)
        profile_layout.addWidget(self.combo_profile)

        profile_btns = QHBoxLayout()
        profile_btns.setSpacing(6)

        self.btn_save_profile = QPushButton("Сохранить")
        self.btn_save_profile.setToolTip("Сохранить текущие параметры в активный профиль")
        self.btn_save_profile.clicked.connect(self.on_save_current_profile)
        profile_btns.addWidget(self.btn_save_profile)

        self.btn_new_profile = QPushButton("Новый…")
        self.btn_new_profile.setToolTip("Создать новый профиль на основе текущих настроек")
        self.btn_new_profile.clicked.connect(self.on_create_new_profile)
        profile_btns.addWidget(self.btn_new_profile)

        self.btn_menu_profile = QPushButton("⚙ ▾")
        self.btn_menu_profile.setToolTip("Дополнительные действия: переименовать, удалить, экспорт, импорт")
        self.btn_menu_profile.clicked.connect(self.show_profile_menu)
        profile_btns.addWidget(self.btn_menu_profile)

        for button in (self.btn_save_profile, self.btn_new_profile, self.btn_menu_profile):
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            button.setStyleSheet("padding-left: 10px; padding-right: 10px;")

        profile_layout.addLayout(profile_btns)
        right_layout.addWidget(group_profile)

        group_printer = QGroupBox("Настройки печати")
        form_layout = QFormLayout(group_printer)
        form_layout.setSpacing(14)
        
        self.combo_printers = PrintSettingComboBox()
        self.combo_printers.currentTextChanged.connect(self.on_printer_changed)
        form_layout.addRow(QLabel("Принтер:"), self.combo_printers)
        
        self.combo_papers = PrintSettingComboBox()
        fallback_label = QLabel("Резервный:")
        fallback_label.setToolTip("Используется, если плоттер не поддерживает размер бумаги для рамки")
        self.combo_papers.currentTextChanged.connect(self.on_fallback_paper_changed)
        form_layout.addRow(fallback_label, self.combo_papers)
        
        self.combo_style = QComboBox()
        self.combo_style.currentTextChanged.connect(lambda _: self.save_settings())
        form_layout.addRow(QLabel("Стиль:"), self.combo_style)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["В отдельные файлы", "В один файл (PDF)"])
        self.combo_mode.currentTextChanged.connect(self.on_mode_changed)
        form_layout.addRow(QLabel("Режим:"), self.combo_mode)

        self.combo_template = QComboBox()
        self.combo_template.setEditable(True)
        self.combo_template.setView(QListView())
        for _, tpl in PRESET_TEMPLATES:
            self.combo_template.addItem(tpl)
        self.combo_template.setToolTip(
            "Шаблон имени файла при экспорте в отдельные PDF.\n"
            "Переменные:\n"
            "  {Шифр} — обозначение документа / шифр\n"
            "  {Номер} или {Номер:02d} — номер листа\n"
            "  {Наименование} — название листа\n"
            "  {Формат} — формат бумаги (A3, A2...)\n"
            "  {DWG} — имя исходного чертежа\n"
            "  {Объект} — наименование объекта\n"
            "  {Здание} — здание / сооружение\n"
            "  {Масштаб} — масштаб"
        )
        self.combo_template.currentTextChanged.connect(self.on_template_changed)
        form_layout.addRow(QLabel("Шаблон:"), self.combo_template)

        self.lbl_template_preview = QLabel("Пример:")
        self.lbl_template_preview.setWordWrap(True)
        self.lbl_template_preview.setStyleSheet("color: #89b4fa; font-size: 11px;")
        form_layout.addRow("", self.lbl_template_preview)

        for cb in [self.combo_printers, self.combo_papers, self.combo_style, self.combo_mode, self.combo_template]:
            cb.setView(QListView())
            cb.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            cb.setMinimumContentsLength(8)

        self.chk_open_after = QCheckBox("Открыть результат")
        self.chk_open_after.setChecked(True)
        self.chk_open_after.setToolTip("Автоматически открыть объединенный PDF (или папку) после завершения печати")
        self.chk_open_after.toggled.connect(lambda _: self.save_settings())
        form_layout.addRow("", self.chk_open_after)

        right_layout.addWidget(group_printer)

        # Выбор типа рамок для поиска
        group_frames = QGroupBox("Поиск рамок")
        frames_form = QVBoxLayout(group_frames)
        frames_form.setSpacing(10)

        self.combo_frame_type = QComboBox()
        self.combo_frame_type.setView(QListView())
        self.combo_frame_type.addItem("Рамки СПДС", "spds")
        self.combo_frame_type.addItem("Любые блоки", "all_blocks")
        self.combo_frame_type.addItem("Конкретный блок...", "custom_block")
        self.combo_frame_type.addItem("Полилинии", "polyline")
        self.combo_frame_type.addItem("Все типы сразу", "all")
        self.combo_frame_type.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.combo_frame_type.setMinimumContentsLength(8)
        self.combo_frame_type.currentIndexChanged.connect(self.on_frame_type_changed)
        frames_form.addWidget(self.combo_frame_type)

        self.edit_block_name = QLineEdit()
        self.edit_block_name.setPlaceholderText("Имя или маска блока (напр. Рамка1, SHT_*)")
        self.edit_block_name.setToolTip("Укажите имя или маску блока (можно несколько через запятую)")
        self.edit_block_name.textChanged.connect(lambda _: self.save_settings())
        self.edit_block_name.setVisible(False)
        frames_form.addWidget(self.edit_block_name)

        self.polyline_layer_row = QWidget()
        layer_form = QFormLayout(self.polyline_layer_row)
        layer_form.setContentsMargins(0, 0, 0, 0)
        self.edit_polyline_layer = QLineEdit(DEFAULT_POLYLINE_LAYER)
        self.edit_polyline_layer.setPlaceholderText(DEFAULT_POLYLINE_LAYER)
        self.edit_polyline_layer.setToolTip("Введите имена слоёв через запятую, например Рамки АР, Рамки КЖ")
        self.edit_polyline_layer.editingFinished.connect(self.save_settings)
        layer_form.addRow("Слои рамок", self.edit_polyline_layer)
        self.polyline_layer_row.hide()
        frames_form.addWidget(self.polyline_layer_row)

        self.lbl_frame_type_warning = QLabel(
            "⚠️ Поиск по всем типам рамок (СПДС + блоки + полилинии) занимает больше времени при пакетной обработке."
        )
        self.lbl_frame_type_warning.setWordWrap(True)
        self.lbl_frame_type_warning.setStyleSheet("color: #fab387; font-size: 11px;")
        self.lbl_frame_type_warning.setVisible(False)
        frames_form.addWidget(self.lbl_frame_type_warning)

        right_layout.addWidget(group_frames)
        right_layout.addStretch()
        
        footer = QHBoxLayout()
        footer.addStretch()
        self.btn_toggle_settings = QPushButton("Свернуть настройки")
        self.btn_toggle_settings.setProperty("cssClass", "btn_tool")
        self.btn_toggle_settings.setCheckable(True)
        self.btn_toggle_settings.toggled.connect(self.set_settings_collapsed)
        footer.addWidget(self.btn_toggle_settings)

        self.btn_print = QPushButton("ПЕЧАТЬ (0 листов)")
        self.btn_print.setObjectName("btn_print")
        self.btn_print.setEnabled(False)
        self.btn_print.clicked.connect(self.print_selected_frames)
        footer.addWidget(self.btn_print)
        window_layout.addLayout(footer)
        
        main_layout.addWidget(right_widget)
        for button in (btn_refresh, self.btn_scan, btn_batch):
            button.setMinimumWidth(button.sizeHint().width())

        # Горячая клавиша F1 для вызова руководства пользователя
        self.shortcut_f1 = QShortcut(QKeySequence("F1"), self)
        self.shortcut_f1.activated.connect(self.show_help_dialog)

        # Горячая клавиша F2 для вызова журнала диагностики
        self.shortcut_f2 = QShortcut(QKeySequence("F2"), self)
        self.shortcut_f2.activated.connect(self.show_diagnostics_dialog)

    def set_settings_collapsed(self, collapsed: bool):
        self.settings_panel.setVisible(not collapsed)
        self.btn_toggle_settings.setText("Показать настройки" if collapsed else "Свернуть настройки")
        self.save_settings()

    def show_help_dialog(self):
        """Открывает окно руководства пользователя."""
        dlg = HelpDialog(current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
        dlg.exec()

    def show_diagnostics_dialog(self):
        """Открывает окно журнала диагностики и ошибок."""
        extra = {}
        if getattr(self, "connector", None):
            extra["AutoCAD подключен"] = "Да" if getattr(self.connector, "app", None) else "Нет"
            extra["Активный чертеж"] = self.connector.get_active_document_name()
        extra["Выбранный плоттер"] = self.combo_printers.currentText() if hasattr(self, "combo_printers") else "—"
        extra["Резервный формат"] = self.combo_papers.currentText() if hasattr(self, "combo_papers") else "—"
        extra["Стиль печати"] = self.combo_style.currentText() if hasattr(self, "combo_style") else "—"
        extra["Загружено рамок"] = str(len(getattr(self, "frames", [])))

        dlg = DiagnosticsDialog(
            current_theme_id=getattr(self, "current_theme", "dark_catppuccin"),
            extra_diagnostics_info=extra,
            parent=self
        )
        dlg.exec()

    def show_about_dialog(self):
        """Открывает окно «О программе»."""
        dlg = AboutDialog(
            current_theme_id=getattr(self, "current_theme", "dark_catppuccin"),
            connector=getattr(self, "connector", None),
            parent=self
        )
        dlg.exec()

    def show_update_dialog(self):
        """Открывает окно с описанием и скачиванием доступного обновления."""
        if not getattr(self, "available_update", None):
            return
        from ui.update_dialog import UpdateDialog
        dlg = UpdateDialog(
            update_info=self.available_update,
            current_version=APP_VERSION,
            current_theme_id=getattr(self, "current_theme", "dark_catppuccin"),
            parent=self
        )
        dlg.exec()

    def start_background_update_check(self):
        """Запускает фоновую ненавязчивую проверку обновлений при старте приложения."""
        import time
        import threading

        if not self.config_manager.get("auto_check_updates", True):
            return

        # Проверяем не чаще одного раза в 4 часа
        last_check = float(self.config_manager.get("last_update_check", 0) or 0)
        now = time.time()
        if now - last_check < 4 * 3600:
            return

        def _bg_check():
            try:
                from core.updater import check_for_updates
                info = check_for_updates(current_version=APP_VERSION, timeout=8.0)
                self.update_check_finished.emit(info, now)
            except Exception as e:
                print(f"[Updater] Ошибка фоновой проверки: {e}")

        t = threading.Thread(target=_bg_check, daemon=True)
        t.start()

    def _finish_background_update_check(self, update_info, checked_at: float):
        self.config_manager.load()
        self.config_manager.save({"last_update_check": checked_at})
        if update_info:
            self.on_update_found(update_info)

    def on_update_found(self, update_info):
        """Вызывается в основном потоке при обнаружении новой версии."""
        self.available_update = update_info
        self.btn_update_alert.setText(f"✨ Доступно v{update_info.version}")
        self.btn_update_alert.setVisible(True)
        # Открываем диалог обновления, чтобы пользователь сразу увидел список изменений
        self.show_update_dialog()

    def apply_initial_config(self):
        """Применяет сохраненные настройки из config.json к элементам интерфейса."""
        cfg = self.config_manager.load()
        if not isinstance(cfg, dict):
            cfg = {}
        self.btn_toggle_settings.setChecked(cfg.get("settings_collapsed") is True)
        self.chk_sync_acad.setChecked(bool(cfg.get("sync_autocad", True)))
        self.chk_open_after.setChecked(bool(cfg.get("open_after_print", True)))
        
        saved_theme = cfg.get("theme", "dark_catppuccin")
        if isinstance(saved_theme, str) and hasattr(self, "combo_theme"):
            idx_theme = self.combo_theme.findData(saved_theme)
            if idx_theme >= 0:
                self.combo_theme.blockSignals(True)
                self.combo_theme.setCurrentIndex(idx_theme)
                self.combo_theme.blockSignals(False)
            self.apply_theme(saved_theme)

        saved_mode = cfg.get("merge_mode", "В один файл (PDF)")
        if isinstance(saved_mode, str):
            idx_mode = self.combo_mode.findText(saved_mode)
            if idx_mode >= 0:
                self.combo_mode.setCurrentIndex(idx_mode)
                
        saved_source = cfg.get("source_mode", "Модель (Model Space)")
        if isinstance(saved_source, str):
            idx_source = self.combo_source.findText(saved_source)
            if idx_source >= 0:
                self.combo_source.setCurrentIndex(idx_source)

        saved_frame_type = cfg.get("frame_type", "spds")
        if hasattr(self, "combo_frame_type") and isinstance(saved_frame_type, str):
            idx_ft = self.combo_frame_type.findData(saved_frame_type)
            if idx_ft >= 0:
                self.combo_frame_type.blockSignals(True)
                self.combo_frame_type.setCurrentIndex(idx_ft)
                self.combo_frame_type.blockSignals(False)
            self.on_frame_type_changed(self.combo_frame_type.currentIndex())

        saved_custom_block = cfg.get("custom_block_name", "")
        if hasattr(self, "edit_block_name") and isinstance(saved_custom_block, str):
            self.edit_block_name.setText(saved_custom_block)
        saved_layer = cfg.get("polyline_layer", DEFAULT_POLYLINE_LAYER)
        if isinstance(saved_layer, str):
            self.edit_polyline_layer.setText(saved_layer)

        saved_template = cfg.get("filename_template", "Лист {Номер} - {Наименование}")
        if hasattr(self, "combo_template") and isinstance(saved_template, str) and saved_template:
            idx_tpl = self.combo_template.findText(saved_template)
            if idx_tpl >= 0:
                self.combo_template.blockSignals(True)
                self.combo_template.setCurrentIndex(idx_tpl)
                self.combo_template.blockSignals(False)
            else:
                self.combo_template.setEditText(saved_template)
        self.update_template_preview()

        # Восстановление профилей проектов
        if hasattr(self, "combo_profile"):
            self.update_profile_combo()

        # Восстановление скрытых колонок
        hidden_cols = cfg.get("hidden_columns", [])
        if isinstance(hidden_cols, list):
            for c_idx in hidden_cols:
                if isinstance(c_idx, int) and 0 < c_idx < self.table.columnCount():
                    self.table.setColumnHidden(c_idx, True)

    def on_frame_type_changed(self, index: int):
        if not hasattr(self, "combo_frame_type"):
            return
        mode = self.combo_frame_type.currentData()
        if hasattr(self, "edit_block_name"):
            self.edit_block_name.setVisible(mode == "custom_block")
        if hasattr(self, "lbl_frame_type_warning"):
            self.lbl_frame_type_warning.setVisible(mode == "all")
        self.polyline_layer_row.setVisible(
            mode in ("polyline", "all") and self.combo_source.currentIndex() == 0
        )
        self.save_settings()

    def selected_polyline_layer(self) -> str:
        return self.edit_polyline_layer.text().strip() or DEFAULT_POLYLINE_LAYER

    def on_theme_changed(self, index: int):
        if getattr(self, "_is_loading_config", False):
            return
        theme_id = self.combo_theme.currentData()
        if theme_id:
            self.apply_theme(theme_id)
            self.save_settings()

    def apply_theme(self, theme_id: str):
        if theme_id not in THEMES:
            theme_id = "dark_catppuccin"
        self.current_theme = theme_id
        self.setStyleSheet(build_theme_qss(theme_id))
        
        # Обновляем цвет статуса документа в соответствии с новой темой
        if hasattr(self, "lbl_document"):
            doc_name = self.lbl_document.text()
            ok_col, err_col = get_theme_status_colors(theme_id)
            if "не подключено" in doc_name.lower() or "ошибка" in doc_name.lower():
                self.lbl_document.setStyleSheet(f"color: {err_col}; font-weight: bold;")
            else:
                self.lbl_document.setStyleSheet(f"color: {ok_col}; font-weight: bold;")

        self.update_print_counter()
        apply_title_bar_theme(self, theme_id)

    def showEvent(self, event):
        super().showEvent(event)
        apply_title_bar_theme(self, getattr(self, "current_theme", "dark_catppuccin"))

    def on_source_mode_changed(self, text: str):
        if "Layout" in text or "Листы" in text:
            self.btn_scan.setText("Загрузить листы")
        else:
            self.btn_scan.setText("Найти рамки")
        if hasattr(self, "combo_frame_type"):
            self.on_frame_type_changed(self.combo_frame_type.currentIndex())

    def on_printer_changed(self, printer_name: str):
        self.update_paper_sizes(printer_name)
        self.save_settings()

    def on_fallback_paper_changed(self):
        self._reset_paper_warnings()
        self.save_settings()

    def _reset_paper_warnings(self):
        for frame in self.frames:
            frame.fallback_warning = ""
        self._refresh_table_formats()

    def on_mode_changed(self, text: str = ""):
        self.update_template_preview()
        self.save_settings()

    def on_template_changed(self, text: str = ""):
        self.update_template_preview()
        self.save_settings()

    def update_template_preview(self):
        tpl = self.combo_template.currentText().strip() if hasattr(self, "combo_template") else ""
        if not tpl:
            tpl = get_default_template()
        target_frame = None
        if hasattr(self, "table") and hasattr(self, "frames") and self.frames:
            curr_row = self.table.currentRow()
            if 0 <= curr_row < len(self.frames):
                target_frame = self.frames[curr_row]
            else:
                target_frame = self.frames[0]
        preview = preview_filename(tpl, target_frame)
        if hasattr(self, "lbl_template_preview"):
            is_merged = (hasattr(self, "combo_mode") and self.combo_mode.currentIndex() == 1)
            suffix = " (для отд. файлов)" if is_merged else ""
            self.lbl_template_preview.setText(f"Пример: {preview}{suffix}")

    def update_profile_combo(self):
        """Обновляет список профилей в выпадающем списке и выбирает активный."""
        if not hasattr(self, "combo_profile") or not hasattr(self, "profile_manager"):
            return
        self.combo_profile.blockSignals(True)
        self.combo_profile.clear()
        names = self.profile_manager.get_profile_names()
        for name in names:
            self.combo_profile.addItem(name)
        active = self.profile_manager.get_active_profile_name()
        idx = self.combo_profile.findText(active)
        if idx >= 0:
            self.combo_profile.setCurrentIndex(idx)
        self.combo_profile.blockSignals(False)

    def on_profile_selected(self, profile_name: str):
        """Обработчик выбора профиля из списка."""
        if getattr(self, "_is_loading_config", False) or not profile_name:
            return
        settings = self.profile_manager.get_profile(profile_name)
        if settings:
            self.apply_profile_settings(settings)
            self.profile_manager.set_active_profile_name(profile_name)
            self.lbl_status_right.setText(f"Загружен профиль «{profile_name}»")

    def apply_profile_settings(self, settings: Dict[str, Any]):
        """Применяет словарь настроек профиля к элементам интерфейса."""
        if not settings or not isinstance(settings, dict):
            return
        self._is_loading_config = True
        try:
            # 1. Принтер
            printer = settings.get("printer", "")
            if printer and hasattr(self, "combo_printers"):
                idx = self.combo_printers.findText(printer)
                if idx >= 0:
                    self.combo_printers.setCurrentIndex(idx)
            # 2. Стиль
            style = settings.get("plot_style", "")
            if style and hasattr(self, "combo_style"):
                idx = self.combo_style.findText(style)
                if idx >= 0:
                    self.combo_style.setCurrentIndex(idx)
            # 3. Бумага
            paper = settings.get("fallback_paper", "")
            if paper and hasattr(self, "combo_papers"):
                idx = self.combo_papers.findText(paper)
                if idx >= 0:
                    self.combo_papers.setCurrentIndex(idx)
            # 4. Режим
            mode = settings.get("merge_mode", "")
            if mode and hasattr(self, "combo_mode"):
                idx = self.combo_mode.findText(mode)
                if idx >= 0:
                    self.combo_mode.setCurrentIndex(idx)
            # 5. Шаблон
            template = settings.get("filename_template", "")
            if template and hasattr(self, "combo_template"):
                idx = self.combo_template.findText(template)
                if idx >= 0:
                    self.combo_template.setCurrentIndex(idx)
                else:
                    self.combo_template.setEditText(template)
            # 6. Чекбоксы
            if "open_after_print" in settings and hasattr(self, "chk_open_after"):
                self.chk_open_after.setChecked(bool(settings["open_after_print"]))
            if "sync_autocad" in settings and hasattr(self, "chk_sync_acad"):
                self.chk_sync_acad.setChecked(bool(settings["sync_autocad"]))
            # 7. Пространство
            source = settings.get("source_mode", "")
            if source and hasattr(self, "combo_source"):
                idx = self.combo_source.findText(source)
                if idx >= 0:
                    self.combo_source.setCurrentIndex(idx)
            # 8. Тип рамок
            frame_type = settings.get("frame_type", "")
            if frame_type and hasattr(self, "combo_frame_type"):
                idx = self.combo_frame_type.findData(frame_type)
                if idx >= 0:
                    self.combo_frame_type.setCurrentIndex(idx)
                    self.on_frame_type_changed(idx)
            # 9. Имя блока
            custom_block = settings.get("custom_block_name", "")
            if hasattr(self, "edit_block_name"):
                self.edit_block_name.setText(custom_block or "")
            saved_layer = settings.get("polyline_layer", DEFAULT_POLYLINE_LAYER)
            self.edit_polyline_layer.setText(saved_layer if isinstance(saved_layer, str) else DEFAULT_POLYLINE_LAYER)
        finally:
            self._is_loading_config = False

        self.update_template_preview()
        self.save_settings()

    def get_current_profile_settings(self) -> Dict[str, Any]:
        """Собирает текущие параметры печати из интерфейса для сохранения в профиль."""
        return {
            "printer": self.combo_printers.currentText() if hasattr(self, "combo_printers") else "DWG To PDF.pc3",
            "plot_style": self.combo_style.currentText() if hasattr(self, "combo_style") else "monochrome.ctb",
            "fallback_paper": self.combo_papers.currentText() if hasattr(self, "combo_papers") else "",
            "fallback_paper_canonical": self.paper_dict.get(self.combo_papers.currentText(), "") if hasattr(self, "combo_papers") else "",
            "merge_mode": self.combo_mode.currentText() if hasattr(self, "combo_mode") else "В один файл (PDF)",
            "filename_template": self.combo_template.currentText().strip() if hasattr(self, "combo_template") else "Лист {Номер} - {Наименование}",
            "open_after_print": self.chk_open_after.isChecked() if hasattr(self, "chk_open_after") else True,
            "sync_autocad": self.chk_sync_acad.isChecked() if hasattr(self, "chk_sync_acad") else True,
            "source_mode": self.combo_source.currentText() if hasattr(self, "combo_source") else "Модель (Model Space)",
            "frame_type": self.combo_frame_type.currentData() if hasattr(self, "combo_frame_type") else "spds",
            "custom_block_name": self.edit_block_name.text() if hasattr(self, "edit_block_name") else "",
            "polyline_layer": self.selected_polyline_layer(),
        }

    def on_save_current_profile(self):
        """Сохраняет текущие параметры интерфейса в активный профиль."""
        curr_name = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        if not curr_name:
            return
        current_settings = self.get_current_profile_settings()
        self.profile_manager.save_profile(curr_name, current_settings)
        self.lbl_status_right.setText(f"Настройки сохранены в профиль «{curr_name}»")
        QMessageBox.information(
            self,
            "Профиль сохранён",
            f"Текущие параметры успешно сохранены в профиль «{curr_name}»."
        )

    def on_create_new_profile(self):
        """Создает новый именованный профиль на основе текущих настроек."""
        name, ok = QInputDialog.getText(
            self,
            "Новый профиль",
            "Введите имя нового профиля проекта:"
        )
        if not ok or not name or not name.strip():
            return
        name = name.strip()
        current_settings = self.get_current_profile_settings()
        created, err = self.profile_manager.create_profile(name, current_settings)
        if created:
            self.update_profile_combo()
            self.combo_profile.setCurrentText(name)
            self.lbl_status_right.setText(f"Создан профиль «{name}»")
        else:
            QMessageBox.warning(self, "Ошибка создания профиля", err)

    def show_profile_menu(self):
        """Открывает контекстное меню управления профилями (переименование, удаление, экспорт, импорт)."""
        curr_name = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        menu = QMenu(self)

        act_rename = menu.addAction("✏️ Переименовать...")
        act_delete = menu.addAction("🗑️ Удалить")

        is_builtin = self.profile_manager.is_builtin(curr_name)
        if is_builtin:
            act_rename.setEnabled(False)
            act_rename.setToolTip("Встроенный базовый профиль нельзя переименовать")
            act_delete.setEnabled(False)
            act_delete.setToolTip("Встроенный базовый профиль нельзя удалить")

        menu.addSeparator()
        act_export = menu.addAction("📤 Экспорт профиля в файл...")
        act_import = menu.addAction("📥 Импорт профиля из файла...")

        action = menu.exec(self.btn_menu_profile.mapToGlobal(self.btn_menu_profile.rect().bottomLeft()))
        if action == act_rename:
            self.on_rename_profile()
        elif action == act_delete:
            self.on_delete_profile()
        elif action == act_export:
            self.on_export_profile()
        elif action == act_import:
            self.on_import_profile()

    def on_rename_profile(self):
        """Переименовывает текущий пользовательский профиль."""
        curr_name = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        if self.profile_manager.is_builtin(curr_name):
            QMessageBox.information(self, "Профиль", "Встроенный базовый профиль нельзя переименовать.")
            return
        new_name, ok = QInputDialog.getText(
            self,
            "Переименование профиля",
            "Новое имя профиля:",
            text=curr_name
        )
        if not ok or not new_name or not new_name.strip():
            return
        new_name = new_name.strip()
        renamed, err = self.profile_manager.rename_profile(curr_name, new_name)
        if renamed:
            self.update_profile_combo()
            self.combo_profile.setCurrentText(new_name)
            self.lbl_status_right.setText(f"Профиль переименован в «{new_name}»")
        else:
            QMessageBox.warning(self, "Ошибка переименования", err)

    def on_delete_profile(self):
        """Удаляет текущий пользовательский профиль."""
        curr_name = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        if self.profile_manager.is_builtin(curr_name):
            QMessageBox.information(self, "Профиль", "Встроенный базовый профиль нельзя удалить.")
            return
        reply = QMessageBox.question(
            self,
            "Удаление профиля",
            f"Вы уверены, что хотите удалить профиль «{curr_name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted, err = self.profile_manager.delete_profile(curr_name)
            if deleted:
                self.update_profile_combo()
                self.lbl_status_right.setText(f"Профиль «{curr_name}» удалён")
            else:
                QMessageBox.warning(self, "Ошибка удаления", err)

    def on_export_profile(self):
        """Экспортирует настройки выбранного профиля в JSON-файл."""
        curr_name = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        safe_name = "".join(c for c in curr_name if c.isalnum() or c in " -_").strip() or "профиль"
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Экспорт профиля",
            f"Профиль_{safe_name}.json",
            "JSON Files (*.json)"
        )
        if filepath:
            exported, err = self.profile_manager.export_profile(curr_name, filepath)
            if exported:
                QMessageBox.information(
                    self,
                    "Экспорт завершён",
                    f"Профиль «{curr_name}» успешно экспортирован в:\n{filepath}"
                )
            else:
                QMessageBox.warning(self, "Ошибка экспорта", err)

    def on_import_profile(self):
        """Импортирует профиль из JSON-файла."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Импорт профиля",
            "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if filepath:
            imported, err, new_name = self.profile_manager.import_profile(filepath)
            if imported and new_name:
                self.update_profile_combo()
                self.combo_profile.setCurrentText(new_name)
                QMessageBox.information(
                    self,
                    "Импорт завершён",
                    f"Профиль «{new_name}» успешно импортирован и активирован."
                )
            else:
                QMessageBox.warning(self, "Ошибка импорта", err)

    def save_settings(self, *, window_geometry=None):
        """Сохраняет текущие параметры печати и состояния чекбоксов в config.json."""
        if getattr(self, "_is_loading_config", False):
            return
        
        printer_text = self.combo_printers.currentText()
        style_text = self.combo_style.currentText()
        paper_text = self.combo_papers.currentText()
        mode_text = self.combo_mode.currentText()
        source_text = self.combo_source.currentText()
        template_text = self.combo_template.currentText().strip() if hasattr(self, "combo_template") else ""
        active_prof = self.combo_profile.currentText().strip() if hasattr(self, "combo_profile") else ""
        theme_val = self.combo_theme.currentData() if hasattr(self, "combo_theme") else getattr(self, "current_theme", "dark_catppuccin")
        frame_type_val = self.combo_frame_type.currentData() if hasattr(self, "combo_frame_type") else "spds"
        custom_block_val = self.edit_block_name.text() if hasattr(self, "edit_block_name") else ""
        hidden_cols = [c for c in range(self.table.columnCount()) if self.table.isColumnHidden(c)]
        
        current_cfg = self.config_manager.load()
        if not isinstance(current_cfg, dict):
            current_cfg = {}
        settings = {
            "printer": printer_text if printer_text else current_cfg.get("printer", "DWG To PDF.pc3"),
            "plot_style": style_text if style_text else current_cfg.get("plot_style", "monochrome.ctb"),
            "fallback_paper": paper_text if paper_text else current_cfg.get("fallback_paper", ""),
            "fallback_paper_canonical": (self.paper_dict.get(paper_text, "") if paper_text
                                         else current_cfg.get("fallback_paper_canonical", "")),
            "merge_mode": mode_text if mode_text else current_cfg.get("merge_mode", "В один файл (PDF)"),
            "filename_template": template_text if template_text else current_cfg.get("filename_template", "Лист {Номер} - {Наименование}"),
            "active_profile": active_prof if active_prof else current_cfg.get("active_profile", "По умолчанию"),
            "open_after_print": self.chk_open_after.isChecked(),
            "sync_autocad": self.chk_sync_acad.isChecked(),
            "source_mode": source_text if source_text else current_cfg.get("source_mode", "Модель (Model Space)"),
            "frame_type": frame_type_val if frame_type_val else current_cfg.get("frame_type", "spds"),
            "custom_block_name": custom_block_val,
            "polyline_layer": self.selected_polyline_layer(),
            "theme": theme_val if theme_val else current_cfg.get("theme", "dark_catppuccin"),
            "hidden_columns": hidden_cols,
            "settings_collapsed": self.btn_toggle_settings.isChecked(),
        }
        if window_geometry is not None:
            settings["window_geometry"] = window_geometry
        self.config_manager.save(settings)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.handle_dropped_urls(event.mimeData().urls())
        else:
            super().dropEvent(event)

    def handle_dropped_urls(self, urls):
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        dwg_files = []
        for p in paths:
            if os.path.isfile(p) and p.lower().endswith(".dwg"):
                dwg_files.append(p)
            elif os.path.isdir(p):
                for root, _, files in os.walk(p):
                    for f in files:
                        if f.lower().endswith(".dwg") and not f.startswith(".~"):
                            dwg_files.append(os.path.join(root, f))
        if dwg_files:
            self.process_batch_dwg_files(dwg_files)
        else:
            QMessageBox.information(self, "Файлы не найдены", "Среди перетащенных объектов не найдено файлов .dwg")

    def add_dwg_files_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите чертежи AutoCAD (DWG)",
            "",
            "AutoCAD Drawings (*.dwg);;All Files (*.*)"
        )
        if files:
            self.process_batch_dwg_files(files)

    def add_dwg_folder_dialog(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку с чертежами AutoCAD (DWG)",
            ""
        )
        if folder:
            dwg_files = []
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.lower().endswith(".dwg") and not f.startswith(".~"):
                        dwg_files.append(os.path.join(root, f))
            if not dwg_files:
                QMessageBox.information(self, "Поиск DWG", f"В папке '{folder}' не найдено файлов .dwg")
                return
            self.process_batch_dwg_files(dwg_files)

    def clear_frames(self):
        self.frames = []
        self._is_updating_table = True
        try:
            self.table.setRowCount(0)
        finally:
            self._is_updating_table = False
        try:
            self.connector.clear_highlight()
        except Exception:
            pass
        self.update_format_filter_items()
        self.apply_filter()
        self.update_print_counter()

    def close_opened_documents_dialog(self):
        """
        Закрывает в AutoCAD все чертежи, которые были открыты этой программой,
        не затрагивая чертежи пользователя.
        """
        try:
            self.connector.connect()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка подключения", f"Не удалось подключиться к AutoCAD:\n{e}\n\nУбедитесь, что AutoCAD запущен.")
            return

        try:
            self.connector.clear_highlight()
            closed_count = self.connector.close_opened_documents()
            self.refresh_document_status()
            if closed_count > 0:
                QMessageBox.information(
                    self,
                    "Закрытие чертежей",
                    f"Успешно закрыто чертежей, открытых программой: {closed_count}."
                )
            else:
                QMessageBox.information(
                    self,
                    "Закрытие чертежей",
                    "Нет чертежей, открытых программой (все чертежи уже закрыты или были открыты вами вручную)."
                )
        except Exception as e:
            QMessageBox.warning(
                self,
                "Ошибка",
                f"Произошла ошибка при закрытии чертежей:\n{e}"
            )

    def process_batch_dwg_files(self, file_paths):
        if not file_paths:
            return
            
        try:
            self.connector.connect()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка подключения", f"Не удалось подключиться к AutoCAD:\n{e}\n\nУбедитесь, что AutoCAD запущен.")
            return

        source_mode = self.combo_source.currentText()
        progress_dlg = PrintProgressDialog(
            len(file_paths),
            parent=self,
            title="Пакетное сканирование DWG",
            title_text="Поиск листов в чертежах...",
            cancel_status="Отмена сканирования, завершение текущего файла..."
        )
        progress_dlg.show()
        QApplication.processEvents()

        def on_scan_progress(idx, total, fname, status):
            progress_dlg.set_progress(idx, status)

        def is_cancelled():
            QApplication.processEvents()
            return progress_dlg.is_cancelled

        try:
            frame_type = self.combo_frame_type.currentData() if hasattr(self, "combo_frame_type") else "spds"
            custom_block = self.edit_block_name.text() if hasattr(self, "edit_block_name") else ""
            new_frames = self.scanner.scan_files(
                connector=self.connector,
                file_paths=file_paths,
                source_mode=source_mode,
                frame_type=frame_type,
                custom_block_name=custom_block,
                polyline_layer=self.selected_polyline_layer(),
                progress_callback=on_scan_progress,
                is_cancelled=is_cancelled
            )
            progress_dlg.close()

            scan_rep = getattr(self.scanner, "last_scan_report", None)
            if scan_rep:
                get_stats_manager().record_scan_batch(scan_rep)
            if scan_rep and scan_rep.cancelled and not new_frames:
                if scan_rep.failed_files_count > 0:
                    dlg = ReportDialog(scan_rep, current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
                    dlg.repeat_scan_requested.connect(self.process_batch_dwg_files)
                    dlg.exec()
                else:
                    self.status_bar.showMessage("Сканирование чертежей отменено пользователем", 5000)
                return

            if not new_frames:
                if scan_rep and (scan_rep.failed_files_count > 0 or scan_rep.has_warnings):
                    dlg = ReportDialog(scan_rep, current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
                    dlg.repeat_scan_requested.connect(self.process_batch_dwg_files)
                    dlg.exec()
                else:
                    QMessageBox.information(self, "Результат", "В указанных чертежах рамки/листы не найдены.")
                return

            self._is_updating_table = True
            try:
                for frame in new_frames:
                    self.frames.append(frame)
                    self.add_table_row(
                        True,
                        frame.sheet_number,
                        frame.sheet_name,
                        frame.paper_format,
                        frame.source_type,
                        dwg_name=frame.dwg_name,
                        doc_code=frame.doc_code,
                        object_name=frame.object_name,
                        building_name=frame.building_name,
                        fallback_warning=getattr(frame, "fallback_warning", "")
                    )
            finally:
                self._is_updating_table = False

            # Выполняем сквозную сортировку по номерам листов для всего общего списка чертежей
            self.sort_by_sheet_number()
            self.refresh_document_status()
            self.update_format_filter_items()
            self.apply_filter()

            if scan_rep and (scan_rep.failed_files_count > 0 or scan_rep.empty_files_count > 0
                             or scan_rep.cancelled or scan_rep.has_warnings):
                dlg = ReportDialog(scan_rep, current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
                dlg.repeat_scan_requested.connect(self.process_batch_dwg_files)
                dlg.exec()
            else:
                QMessageBox.information(
                    self,
                    "Сканирование завершено",
                    f"Обработано файлов: {len(file_paths)}\nДобавлено листов: {len(new_frames)} (всего в очереди: {len(self.frames)})"
                )


        except Exception as e:
            progress_dlg.close()
            log_error("Ошибка при пакетном сканировании", exc=e, module="Scanner")
            QMessageBox.critical(self, "Ошибка", f"Ошибка при пакетном сканировании: {e}\n\nЖурнал ошибок доступен по клавише F2 («Диагностика»).")
        finally:
            progress_dlg.close()

    def refresh_document_status(self):
        ok_col, err_col = get_theme_status_colors(getattr(self, "current_theme", "dark_catppuccin"))
        try:
            self.connector.connect()
            doc_name = self.connector.get_active_document_name()
            self.lbl_document.setText(doc_name)
            self.lbl_document.setStyleSheet(f"color: {ok_col}; font-weight: bold;")
            
            # Инициализируем принтер с коннектором для поддержки переключения чертежей
            self.printer = BatchPrinter(self.connector.doc, connector=self.connector)
            if self.connector.doc:
                self.load_printer_settings()
            else:
                # Нет открытого чертежа — AutoCAD не отдаёт списки плоттеров. Показываем
                # сохранённые настройки, чтобы можно было печатать из папки.
                self.load_printer_settings_from_config()
            
        except Exception as e:
            self.lbl_document.setText("Ошибка подключения")
            self.lbl_document.setStyleSheet(f"color: {err_col}; font-weight: bold;")
            if self.printer:
                self.printer.available_paper_formats = None
            self._reset_paper_warnings()

            
    def load_printer_settings(self):
        if not self.printer: return
        
        was_loading = self._is_loading_config
        self._is_loading_config = True
        try:
            # Списки теперь настоящие — убираем подсказку «загрузятся позже»
            for combo in (self.combo_printers, self.combo_papers, self.combo_style):
                combo.setToolTip("")
            # Загружаем принтеры
            printers = self.printer.get_printers()
            self.combo_printers.blockSignals(True)
            self.combo_printers.clear()
            self.combo_printers.addItems(printers)
            
            # Восстанавливаем сохраненный принтер или DWG To PDF по умолчанию
            saved_printer = self.config_manager.get("printer", "DWG To PDF.pc3")
            if isinstance(saved_printer, str):
                idx = self.combo_printers.findText(saved_printer)
                if idx < 0:
                    idx = self.combo_printers.findText("DWG To PDF.pc3")
                if idx >= 0:
                    self.combo_printers.setCurrentIndex(idx)
            self.combo_printers.blockSignals(False)
            
            # Загружаем форматы
            self.update_paper_sizes(self.combo_printers.currentText())
            
            # Загружаем стили
            styles = self.printer.get_plot_styles()
            self.combo_style.blockSignals(True)
            self.combo_style.clear()
            self.combo_style.addItems(styles)
            
            # Восстанавливаем сохраненный стиль или monochrome.ctb по умолчанию
            saved_style = self.config_manager.get("plot_style", "monochrome.ctb")
            if isinstance(saved_style, str):
                idx_style = self.combo_style.findText(saved_style)
                if idx_style < 0:
                    idx_style = self.combo_style.findText("monochrome.ctb")
                if idx_style >= 0:
                    self.combo_style.setCurrentIndex(idx_style)
            self.combo_style.blockSignals(False)
        finally:
            self._is_loading_config = was_loading
        
    def load_printer_settings_from_config(self):
        """
        Без открытого чертежа (стартовая вкладка AutoCAD) списки плоттеров, форматов и стилей
        получить нельзя. Заполняем поля сохранёнными значениями из config.json (или стандартными),
        чтобы печать из папки работала; полные списки загрузятся, когда появится чертёж.
        """
        was_loading = self._is_loading_config
        self._is_loading_config = True
        try:
            printer = self.config_manager.get("printer") or "DWG To PDF.pc3"
            style = self.config_manager.get("plot_style") or "monochrome.ctb"
            paper = self.config_manager.get("fallback_paper") or ""
            if "b5" in paper.lower() or "в5" in paper.lower():
                paper = ""
            paper_sys = self.config_manager.get("fallback_paper_canonical") or paper

            hint = "Полный список появится, когда в AutoCAD будет открыт чертёж (кнопка «Обновить связь»)"
            for combo, value in ((self.combo_printers, printer), (self.combo_papers, paper), (self.combo_style, style)):
                combo.blockSignals(True)
                combo.clear()
                if value:
                    combo.addItem(value)
                combo.setToolTip(hint)
                combo.blockSignals(False)
            self.paper_dict = {paper: paper_sys} if paper else {}
        finally:
            self._is_loading_config = was_loading
        self._reset_paper_warnings()

    def update_paper_sizes(self, printer_name: str):
        if not self.printer:
            return
        if not printer_name:
            self.printer.available_paper_formats = None
            self._reset_paper_warnings()
            return
        self.paper_dict = self.printer.get_media_names(printer_name)
        
        self.combo_papers.blockSignals(True)
        self.combo_papers.clear()
        papers = list(self.paper_dict.keys())
        self.combo_papers.addItems(papers)
        
        # Пытаемся восстановить сохраненный или ISO full bleed A2
        # Восстановление сохраненного формата (игнорируя устаревший случайный B5)
        saved_paper = self.config_manager.get("fallback_paper", "")
        if isinstance(saved_paper, str) and ("b5" in saved_paper.lower() or "в5" in saved_paper.lower()):
            saved_paper = ""

        idx_saved = -1
        if isinstance(saved_paper, str) and saved_paper:
            idx_saved = self.combo_papers.findText(saved_paper)
        if idx_saved >= 0:
            self.combo_papers.setCurrentIndex(idx_saved)
        else:
            # Ищем наилучший резервный формат (приоритет: А3 без полей -> любой А3 -> А1 без полей -> любой А1 -> А2)
            chosen_idx = -1

            def is_bleed(p_name: str) -> bool:
                pl = p_name.lower()
                return "без полей" in pl or "full bleed" in pl

            # 1. А3 альбомный без полей (420 x 297)
            for i, p in enumerate(papers):
                pl = p.lower()
                if ("a3" in pl or "а3" in pl) and is_bleed(p) and "420" in pl:
                    chosen_idx = i
                    break
            # 2. Любой А3 без полей
            if chosen_idx < 0:
                for i, p in enumerate(papers):
                    pl = p.lower()
                    if ("a3" in pl or "а3" in pl) and is_bleed(p):
                        chosen_idx = i
                        break
            # 3. Любой А3
            if chosen_idx < 0:
                for i, p in enumerate(papers):
                    pl = p.lower()
                    if "a3" in pl or "а3" in pl:
                        chosen_idx = i
                        break
            # 4. А1 без полей
            if chosen_idx < 0:
                for i, p in enumerate(papers):
                    pl = p.lower()
                    if ("a1" in pl or "а1" in pl) and is_bleed(p):
                        chosen_idx = i
                        break
            # 5. Любой А1
            if chosen_idx < 0:
                for i, p in enumerate(papers):
                    pl = p.lower()
                    if "a1" in pl or "а1" in pl:
                        chosen_idx = i
                        break
            # 6. А2 без полей
            if chosen_idx < 0:
                for i, p in enumerate(papers):
                    pl = p.lower()
                    if ("a2" in pl or "а2" in pl) and is_bleed(p):
                        chosen_idx = i
                        break

            if chosen_idx >= 0:
                self.combo_papers.setCurrentIndex(chosen_idx)
        self.combo_papers.blockSignals(False)
        self._reset_paper_warnings()
                
    def scan_frames(self):
        try:
            self.connector.connect()
            self.connector.clear_highlight()
            
            is_layouts_mode = "Layout" in self.combo_source.currentText() or "Листы" in self.combo_source.currentText()
            frame_type = self.combo_frame_type.currentData() if hasattr(self, "combo_frame_type") else "spds"
            custom_block = self.edit_block_name.text() if hasattr(self, "edit_block_name") else ""
            
            if is_layouts_mode:
                self.frames = self.scanner.scan_layouts(
                    self.connector.doc,
                    frame_type=frame_type,
                    custom_block_name=custom_block
                )
            else:
                self.frames = self.scanner.scan_document(
                    self.connector.doc,
                    frame_type=frame_type,
                    custom_block_name=custom_block,
                    space="model",
                    polyline_layer=self.selected_polyline_layer(),
                )
            
            # Обновляем таблицу
            self._is_updating_table = True
            try:
                self.table.setRowCount(0)
                for frame in self.frames:
                    self.add_table_row(
                        True,
                        frame.sheet_number,
                        frame.sheet_name,
                        frame.paper_format,
                        frame.source_type,
                        dwg_name=frame.dwg_name,
                        doc_code=frame.doc_code,
                        object_name=frame.object_name,
                        building_name=frame.building_name,
                        fallback_warning=getattr(frame, "fallback_warning", "")
                    )
            finally:
                self._is_updating_table = False

            self.update_format_filter_items()
            self.apply_filter()
            
            warnings = self.scanner.last_scan_warnings
            if warnings:
                summary = f"Найдено рамок или листов: {len(self.frames)}."
                QMessageBox.warning(self, "Результат поиска", "\n".join([summary, *warnings]))
            elif not self.frames:
                msg = "Вкладки листов (Layouts) не найдены!" if is_layouts_mode else "Рамки не найдены!"
                QMessageBox.information(self, "Результат", msg)
                
        except Exception as e:
            log_error("Ошибка при сканировании чертежа", exc=e, module="Scanner")
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сканировании: {e}\n\nЖурнал ошибок доступен по клавише F2 («Диагностика»).")

    def add_table_row(
        self,
        checked: bool,
        num: str,
        name: str,
        paper_format: str,
        source: str,
        dwg_name: str = "",
        doc_code: str = "",
        object_name: str = "",
        building_name: str = "",
        fallback_warning: str = "",
        frame: Any = None
    ):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        chk_widget = QWidget()
        chk_layout = QHBoxLayout(chk_widget)
        chk_layout.setContentsMargins(0, 0, 0, 0)
        chk_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chk = QCheckBox()
        chk.setChecked(checked)
        chk.setStyleSheet("QCheckBox::indicator { width: 18px; height: 18px; }")
        
        # Обновляем счетчик при клике
        chk.toggled.connect(self.update_print_counter)
        
        chk_layout.addWidget(chk)
        self.table.setCellWidget(row, 0, chk_widget)
        
        item_num = QTableWidgetItem(num)
        item_num.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        item_code = QTableWidgetItem(doc_code)
        item_code.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item_code.setToolTip(doc_code)

        item_name = QTableWidgetItem(name)
        item_name.setToolTip(name)

        item_obj = QTableWidgetItem(object_name)
        item_obj.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item_obj.setToolTip(object_name)

        item_bld = QTableWidgetItem(building_name)
        item_bld.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item_bld.setToolTip(building_name)

        item_fmt = QTableWidgetItem(paper_format or "Не определен")
        item_fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        item_dwg = QTableWidgetItem(dwg_name)
        item_dwg.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        item_dwg.setToolTip(dwg_name)
        
        item_src = QTableWidgetItem(source)
        item_src.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        for it in (item_num, item_code, item_name, item_obj, item_bld, item_fmt, item_dwg, item_src):
            it.setFlags(flags)
            
        self.table.setItem(row, 1, item_num)
        self.table.setItem(row, 2, item_code)
        self.table.setItem(row, 3, item_name)
        self.table.setItem(row, 4, item_obj)
        self.table.setItem(row, 5, item_bld)
        self.table.setItem(row, 6, item_fmt)
        self.table.setItem(row, 7, item_dwg)
        self.table.setItem(row, 8, item_src)

        f_obj = frame if frame else (self.frames[row] if row < len(self.frames) else None)
        if f_obj:
            if f_obj.is_empty_layout:
                item_name.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
                item_name.setToolTip(
                    f"{name}\n\nПустой лист: в модели нет объектов, а на листе нет содержимого "
                    "кроме возможных границ видовых экранов."
                )
            self._update_format_item(row, f_obj)
        elif fallback_warning:
            item_fmt.setText(f"⚠️ {paper_format}")
            item_fmt.setToolTip(f"⚠️ {fallback_warning}")

        if not getattr(self, "_is_updating_table", False):
            self.update_print_counter()

    def _update_format_item(self, row: int, frame: Any):
        """Оформляет ячейку формата: текст, масштаб, бейдж ⚠️/✏️ и всплывающую подсказку."""
        item = self.table.item(row, 6)
        if not item:
            return

        fmt_display = getattr(frame, "paper_format", "") or "Не определен"
        warn = getattr(frame, "fallback_warning", "")
        is_ambig = getattr(frame, "is_ambiguous", False)
        user_over = getattr(frame, "user_override", False)
        fmt_reason = getattr(frame, "format_reason", "")
        scale_val = getattr(frame, "scale", 1) or 1
        pos_fmts = getattr(frame, "possible_formats", [])

        if warn:
            item.setText(f"⚠️ {fmt_display}")
            item.setToolTip(f"⚠️ {warn}\n\n(Дважды кликните по ячейке для ручного выбора формата)")
        elif is_ambig and not user_over:
            item.setText(f"⚠️ {fmt_display}")
            alts = [f"{af} (М1:{asc})" for af, asc in pos_fmts if (af, asc) != (fmt_display, scale_val)]
            alt_text = f"\nВозможные альтернативы: {', '.join(alts)}" if alts else ""
            item.setToolTip(
                f"⚠️ Неоднозначный формат!\n"
                f"Выбран: {fmt_display} (масштаб 1:{scale_val}), основание: {fmt_reason}."
                f"{alt_text}\n\n"
                f"Дважды кликните по ячейке или нажмите правой кнопкой, чтобы уточнить формат."
            )
        elif user_over:
            item.setText(f"✏️ {fmt_display}")
            item.setToolTip(
                f"Формат задан вручную: {fmt_display} (масштаб 1:{scale_val})\n"
                f"Основание: {fmt_reason}\n\n"
                f"Дважды кликните для изменения."
            )
        elif fmt_display not in ALL_FORMATS:
            item.setText(f"⚠️ {fmt_display}")
            item.setToolTip(
                f"⚠️ Нестандартный формат «{fmt_display}». При печати будет применен резервный формат.\n"
                f"(Дважды кликните для выбора стандартного формата)"
            )
        else:
            scale_str = f" (М1:{scale_val})" if scale_val > 1 else ""
            item.setText(f"{fmt_display}{scale_str}")
            item.setToolTip(
                f"Формат: {fmt_display}{scale_str}\n"
                f"Основание: {fmt_reason or 'Геометрия'}"
            )

        media_map = getattr(self.printer, "available_paper_formats", None)
        if not warn and isinstance(media_map, dict) and frame.paper_format not in media_map:
            printer_name = self.combo_printers.currentText()
            fallback = self.combo_papers.currentText() or media_map.get("A3") or media_map.get("A1")
            details = f"У плоттера «{printer_name}» нет бумаги для формата {fmt_display}."
            details += f" При печати будет использован резервный формат «{fallback}»." if fallback else (
                " Выберите резервный формат или другой плоттер."
            )
            if not item.text().startswith("⚠"):
                item.setText(f"⚠️ {item.text()}")
            item.setToolTip(f"{details}\n\n{item.toolTip()}")

    def _refresh_table_formats(self):
        """Обновляет колонку форматов с индикацией предупреждений о резервном формате и неоднозначности."""
        for row in range(self.table.rowCount()):
            if row < len(self.frames):
                frame = self.frames[row]
                self._update_format_item(row, frame)
        
        if not getattr(self, "_is_updating_table", False):
            self.update_print_counter()

    def get_selected_sheet_rows(self) -> List[int]:
        """Возвращает список индексов выделенных строк таблицы"""
        if not self.table.selectionModel():
            return []
        rows = sorted(list(set(idx.row() for idx in self.table.selectionModel().selectedRows())))
        return rows

    def change_sheet_format(self, row: int):
        """Открывает диалог ручного уточнения формата и масштаба листа."""
        if not (0 <= row < len(self.frames)):
            return
        frame = self.frames[row]
        selected_rows = self.get_selected_sheet_rows()
        selected_count = len(selected_rows) if (selected_rows and row in selected_rows and len(selected_rows) > 1) else 1

        dlg = FormatSelectDialog(
            parent=self,
            frame=frame,
            selected_count=selected_count
        )
        if dlg.exec():
            new_fmt = dlg.get_selected_format()
            new_scale = dlg.get_selected_scale()
            apply_all = dlg.apply_to_selected_rows()

            target_rows = selected_rows if apply_all else [row]
            if row not in target_rows:
                target_rows.append(row)

            for r in target_rows:
                if 0 <= r < len(self.frames):
                    self._set_manual_format(r, new_fmt, new_scale)

            self.update_format_filter_items()
            self.apply_filter()
            log_info(f"Формат листа {frame.sheet_number} изменен пользователем на {new_fmt} (М1:{new_scale})", module="UI")

    def quick_switch_format(self, row: int, new_format: str, new_scale: float):
        """Быстрое переключение формата на альтернативный вариант из контекстного меню."""
        if not (0 <= row < len(self.frames)):
            return
        self._set_manual_format(row, new_format, new_scale)
        self.update_format_filter_items()
        self.apply_filter()
        frame = self.frames[row]
        log_info(f"Быстрое переключение формата листа {frame.sheet_number} на {new_format} (М1:{new_scale})", module="UI")

    def _set_manual_format(self, row: int, paper_format: str, scale: float):
        frame = self.frames[row]
        bounds = frame.format_candidate_bounds.get((paper_format, scale))
        if bounds is not None:
            x1, y1, x2, y2 = bounds
            frame.min_point = (x1, y1, frame.min_point[2])
            frame.max_point = (x2, y2, frame.max_point[2])
        frame.paper_format = paper_format
        frame.scale = scale
        frame.format_reason = f"Задано вручную: {paper_format} (М1:{scale})"
        frame.is_ambiguous = False
        frame.user_override = True
        frame.fallback_warning = ""
        self._update_format_item(row, frame)
        
    def is_filter_active(self) -> bool:
        """Возвращает True, если активен поиск по тексту или выбран конкретный формат."""
        if not hasattr(self, 'txt_search') or not hasattr(self, 'combo_filter_format'):
            return False
        search_text = self.txt_search.text().strip()
        fmt_idx = self.combo_filter_format.currentIndex()
        return bool(search_text) or (fmt_idx > 0)

    def update_format_filter_items(self):
        """Обновляет выпадающий список форматов в комбобоксе фильтра на основе текущих рамок."""
        if not hasattr(self, 'combo_filter_format'):
            return
        cur_fmt = self.combo_filter_format.currentText()
        if " (" in cur_fmt:
            cur_fmt = cur_fmt.split(" (")[0].strip()

        self.combo_filter_format.blockSignals(True)
        self.combo_filter_format.clear()

        counts = {}
        for f in self.frames:
            fmt = f.paper_format or "Не определен"
            counts[fmt] = counts.get(fmt, 0) + 1

        def format_sort_key(name):
            import re
            m = re.match(r'A(\d+)', name, re.IGNORECASE)
            if m:
                return (0, int(m.group(1)), name)
            return (1, 0, name)

        sorted_formats = sorted(counts.keys(), key=format_sort_key)
        total_count = len(self.frames)
        self.combo_filter_format.addItem(f"Все форматы ({total_count})")

        selected_idx = 0
        for i, fmt in enumerate(sorted_formats):
            label = f"{fmt} ({counts[fmt]})"
            self.combo_filter_format.addItem(label)
            if fmt == cur_fmt:
                selected_idx = i + 1

        self.combo_filter_format.setCurrentIndex(selected_idx)
        self.combo_filter_format.blockSignals(False)

    def apply_filter(self):
        """Фильтрует строки таблицы на лету по поисковому запросу и выбранному формату."""
        if not hasattr(self, 'txt_search') or not hasattr(self, 'combo_filter_format'):
            return
        search_text = self.txt_search.text().strip().lower()
        cur_fmt = self.combo_filter_format.currentText()
        selected_format = None
        if self.combo_filter_format.currentIndex() > 0:
            selected_format = cur_fmt.split(" (")[0].strip()

        for r in range(self.table.rowCount()):
            if r >= len(self.frames):
                break
            frame = self.frames[r]

            match_fmt = True
            if selected_format:
                match_fmt = (frame.paper_format == selected_format)

            match_text = True
            if search_text:
                num_str = str(frame.sheet_number or "").lower()
                name_str = str(frame.sheet_name or "").lower()
                fmt_str = str(frame.paper_format or "").lower()
                dwg_str = str(frame.dwg_name or "").lower()
                code_str = str(getattr(frame, 'doc_code', '') or '').lower()
                obj_str = str(getattr(frame, 'object_name', '') or '').lower()
                bld_str = str(getattr(frame, 'building_name', '') or '').lower()
                match_text = (
                    search_text in num_str or
                    search_text in name_str or
                    search_text in code_str or
                    search_text in obj_str or
                    search_text in bld_str or
                    search_text in fmt_str or
                    search_text in dwg_str
                )

            visible = match_fmt and match_text
            self.table.setRowHidden(r, not visible)

        filter_active = self.is_filter_active()
        if hasattr(self, 'btn_move_up') and hasattr(self, 'btn_move_down'):
            self.btn_move_up.setEnabled(not filter_active)
            self.btn_move_down.setEnabled(not filter_active)
            if filter_active:
                self.btn_move_up.setToolTip("Сбросьте поиск/фильтр для ручного перемещения строк")
                self.btn_move_down.setToolTip("Сбросьте поиск/фильтр для ручного перемещения строк")
                self.table.setDragEnabled(False)
            else:
                self.btn_move_up.setToolTip("Поднять выбранный лист выше в очереди печати")
                self.btn_move_down.setToolTip("Опустить выбранный лист ниже в очереди печати")
                self.table.setDragEnabled(True)

        self.update_print_counter()

    def reset_filter(self):
        """Сбрасывает поисковую строку и восстанавливает показ всех форматов."""
        if hasattr(self, 'txt_search'):
            self.txt_search.blockSignals(True)
            self.txt_search.clear()
            self.txt_search.blockSignals(False)
        if hasattr(self, 'combo_filter_format'):
            self.combo_filter_format.blockSignals(True)
            self.combo_filter_format.setCurrentIndex(0)
            self.combo_filter_format.blockSignals(False)

        for r in range(self.table.rowCount()):
            self.table.setRowHidden(r, False)

        if hasattr(self, 'btn_move_up') and hasattr(self, 'btn_move_down'):
            self.btn_move_up.setEnabled(True)
            self.btn_move_down.setEnabled(True)
            self.btn_move_up.setToolTip("Поднять выбранный лист выше в очереди печати")
            self.btn_move_down.setToolTip("Опустить выбранный лист ниже в очереди печати")
            self.table.setDragEnabled(True)

        self.update_print_counter()

    def get_frames_to_print(self) -> list:
        """Возвращает список рамок, отмеченных галочкой и видимых в таблице."""
        selected = []
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                chk_widget = self.table.cellWidget(i, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    if chk.isChecked() and i < len(self.frames):
                        selected.append(self.frames[i])
        return selected

    def update_print_counter(self):
        self.update_template_preview()
        count = 0
        total_visible = 0
        total_sheets = self.table.rowCount()
        selected_formats = {}
        selected_dwgs = set()

        for i in range(total_sheets):
            if not self.table.isRowHidden(i):
                total_visible += 1
                if self.is_row_checked(i):
                    count += 1
                    # Формат листа (колонка 6)
                    fmt = ""
                    fmt_item = self.table.item(i, 6)
                    if fmt_item and fmt_item.text().strip():
                        fmt = fmt_item.text().strip()
                    elif i < len(self.frames) and self.frames[i].paper_format:
                        fmt = self.frames[i].paper_format.strip()
                    if not fmt:
                        fmt = "—"
                    selected_formats[fmt] = selected_formats.get(fmt, 0) + 1

                    # Имя чертежа (колонка 7)
                    dwg = ""
                    dwg_item = self.table.item(i, 7)
                    if dwg_item and dwg_item.text().strip():
                        dwg = dwg_item.text().strip()
                    elif i < len(self.frames) and self.frames[i].dwg_name:
                        dwg = self.frames[i].dwg_name.strip()
                    if dwg:
                        selected_dwgs.add(dwg)

        if self.is_filter_active():
            self.btn_print.setText(f"ПЕЧАТЬ ({count} из {total_visible} листов)")
        else:
            self.btn_print.setText(f"ПЕЧАТЬ ({count} листов)")
        self.btn_print.setEnabled(count > 0)

        self.update_status_bar(total_sheets, total_visible, count, selected_formats, selected_dwgs)

    def update_status_bar(self, total_sheets: int, total_visible: int, count: int, selected_formats: dict, selected_dwgs: set):
        if not hasattr(self, "lbl_status_left") or not hasattr(self, "lbl_status_right"):
            return

        theme_id = getattr(self, "current_theme", "dark_catppuccin")
        ok_col, err_col = get_theme_status_colors(theme_id)
        theme_meta = THEMES.get(theme_id, THEMES["dark_catppuccin"])
        accent_col = theme_meta.get("accent_color", "#89b4fa")
        text_muted = theme_meta.get("text_muted", "#a6adc8")

        if total_sheets == 0:
            self.lbl_status_left.setText("<span>Листов в очереди: <b>0</b></span>")
            self.lbl_status_right.setText("Добавьте чертежи .dwg или нажмите «Найти рамки» | F2 — Диагностика")
            return

        def format_sort_key(fmt: str):
            f = fmt.strip().upper().replace("А", "A")
            import re
            m = re.match(r"A(\d)(?:[XХ](\d+))?", f)
            if m:
                base = int(m.group(1))
                mult = int(m.group(2)) if m.group(2) else 1
                return (0, -base, mult)
            return (1, f)

        sorted_fmt_keys = sorted(selected_formats.keys(), key=format_sort_key)
        fmt_parts = [f"{k}x{selected_formats[k]}" for k in sorted_fmt_keys]
        fmt_str = f" <span style='color: {accent_col};'>({', '.join(fmt_parts)})</span>" if fmt_parts else ""

        parts = []
        parts.append(f"Всего листов: <b>{total_sheets}</b>")
        if self.is_filter_active():
            parts.append(f"В фильтре: <b>{total_visible}</b>")

        if count > 0:
            parts.append(f"К печати: <b style='color: {ok_col};'>{count}</b>{fmt_str}")
        else:
            parts.append(f"К печати: <b style='color: {text_muted};'>0</b>")

        if selected_dwgs:
            parts.append(f"Чертежей: <b>{len(selected_dwgs)}</b>")

        sep = f" &nbsp;<span style='color: {text_muted};'>|</span>&nbsp; "
        self.lbl_status_left.setText(sep.join(parts))

        if self.is_filter_active():
            self.lbl_status_right.setText("Фильтр активен")
        elif count == 0:
            self.lbl_status_right.setText("Отметьте листы галочками | F1 — Инструкция | F2 — Диагностика")
        else:
            self.lbl_status_right.setText("Двойной клик — в AutoCAD | F1 — Инструкция | F2 — Диагностика")

    def is_row_checked(self, row: int) -> bool:
        chk_widget = self.table.cellWidget(row, 0)
        if chk_widget:
            chk = chk_widget.layout().itemAt(0).widget()
            return chk.isChecked()
        return True

    def on_key_move_requested(self, direction: int):
        if self.is_filter_active():
            return
        if direction < 0:
            self.move_row_up()
        else:
            self.move_row_down()

    def move_row_up(self):
        if self.is_filter_active():
            return
        row = self.table.currentRow()
        if row > 0:
            self.move_row(row, row - 1)

    def move_row_down(self):
        if self.is_filter_active():
            return
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount() - 1:
            self.move_row(row, row + 1)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._check_restored_geometry:
            return
        self._check_restored_geometry = False
        if self.isMaximized() or self.isFullScreen():
            return

        available = self.screen().availableGeometry()
        frame = self.frameGeometry()
        if available.contains(frame):
            return
        self.resize(
            min(self.width(), available.width() - (frame.width() - self.width())),
            min(self.height(), available.height() - (frame.height() - self.height())),
        )
        frame = self.frameGeometry()
        frame.moveLeft(max(available.left(), min(frame.left(), available.right() - frame.width() + 1)))
        frame.moveTop(max(available.top(), min(frame.top(), available.bottom() - frame.height() + 1)))
        self.move(frame.topLeft())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_table_tools_layout(event.size().width())

    def update_table_tools_layout(self, total_width: int):
        """Адаптивное переключение кнопок под таблицей: 1 ряд при широком окне, 2 при узком."""
        single = (total_width >= 1250)
        if getattr(self, "_is_single_row_tools", None) == single:
            return
        self._is_single_row_tools = single

        while self.table_tools_row1.count():
            self.table_tools_row1.takeAt(0)
        while self.table_tools_row2.count():
            self.table_tools_row2.takeAt(0)

        if single:
            self.table_tools_row2_widget.setVisible(False)
            for w in [self.btn_select_all, self.btn_deselect_all, self.btn_sort_num,
                      self.btn_export, self.btn_move_up, self.btn_move_down]:
                self.table_tools_row1.addWidget(w)
            self.table_tools_row1.addStretch()
            self.table_tools_row1.addWidget(self.chk_sync_acad)
            self.table_tools_row1.addWidget(self.btn_show_acad)
        else:
            self.table_tools_row2_widget.setVisible(True)
            for w in [self.btn_select_all, self.btn_deselect_all, self.btn_sort_num, self.btn_export]:
                self.table_tools_row1.addWidget(w)
            self.table_tools_row1.addStretch()

            for w in [self.btn_move_up, self.btn_move_down]:
                self.table_tools_row2.addWidget(w)
            self.table_tools_row2.addStretch()
            self.table_tools_row2.addWidget(self.chk_sync_acad)
            self.table_tools_row2.addWidget(self.btn_show_acad)

    def on_column_resized(self, logical_index, old_size, new_size):
        if getattr(self, "_is_loading_config", False):
            return
        try:
            header = self.table.horizontalHeader()
            widths = [header.sectionSize(i) for i in range(self.table.columnCount())]
            self.config_manager.set("table_column_widths", widths)
            self.config_manager.save()
        except Exception:
            pass

    def on_row_drag_moved(self, from_row: int, to_row: int):
        if self.is_filter_active():
            return
        if from_row != to_row:
            self.move_row(from_row, to_row)

    def move_row(self, from_row: int, to_row: int):
        if self.is_filter_active() or from_row == to_row or not self.frames:
            return
        if not (0 <= from_row < len(self.frames) and 0 <= to_row < len(self.frames)):
            return

        # 1. Сохраняем состояние чекбоксов для каждого фрейма ДО перемещения
        checked_states = []
        for r in range(len(self.frames)):
            checked_states.append(self.is_row_checked(r))

        # 2. Перемещаем в self.frames и в checked_states
        frame = self.frames.pop(from_row)
        self.frames.insert(to_row, frame)

        chk = checked_states.pop(from_row)
        checked_states.insert(to_row, chk)

        # 3. Перестраиваем строки таблицы
        self._is_updating_table = True
        try:
            self.table.setRowCount(0)
            for i, f in enumerate(self.frames):
                is_chk = checked_states[i] if i < len(checked_states) else True
                self.add_table_row(
                    is_chk,
                    f.sheet_number,
                    f.sheet_name,
                    f.paper_format,
                    f.source_type,
                    dwg_name=f.dwg_name,
                    doc_code=f.doc_code,
                    object_name=f.object_name,
                    building_name=f.building_name,
                    fallback_warning=getattr(f, "fallback_warning", "")
                )
        finally:
            self._is_updating_table = False

        # 4. Выделяем строку на новом месте
        self.table.selectRow(to_row)
        self.apply_filter()

    def select_all_rows(self, checked: bool = True):
        self._is_updating_table = True
        try:
            for i in range(self.table.rowCount()):
                if not self.table.isRowHidden(i):
                    chk_widget = self.table.cellWidget(i, 0)
                    if chk_widget:
                        chk = chk_widget.layout().itemAt(0).widget()
                        chk.setChecked(checked)
        finally:
            self._is_updating_table = False
        self.update_print_counter()

    def invert_selection(self):
        """Инвертирует выбор (галочки) всех видимых листов."""
        self._is_updating_table = True
        try:
            for i in range(self.table.rowCount()):
                if not self.table.isRowHidden(i):
                    chk_widget = self.table.cellWidget(i, 0)
                    if chk_widget:
                        chk = chk_widget.layout().itemAt(0).widget()
                        chk.setChecked(not chk.isChecked())
        finally:
            self._is_updating_table = False
        self.update_print_counter()

    def print_only_this_row(self, target_row: int):
        """Снимает выбор со всех листов и оставляет отмеченным только выбранный лист."""
        self._is_updating_table = True
        try:
            for i in range(self.table.rowCount()):
                chk_widget = self.table.cellWidget(i, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    chk.setChecked(i == target_row)
        finally:
            self._is_updating_table = False
        self.update_print_counter()

    def print_same_dwg_rows(self, target_dwg: str):
        """Отмечает листы только указанного чертежа DWG, снимая выбор с остальных."""
        if not target_dwg:
            return
        self._is_updating_table = True
        try:
            for i in range(self.table.rowCount()):
                dwg_item = self.table.item(i, 7)
                dwg = dwg_item.text().strip() if dwg_item else ""
                if not dwg and i < len(self.frames):
                    dwg = self.frames[i].dwg_name or ""
                chk_widget = self.table.cellWidget(i, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    chk.setChecked(dwg.lower() == target_dwg.lower())
        finally:
            self._is_updating_table = False
        self.update_print_counter()

    def copy_full_row(self, row: int):
        """Копирует данные строки таблицы с табуляцией для вставки в Excel."""
        cols_text = []
        for c in range(1, self.table.columnCount()):
            item = self.table.item(row, c)
            cols_text.append(item.text().strip() if item else "")
        QGuiApplication.clipboard().setText("\t".join(cols_text))

    def show_table_context_menu(self, pos):
        """Контекстное меню по правому клику мыши на таблицу листов."""
        row = self.table.rowAt(pos.y())
        menu = QMenu(self)

        if row >= 0:
            self.table.selectRow(row)

            act_show = QAction("Показать в AutoCAD", self)
            act_show.triggered.connect(self.show_current_frame_in_autocad)
            menu.addAction(act_show)

            if row < len(self.frames):
                frame = self.frames[row]
                act_fmt = QAction(f"✏️ Уточнить / изменить формат «{frame.paper_format}»...", self)
                act_fmt.triggered.connect(lambda _, r=row: self.change_sheet_format(r))
                menu.addAction(act_fmt)

                possible = getattr(frame, "possible_formats", [])
                alts = [(f, s) for f, s in possible if (f, s) != (frame.paper_format, frame.scale)]
                if not (frame.is_ambiguous or frame.user_override):
                    alts = []
                if alts:
                    quick_menu = menu.addMenu("➜ Быстро переключить формат")
                    for alt_fmt, alt_scale in alts:
                        act_alt = QAction(f"{alt_fmt} (масштаб 1:{alt_scale})", self)
                        act_alt.triggered.connect(
                            lambda _, r=row, af=alt_fmt, asc=alt_scale: self.quick_switch_format(r, af, asc)
                        )
                        quick_menu.addAction(act_alt)

            menu.addSeparator()

            act_only_this = QAction("Печатать только этот лист", self)
            act_only_this.triggered.connect(lambda: self.print_only_this_row(row))
            menu.addAction(act_only_this)

            dwg_item = self.table.item(row, 7)
            dwg_name = dwg_item.text().strip() if dwg_item else ""
            if not dwg_name and row < len(self.frames):
                dwg_name = self.frames[row].dwg_name or ""
            if dwg_name:
                act_only_dwg = QAction(f"Печатать только листы «{dwg_name}»", self)
                act_only_dwg.triggered.connect(lambda _, d=dwg_name: self.print_same_dwg_rows(d))
                menu.addAction(act_only_dwg)

            menu.addSeparator()

        act_select_all = QAction("Выбрать все", self)
        act_select_all.triggered.connect(lambda: self.select_all_rows(True))
        menu.addAction(act_select_all)

        act_deselect_all = QAction("Снять все", self)
        act_deselect_all.triggered.connect(lambda: self.select_all_rows(False))
        menu.addAction(act_deselect_all)

        act_invert = QAction("Инвертировать выбор", self)
        act_invert.triggered.connect(self.invert_selection)
        menu.addAction(act_invert)

        if row >= 0:
            menu.addSeparator()
            copy_menu = menu.addMenu("Копировать")

            name_item = self.table.item(row, 3)
            name_text = name_item.text().strip() if name_item else ""
            act_copy_name = QAction("Наименование листа", self)
            act_copy_name.triggered.connect(lambda _, t=name_text: QGuiApplication.clipboard().setText(t))
            copy_menu.addAction(act_copy_name)

            code_item = self.table.item(row, 2)
            code_text = code_item.text().strip() if code_item else ""
            act_copy_code = QAction("Обозначение документа (шифр)", self)
            act_copy_code.triggered.connect(lambda _, t=code_text: QGuiApplication.clipboard().setText(t))
            copy_menu.addAction(act_copy_code)

            num_item = self.table.item(row, 1)
            num_text = num_item.text().strip() if num_item else ""
            act_copy_num = QAction("Номер листа", self)
            act_copy_num.triggered.connect(lambda _, t=num_text: QGuiApplication.clipboard().setText(t))
            copy_menu.addAction(act_copy_num)

            copy_menu.addSeparator()

            act_copy_row = QAction("Всю строку таблицы (для Excel)", self)
            act_copy_row.triggered.connect(lambda _, r=row: self.copy_full_row(r))
            copy_menu.addAction(act_copy_row)

            if not self.is_filter_active():
                menu.addSeparator()
                act_up = QAction("▲ Вверх (Ctrl+↑)", self)
                act_up.setEnabled(row > 0)
                act_up.triggered.connect(self.move_row_up)
                menu.addAction(act_up)

                act_down = QAction("▼ Вниз (Ctrl+↓)", self)
                act_down.setEnabled(row < self.table.rowCount() - 1)
                act_down.triggered.connect(self.move_row_down)
                menu.addAction(act_down)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def show_header_context_menu(self, pos):
        """Контекстное меню по правому клику мыши на шапку таблицы (настройка видимости колонок)."""
        menu = QMenu(self)

        lbl_title = QAction("Видимость колонок:", self)
        lbl_title.setEnabled(False)
        menu.addAction(lbl_title)
        menu.addSeparator()

        header_labels = [
            "Печать",
            "Лист",
            "Обозначение документа",
            "Название листа",
            "Объект строительства",
            "Здание / сооружение",
            "Формат",
            "Чертеж",
            "Источник"
        ]

        for col_idx in range(self.table.columnCount()):
            label = header_labels[col_idx] if col_idx < len(header_labels) else f"Колонка {col_idx}"
            act = QAction(label, self)
            act.setCheckable(True)
            act.setChecked(not self.table.isColumnHidden(col_idx))

            if col_idx == 0:
                act.setEnabled(False)
            else:
                act.toggled.connect(lambda checked, idx=col_idx: self.toggle_column_visibility(idx, checked))

            menu.addAction(act)

        menu.addSeparator()

        act_show_all = QAction("Показать все колонки", self)
        act_show_all.triggered.connect(self.show_all_columns)
        menu.addAction(act_show_all)

        act_reset_widths = QAction("Сбросить ширину колонок", self)
        act_reset_widths.triggered.connect(self.reset_column_widths)
        menu.addAction(act_reset_widths)

        header = self.table.horizontalHeader()
        menu.exec(header.mapToGlobal(pos))

    def toggle_column_visibility(self, col_idx: int, visible: bool):
        """Переключает видимость колонки и сохраняет настройки в config.json."""
        self.table.setColumnHidden(col_idx, not visible)
        hidden_cols = [c for c in range(self.table.columnCount()) if self.table.isColumnHidden(c)]
        self.config_manager.set("hidden_columns", hidden_cols)
        self.config_manager.save()

    def show_all_columns(self):
        """Отображает все скрытые колонки таблицы."""
        for c in range(self.table.columnCount()):
            self.table.setColumnHidden(c, False)
        self.config_manager.set("hidden_columns", [])
        self.config_manager.save()

    def reset_column_widths(self):
        """Сбрасывает ширину колонок к рекомендуемым значениям по умолчанию."""
        default_widths = [65, 60, 180, 260, 220, 200, 75, 140, 90]
        header = self.table.horizontalHeader()
        for col_idx, width in enumerate(default_widths):
            header.resizeSection(col_idx, width)
        self.config_manager.set("table_column_widths", default_widths)
        self.config_manager.save()

    def sort_by_sheet_number(self):
        if not self.frames:
            return
        # Сохраняем связку (frame, is_checked)
        pairs = []
        for i in range(self.table.rowCount()):
            pairs.append((self.frames[i], self.is_row_checked(i)))
            
        pairs.sort(key=lambda item: frame_natural_sort_key(item[0]))
        self.frames = [p[0] for p in pairs]
        checked_states = [p[1] for p in pairs]
        
        self._is_updating_table = True
        try:
            self.table.setRowCount(0)
            for i, frame in enumerate(self.frames):
                self.add_table_row(
                    checked_states[i],
                    frame.sheet_number,
                    frame.sheet_name,
                    frame.paper_format,
                    frame.source_type,
                    dwg_name=frame.dwg_name,
                    doc_code=frame.doc_code,
                    object_name=frame.object_name,
                    building_name=frame.building_name,
                    fallback_warning=getattr(frame, "fallback_warning", "")
                )
        finally:
            self._is_updating_table = False
        self.apply_filter()


    def on_table_cell_changed(self, current_row: int, current_column: int, previous_row: int, previous_column: int):
        self.update_template_preview()
        if self._is_updating_table:
            return
        if not hasattr(self, 'chk_sync_acad') or not self.chk_sync_acad.isChecked():
            return
        if not self.connector.doc:
            return
        if 0 <= current_row < len(self.frames):
            frame = self.frames[current_row]
            self.connector.show_frame(frame, zoom=True, highlight=True)

    def on_table_cell_double_clicked(self, row: int, column: int):
        if column == 6:  # Колонка "Формат" — ручное уточнение / изменение формата
            self.change_sheet_format(row)
            return
        if 0 <= row < len(self.frames):
            frame = self.frames[row]
            try:
                self.connector.show_frame(frame, zoom=True, highlight=True)
                self.connector.activate_autocad_window()
            except Exception as e:
                print(f"Ошибка при двойном клике: {e}")

    def show_current_frame_in_autocad(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.frames):
            frame = self.frames[row]
            try:
                self.connector.show_frame(frame, zoom=True, highlight=True)
                self.connector.activate_autocad_window()
            except Exception as e:
                QMessageBox.warning(self, "AutoCAD", f"Не удалось показать рамку в AutoCAD:\n{e}")
        else:
            QMessageBox.information(self, "Информация", "Выберите лист в таблице, чтобы показать его в AutoCAD.")

    def export_sheet_list_dialog(self):
        if not self.frames:
            QMessageBox.information(self, "Экспорт ведомости", "Список листов пуст. Сначала выполните поиск рамок.")
            return

        # Если активен фильтр, собираем только видимые листы
        export_frames = []
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i) and i < len(self.frames):
                export_frames.append(self.frames[i])

        if not export_frames:
            export_frames = self.frames

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить ведомость листов",
            "Ведомость_листов.xlsx",
            "Книга Excel (*.xlsx);;CSV (разделители - точки с запятой) (*.csv)"
        )
        if not filepath:
            return

        try:
            SheetExporter.export(export_frames, filepath)
            QMessageBox.information(
                self,
                "Экспорт завершен",
                f"Ведомость листов ({len(export_frames)} поз.) успешно сохранена в:\n{filepath}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Ошибка экспорта", f"Не удалось сохранить файл:\n{e}")

    def closeEvent(self, event):
        try:
            self.save_settings(window_geometry=bytes(self.saveGeometry().toBase64()).decode("ascii"))
        except Exception:
            pass
        try:
            self.connector.clear_highlight()
        except Exception:
            pass
        super().closeEvent(event)

    def print_selected_frames(self):
        if not self.frames:
            return
            
        if not self.printer:
            self.printer = BatchPrinter(self.connector.doc, connector=self.connector)
        else:
            self.printer.connector = self.connector

        # 1. Собираем выбранные рамки (с учетом видимости фильтра)
        selected_frames = self.get_frames_to_print()
        if not selected_frames:
            QMessageBox.information(self, "Печать", "Нет выбранных листов для печати (отметьте нужные листы чекбоксами).")
            return
            
        merge_pdf = (self.combo_mode.currentIndex() == 1)
        
        # 2. Выбираем папку или файл для сохранения
        if merge_pdf:
            output_path, _ = QFileDialog.getSaveFileName(self, "Сохранить объединенный PDF", "Многостраничный_чертеж.pdf", "PDF Files (*.pdf)")
        else:
            output_path = QFileDialog.getExistingDirectory(self, "Выберите папку для сохранения PDF", "")
            
        if not output_path:
            return # Пользователь отменил выбор
            
        # 3. Получаем настройки принтера
        printer_name = self.combo_printers.currentText()
        local_paper_name = self.combo_papers.currentText()
        sys_paper_name = self.paper_dict.get(local_paper_name, local_paper_name)
        style_name = self.combo_style.currentText()
        filename_template = self.combo_template.currentText().strip() if hasattr(self, "combo_template") else ""
        if not filename_template:
            filename_template = get_default_template()
        
        # 4. Запускаем пакетную печать с диалогом прогресса
        self.btn_print.setEnabled(False)
        self.btn_print.setText("ПЕЧАТАЮ...")
        
        total_steps = len(selected_frames) + (1 if merge_pdf else 0)
        progress_dlg = PrintProgressDialog(total_steps, parent=self)
        progress_dlg.show()
        QApplication.processEvents()
        
        def on_progress(current_step, total, status_text):
            progress_dlg.set_progress(current_step, status_text)
            self.btn_print.setText(f"ПЕЧАТЬ ({current_step}/{total_steps})...")
            
        def is_cancelled():
            QApplication.processEvents()
            return progress_dlg.is_cancelled
            
        try:
            report = self.printer.print_frames(
                frames=selected_frames,
                printer_name=printer_name,
                canonical_media_name=sys_paper_name,
                style_name=style_name,
                output_path=output_path,
                merge_pdf=merge_pdf,
                progress_callback=on_progress,
                is_cancelled=is_cancelled,
                filename_template=filename_template
            )
            
            progress_dlg.close()
            
            # Обновляем отображение таблицы (например, отметки резервного формата)
            if report and report.fallback_count > 0:
                self._refresh_table_formats()

            # Открываем готовый объединенный PDF или папку с файлами
            if self.chk_open_after.isChecked() and report and report.success_count > 0:
                try:
                    os.startfile(output_path)
                except Exception as e:
                    log_warn(f"Не удалось открыть файл '{output_path}'", exc=e, module="Printing")

            # Открываем подробный итоговый отчёт
            if report:
                get_stats_manager().record_print_batch(report)
                dlg = ReportDialog(report, current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
                dlg.repeat_requested.connect(self.on_repeat_failed_frames)
                dlg.exec()
            else:
                QMessageBox.information(self, "Успех", f"Успешно напечатано {len(selected_frames)} листов в:\n{output_path}")

        except PrintCancelledError:
            progress_dlg.close()
            log_info("Пакетная печать отменена пользователем", module="Printing")
            last_rep = getattr(self.printer, "last_report", None)
            if last_rep:
                get_stats_manager().record_print_batch(last_rep)
            if last_rep and last_rep.items:
                dlg = ReportDialog(last_rep, current_theme_id=getattr(self, "current_theme", "dark_catppuccin"), parent=self)
                dlg.repeat_requested.connect(self.on_repeat_failed_frames)
                dlg.exec()
            else:
                QMessageBox.information(self, "Печать отменена", "Пакетная печать была отменена пользователем.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            log_error("Ошибка при пакетной печати", exc=e, module="Printing")
            progress_dlg.close()
            QMessageBox.critical(
                self,
                "Ошибка печати",
                f"Произошла ошибка при печати:\n{e}\n\n"
                f"Подробный журнал ошибок доступен по клавише F2 («Диагностика»)."
            )
        finally:
            progress_dlg.close()
            self.update_print_counter()

    def on_repeat_failed_frames(self, failed_frames: list):
        """Отмечает в таблице галочками только неудачные / отмененные листы для повторной печати."""
        if not failed_frames:
            return
        failed_handles = {getattr(f, "handle", "") for f in failed_frames if getattr(f, "handle", "")}
        failed_ids = {getattr(f, "object_id", 0) for f in failed_frames if getattr(f, "object_id", 0)}
        failed_keys = {(getattr(f, "dwg_path", ""), getattr(f, "sheet_number", "")) for f in failed_frames}

        for row in range(self.table.rowCount()):
            if row < len(self.frames):
                frame = self.frames[row]
                match = False
                if frame.handle and frame.handle in failed_handles:
                    match = True
                elif frame.object_id and frame.object_id in failed_ids:
                    match = True
                elif (frame.dwg_path, frame.sheet_number) in failed_keys:
                    match = True

                chk_widget = self.table.cellWidget(row, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    chk.setChecked(match)

        self.update_print_counter()
        self.lbl_status_right.setText(f"Отмечены для повтора листы: {len(failed_frames)} шт. | Нажмите «ПЕЧАТЬ»")

if __name__ == "__main__":
    from PySide6.QtGui import QFont
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = PrintManagerUI()
    window.show()
    sys.exit(app.exec())

