import time
import fnmatch
from typing import List, Any
from core.models import Frame, detect_paper_format
from parsers.base_parser import BaseParser


from core.resource_utils import get_resource_path


class BlockParser(BaseParser):
    def __init__(self, block_names: List[str] = None, sheet_attr_tags: List[str] = None, title_attr_tags: List[str] = None):
        """
        :param block_names: Список имен блоков или масок (например, ["SHT_*", "Формат*"])
        :param sheet_attr_tags: Список тегов атрибутов, в которых хранится номер листа
        :param title_attr_tags: Список тегов атрибутов названия листа
        """
        self.block_names = [name.lower() for name in (block_names or ["SHT_*", "Формат*"])]
        self.sheet_attr_tags = [tag.upper() for tag in (sheet_attr_tags or ["SHEET", "ЛИСТ", "НОМЕР", "НОМЕР_ЛИСТА", "SH_NUM"])]
        self.title_attr_tags = [tag.upper() for tag in (title_attr_tags or ["TITLE", "НАИМЕНОВАНИЕ", "НАЗВАНИЕ", "НАИМЕНОВАНИЕ_ЛИСТА", "SHEET_NAME"])]

        # Путь к LISP-экстрактору рамок-блоков
        self.lisp_path = get_resource_path("core/lisp/block_export.lsp")

    def _convert_items_to_frames(self, items: list) -> List[Frame]:
        frames = []
        for item in items:
            hdl = item.get("handle", "")
            b_name = item.get("block_name", "")
            num = item.get("sheet_number", "Unknown")
            name = item.get("sheet_name", "Unknown")
            sc = float(item.get("scale", 1.0))
            min_x = float(item.get("min_x", 0.0))
            min_y = float(item.get("min_y", 0.0))
            max_x = float(item.get("max_x", 0.0))
            max_y = float(item.get("max_y", 0.0))

            w = max_x - min_x
            h = max_y - min_y

            fmt = detect_paper_format(w, h, b_name, scale=sc)

            frame = Frame(
                object_id=0,
                sheet_number=num,
                sheet_name=name.replace("\r", " ").replace("\n", " ").strip(),
                min_point=(min_x, min_y, 0.0),
                max_point=(max_x, max_y, 0.0),
                source_type="Block",
                paper_format=fmt,
                handle=hdl
            )
            frames.append(frame)
        return frames

    def _has_block_definitions(self, doc: Any) -> bool:
        """Быстрая проверка таблицы определений блоков (занимает 0.002 сек)"""
        try:
            blocks = doc.Blocks
            for b_idx in range(blocks.Count):
                b_name = getattr(blocks.Item(b_idx), 'Name', '').lower()
                for pattern in self.block_names:
                    if fnmatch.fnmatch(b_name, pattern):
                        return True
            return False
        except Exception:
            return True

    def _find_frames_via_lisp(self, doc: Any) -> List[Frame]:
        t_start = time.perf_counter()
        data = self._run_lisp_export(
            doc, self.lisp_path, "sht-export-blocks",
            [",".join(self.block_names), ",".join(self.sheet_attr_tags), ",".join(self.title_attr_tags)],
            prefix="acad_blocks")
        frames = self._convert_items_to_frames(data)
        print(f"[BlockParser] LISP экспорт выполнен за {time.perf_counter() - t_start:.3f} сек "
              f"(найдено {len(frames)} рамок)")
        return frames

    def _find_frames_fallback_com(self, doc: Any) -> List[Frame]:
        frames = []
        try:
            model_space = doc.ModelSpace
        except Exception:
            return frames

        for i in range(model_space.Count):
            try:
                obj = model_space.Item(i)
                if getattr(obj, 'EntityName', '') == 'AcDbBlockReference':
                    block_name = ""
                    try:
                        block_name = obj.EffectiveName
                    except Exception:
                        try:
                            block_name = obj.Name
                        except Exception:
                            pass

                    matched = False
                    for pattern in self.block_names:
                        if fnmatch.fnmatch(block_name.lower(), pattern):
                            matched = True
                            break

                    if matched:
                        min_pt, max_pt = obj.GetBoundingBox()
                        sheet_number = "Unknown"
                        sheet_name = "Unknown"
                        if obj.HasAttributes:
                            for attr in obj.GetAttributes():
                                tag = attr.TagString.upper()
                                if tag in self.sheet_attr_tags:
                                    sheet_number = attr.TextString
                                elif tag in self.title_attr_tags or tag == "TITLE":
                                    sheet_name = attr.TextString

                        w = max_pt[0] - min_pt[0]
                        h = max_pt[1] - min_pt[1]
                        blk_scale = getattr(obj, 'XScaleFactor', None)
                        frame = Frame(
                            object_id=getattr(obj, 'ObjectID', 0),
                            sheet_number=sheet_number,
                            sheet_name=sheet_name,
                            min_point=min_pt,
                            max_point=max_pt,
                            source_type="Block",
                            paper_format=detect_paper_format(w, h, block_name, scale=blk_scale),
                            handle=getattr(obj, 'Handle', '')
                        )
                        frames.append(frame)
            except Exception:
                continue

        return frames

    def find_frames(self, doc: Any) -> List[Frame]:
        # 1. Быстрая проверка наличия определений блоков в таблице Blocks (0.001 сек)
        if not self._has_block_definitions(doc):
            return []

        # 2. Быстрый экспорт через LISP-мост
        try:
            return self._find_frames_via_lisp(doc)
        except Exception as e:
            print(f"Предупреждение: LISP поиск блоков не сработал ({e}), запуск резервного метода...")
            return self._find_frames_fallback_com(doc)
