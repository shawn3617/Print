from typing import List
from core.models import Frame
from parsers.block_parser import BlockParser
from parsers.spds_parser import SPDSParser
from parsers.polyline_parser import PolylineParser

class DocumentScanner:
    """
    Агрегатор, который запускает все парсеры и собирает рамки со всего чертежа.
    """
    def __init__(self):
        # Настраиваем парсеры
        self.parsers = [
            BlockParser(block_names=["SHT_*", "Формат*"], sheet_attr_tags=["SHEET", "ЛИСТ"]),
            SPDSParser(),
            PolylineParser(target_layer="0000_Формат")
        ]

    def scan_document(self, doc) -> List[Frame]:
        all_frames = []
        for parser in self.parsers:
            try:
                frames = parser.find_frames(doc)
                all_frames.extend(frames)
            except Exception as e:
                print(f"Ошибка при работе парсера {parser.__class__.__name__}: {e}")
        
        # Сортируем рамки по номеру листа (если возможно)
        def sort_key(frame):
            try:
                # Всегда возвращаем кортеж (is_string, value), чтобы float и str не сравнивались напрямую
                return (0, float(frame.sheet_number))
            except ValueError:
                return (1, frame.sheet_number)
                
        all_frames.sort(key=sort_key)
        return all_frames
