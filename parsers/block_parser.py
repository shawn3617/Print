import time
import fnmatch
from typing import List, Any
from core.models import Frame, detect_paper_format
from parsers.base_parser import BaseParser


from core.resource_utils import get_resource_path


class BlockParser(BaseParser):
    def __init__(
        self,
        block_names: List[str] = None,
        sheet_attr_tags: List[str] = None,
        title_attr_tags: List[str] = None,
        shifr_attr_tags: List[str] = None,
        object_attr_tags: List[str] = None,
        building_attr_tags: List[str] = None,
    ):
        """
        :param block_names: Список имен блоков или масок (например, ["SHT_*", "Формат*"])
        :param sheet_attr_tags: Список тегов атрибутов, в которых хранится номер листа
        :param title_attr_tags: Список тегов атрибутов названия листа
        :param shifr_attr_tags: Список тегов атрибутов шифра / обозначения (графа 1)
        :param object_attr_tags: Список тегов атрибутов наименования объекта (графа 2)
        :param building_attr_tags: Список тегов атрибутов наименования здания (графа 3)
        """
        self.block_names = [name.lower() for name in (block_names or ["SHT_*", "Формат*"])]
        self.sheet_attr_tags = [tag.upper() for tag in (sheet_attr_tags or ["SHEET", "ЛИСТ", "НОМЕР", "НОМЕР_ЛИСТА", "SH_NUM"])]
        self.title_attr_tags = [tag.upper() for tag in (title_attr_tags or ["TITLE", "НАИМЕНОВАНИЕ", "НАЗВАНИЕ", "НАИМЕНОВАНИЕ_ЛИСТА", "SHEET_NAME"])]
        self.shifr_attr_tags = [tag.upper() for tag in (shifr_attr_tags or ["SHIFR", "ШИФР", "DOC_CODE", "CODE", "DESIGNATION", "ОБОЗНАЧЕНИЕ", "ОБОЗНАЧЕНИЕ_ДОКУМЕНТА"])]
        self.object_attr_tags = [tag.upper() for tag in (object_attr_tags or ["OBJECT", "ОБЪЕКТ", "OBJECT_NAME", "НАИМЕНОВАНИЕ_ОБЪЕКТА", "COMPLEXNAME", "ПРЕДПРИЯТИЕ"])]
        self.building_attr_tags = [tag.upper() for tag in (building_attr_tags or ["BUILDING", "ЗДАНИЕ", "BUILDING_NAME", "НАИМЕНОВАНИЕ_ЗДАНИЯ", "СООРУЖЕНИЕ", "ПОЗИЦИЯ", "DRAWINGNAME1"])]

        # Путь к LISP-экстрактору рамок-блоков
        self.lisp_path = get_resource_path("core/lisp/block_export.lsp")

    @staticmethod
    def _get_attr_value(attrs: dict, tags: List[str]) -> str:
        for t in tags:
            if t in attrs and attrs[t]:
                return attrs[t]
        return ""

    @staticmethod
    def _check_is_title(sheet_num: str, sheet_name: str, block_name: str) -> tuple:
        """
        Проверяет, является ли блок титульным листом.
        Возвращает (sheet_number, sheet_name).
        """
        clean_name = (sheet_name or "").replace("\r", " ").replace("\n", " ").strip()
        if clean_name.lower() == "unknown":
            clean_name = ""

        clean_num = (sheet_num or "").strip()
        if clean_num.lower() == "unknown":
            clean_num = ""

        b_lower = (block_name or "").lower().strip()
        is_title = (
            clean_name.lower() in ("титульный лист", "титул", "обложка")
            or "титул" in b_lower
            or "title" in b_lower
            or "обложк" in b_lower
            or b_lower.endswith("_t")
            or b_lower.endswith("_т")
            or "_t_" in b_lower
            or "_т_" in b_lower
        )
        if is_title:
            return "", "Титульный лист"
        return clean_num or "Unknown", clean_name

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

            attrs = {k.upper(): str(v).strip() for k, v in item.get("attrs", {}).items()}
            doc_code = self._get_attr_value(attrs, self.shifr_attr_tags)
            object_name = self._get_attr_value(attrs, self.object_attr_tags)
            building_name = self._get_attr_value(attrs, self.building_attr_tags)

            num, name = self._check_is_title(num, name, b_name)

            frame = Frame(
                object_id=0,
                sheet_number=num,
                sheet_name=name,
                min_point=(min_x, min_y, 0.0),
                max_point=(max_x, max_y, 0.0),
                source_type="Block",
                paper_format=fmt,
                handle=hdl,
                doc_code=doc_code,
                object_name=object_name,
                building_name=building_name
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
                        attrs = {}
                        if obj.HasAttributes:
                            for attr in obj.GetAttributes():
                                attrs[attr.TagString.upper()] = attr.TextString.strip()

                        sheet_number = self._get_attr_value(attrs, self.sheet_attr_tags) or "Unknown"
                        sheet_name = self._get_attr_value(attrs, self.title_attr_tags) or "Unknown"
                        doc_code = self._get_attr_value(attrs, self.shifr_attr_tags)
                        object_name = self._get_attr_value(attrs, self.object_attr_tags)
                        building_name = self._get_attr_value(attrs, self.building_attr_tags)

                        sheet_number, sheet_name = self._check_is_title(sheet_number, sheet_name, block_name)

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
                            handle=getattr(obj, 'Handle', ''),
                            doc_code=doc_code,
                            object_name=object_name,
                            building_name=building_name
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
