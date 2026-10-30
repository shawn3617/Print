"""
Окно справки и руководства пользователя PrintPDF.
Оформлено в виде вкладок с понятными пошаговыми инструкциями,
советами для проектировщиков и ответами на частые вопросы.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTabWidget, QTextBrowser, QLabel, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont

from core.resource_utils import get_resource_path
from ui.themes import THEMES


def _get_help_html(theme_id: str, tab_id: str) -> str:
    theme = THEMES.get(theme_id, THEMES["dark_catppuccin"])
    is_light = (theme_id == "light")

    text_color = theme.get("text_primary", "#cdd6f4")
    accent_color = theme.get("accent_color", "#89b4fa")
    border_color = theme.get("border", "#45475a")
    bg_card = theme.get("bg_card", "#181825")
    bg_input = theme.get("bg_input", "#313244")

    box_info_bg = "#e0f2fe" if is_light else "rgba(137, 180, 250, 0.12)"
    box_info_border = "#38bdf8" if is_light else "#89b4fa"

    box_tip_bg = "#f0fdf4" if is_light else "rgba(166, 227, 161, 0.12)"
    box_tip_border = "#4ade80" if is_light else "#a6e3a1"

    box_warn_bg = "#fffbeb" if is_light else "rgba(249, 226, 175, 0.12)"
    box_warn_border = "#facc15" if is_light else "#f9e2af"

    code_bg = "#f1f5f9" if is_light else "#313244"
    code_color = "#0f172a" if is_light else "#f5c2e7"

    css = f"""
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 14px;
            color: {text_color};
            line-height: 1.6;
            margin: 10px 15px;
        }}
        h2 {{
            color: {accent_color};
            font-size: 18px;
            margin-top: 5px;
            margin-bottom: 12px;
            border-bottom: 1px solid {border_color};
            padding-bottom: 6px;
        }}
        h3 {{
            color: {accent_color};
            font-size: 15px;
            margin-top: 16px;
            margin-bottom: 8px;
        }}
        p, li {{
            margin-bottom: 6px;
        }}
        ul, ol {{
            margin-top: 4px;
            margin-bottom: 12px;
            padding-left: 24px;
        }}
        b {{
            font-weight: 600;
        }}
        code {{
            background-color: {code_bg};
            color: {code_color};
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Consolas', monospace;
            font-size: 13px;
        }}
        .box {{
            border-radius: 6px;
            padding: 10px 14px;
            margin: 12px 0;
            font-size: 13px;
        }}
        .box-info {{
            background-color: {box_info_bg};
            border-left: 4px solid {box_info_border};
        }}
        .box-tip {{
            background-color: {box_tip_bg};
            border-left: 4px solid {box_tip_border};
        }}
        .box-warn {{
            background-color: {box_warn_bg};
            border-left: 4px solid {box_warn_border};
        }}
        .step-num {{
            display: inline-block;
            background-color: {accent_color};
            color: {'#11111b' if not is_light else '#ffffff'};
            font-weight: bold;
            border-radius: 12px;
            width: 22px;
            height: 22px;
            text-align: center;
            line-height: 22px;
            margin-right: 6px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        th, td {{
            border: 1px solid {border_color};
            padding: 6px 10px;
            text-align: left;
            font-size: 13px;
        }}
        th {{
            background-color: {bg_input};
            color: {accent_color};
        }}
    </style>
    """

    content = ""

    if tab_id == "quickstart":
        content = """
        <h2>🚀 Быстрый старт: печать в 3 шага</h2>
        <p>Программа предназначена для пакетной печати чертежей AutoCAD в один многостраничный PDF-документ или отдельные файлы.</p>
        
        <h3>Печать текущего открытого чертежа:</h3>
        <ol>
            <li><b>Откройте чертёж в AutoCAD.</b> В строке статуса программы отобразится имя файла (зелёным цветом).</li>
            <li>Нажмите <b>«Найти рамки»</b>. Программа за доли секунды просканирует чертёж и заполнит таблицу (номера, названия, форматы).</li>
            <li>Отметьте нужные листы галочками и нажмите зелёную кнопку <b>«ПЕЧАТЬ»</b>.</li>
        </ol>

        <div class="box box-tip">
            💡 <b>Совет:</b> Готовый объединённый PDF автоматически откроется в вашей программе просмотра сразу после завершения печати.
        </div>

        <h3>Пакетная печать группы чертежей:</h3>
        <ul>
            <li>Кнопка <b>«+ DWG...»</b> — добавление нескольких выбранных файлов чертежей в общий список.</li>
            <li>Кнопка <b>«+ Папка...»</b> — сканирование всех DWG-чертежей из выбранной папки (включая подпапки).</li>
            <li>Кнопка <b>«Закрыть чертежи»</b> — автоматически закроет в AutoCAD только те файлы, которые программа открывала сама, не закрывая чертежи, открытые вами вручную.</li>
        </ul>

        <div class="box box-info">
            📌 <b>Связь с AutoCAD:</b> Если вы переключили чертёж в AutoCAD, нажмите <b>«Обновить связь»</b> в верхней панели.
        </div>
        """

    elif tab_id == "frames":
        content = """
        <h2>📐 Какие рамки и штампы распознаёт программа</h2>
        <p>PrintPDF оснащён универсальными алгоритмами поиска и автоматически распознаёт любые виды оформления чертежей:</p>

        <h3>1. Рамки СПДС GraphiCS (форматы ГОСТ):</h3>
        <ul>
            <li>Поддерживаются любые версии СПДС (GraphiCS, СПДС Стройплощадка и встроенный СПДС AutoCAD).</li>
            <li>Номер листа, наименование, шифр (обозначение), объект и здание считываются напрямую из граф шаблона штампа.</li>
            <li>Автоматически распознаются обложки и титульные листы.</li>
        </ul>

        <h3>2. Пользовательские блоки и составные рамки:</h3>
        <ul>
            <li><b>Одинарные блоки:</b> стандартные блоки рамок (<code>*Формат*</code>, <code>*SHT*</code>, <code>*Рамка*</code>, <code>*Title*</code> и др.).</li>
            <li><b>Составные рамки:</b> если внешняя граница формата и угловой штамп выполнены двумя отдельными блоками (например, <code>BRU_format</code> + <code>BRU_stamp_r1</code>), программа автоматически определяет вложенность штампа и объединяет их в один лист.</li>
            <li><b>Динамические блоки:</b> блоки с выпадающими списками форматов и спецтегами (например, <code>vcFormat</code> с атрибутами <code>!НОМЕР</code>, <code>!ШИФР</code>, <code>!ФОРМАТ</code>).</li>
            <li><b>Многострочные названия:</b> составные теги (строка 1, 2, 3) аккуратно объединяются в единое наименование листа с очисткой служебных кодов MText.</li>
        </ul>

        <h3>3. Рамки из полилиний:</h3>
        <ul>
            <li>Поиск замкнутых полилиний на слое <code>0000_Формат</code> или по внешним габаритам ГОСТ.</li>
            <li>Считывание граф штампа по ГОСТ 21.101 (Форма 3 для основных надписей и Форма 4 для чертежей строительных изделий).</li>
        </ul>

        <h3>4. Пространство листа (Layouts):</h3>
        <ul>
            <li>Переключите выпадающий список <b>«Источник»</b> на <code>Листы (Layouts)</code>, чтобы отправить на печать подготовленные вкладки листов с видовыми экранами.</li>
        </ul>
        """

    elif tab_id == "table":
        content = """
        <h2>📋 Управление листами в таблице</h2>

        <h3>Порядок и сортировка листов:</h3>
        <ul>
            <li><b>Перетаскивание мышью (Drag & Drop):</b> зажмите строку таблицы левой кнопкой мыши и переместите её на нужное место в очереди печати.</li>
            <li><b>Кнопки порядка:</b> <code>▲ Вверх (Ctrl+↑)</code> и <code>▼ Вниз (Ctrl+↓)</code> сдвигают выделенный лист.</li>
            <li><b>Кнопка «По номерам»:</b> выполняет естественную сортировку ГОСТ (Лист 1, 2, 2а, 3, 10, а не 1, 10, 2).</li>
        </ul>

        <h3>Поиск и фильтрация:</h3>
        <ul>
            <li><b>Поле «Поиск»:</b> мгновенно фильтрует список по номеру листа, тексту наименования, шифру или имени DWG-файла.</li>
            <li><b>Фильтр «Формат»:</b> отображает только листы нужного формата (например, отобрать только А3 или А4).</li>
        </ul>

        <h3>Контекстное меню (правый клик по строке):</h3>
        <ul>
            <li><b>Показать в AutoCAD:</b> разворачивает окно AutoCAD и мягко подсвечивает рамку (также работает <b>двойной клик</b> по строке).</li>
            <li><b>Печатать только этот лист:</b> оставляет галочку только на текущем листе, снимая со всех остальных в один клик.</li>
            <li><b>Печатать только листы чертежа (...):</b> оставляет выделенными только листы выбранного DWG-файла (незаменимо в пакетах).</li>
            <li><b>Подменю «Копировать»:</b> копирование наименования, шифра или всей строки с табуляцией (для мгновенной вставки в Excel).</li>
            <li><b>Настройка колонок:</b> кликните правой кнопкой мыши по <i>шапке таблицы</i>, чтобы скрыть или показать нужные графы.</li>
        </ul>

        <div class="box box-tip">
            📊 <b>Экспорт ведомости:</b> Кнопка <b>«В Excel / CSV...»</b> позволяет выгрузить готовую ведомость рабочих чертежей основного комплекта прямо в таблицу Excel (.xlsx).
        </div>
        """

    elif tab_id == "printer":
        content = """
        <h2>🖨️ Настройки печати и плоттеры</h2>

        <h3>Автоподбор форматов бумаги:</h3>
        <p>Вам <b>не нужно вручную настраивать формат каждого листа</b>. Программа определяет физический размер каждой рамки в масштабе чертежа и автоматически назначает плоттеру соответствующий формат бумаги:</p>
        <ul>
            <li><b>Стандартные форматы:</b> А4, А3, А2, А1, А0 (альбомные и книжные).</li>
            <li><b>Удлинённые форматы ГОСТ 2.301-68:</b> А4x3...А4x9, А3x3...А3x7, А2x3...А2x5, А1x3...А1x4, А0x2...А0x3.</li>
            <li><b>Автоповорот:</b> ориентация листа (альбомная/книжная) подбирается автоматически.</li>
        </ul>

        <h3>Рекомендуемые плоттеры:</h3>
        <ul>
            <li><code>PDF_ГОСТ.pc3</code> — фирменный плоттер со всеми предустановленными форматами ГОСТ без полей (поставляется в комплекте программы для AutoCAD 2021 и 2024).</li>
            <li><code>DWG To PDF.pc3</code> — стандартный плоттер AutoCAD.</li>
        </ul>

        <div class="box box-warn">
            ⚠️ <b>Резервный формат бумаги:</b> Параметр в выпадающем списке «Резервный» используется <b>только</b> в том случае, если в выбранном плоттере отсутствует формат под конкретную рамку. Рекомендуется выбирать <code>ISO без полей А3</code>.
        </div>

        <h3>Режим вывода:</h3>
        <ul>
            <li><b>«В один файл (PDF)»:</b> объединяет все выбранные листы в единый готовый буклет (многостраничный PDF).</li>
            <li><b>«В отдельные файлы»:</b> сохраняет каждый лист отдельным PDF-файлом с именем вида <code>Лист 1 - План этажа.pdf</code>.</li>
        </ul>
        """

    elif tab_id == "faq":
        content = """
        <h2>❓ Частые вопросы и решение проблем</h2>

        <h3>1. В верхней панели горит «Не подключено»</h3>
        <p><b>Решение:</b> Убедитесь, что AutoCAD запущен и в нём открыт файл чертежа. Нажмите кнопку <b>«Обновить связь»</b>. Если AutoCAD запущен от имени Администратора, перезапустите программу также от Администратора.</p>

        <h3>2. Окно безопасности AutoCAD: «Файл чертежа не является доверенным»</h3>
        <p><b>Решение:</b> Если чертёж открыт из сетевой папки, AutoCAD блокирует внешние команды до подтверждения. Перейдите в окно AutoCAD и нажмите <b>«Открыть файл»</b> (Enter) в появившемся диалоге.</p>

        <h3>3. Длинный чертёж (например, А2x4) напечатался на листе А3 с белыми полями</h3>
        <p><b>Решение:</b> Проверьте, какой плоттер выбран в настройках справа. Выберите <code>PDF_ГОСТ.pc3</code> или <code>DWG To PDF.pc3</code>. В них содержатся точные форматы ГОСТ без полей.</p>

        <h3>4. Не видно надписей в выпадающих списках на Windows 11</h3>
        <p><b>Решение:</b> В правом верхнем углу переключите тему оформления на <code>AutoCAD Dark (Графит)</code>, <code>Тёмная (Catppuccin)</code> или <code>Светлая (Классика)</code>. Тема сохранится автоматически.</p>

        <h3>5. Горячие клавиши в программе:</h3>
        <table>
            <tr><th>Клавиша</th><th>Действие</th></tr>
            <tr><td><b>F1</b></td><td>Открыть это окно справки и инструкции</td></tr>
            <tr><td><b>Ctrl + ↑</b></td><td>Поднять выбранный лист выше в очереди печати</td></tr>
            <tr><td><b>Ctrl + ↓</b></td><td>Опустить выбранный лист ниже в очереди печати</td></tr>
            <tr><td><b>Двойной клик</b></td><td>Центрировать и подсветить лист в AutoCAD</td></tr>
            <tr><td><b>Space (Пробел)</b></td><td>Включить / снять галочку печати для строки</td></tr>
            <tr><td><b>Esc</b></td><td>Закрыть окно справки / отменить операцию</td></tr>
        </table>
        """

    return f"<!DOCTYPE html><html><head>{css}</head><body>{content}</body></html>"


class HelpDialog(QDialog):
    """Диалоговое окно справки и руководства пользователя."""

    def __init__(self, current_theme_id: str = "dark_catppuccin", parent=None):
        super().__init__(parent)
        self.current_theme_id = current_theme_id

        self.setWindowTitle("Инструкция пользователя — PrintPDF")
        self.resize(860, 650)
        self.setMinimumSize(720, 500)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMaximizeButtonHint)

        icon_path = get_resource_path("autocad_to_pdf_icon.ico")
        if icon_path:
            self.setWindowIcon(QIcon(icon_path))

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Шапка
        header_layout = QHBoxLayout()
        lbl_title = QLabel("📖 Руководство пользователя AutoCAD Batch PDF Plotter")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        lbl_title.setProperty("cssClass", "header_accent")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        lbl_hint = QLabel("Горячая клавиша: F1")
        lbl_hint.setStyleSheet("color: #a6adc8; font-size: 12px;")
        header_layout.addWidget(lbl_hint)
        layout.addLayout(header_layout)

        # Вкладки инструкции
        self.tabs = QTabWidget()
        self.tabs.setObjectName("help_tabs")

        tabs_data = [
            ("quickstart", "🚀 Быстрый старт"),
            ("frames", "📐 Рамки и штампы"),
            ("table", "📋 Таблица листов"),
            ("printer", "🖨️ Печать и плоттеры"),
            ("faq", "❓ Вопросы и ответы (FAQ)"),
        ]

        self.browsers = {}
        for tab_id, tab_title in tabs_data:
            browser = QTextBrowser()
            browser.setOpenExternalLinks(True)
            html = _get_help_html(self.current_theme_id, tab_id)
            browser.setHtml(html)
            self.tabs.addTab(browser, tab_title)
            self.browsers[tab_id] = browser

        layout.addWidget(self.tabs, stretch=1)

        # Нижняя панель с кнопкой закрытия
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        btn_close = QPushButton("Закрыть")
        btn_close.setProperty("cssClass", "btn_tool")
        btn_close.setMinimumWidth(100)
        btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(btn_close)

        layout.addLayout(bottom_layout)

    def update_theme(self, theme_id: str):
        self.current_theme_id = theme_id
        for tab_id, browser in self.browsers.items():
            browser.setHtml(_get_help_html(theme_id, tab_id))
