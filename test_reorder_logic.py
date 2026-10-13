import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import PrintManagerUI
from core.models import Frame

def test_reorder():
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
        
    from unittest.mock import MagicMock
    win = PrintManagerUI(config_manager=MagicMock())
    
    # Создаем 4 тестовые рамки
    win.frames = [
        Frame(1, "1", "Общие данные", (0, 0, 0), (29700, 21000, 0), "SPDS", "A4"),
        Frame(2, "2", "План 1 этажа", (0, 0, 0), (59400, 42000, 0), "SPDS", "A2"),
        Frame(3, "3", "Фасад 1-5", (0, 0, 0), (59400, 42000, 0), "SPDS", "A2"),
        Frame(4, "4", "Спецификация", (0, 0, 0), (29700, 21000, 0), "SPDS", "A4"),
    ]
    
    # Заполняем таблицу
    win.table.setRowCount(0)
    for f in win.frames:
        win.add_table_row(True, f.sheet_number, f.sheet_name, f.paper_format, f.source_type)
        
    assert win.table.rowCount() == 4
    print("Начальный порядок:", [f.sheet_number for f in win.frames])
    
    # 1. Перемещаем строку 3 (Лист 4) наверх (индекс 0)
    win.move_row(3, 0)
    order_after = [f.sheet_number for f in win.frames]
    print("После перемещения листа 4 на 1-е место:", order_after)
    assert order_after == ["4", "1", "2", "3"], f"Ошибка порядка: {order_after}"
    assert win.table.item(0, 1).text() == "4"
    assert win.table.item(1, 1).text() == "1"
    
    # 2. Выбираем строку 2 (Лист 2) и двигаем вверх
    win.table.setCurrentCell(2, 1)
    win.move_row_up()
    order_after_up = [f.sheet_number for f in win.frames]
    print("После 'Вверх' для строки 2:", order_after_up)
    assert order_after_up == ["4", "2", "1", "3"], f"Ошибка порядка: {order_after_up}"
    
    # 3. Двигаем вниз
    win.move_row_down()
    order_after_down = [f.sheet_number for f in win.frames]
    print("После 'Вниз':", order_after_down)
    assert order_after_down == ["4", "1", "2", "3"]
    
    # 4. Сброс к сортировке по номерам
    win.sort_by_sheet_number()
    order_reset = [f.sheet_number for f in win.frames]
    print("После 'По номерам листа':", order_reset)
    assert order_reset == ["1", "2", "3", "4"]
    
    # 5. Проверка чекбоксов (выбрать все / снять все)
    win.select_all_rows(False)
    assert not win.is_row_checked(0)
    assert not win.is_row_checked(1)
    win.select_all_rows(True)
    assert win.is_row_checked(0)
    assert win.is_row_checked(1)
    
    print("\n ВСЕ ТЕСТЫ РУЧНОГО ИЗМЕНЕНИЯ ПОРЯДКА ПРОЙДЕНЫ УСПЕШНО!")

if __name__ == "__main__":
    test_reorder()
