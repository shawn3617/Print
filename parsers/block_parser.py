import fnmatch
from typing import List, Any
from core.models import Frame, detect_paper_format
from parsers.base_parser import BaseParser

class BlockParser(BaseParser):
    def __init__(self, block_names: List[str], sheet_attr_tags: List[str] = None):
        """
        :param block_names: Список имен блоков или масок (например, ["SHT_*", "Формат А3"])
        :param sheet_attr_tags: Список тегов атрибутов, в которых хранится номер листа
        """
        self.block_names = [name.lower() for name in block_names]
        self.sheet_attr_tags = [tag.upper() for tag in (sheet_attr_tags or ["ЛИСТ"])]

    def find_frames(self, doc: Any) -> List[Frame]:
        frames = []
        model_space = doc.ModelSpace
        for i in range(model_space.Count):
            obj = model_space.Item(i)
            
            # Проверяем, является ли объект вхождением блока
            if getattr(obj, 'EntityName', '') == 'AcDbBlockReference':
                # Для динамических блоков используем EffectiveName, для обычных Name
                block_name = ""
                try:
                    block_name = obj.EffectiveName
                except Exception:
                    try:
                        block_name = obj.Name
                    except Exception:
                        pass
                        
                # Проверяем имя блока по всем переданным маскам
                matched = False
                for pattern in self.block_names:
                    if fnmatch.fnmatch(block_name.lower(), pattern):
                        matched = True
                        break
                        
                if matched:
                    try:
                        # Получаем габариты рамки
                        min_pt, max_pt = obj.GetBoundingBox()
                        
                        # Читаем атрибуты блока для поиска номера листа
                        sheet_number = "Unknown"
                        sheet_name = "Unknown"
                        if obj.HasAttributes:
                            for attr in obj.GetAttributes():
                                tag = attr.TagString.upper()
                                if tag in self.sheet_attr_tags:
                                    sheet_number = attr.TextString
                                elif tag == "TITLE":
                                    sheet_name = attr.TextString
                                    
                        w = max_pt[0] - min_pt[0]
                        h = max_pt[1] - min_pt[1]
                        frame = Frame(
                            object_id=obj.ObjectID,
                            sheet_number=sheet_number,
                            sheet_name=sheet_name,
                            min_point=min_pt,
                            max_point=max_pt,
                            source_type="Block",
                            paper_format=detect_paper_format(w, h, block_name)
                        )
                        frames.append(frame)
                    except Exception as e:
                        print(f"Ошибка при чтении блока {block_name}: {e}")
                        
        return frames
