from typing import List
from core.models import Frame, natural_sheet_sort_key, frame_natural_sort_key
from parsers.block_parser import BlockParser

from parsers.spds_parser import SPDSParser
from parsers.polyline_parser import PolylineParser

class DocumentScanner:
    """
    Агрегатор, который запускает все парсеры и собирает рамки со всего чертежа.
    """
    def __init__(self):
        # Настраиваем парсеры: быстрый LISP-парсер СПДС первым
        self.parsers = [
            SPDSParser(),
            BlockParser(block_names=["SHT_*", "Формат*"], sheet_attr_tags=["SHEET", "ЛИСТ"]),
            PolylineParser(target_layer="0000_Формат")
        ]

    def scan_document(self, doc) -> List[Frame]:
        import time
        all_frames: List[Frame] = []
        for parser in self.parsers:
            try:
                t_p0 = time.perf_counter()
                frames = parser.find_frames(doc)
                dt_p = time.perf_counter() - t_p0
                print(f"[{parser.__class__.__name__}] завершен за {dt_p:.3f} сек (найдено {len(frames)} рамок)")
                if frames:
                    all_frames.extend(frames)
            except Exception as e:
                print(f"Ошибка при работе парсера {parser.__class__.__name__}: {e}")

        # Дедупликация рамок при совпадении координат (если несколько парсеров зацепили одну область)
        if all_frames:
            unique_frames = []
            for f in all_frames:
                dup = False
                for u in unique_frames:
                    if (abs(f.min_point[0] - u.min_point[0]) < 100.0 and
                        abs(f.min_point[1] - u.min_point[1]) < 100.0 and
                        abs(f.max_point[0] - u.max_point[0]) < 100.0 and
                        abs(f.max_point[1] - u.max_point[1]) < 100.0):
                        dup = True
                        break
                if not dup:
                    unique_frames.append(f)
            all_frames = unique_frames
        
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

        # Заполняем информацию о чертеже (dwg_path, dwg_name)
        doc_path = ""
        doc_name = ""
        try:
            doc_path = getattr(doc, "FullName", "") or ""
            doc_name = getattr(doc, "Name", "") or ""
        except Exception:
            pass

        for f in all_frames:
            if not f.dwg_path and doc_path:
                f.dwg_path = doc_path
            if not f.dwg_name and doc_name:
                f.dwg_name = doc_name

        # Сортируем рамки по номеру листа с естественной сортировкой (4, 4а, 4.1, 5...)
        all_frames.sort(key=frame_natural_sort_key)
        return all_frames



    def scan_layouts(self, doc) -> List[Frame]:
        """
        Сканирует вкладки пространства листа (Layouts), исключая пространство модели (Model).
        Возвращает список Frame для каждой вкладки, упорядоченный по визуальному порядку вкладок (TabOrder).
        """
        import re
        from core.models import detect_format_from_media_name
        
        layout_frames = []
        doc_path = ""
        doc_name = ""
        try:
            doc_path = getattr(doc, "FullName", "") or ""
            doc_name = getattr(doc, "Name", "") or ""
        except Exception:
            pass

        try:
            layouts = doc.Layouts
            for i in range(layouts.Count):
                layout = layouts.Item(i)
                # Пропускаем пространство модели
                if getattr(layout, "ModelType", False) or layout.Name.lower() == "model":
                    continue
                    
                tab_order = getattr(layout, "TabOrder", i)
                name = layout.Name
                media_name = getattr(layout, "CanonicalMediaName", "")
                handle = getattr(layout, "Handle", "")
                obj_id = getattr(layout, "ObjectID", 0)
                
                # Определение формата бумаги по настройкам листа
                paper_fmt = detect_format_from_media_name(media_name)
                
                # Номер листа: извлекаем число из названия вкладки, иначе tab_order
                num_match = re.search(r'\d+', name)
                sheet_num = num_match.group(0) if num_match else str(tab_order)
                
                frame = Frame(
                    object_id=obj_id,
                    sheet_number=sheet_num,
                    sheet_name=name,
                    min_point=(0.0, 0.0, 0.0),
                    max_point=(0.0, 0.0, 0.0),
                    source_type="Layout",
                    paper_format=paper_fmt,
                    handle=handle,
                    dwg_path=doc_path,
                    dwg_name=doc_name
                )
                layout_frames.append((tab_order, frame))

                
        except Exception as e:
            print(f"Ошибка при сканировании Layouts: {e}")
            
        # Сортируем строго по TabOrder (порядок вкладок в интерфейсе AutoCAD)
        layout_frames.sort(key=lambda x: x[0])
        return [item[1] for item in layout_frames]

    def scan_files(self, connector, file_paths: List[str], source_mode: str = "Модель", progress_callback=None, is_cancelled=None) -> List[Frame]:
        """
        Пакетное сканирование нескольких DWG-файлов.
        Для каждого файла открывает чертеж в AutoCAD (если не открыт),
        извлекает рамки или листы, и закрывает чертеж, если он был открыт процедурой.
        
        progress_callback: callable(current_file_idx, total_files, file_name, status_text)
        is_cancelled: callable() -> bool
        """
        import os
        
        all_frames: List[Frame] = []
        if not file_paths:
            return all_frames
            
        # Запоминаем исходно открытые чертежи, чтобы случайно не закрыть файлы пользователя
        initially_open_files = set()
        try:
            for full_path, _ in connector.get_open_documents():
                if full_path:
                    initially_open_files.add(os.path.abspath(full_path).lower())
        except Exception:
            pass
            
        initial_doc = getattr(connector, "doc", None)
        total_files = len(file_paths)
        is_layouts = "layout" in source_mode.lower() or "лист" in source_mode.lower()

        for idx, fpath in enumerate(file_paths):
            if is_cancelled and is_cancelled():
                break
                
            abs_path = os.path.abspath(fpath)
            fname = os.path.basename(abs_path)
            
            if progress_callback:
                progress_callback(idx, total_files, fname, f"Открытие чертежа {idx + 1} из {total_files}: {fname}...")
                
            doc = None
            was_opened = False
            try:
                doc, was_opened = connector.open_document(abs_path, read_only=True)
                
                if progress_callback:
                    status_act = "Поиск листов (Layouts)" if is_layouts else "Поиск рамок чертежа"
                    progress_callback(idx, total_files, fname, f"{status_act} ({idx + 1}/{total_files}): {fname}...")
                    
                if is_layouts:
                    doc_frames = self.scan_layouts(doc)
                else:
                    doc_frames = self.scan_document(doc)
                    
                for fr in doc_frames:
                    if not fr.dwg_path:
                        fr.dwg_path = abs_path
                    if not fr.dwg_name:
                        fr.dwg_name = fname
                        
                all_frames.extend(doc_frames)
                
            except Exception as e:
                print(f"Ошибка при обработке файла '{abs_path}': {e}")
            finally:
                # Закрываем чертеж только если мы его сами открыли и его изначально не было в AutoCAD
                if doc and was_opened and abs_path.lower() not in initially_open_files:
                    try:
                        connector.close_document(doc, save_changes=False)
                        import time
                        time.sleep(0.3)
                    except Exception:
                        pass
                        
        if progress_callback:
            progress_callback(total_files, total_files, "", "Сканирование завершено!")
            
        # По возможности возвращаем исходный активный документ
        if initial_doc:
            try:
                connector.activate_document(initial_doc)
            except Exception:
                pass
                
        # Сквозная сортировка всех рамок по номеру листа
        all_frames.sort(key=frame_natural_sort_key)
        return all_frames



