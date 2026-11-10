"""
Скрипт генерации тестовых чертежей AutoCAD (tools/create_test_dwgs.py).

Создает эталонный набор чертежей DWG для тестирования PrintPDF:
1. sample_model_sheets.dwg:
   - Листы в Пространстве Модели (Model Space);
   - Стандартные форматы: A4 (книжный), A3 (альбомный), A2 (масштаб 1:50), A1 (масштаб 1:100), A3x3 (кратный);
   - Штампы по ГОСТ с атрибутами (Шифр, Номер листа, Наименование);
   - Внешняя рамка (для сканера рамок) и внутренняя рамка с отступами 20/5 мм.
2. sample_layouts_tabs.dwg:
   - Листы в Пространстве Листа (Layouts);
   - Вкладки с настроенными форматами A3, A2, A4 и TabOrder (1, 2, 3);
   - Штампы и геометрия в каждом Layout.
"""

import os
import sys

# Обеспечиваем импорт пакета core при запуске из папки tools
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import win32com.client
import pythoncom
from typing import List, Tuple

from core.autocad_connector import AutoCADConnector
from core.logger import get_logger

logger = get_logger("create_test_dwgs")


def _var_pt(x: float, y: float, z: float = 0.0):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(x), float(y), float(z)])


def _var_polyline_coords(coords: List[float]):
    return win32com.client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, [float(c) for c in coords])


def _create_stamp_block(doc, block_name: str = "STAMP_GOST"):
    """Создает определение блока штампа с атрибутами DOC_CODE, SHEET, SHEET_NAME"""
    pt0 = _var_pt(0, 0, 0)
    try:
        block = doc.Blocks.Item(block_name)
        return block
    except Exception:
        pass

    block = doc.Blocks.Add(pt0, block_name)

    # Внешняя рамка штампа 185 x 55 мм
    coords = [0.0, 0.0, 185.0, 0.0, 185.0, 55.0, 0.0, 55.0]
    p = block.AddLightWeightPolyline(_var_polyline_coords(coords))
    p.Closed = True

    # Линии штампа (основные графы)
    block.AddLine(_var_pt(0, 15, 0), _var_pt(185, 15, 0))
    block.AddLine(_var_pt(130, 0, 0), _var_pt(130, 55, 0))
    block.AddLine(_var_pt(150, 15, 0), _var_pt(150, 55, 0))
    block.AddLine(_var_pt(167, 15, 0), _var_pt(167, 55, 0))

    # Атрибуты блока
    # AddAttribute(Height, Mode, Prompt, InsertionPoint, Tag, Value)
    block.AddAttribute(5.0, 0, "Обозначение документа", _var_pt(10, 42, 0), "DOC_CODE", "001-2026-АР")
    block.AddAttribute(3.5, 0, "Номер листа", _var_pt(155, 30, 0), "SHEET", "1")
    block.AddAttribute(3.5, 0, "Количество листов", _var_pt(172, 30, 0), "TOTAL_SHEETS", "5")
    block.AddAttribute(4.0, 0, "Наименование листа", _var_pt(10, 20, 0), "SHEET_NAME", "Общие данные")
    block.AddAttribute(4.0, 0, "Наименование объекта", _var_pt(10, 5, 0), "OBJECT_NAME", "Жилой дом")

    return block


def add_sheet_to_space(
    space,
    origin_x: float,
    origin_y: float,
    width_mm: float,
    height_mm: float,
    scale: float,
    sheet_number: str,
    sheet_name: str,
    doc_code: str = "001-2026-АР",
    block_name: str = "STAMP_GOST"
):
    """
    Добавляет лист чертежа:
    - Внешняя полилиния (формат с учетом масштаба)
    - Внутренняя полилиния (отступы 20 мм слева, 5 мм справа/сверху/снизу с учетом масштаба)
    - Вставка блока штампа с атрибутами
    """
    w = width_mm * scale
    h = height_mm * scale

    # 1. Внешняя рамка
    x1, y1 = origin_x, origin_y
    x2, y2 = origin_x + w, origin_y + h
    outer_coords = [x1, y1, x2, y1, x2, y2, x1, y2]
    outer_poly = space.AddLightWeightPolyline(_var_polyline_coords(outer_coords))
    outer_poly.Closed = True

    # 2. Внутренняя рамка (ГОСТ: 20 мм поле для подшивки, 5 мм остальные поля)
    ix1 = origin_x + 20.0 * scale
    iy1 = origin_y + 5.0 * scale
    ix2 = origin_x + w - 5.0 * scale
    iy2 = origin_y + h - 5.0 * scale
    inner_coords = [ix1, iy1, ix2, iy1, ix2, iy2, ix1, iy2]
    inner_poly = space.AddLightWeightPolyline(_var_polyline_coords(inner_coords))
    inner_poly.Closed = True

    # 3. Вставка штампа в правый нижний угол внутренней рамки
    stamp_x = ix2 - 185.0 * scale
    stamp_y = iy1
    ins_pt = _var_pt(stamp_x, stamp_y, 0)
    block_ref = space.InsertBlock(ins_pt, block_name, scale, scale, scale, 0.0)

    # Заполнение атрибутов
    try:
        attrs = block_ref.GetAttributes()
        for att in attrs:
            tag = att.TagString.upper()
            if tag == "SHEET":
                att.TextString = sheet_number
            elif tag == "SHEET_NAME":
                att.TextString = sheet_name
            elif tag == "DOC_CODE":
                att.TextString = doc_code
    except Exception as e:
        logger.warning(f"Не удалось заполнить атрибуты штампа листа {sheet_number}: {e}")

    # Добавляем текстовый заголовок внутри листа для проверки извлечения текста
    text_pt = _var_pt(ix1 + 10.0 * scale, iy2 - 25.0 * scale, 0)
    text_entity = space.AddText(f"Лист {sheet_number} - {sheet_name}", text_pt, 7.0 * scale)

    return outer_poly


def create_model_sheets_dwg(output_path: str, connector: AutoCADConnector) -> str:
    """Создает sample_model_sheets.dwg с 5 листами разных форматов и масштабов в ModelSpace"""
    doc = connector.app.Documents.Add()
    _create_stamp_block(doc)

    # 5 листов по ГОСТ:
    # Лист 1: A4 книжный (210 x 297), М 1:1
    add_sheet_to_space(
        space=doc.ModelSpace,
        origin_x=0.0, origin_y=0.0,
        width_mm=210.0, height_mm=297.0, scale=1.0,
        sheet_number="1", sheet_name="Титульный лист"
    )

    # Лист 2: A3 альбомный (420 x 297), М 1:1
    add_sheet_to_space(
        space=doc.ModelSpace,
        origin_x=300.0, origin_y=0.0,
        width_mm=420.0, height_mm=297.0, scale=1.0,
        sheet_number="2", sheet_name="План 1 этажа на отм. 0.000"
    )

    # Лист 3: A2 альбомный (594 x 420), М 1:50
    add_sheet_to_space(
        space=doc.ModelSpace,
        origin_x=1000.0, origin_y=0.0,
        width_mm=594.0, height_mm=420.0, scale=50.0,
        sheet_number="3", sheet_name="Фасад в осях 1-12"
    )

    # Лист 4: A1 альбомный (841 x 594), М 1:100
    add_sheet_to_space(
        space=doc.ModelSpace,
        origin_x=35000.0, origin_y=0.0,
        width_mm=841.0, height_mm=594.0, scale=100.0,
        sheet_number="4", sheet_name="Схема расположения колонн"
    )

    # Лист 5: A3x3 альбомный (891 x 420), М 1:1
    add_sheet_to_space(
        space=doc.ModelSpace,
        origin_x=125000.0, origin_y=0.0,
        width_mm=891.0, height_mm=420.0, scale=1.0,
        sheet_number="5", sheet_name="Развертка стен и оборудования"
    )

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    doc.SaveAs(os.path.abspath(output_path))
    doc.Close(False)
    logger.info(f"Создан эталонный чертеж модели: {output_path}")
    return output_path


def create_layouts_sheets_dwg(output_path: str, connector: AutoCADConnector) -> str:
    """Создает sample_layouts_tabs.dwg с 3 листами в Paper Space (Layouts)"""
    doc = connector.app.Documents.Add()
    _create_stamp_block(doc)

    layout_specs = [
        ("01 - Общие данные", 1, 420.0, 297.0, "ISO_full_bleed_A3_(420.00_x_297.00_MM)", "1", "Общие данные"),
        ("02 - План кровли", 2, 594.0, 420.0, "ISO_full_bleed_A2_(594.00_x_420.00_MM)", "2", "План кровли"),
        ("03 - Спецификация", 3, 210.0, 297.0, "ISO_A4_(210.00_x_297.00_MM)", "3", "Спецификация оборудования")
    ]

    for name, order, w_mm, h_mm, media_name, sheet_num, sheet_name in layout_specs:
        try:
            layout = doc.Layouts.Add(name)
        except Exception:
            layout = doc.Layouts.Item(name)

        layout.TabOrder = order
        try:
            layout.ConfigName = "DWG To PDF.pc3"
            layout.CanonicalMediaName = media_name
        except Exception as e:
            logger.debug(f"Настройка плоттера макета {name}: {e}")

        # Добавляем геометрию листа в Block макета
        space = layout.Block
        add_sheet_to_space(
            space=space,
            origin_x=0.0, origin_y=0.0,
            width_mm=w_mm, height_mm=h_mm, scale=1.0,
            sheet_number=sheet_num, sheet_name=sheet_name
        )

    # Удаляем дефолтные Layout1 / Layout2, если они пусты
    for default_name in ["Layout1", "Layout2"]:
        try:
            doc.Layouts.Item(default_name).Delete()
        except Exception:
            pass

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    doc.SaveAs(os.path.abspath(output_path))
    doc.Close(False)
    logger.info(f"Создан эталонный чертеж макетов: {output_path}")
    return output_path


def generate_all_samples():
    """Генерирует все эталонные файлы в tests/samples"""
    connector = AutoCADConnector()
    if not connector.connect():
        print("Ошибка: AutoCAD не доступен. Запустите AutoCAD для генерации DWG.")
        return False

    out_dir = os.path.abspath("tests/samples")
    os.makedirs(out_dir, exist_ok=True)

    model_dwg = os.path.join(out_dir, "sample_model_sheets.dwg")
    layouts_dwg = os.path.join(out_dir, "sample_layouts_tabs.dwg")

    print(f"Генерация {model_dwg}...")
    create_model_sheets_dwg(model_dwg, connector)

    print(f"Генерация {layouts_dwg}...")
    create_layouts_sheets_dwg(layouts_dwg, connector)

    print("Генерация тестовых чертежей завершена успешно!")
    return True


if __name__ == "__main__":
    generate_all_samples()
