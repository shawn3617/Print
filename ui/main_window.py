import os
import sys

# Гарантируем корректный импорт модулей core/parsers даже при прямом запуске скрипта
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QLabel, QHeaderView, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog, QAbstractItemView, QDialog, QProgressBar,
    QLineEdit
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag

from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
from core.printer import BatchPrinter, PrintCancelledError
from core.config_manager import ConfigManager
from core.models import natural_sheet_sort_key, frame_natural_sort_key
from core.exporter import SheetExporter


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
    def __init__(self, total_steps: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Пакетная печать PDF")
        self.setModal(True)
        self.setFixedSize(500, 170)
        self.is_cancelled = False
        
        # Убираем кнопку контекстной справки (?) в Windows
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        self.lbl_title = QLabel("Идет печать чертежей...")
        self.lbl_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #89b4fa;")
        layout.addWidget(self.lbl_title)
        
        self.lbl_status = QLabel("Подготовка к печати...")
        self.lbl_status.setStyleSheet("font-size: 13px; color: #cdd6f4;")
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
        self.lbl_status.setText("Отмена печати, завершение текущей операции...")
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
    def __init__(self, config_manager=None):
        super().__init__()
        self.setWindowTitle("Smart Batch Print - AutoCAD")
        self.resize(1100, 650)
        self.setAcceptDrops(True)
        self.config_manager = config_manager or ConfigManager()
        self._is_loading_config = True
        self.connector = AutoCADConnector()
        self.scanner = DocumentScanner()
        self.printer = None
        self.frames = []
        self.paper_dict = {} # Словарь {Локальное_Имя: Системное_Имя}
        self._is_updating_table = False
        
        self.setup_theme()
        self.init_ui()
        self.apply_initial_config()
        self.refresh_document_status()
        self._is_loading_config = False

    def setup_theme(self):
        # Премиальная темная тема
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; font-size: 14px; font-family: 'Segoe UI', Arial; }
            QGroupBox { color: #cdd6f4; font-size: 14px; font-weight: bold; border: 1px solid #45475a; border-radius: 8px; margin-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 5px; font-size: 14px; }
            QComboBox::drop-down { border: none; }
            QLineEdit { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 10px; font-size: 13px; }
            QLineEdit:focus { border: 1px solid #89b4fa; }
            QCheckBox { color: #cdd6f4; font-size: 13px; spacing: 6px; }
            QCheckBox::indicator { width: 16px; height: 16px; }
            QPushButton { background-color: #89b4fa; color: #11111b; border: none; border-radius: 6px; padding: 10px 20px; font-size: 14px; font-weight: bold; }
            QPushButton:hover { background-color: #74c7ec; }
            QPushButton:pressed { background-color: #89dceb; }
            QPushButton#btn_print { background-color: #a6e3a1; font-size: 16px; padding: 15px; }
            QPushButton#btn_print:hover { background-color: #94e2d5; }
            QTableWidget { background-color: #181825; color: #cdd6f4; gridline-color: #313244; border: 1px solid #45475a; border-radius: 8px; }
            QTableWidget::item:selected { background-color: #45475a; color: #ffffff; }
            QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 5px; border: 1px solid #45475a; font-weight: bold; }
            QPushButton[cssClass="btn_tool"] { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 6px 14px; font-size: 13px; font-weight: normal; }
            QPushButton[cssClass="btn_tool"]:hover { background-color: #45475a; color: #ffffff; }
            QPushButton[cssClass="btn_tool"]:pressed { background-color: #585b70; }
            QScrollBar:vertical { background-color: #181825; width: 14px; margin: 0px; }
            QScrollBar::handle:vertical { background-color: #45475a; min-height: 20px; border-radius: 7px; }
            QScrollBar::handle:vertical:hover { background-color: #585b70; }
            QDialog { background-color: #1e1e2e; }
            QProgressBar { background-color: #313244; color: #ffffff; border: 1px solid #45475a; border-radius: 6px; text-align: center; font-size: 13px; font-weight: bold; min-height: 24px; }
            QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #a6e3a1); border-radius: 5px; }
        """)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ЛЕВАЯ ЧАСТЬ
        left_layout = QVBoxLayout()
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Активный чертеж:"))
        self.lbl_document = QLabel("Не подключено")
        self.lbl_document.setStyleSheet("color: #a6e3a1; font-weight: bold;")
        self.lbl_document.setSizePolicy(self.lbl_document.sizePolicy().Policy.Expanding, self.lbl_document.sizePolicy().Policy.Fixed)
        top_bar.addWidget(self.lbl_document)
        btn_refresh = QPushButton("Обновить связь")
        btn_refresh.setProperty("cssClass", "btn_tool")
        btn_refresh.clicked.connect(self.refresh_document_status)
        top_bar.addWidget(btn_refresh)
        
        top_bar.addWidget(QLabel("Источник:"))
        self.combo_source = QComboBox()
        self.combo_source.addItems(["Модель (Model Space)", "Листы (Layouts)"])
        self.combo_source.currentTextChanged.connect(self.on_source_mode_changed)
        top_bar.addWidget(self.combo_source)
        
        self.btn_scan = QPushButton("Найти рамки")
        self.btn_scan.clicked.connect(self.scan_frames)
        top_bar.addWidget(self.btn_scan)
        left_layout.addLayout(top_bar)

        # Панель пакетной обработки чертежей
        batch_bar = QHBoxLayout()
        batch_bar.setSpacing(8)

        lbl_batch = QLabel("Пакет чертежей:")
        lbl_batch.setStyleSheet("font-weight: bold; color: #89b4fa;")
        batch_bar.addWidget(lbl_batch)

        btn_add_dwg = QPushButton("+ Добавить DWG...")
        btn_add_dwg.setProperty("cssClass", "btn_tool")
        btn_add_dwg.setToolTip("Выбрать один или несколько DWG-файлов для сканирования и печати")
        btn_add_dwg.clicked.connect(self.add_dwg_files_dialog)
        batch_bar.addWidget(btn_add_dwg)

        btn_add_folder = QPushButton("+ Папка с DWG...")
        btn_add_folder.setProperty("cssClass", "btn_tool")
        btn_add_folder.setToolTip("Выбрать папку для добавления всех чертежей .dwg")
        btn_add_folder.clicked.connect(self.add_dwg_folder_dialog)
        batch_bar.addWidget(btn_add_folder)

        btn_clear = QPushButton("Очистить список")
        btn_clear.setProperty("cssClass", "btn_tool")
        btn_clear.setToolTip("Очистить таблицу найденных листов")
        btn_clear.clicked.connect(self.clear_frames)
        batch_bar.addWidget(btn_clear)

        btn_close_opened = QPushButton("Закрыть чертежи программы")
        btn_close_opened.setProperty("cssClass", "btn_tool")
        btn_close_opened.setToolTip("Закрыть в AutoCAD все чертежи, которые были открыты программой (для просмотра или печати)")
        btn_close_opened.clicked.connect(self.close_opened_documents_dialog)
        batch_bar.addWidget(btn_close_opened)

        batch_bar.addStretch()
        left_layout.addLayout(batch_bar)

        # Панель фильтрации и быстрого поиска
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        lbl_filter = QLabel("Поиск:")
        lbl_filter.setStyleSheet("font-weight: bold; color: #89b4fa;")
        filter_bar.addWidget(lbl_filter)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Номер, название или чертеж...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self.apply_filter)
        filter_bar.addWidget(self.txt_search, stretch=3)

        lbl_fmt = QLabel("Формат:")
        lbl_fmt.setStyleSheet("font-weight: bold; color: #89b4fa;")
        filter_bar.addWidget(lbl_fmt)

        self.combo_filter_format = QComboBox()
        self.combo_filter_format.addItem("Все форматы")
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
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().resizeSection(2, 160)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().resizeSection(4, 200)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().resizeSection(5, 170)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().resizeSection(7, 130)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setToolTip("Листы можно перетаскивать мышкой или перемещать кнопками «Вверх» / «Вниз» (Ctrl+↑ / Ctrl+↓).\nМожно перетаскивать файлы DWG из проводника прямо в окно программы.")
        self.table.row_moved.connect(self.on_row_drag_moved)
        self.table.key_move_requested.connect(self.on_key_move_requested)
        self.table.currentCellChanged.connect(self.on_table_cell_changed)
        self.table.cellDoubleClicked.connect(self.on_table_cell_double_clicked)
        left_layout.addWidget(self.table)


        # Панель управления порядком и выбором листов
        table_tools = QHBoxLayout()
        table_tools.setSpacing(8)

        btn_select_all = QPushButton("Выбрать все")
        btn_select_all.setProperty("cssClass", "btn_tool")
        btn_select_all.clicked.connect(lambda: self.select_all_rows(True))
        table_tools.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Снять все")
        btn_deselect_all.setProperty("cssClass", "btn_tool")
        btn_deselect_all.clicked.connect(lambda: self.select_all_rows(False))
        table_tools.addWidget(btn_deselect_all)

        btn_sort_num = QPushButton("По номерам")
        btn_sort_num.setProperty("cssClass", "btn_tool")
        btn_sort_num.setToolTip("Сбросить ручной порядок и отсортировать по возрастанию номеров листов")
        btn_sort_num.clicked.connect(self.sort_by_sheet_number)
        table_tools.addWidget(btn_sort_num)

        btn_export = QPushButton("В Excel / CSV...")
        btn_export.setProperty("cssClass", "btn_tool")
        btn_export.setToolTip("Экспортировать ведомость листов таблицы в Excel (.xlsx) или CSV")
        btn_export.clicked.connect(self.export_sheet_list_dialog)
        table_tools.addWidget(btn_export)

        self.btn_move_up = QPushButton("▲ Вверх (Ctrl+↑)")
        self.btn_move_up.setProperty("cssClass", "btn_tool")
        self.btn_move_up.setToolTip("Поднять выбранный лист выше в очереди печати")
        self.btn_move_up.clicked.connect(self.move_row_up)
        table_tools.addWidget(self.btn_move_up)

        self.btn_move_down = QPushButton("▼ Вниз (Ctrl+↓)")
        self.btn_move_down.setProperty("cssClass", "btn_tool")
        self.btn_move_down.setToolTip("Опустить выбранный лист ниже в очереди печати")
        self.btn_move_down.clicked.connect(self.move_row_down)
        table_tools.addWidget(self.btn_move_down)

        table_tools.addStretch()

        self.chk_sync_acad = QCheckBox("Подсветка в AutoCAD")
        self.chk_sync_acad.setChecked(True)
        self.chk_sync_acad.setToolTip("Автоматически центрировать и подсвечивать выбранную рамку в AutoCAD при клике или переходе стрелками")
        self.chk_sync_acad.toggled.connect(lambda _: self.save_settings())
        table_tools.addWidget(self.chk_sync_acad)

        btn_show_acad = QPushButton("В AutoCAD")
        btn_show_acad.setProperty("cssClass", "btn_tool")
        btn_show_acad.setToolTip("Центрировать выбранную рамку в окне AutoCAD и развернуть окно")
        btn_show_acad.clicked.connect(self.show_current_frame_in_autocad)
        table_tools.addWidget(btn_show_acad)

        left_layout.addLayout(table_tools)
        main_layout.addLayout(left_layout, stretch=3)

        # ПРАВАЯ ЧАСТЬ
        right_layout = QVBoxLayout()
        group_printer = QGroupBox("Настройки печати")
        form_layout = QFormLayout(group_printer)
        form_layout.setSpacing(15)
        
        self.combo_printers = QComboBox()
        self.combo_printers.currentTextChanged.connect(self.on_printer_changed)
        form_layout.addRow(QLabel("Принтер:"), self.combo_printers)
        
        self.combo_papers = QComboBox()
        self.combo_papers.setToolTip("Используется только если программа не смогла автоматически подобрать нужный размер бумаги для рамки (например, если в принтере нет такого формата)")
        self.combo_papers.currentTextChanged.connect(lambda _: self.save_settings())
        form_layout.addRow(QLabel("Резервный формат:"), self.combo_papers)
        
        self.combo_style = QComboBox()
        self.combo_style.currentTextChanged.connect(lambda _: self.save_settings())
        form_layout.addRow(QLabel("Стиль:"), self.combo_style)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["В отдельные файлы", "В один файл (PDF)"])
        self.combo_mode.currentTextChanged.connect(lambda _: self.save_settings())
        form_layout.addRow(QLabel("Режим:"), self.combo_mode)

        self.chk_open_after = QCheckBox("Открыть результат")
        self.chk_open_after.setChecked(True)
        self.chk_open_after.setToolTip("Автоматически открыть объединенный PDF (или папку) после завершения печати")
        self.chk_open_after.toggled.connect(lambda _: self.save_settings())
        form_layout.addRow("", self.chk_open_after)

        right_layout.addWidget(group_printer)
        right_layout.addStretch()
        
        self.btn_print = QPushButton("ПЕЧАТЬ (0 листов)")
        self.btn_print.setObjectName("btn_print")
        self.btn_print.setEnabled(False)
        self.btn_print.clicked.connect(self.print_selected_frames)
        right_layout.addWidget(self.btn_print)
        
        main_layout.addLayout(right_layout, stretch=1)

    def apply_initial_config(self):
        """Применяет сохраненные настройки из config.json к элементам интерфейса."""
        cfg = self.config_manager.load()
        if not isinstance(cfg, dict):
            cfg = {}
        self.chk_sync_acad.setChecked(bool(cfg.get("sync_autocad", True)))
        self.chk_open_after.setChecked(bool(cfg.get("open_after_print", True)))
        
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

    def on_source_mode_changed(self, text: str):
        if "Layout" in text or "Листы" in text:
            self.btn_scan.setText("Загрузить листы")
        else:
            self.btn_scan.setText("Найти рамки")
        self.save_settings()

    def on_printer_changed(self, printer_name: str):
        self.update_paper_sizes(printer_name)
        self.save_settings()

    def save_settings(self):
        """Сохраняет текущие параметры печати и состояния чекбоксов в config.json."""
        if getattr(self, "_is_loading_config", False):
            return
        
        printer_text = self.combo_printers.currentText()
        style_text = self.combo_style.currentText()
        paper_text = self.combo_papers.currentText()
        mode_text = self.combo_mode.currentText()
        source_text = self.combo_source.currentText()
        
        current_cfg = self.config_manager.load()
        if not isinstance(current_cfg, dict):
            current_cfg = {}
        settings = {
            "printer": printer_text if printer_text else current_cfg.get("printer", "DWG To PDF.pc3"),
            "plot_style": style_text if style_text else current_cfg.get("plot_style", "monochrome.ctb"),
            "fallback_paper": paper_text if paper_text else current_cfg.get("fallback_paper", ""),
            "merge_mode": mode_text if mode_text else current_cfg.get("merge_mode", "В один файл (PDF)"),
            "open_after_print": self.chk_open_after.isChecked(),
            "sync_autocad": self.chk_sync_acad.isChecked(),
            "source_mode": source_text if source_text else current_cfg.get("source_mode", "Модель (Model Space)"),
        }
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
        progress_dlg = PrintProgressDialog(len(file_paths), parent=self)
        progress_dlg.setWindowTitle("Пакетное сканирование DWG")
        progress_dlg.lbl_title.setText("Поиск листов в чертежах...")
        progress_dlg.show()
        QApplication.processEvents()

        def on_scan_progress(idx, total, fname, status):
            progress_dlg.set_progress(idx, status)

        def is_cancelled():
            QApplication.processEvents()
            return progress_dlg.is_cancelled

        try:
            new_frames = self.scanner.scan_files(
                connector=self.connector,
                file_paths=file_paths,
                source_mode=source_mode,
                progress_callback=on_scan_progress,
                is_cancelled=is_cancelled
            )
            progress_dlg.close()

            if not new_frames:
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
                        building_name=frame.building_name
                    )
            finally:
                self._is_updating_table = False

            # Выполняем сквозную сортировку по номерам листов для всего общего списка чертежей
            self.sort_by_sheet_number()
            self.refresh_document_status()
            self.update_format_filter_items()
            self.apply_filter()

            QMessageBox.information(
                self,
                "Сканирование завершено",
                f"Обработано файлов: {len(file_paths)}\nДобавлено листов: {len(new_frames)} (всего в очереди: {len(self.frames)})"
            )


        except Exception as e:
            progress_dlg.close()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при пакетном сканировании: {e}")
        finally:
            progress_dlg.close()

    def refresh_document_status(self):
        try:
            self.connector.connect()
            doc_name = self.connector.get_active_document_name()
            self.lbl_document.setText(doc_name)
            self.lbl_document.setStyleSheet("color: #a6e3a1; font-weight: bold;")
            
            # Инициализируем принтер с коннектором для поддержки переключения чертежей
            self.printer = BatchPrinter(self.connector.doc, connector=self.connector)
            if self.connector.doc:
                self.load_printer_settings()
            
        except Exception as e:
            self.lbl_document.setText("Ошибка подключения")
            self.lbl_document.setStyleSheet("color: #f38ba8; font-weight: bold;")

            
    def load_printer_settings(self):
        if not self.printer: return
        
        was_loading = self._is_loading_config
        self._is_loading_config = True
        try:
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
        
    def update_paper_sizes(self, printer_name: str):
        if not self.printer or not printer_name: return
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
                
    def scan_frames(self):
        try:
            self.connector.connect()
            self.connector.clear_highlight()
            
            is_layouts_mode = "Layout" in self.combo_source.currentText() or "Листы" in self.combo_source.currentText()
            
            if is_layouts_mode:
                self.frames = self.scanner.scan_layouts(self.connector.doc)
            else:
                self.frames = self.scanner.scan_document(self.connector.doc)
            
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
                        building_name=frame.building_name
                    )
            finally:
                self._is_updating_table = False

            self.update_format_filter_items()
            self.apply_filter()
            
            if not self.frames:
                msg = "Вкладки листов (Layouts) не найдены!" if is_layouts_mode else "Рамки не найдены!"
                QMessageBox.information(self, "Результат", msg)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сканировании: {e}")

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
        building_name: str = ""
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

        item_fmt = QTableWidgetItem(paper_format)
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
        count = 0
        total_visible = 0
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                total_visible += 1
                chk_widget = self.table.cellWidget(i, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    if chk.isChecked():
                        count += 1
        if self.is_filter_active():
            self.btn_print.setText(f"ПЕЧАТЬ ({count} из {total_visible} листов)")
        else:
            self.btn_print.setText(f"ПЕЧАТЬ ({count} листов)")
        self.btn_print.setEnabled(count > 0)

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
                    building_name=f.building_name
                )
        finally:
            self._is_updating_table = False

        # 4. Выделяем строку на новом месте
        self.table.selectRow(to_row)
        self.apply_filter()

    def select_all_rows(self, checked: bool = True):
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                chk_widget = self.table.cellWidget(i, 0)
                if chk_widget:
                    chk = chk_widget.layout().itemAt(0).widget()
                    chk.setChecked(checked)
        self.update_print_counter()

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
                    building_name=frame.building_name
                )
        finally:
            self._is_updating_table = False
        self.apply_filter()


    def on_table_cell_changed(self, current_row: int, current_column: int, previous_row: int, previous_column: int):
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
            self.save_settings()
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
            self.printer.print_frames(
                frames=selected_frames,
                printer_name=printer_name,
                canonical_media_name=sys_paper_name,
                style_name=style_name,
                output_path=output_path,
                merge_pdf=merge_pdf,
                progress_callback=on_progress,
                is_cancelled=is_cancelled
            )
            
            progress_dlg.close()
            
            # Открываем готовый объединенный PDF или папку с файлами
            if self.chk_open_after.isChecked():
                try:
                    os.startfile(output_path)
                except Exception as e:
                    print(f"Не удалось открыть файл: {e}")

            QMessageBox.information(self, "Успех", f"Успешно напечатано {len(selected_frames)} листов в:\n{output_path}")
        except PrintCancelledError:
            progress_dlg.close()
            QMessageBox.information(self, "Печать отменена", "Пакетная печать была отменена пользователем.")
        except Exception as e:
            import traceback
            traceback.print_exc()
            progress_dlg.close()
            QMessageBox.critical(self, "Ошибка печати", f"Произошла ошибка при печати:\n{e}")
        finally:
            progress_dlg.close()
            self.update_print_counter()

if __name__ == "__main__":
    from PySide6.QtGui import QFont
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 10))
    window = PrintManagerUI()
    window.show()
    sys.exit(app.exec())

