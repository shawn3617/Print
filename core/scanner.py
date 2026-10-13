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
        
        # Согласование масштабов рамок чертежа:
        # Если в чертеже преобладает определенный масштаб (например, 1:100),
        # перепроверяем форматы рамок через доминирующий масштаб проекта.
        if len(all_frames) > 1:
            try:
                from core.models import ALL_FORMATS, detect_paper_format
                from collections import Counter
                scales = []
                for f in all_frames:
                    fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
                    w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                    sc = round(w / fw)
                    if sc > 0:
                        scales.append(sc)
                if scales:
                    common_scale, count = Counter(scales).most_common(1)[0]
                    if count >= len(all_frames) * 0.5 and common_scale in [1, 10, 20, 25, 50, 100, 200]:
                        for f in all_frames:
                            fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
                            w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                            h = min(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                            if round(w / fw) != common_scale:
                                corrected_fmt = detect_paper_format(w, h, scale=common_scale)
                                if corrected_fmt in ALL_FORMATS:
                                    f.paper_format = corrected_fmt
            except Exception as e:
                print(f"Ошибка при согласовании масштабов: {e}")

        # Сортируем рамки по номеру листа (если возможно)
        def sort_key(frame):
            try:
                # Всегда возвращаем кортеж (is_string, value), чтобы float и str не сравнивались напрямую
                return (0, float(frame.sheet_number))
            except ValueError:
                return (1, frame.sheet_number)
                
        all_frames.sort(key=sort_key)
        return all_frames
