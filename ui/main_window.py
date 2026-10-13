import os
import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QLabel, QHeaderView, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QDrag

from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
from core.printer import BatchPrinter

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
        if event.mimeData().hasFormat("application/x-print-row"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-print-row"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
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

class PrintManagerUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Smart Batch Print - AutoCAD")
        self.resize(1000, 600)
        self.connector = AutoCADConnector()
        self.scanner = DocumentScanner()
        self.printer = None
        self.frames = []
        self.paper_dict = {} # Словарь {Локальное_Имя: Системное_Имя}
        
        self.setup_theme()
        self.init_ui()
        self.refresh_document_status()

    def setup_theme(self):
        # Премиальная темная тема
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e2e; }
            QLabel { color: #cdd6f4; font-size: 14px; font-family: 'Segoe UI', Arial; }
            QGroupBox { color: #cdd6f4; font-size: 14px; font-weight: bold; border: 1px solid #45475a; border-radius: 8px; margin-top: 15px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 3px 0 3px; }
            QComboBox { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 4px; padding: 5px; font-size: 14px; }
            QComboBox::drop-down { border: none; }
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
        btn_refresh.clicked.connect(self.refresh_document_status)
        top_bar.addWidget(btn_refresh)
        btn_scan = QPushButton("Найти рамки")
        btn_scan.clicked.connect(self.scan_frames)
        top_bar.addWidget(btn_scan)
        left_layout.addLayout(top_bar)

        self.table = ReorderableTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Печать", "Лист", "Название листа", "Формат", "Источник"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        self.table.setToolTip("Листы можно перетаскивать мышкой или перемещать кнопками «Вверх» / «Вниз» (Ctrl+↑ / Ctrl+↓)")
        self.table.row_moved.connect(self.on_row_drag_moved)
        self.table.key_move_requested.connect(self.on_key_move_requested)
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

        table_tools.addStretch()

        btn_move_up = QPushButton("▲ Вверх (Ctrl+↑)")
        btn_move_up.setProperty("cssClass", "btn_tool")
        btn_move_up.setToolTip("Поднять выбранный лист выше в очереди печати")
        btn_move_up.clicked.connect(self.move_row_up)
        table_tools.addWidget(btn_move_up)

        btn_move_down = QPushButton("▼ Вниз (Ctrl+↓)")
        btn_move_down.setProperty("cssClass", "btn_tool")
        btn_move_down.setToolTip("Опустить выбранный лист ниже в очереди печати")
        btn_move_down.clicked.connect(self.move_row_down)
        table_tools.addWidget(btn_move_down)

        left_layout.addLayout(table_tools)
        main_layout.addLayout(left_layout, stretch=3)

        # ПРАВАЯ ЧАСТЬ
        right_layout = QVBoxLayout()
        group_printer = QGroupBox("Настройки печати")
        form_layout = QFormLayout(group_printer)
        form_layout.setSpacing(15)
        
        self.combo_printers = QComboBox()
        self.combo_printers.currentTextChanged.connect(self.update_paper_sizes)
        form_layout.addRow(QLabel("Принтер:"), self.combo_printers)
        
        self.combo_papers = QComboBox()
        self.combo_papers.setToolTip("Используется только если программа не смогла автоматически подобрать нужный размер бумаги для рамки (например, если в принтере нет такого формата)")
        form_layout.addRow(QLabel("Резервный формат:"), self.combo_papers)
        
        self.combo_style = QComboBox()
        form_layout.addRow(QLabel("Стиль:"), self.combo_style)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["В отдельные файлы", "В один файл (PDF)"])
        form_layout.addRow(QLabel("Режим:"), self.combo_mode)

        self.chk_open_after = QCheckBox("Открыть результат")
        self.chk_open_after.setChecked(True)
        self.chk_open_after.setToolTip("Автоматически открыть объединенный PDF (или папку) после завершения печати")
        form_layout.addRow("", self.chk_open_after)

        right_layout.addWidget(group_printer)
        right_layout.addStretch()
        
        self.btn_print = QPushButton("ПЕЧАТЬ (0 листов)")
        self.btn_print.setObjectName("btn_print")
        self.btn_print.setEnabled(False)
        self.btn_print.clicked.connect(self.print_selected_frames)
        right_layout.addWidget(self.btn_print)
        
        main_layout.addLayout(right_layout, stretch=1)
        
    def refresh_document_status(self):
        try:
            self.connector.connect()
            doc_name = self.connector.get_active_document_name()
            self.lbl_document.setText(doc_name)
            
            # Инициализируем принтер и загружаем реальные настройки из AutoCAD
            self.printer = BatchPrinter(self.connector.doc)
            self.load_printer_settings()
            
        except Exception as e:
            self.lbl_document.setText("Ошибка подключения")
            self.lbl_document.setStyleSheet("color: #f38ba8; font-weight: bold;")
            
    def load_printer_settings(self):
        if not self.printer: return
        
        # Загружаем принтеры
        printers = self.printer.get_printers()
        self.combo_printers.blockSignals(True)
        self.combo_printers.clear()
        self.combo_printers.addItems(printers)
        # Выбираем DWG To PDF по умолчанию, если есть
        idx = self.combo_printers.findText("DWG To PDF.pc3")
        if idx >= 0: self.combo_printers.setCurrentIndex(idx)
        self.combo_printers.blockSignals(False)
        
        # Загружаем форматы
        self.update_paper_sizes(self.combo_printers.currentText())
        
        # Загружаем стили
        styles = self.printer.get_plot_styles()
        self.combo_style.clear()
        self.combo_style.addItems(styles)
        idx_style = self.combo_style.findText("monochrome.ctb")
        if idx_style >= 0: self.combo_style.setCurrentIndex(idx_style)
        
    def update_paper_sizes(self, printer_name: str):
        if not self.printer or not printer_name: return
        self.paper_dict = self.printer.get_media_names(printer_name)
        
        self.combo_papers.clear()
        papers = list(self.paper_dict.keys())
        self.combo_papers.addItems(papers)
        
        # Пытаемся выбрать ISO full bleed A2
        for i, paper in enumerate(papers):
            if "A2" in paper and "full bleed" in paper.lower():
                self.combo_papers.setCurrentIndex(i)
                break
                
    def scan_frames(self):
        try:
            self.connector.connect()
            self.frames = self.scanner.scan_document(self.connector.doc)
            
            # Обновляем таблицу
            self.table.setRowCount(0)
            for frame in self.frames:
                self.add_table_row(True, frame.sheet_number, frame.sheet_name, frame.paper_format, frame.source_type)
                
            self.btn_print.setText(f"ПЕЧАТЬ ({len(self.frames)} листов)")
            self.btn_print.setEnabled(len(self.frames) > 0)
            
            if not self.frames:
                QMessageBox.information(self, "Результат", "Рамки не найдены!")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка при сканировании: {e}")

    def add_table_row(self, checked: bool, num: str, name: str, paper_format: str, source: str):
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
        
        item_name = QTableWidgetItem(name)
        
        item_fmt = QTableWidgetItem(paper_format)
        item_fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        item_src = QTableWidgetItem(source)
        item_src.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsDragEnabled
        for it in (item_num, item_name, item_fmt, item_src):
            it.setFlags(flags)
            
        self.table.setItem(row, 1, item_num)
        self.table.setItem(row, 2, item_name)
        self.table.setItem(row, 3, item_fmt)
        self.table.setItem(row, 4, item_src)
        
    def update_print_counter(self):
        count = 0
        for i in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(i, 0)
            if chk_widget:
                chk = chk_widget.layout().itemAt(0).widget()
                if chk.isChecked():
                    count += 1
        self.btn_print.setText(f"ПЕЧАТЬ ({count} листов)")
        self.btn_print.setEnabled(count > 0)

    def is_row_checked(self, row: int) -> bool:
        chk_widget = self.table.cellWidget(row, 0)
        if chk_widget:
            chk = chk_widget.layout().itemAt(0).widget()
            return chk.isChecked()
        return True

    def on_key_move_requested(self, direction: int):
        if direction < 0:
            self.move_row_up()
        else:
            self.move_row_down()

    def move_row_up(self):
        row = self.table.currentRow()
        if row > 0:
            self.move_row(row, row - 1)

    def move_row_down(self):
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount() - 1:
            self.move_row(row, row + 1)

    def on_row_drag_moved(self, from_row: int, to_row: int):
        if from_row != to_row:
            self.move_row(from_row, to_row)

    def move_row(self, from_row: int, to_row: int):
        if from_row == to_row or not self.frames:
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
        self.table.setRowCount(0)
        for i, f in enumerate(self.frames):
            is_chk = checked_states[i] if i < len(checked_states) else True
            self.add_table_row(is_chk, f.sheet_number, f.sheet_name, f.paper_format, f.source_type)

        # 4. Выделяем строку на новом месте
        self.table.selectRow(to_row)
        self.update_print_counter()

    def select_all_rows(self, checked: bool = True):
        for i in range(self.table.rowCount()):
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
            
        def sort_key(item):
            frame = item[0]
            try:
                return (0, float(frame.sheet_number))
            except ValueError:
                return (1, frame.sheet_number)
                
        pairs.sort(key=sort_key)
        self.frames = [p[0] for p in pairs]
        checked_states = [p[1] for p in pairs]
        
        self.table.setRowCount(0)
        for i, frame in enumerate(self.frames):
            self.add_table_row(checked_states[i], frame.sheet_number, frame.sheet_name, frame.paper_format, frame.source_type)
        self.update_print_counter()

    def print_selected_frames(self):
        if not self.printer or not self.frames:
            return
            
        # 1. Собираем выбранные рамки
        selected_frames = []
        for i in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(i, 0)
            chk = chk_widget.layout().itemAt(0).widget()
            if chk.isChecked():
                selected_frames.append(self.frames[i])
                
        if not selected_frames:
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
        
        # 4. Запускаем пакетную печать
        self.btn_print.setEnabled(False)
        self.btn_print.setText("ПЕЧАТАЮ...")
        QApplication.processEvents() # Обновляем UI
        
        try:
            self.printer.print_frames(
                frames=selected_frames,
                printer_name=printer_name,
                canonical_media_name=sys_paper_name,
                style_name=style_name,
                output_path=output_path,
                merge_pdf=merge_pdf
            )
            
            # Открываем готовый объединенный PDF или папку с файлами
            if self.chk_open_after.isChecked():
                try:
                    os.startfile(output_path)
                except Exception as e:
                    print(f"Не удалось открыть файл: {e}")

            QMessageBox.information(self, "Успех", f"Успешно напечатано {len(selected_frames)} листов в:\n{output_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка печати", f"Произошла ошибка при печати:\n{e}")
        finally:
            self.update_print_counter()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PrintManagerUI()
    window.show()
    sys.exit(app.exec())
