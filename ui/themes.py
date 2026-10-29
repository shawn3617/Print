"""
Модуль цветовых тем оформления интерфейса Smart Batch Print.
Поддерживает:
- "dark_catppuccin": Премиальная тёмно-синяя тема (Catppuccin Mocha)
- "autocad_dark": Графитовая тёмная тема в стиле AutoCAD 2021-2025
- "light": Чистая светлая классическая тема (Classic Light)
"""

from typing import Dict, Any, Tuple


THEMES: Dict[str, Dict[str, Any]] = {
    "dark_catppuccin": {
        "id": "dark_catppuccin",
        "name": "Тёмная (Catppuccin)",
        "status_ok_color": "#a6e3a1",
        "status_err_color": "#f38ba8",
        "accent_color": "#89b4fa",
        "bg_main": "#1e1e2e",
        "bg_card": "#181825",
        "bg_input": "#313244",
        "border": "#45475a",
        "text_primary": "#cdd6f4",
        "text_muted": "#a6adc8",
        "accent_hover": "#74c7ec",
        "accent_focus": "#89b4fa",
        "btn_primary_bg": "#89b4fa",
        "btn_primary_hover": "#74c7ec",
        "btn_primary_pressed": "#89dceb",
        "btn_primary_text": "#11111b",
        "btn_print_bg": "#a6e3a1",
        "btn_print_hover": "#94e2d5",
        "btn_print_text": "#11111b",
        "btn_print_disabled_bg": "#35453b",
        "btn_print_disabled_text": "#6c7086",
        "btn_tool_bg": "#313244",
        "btn_tool_hover": "#45475a",
        "btn_tool_pressed": "#585b70",
        "btn_tool_text": "#cdd6f4",
        "table_bg": "#181825",
        "table_grid": "#313244",
        "table_item_selected_bg": "#45475a",
        "table_item_selected_text": "#ffffff",
        "header_bg": "#313244",
        "header_text": "#cdd6f4",
        "popup_bg": "#1e1e2e",
        "popup_item_hover_bg": "#313244",
        "popup_item_selected_bg": "#45475a",
        "scrollbar_bg": "#181825",
        "scrollbar_handle": "#45475a",
        "scrollbar_handle_hover": "#585b70",
        "progress_bg": "#313244",
        "progress_chunk": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #89b4fa, stop:1 #a6e3a1)",
    },
    "autocad_dark": {
        "id": "autocad_dark",
        "name": "AutoCAD Dark (Графит)",
        "status_ok_color": "#4caf50",
        "status_err_color": "#ef5350",
        "accent_color": "#007acc",
        "bg_main": "#212121",
        "bg_card": "#191919",
        "bg_input": "#2d2d2d",
        "border": "#3c3c3c",
        "text_primary": "#e0e0e0",
        "text_muted": "#9e9e9e",
        "accent_hover": "#1c97ea",
        "accent_focus": "#007acc",
        "btn_primary_bg": "#007acc",
        "btn_primary_hover": "#1c97ea",
        "btn_primary_pressed": "#005a9e",
        "btn_primary_text": "#ffffff",
        "btn_print_bg": "#388e3c",
        "btn_print_hover": "#43a047",
        "btn_print_text": "#ffffff",
        "btn_print_disabled_bg": "#2a382c",
        "btn_print_disabled_text": "#757575",
        "btn_tool_bg": "#2d2d2d",
        "btn_tool_hover": "#3c3c3c",
        "btn_tool_pressed": "#505050",
        "btn_tool_text": "#e0e0e0",
        "table_bg": "#191919",
        "table_grid": "#333333",
        "table_item_selected_bg": "#094771",
        "table_item_selected_text": "#ffffff",
        "header_bg": "#2d2d2d",
        "header_text": "#e0e0e0",
        "popup_bg": "#212121",
        "popup_item_hover_bg": "#333333",
        "popup_item_selected_bg": "#094771",
        "scrollbar_bg": "#191919",
        "scrollbar_handle": "#424242",
        "scrollbar_handle_hover": "#5a5a5a",
        "progress_bg": "#2d2d2d",
        "progress_chunk": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007acc, stop:1 #388e3c)",
    },
    "light": {
        "id": "light",
        "name": "Светлая (Классика)",
        "status_ok_color": "#16a34a",
        "status_err_color": "#dc2626",
        "accent_color": "#0284c7",
        "bg_main": "#f0f2f5",
        "bg_card": "#ffffff",
        "bg_input": "#ffffff",
        "border": "#cfd4dc",
        "text_primary": "#1f2937",
        "text_muted": "#64748b",
        "accent_hover": "#0369a1",
        "accent_focus": "#0284c7",
        "btn_primary_bg": "#0284c7",
        "btn_primary_hover": "#0369a1",
        "btn_primary_pressed": "#075985",
        "btn_primary_text": "#ffffff",
        "btn_print_bg": "#16a34a",
        "btn_print_hover": "#15803d",
        "btn_print_text": "#ffffff",
        "btn_print_disabled_bg": "#cbd5e1",
        "btn_print_disabled_text": "#94a3b8",
        "btn_tool_bg": "#ffffff",
        "btn_tool_hover": "#f1f5f9",
        "btn_tool_pressed": "#e2e8f0",
        "btn_tool_text": "#334155",
        "table_bg": "#ffffff",
        "table_grid": "#e2e8f0",
        "table_item_selected_bg": "#bae6fd",
        "table_item_selected_text": "#0369a1",
        "header_bg": "#f1f5f9",
        "header_text": "#1e293b",
        "popup_bg": "#ffffff",
        "popup_item_hover_bg": "#f1f5f9",
        "popup_item_selected_bg": "#bae6fd",
        "scrollbar_bg": "#f8fafc",
        "scrollbar_handle": "#cbd5e1",
        "scrollbar_handle_hover": "#94a3b8",
        "progress_bg": "#e2e8f0",
        "progress_chunk": "qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #16a34a)",
    }
}


def build_theme_qss(theme_id: str) -> str:
    """Генерирует полный QSS-стиль для указанного идентификатора темы."""
    theme = THEMES.get(theme_id, THEMES["dark_catppuccin"])
    
    return f"""
        QMainWindow {{
            background-color: {theme['bg_main']};
        }}
        QLabel {{
            color: {theme['text_primary']};
            font-size: 14px;
            font-family: 'Segoe UI', Arial, sans-serif;
        }}
        QLabel[cssClass="header_accent"] {{
            font-weight: bold;
            color: {theme['accent_color']};
        }}
        QGroupBox {{
            color: {theme['text_primary']};
            font-size: 14px;
            font-weight: bold;
            border: 1px solid {theme['border']};
            border-radius: 8px;
            margin-top: 15px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 4px 0 4px;
        }}
        QComboBox {{
            background-color: {theme['bg_input']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border']};
            border-radius: 4px;
            padding: 5px;
            font-size: 14px;
        }}
        QComboBox:hover {{
            border: 1px solid {theme['accent_hover']};
        }}
        QComboBox:focus {{
            border: 1px solid {theme['accent_focus']};
        }}
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {theme['popup_bg']};
            color: {theme['text_primary']};
            selection-background-color: {theme['popup_item_selected_bg']};
            selection-color: {theme['table_item_selected_text']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 4px;
            outline: none;
        }}
        QComboBox QAbstractItemView::item {{
            color: {theme['text_primary']};
            min-height: 26px;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {theme['popup_item_hover_bg']};
            color: {theme['text_primary']};
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {theme['popup_item_selected_bg']};
            color: {theme['table_item_selected_text']};
        }}
        QLineEdit {{
            background-color: {theme['bg_input']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 6px 10px;
            font-size: 13px;
        }}
        QLineEdit:focus {{
            border: 1px solid {theme['accent_focus']};
        }}
        QCheckBox {{
            color: {theme['text_primary']};
            font-size: 13px;
            spacing: 6px;
        }}
        QCheckBox::indicator {{
            width: 16px;
            height: 16px;
        }}
        QPushButton {{
            background-color: {theme['btn_primary_bg']};
            color: {theme['btn_primary_text']};
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: 14px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background-color: {theme['btn_primary_hover']};
        }}
        QPushButton:pressed {{
            background-color: {theme['btn_primary_pressed']};
        }}
        QPushButton#btn_print {{
            background-color: {theme['btn_print_bg']};
            color: {theme['btn_print_text']};
            font-size: 16px;
            padding: 15px;
            font-weight: bold;
        }}
        QPushButton#btn_print:hover {{
            background-color: {theme['btn_print_hover']};
        }}
        QPushButton#btn_print:disabled {{
            background-color: {theme['btn_print_disabled_bg']};
            color: {theme['btn_print_disabled_text']};
        }}
        QTableWidget {{
            background-color: {theme['table_bg']};
            color: {theme['text_primary']};
            gridline-color: {theme['table_grid']};
            border: 1px solid {theme['border']};
            border-radius: 8px;
        }}
        QTableWidget::item:selected {{
            background-color: {theme['table_item_selected_bg']};
            color: {theme['table_item_selected_text']};
        }}
        QHeaderView::section {{
            background-color: {theme['header_bg']};
            color: {theme['header_text']};
            padding: 5px;
            border: 1px solid {theme['border']};
            font-weight: bold;
        }}
        QPushButton[cssClass="btn_tool"] {{
            background-color: {theme['btn_tool_bg']};
            color: {theme['btn_tool_text']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 6px 14px;
            font-size: 13px;
            font-weight: normal;
        }}
        QPushButton[cssClass="btn_tool"]:hover {{
            background-color: {theme['btn_tool_hover']};
        }}
        QPushButton[cssClass="btn_tool"]:pressed {{
            background-color: {theme['btn_tool_pressed']};
        }}
        QScrollBar:vertical {{
            background-color: {theme['scrollbar_bg']};
            width: 14px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background-color: {theme['scrollbar_handle']};
            min-height: 20px;
            border-radius: 7px;
        }}
        QScrollBar::handle:vertical:hover {{
            background-color: {theme['scrollbar_handle_hover']};
        }}
        QScrollBar:horizontal {{
            background-color: {theme['scrollbar_bg']};
            height: 14px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background-color: {theme['scrollbar_handle']};
            min-width: 20px;
            border-radius: 7px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background-color: {theme['scrollbar_handle_hover']};
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            width: 0px;
            height: 0px;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal,
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}
        QDialog {{
            background-color: {theme['bg_main']};
        }}
        QProgressBar {{
            background-color: {theme['progress_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            text-align: center;
            font-size: 13px;
            font-weight: bold;
            min-height: 24px;
        }}
        QProgressBar::chunk {{
            background: {theme['progress_chunk']};
            border-radius: 5px;
        }}
        QFrame#status_bar_container {{
            background-color: {theme['bg_card']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
        }}
        QLabel#status_bar_left {{
            color: {theme['text_primary']};
            font-size: 13px;
        }}
        QLabel#status_bar_right {{
            color: {theme['text_muted']};
            font-size: 12px;
        }}
        QMenu {{
            background-color: {theme['popup_bg']};
            color: {theme['text_primary']};
            border: 1px solid {theme['border']};
            border-radius: 6px;
            padding: 4px;
        }}
        QMenu::item {{
            background-color: transparent;
            color: {theme['text_primary']};
            padding: 6px 24px 6px 20px;
            border-radius: 4px;
            font-size: 13px;
        }}
        QMenu::item:selected {{
            background-color: {theme['popup_item_selected_bg']};
            color: {theme['table_item_selected_text']};
        }}
        QMenu::item:disabled {{
            color: {theme['text_muted']};
            background-color: transparent;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {theme['border']};
            margin: 4px 6px;
        }}
        QMenu::indicator {{
            width: 14px;
            height: 14px;
            left: 5px;
        }}
    """


def get_theme_status_colors(theme_id: str) -> Tuple[str, str]:
    """Возвращает пару (цвет_успеха, цвет_ошибки) для указанной темы."""
    theme = THEMES.get(theme_id, THEMES["dark_catppuccin"])
    return theme["status_ok_color"], theme["status_err_color"]
