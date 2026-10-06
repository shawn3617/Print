from dataclasses import dataclass
from typing import Tuple

# Стандартные размеры ГОСТ форматов (ширина x высота в мм, горизонтальная ориентация)
GOST_FORMATS = {
    "A4": (297, 210),
    "A3": (420, 297),
    "A2": (594, 420),
    "A1": (841, 594),
    "A0": (1189, 841),
}

def detect_paper_format(width: float, height: float) -> str:
    """
    Определяет формат бумаги по размерам BoundingBox рамки (в единицах чертежа).
    Сначала вычисляет масштаб, потом подбирает ближайший ГОСТ формат.
    """
    # Определяем масштаб по известным размерам ГОСТ
    dims = [210, 297, 420, 594, 841, 1189]
    best_scale = 1.0
    min_diff = float('inf')
    for d in dims:
        for actual in (width, height):
            scale = actual / d
            if scale > 0.5:  # Масштаб должен быть >= 1
                diff = abs(round(scale) - scale)
                if diff < 0.05 and diff < min_diff:
                    min_diff = diff
                    best_scale = round(scale)
    
    scale = max(1.0, float(best_scale))
    
    # Приводим размеры к мм
    w_mm = width / scale
    h_mm = height / scale
    
    # Ищем ближайший формат
    best_format = "A2"  # По умолчанию
    best_match = float('inf')
    for fmt, (fw, fh) in GOST_FORMATS.items():
        # Проверяем обе ориентации
        diff1 = abs(w_mm - fw) + abs(h_mm - fh)
        diff2 = abs(w_mm - fh) + abs(h_mm - fw)
        diff = min(diff1, diff2)
        if diff < best_match:
            best_match = diff
            best_format = fmt
    return best_format

@dataclass
class Frame:
    """
    Класс, описывающий найденную рамку чертежа.
    """
    object_id: int                          # ID объекта в AutoCAD (ObjectID)
    sheet_number: str                       # Номер листа (извлеченный из штампа/атрибутов)
    sheet_name: str                         # Название листа
    min_point: Tuple[float, float, float]   # Левый нижний угол BoundingBox (X, Y, Z)
    max_point: Tuple[float, float, float]   # Правый верхний угол BoundingBox (X, Y, Z)
    source_type: str                        # Тип источника (SPDS, Polyline, Block)
    paper_format: str = "A2"               # Формат бумаги (A4, A3, A2, A1, A0)
