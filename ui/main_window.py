import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox,
    QLabel, QHeaderView, QCheckBox, QGroupBox, QFormLayout,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt

from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
from core.printer import BatchPrinter

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
            QHeaderView::section { background-color: #313244; color: #cdd6f4; padding: 5px; border: 1px solid #45475a; font-weight: bold; }
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

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Печать", "Лист", "Название листа", "Формат", "Источник"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(True)
        left_layout.addWidget(self.table)
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
        form_layout.addRow(QLabel("Формат:"), self.combo_papers)
        
        self.combo_style = QComboBox()
        form_layout.addRow(QLabel("Стиль:"), self.combo_style)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["В отдельные файлы", "В один файл (PDF)"])
        form_layout.addRow(QLabel("Режим:"), self.combo_mode)

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
        self.table.setItem(row, 1, item_num)
        
        self.table.setItem(row, 2, QTableWidgetItem(name))
        
        item_fmt = QTableWidgetItem(paper_format)
        item_fmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, 3, item_fmt)
        
        self.table.setItem(row, 4, QTableWidgetItem(source))
        
    def update_print_counter(self):
        count = 0
        for i in range(self.table.rowCount()):
            chk_widget = self.table.cellWidget(i, 0)
            chk = chk_widget.layout().itemAt(0).widget()
            if chk.isChecked():
                count += 1
        self.btn_print.setText(f"ПЕЧАТЬ ({count} листов)")
        self.btn_print.setEnabled(count > 0)

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
