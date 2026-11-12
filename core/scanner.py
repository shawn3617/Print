from typing import List
from core.models import Frame, natural_sheet_sort_key, frame_natural_sort_key
from core.logger import log_info, log_warn, log_error
from core.report_models import ScanReport, ScanFileResult
from core.autocad_state import AutoCADStateGuard
from parsers.block_parser import BlockParser

from parsers.spds_parser import SPDSParser
from parsers.polyline_parser import PolylineParser

FRAME_TYPE_SPDS = "spds"
FRAME_TYPE_ALL_BLOCKS = "all_blocks"
FRAME_TYPE_CUSTOM_BLOCK = "custom_block"
FRAME_TYPE_POLYLINE = "polyline"
FRAME_TYPE_ALL = "all"


class DocumentScanner:
    """
    Агрегатор, который запускает выбранные парсеры и собирает рамки со всего чертежа.
    """
    def __init__(self):
        # Настраиваем парсеры по умолчанию
        self.parsers = [
            SPDSParser(),
            BlockParser(),
            PolylineParser(target_layer="0000_Формат")
        ]
        self.last_scan_report = None

    def get_parsers_for_mode(self, frame_type: str = "all", custom_block_name: str = "") -> list:
        """Возвращает список парсеров, соответствующих выбранному режиму поиска рамок."""
        if frame_type == FRAME_TYPE_SPDS:
            return [SPDSParser()]
        elif frame_type == FRAME_TYPE_ALL_BLOCKS:
            return [BlockParser()]
        elif frame_type == FRAME_TYPE_CUSTOM_BLOCK:
            if custom_block_name and custom_block_name.strip():
                raw_names = [n.strip() for n in custom_block_name.replace(";", ",").split(",") if n.strip()]
                masks = []
                for n in raw_names:
                    masks.append(n)
                    if "*" not in n and "?" not in n:
                        masks.append(f"*{n}*")
                return [BlockParser(block_names=masks)]
            else:
                return [BlockParser()]
        elif frame_type == FRAME_TYPE_POLYLINE:
            return [PolylineParser(target_layer="0000_Формат")]
        else:  # FRAME_TYPE_ALL или по умолчанию
            return [
                SPDSParser(),
                BlockParser(),
                PolylineParser(target_layer="0000_Формат")
            ]

    def scan_document(self, doc, frame_type: str = "all", custom_block_name: str = "", space: str = "model") -> List[Frame]:
        import time
        all_frames: List[Frame] = []
        active_parsers = self.get_parsers_for_mode(frame_type, custom_block_name)
        for parser in active_parsers:
            try:
                t_p0 = time.perf_counter()
                frames = parser.find_frames(doc)
                dt_p = time.perf_counter() - t_p0
                msg = f"[{parser.__class__.__name__}] завершен за {dt_p:.3f} сек (найдено {len(frames)} рамок)"
                print(msg)
                log_info(msg, module="Scanner")
                if frames:
                    all_frames.extend(frames)
            except Exception as e:
                print(f"Ошибка при работе парсера {parser.__class__.__name__}: {e}")
                log_error(f"Ошибка при работе парсера {parser.__class__.__name__}", exc=e, module="Scanner")

        # Фильтрация по пространству (Модель / Листы)
        if space == "model":
            all_frames = [f for f in all_frames if getattr(f, "layout_name", "Model").lower() == "model"]
        elif space == "layouts":
            all_frames = [f for f in all_frames if getattr(f, "layout_name", "Model").lower() != "model"]

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
        # Для пространства модели: если в чертеже преобладает определенный масштаб (например, 1:100),
        # перепроверяем форматы рамок через доминирующий масштаб проекта.
        if space == "model" and len(all_frames) > 1:
            try:
                from core.models import ALL_FORMATS, detect_paper_format
                from collections import Counter
                scales = []
                for f in all_frames:
                    if f.source_type == "Polyline" and f.is_ambiguous:
                        continue
                    fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
                    w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                    sc = round(w / fw)
                    if sc > 0:
                        scales.append(sc)
                if scales:
                    common_scale, count = Counter(scales).most_common(1)[0]
                    if count >= len(all_frames) * 0.5 and common_scale in [1, 10, 20, 25, 50, 100, 200]:
                        for f in all_frames:
                            # У каждой полилинии свои признаки масштаба. Общий масштаб DWG
                            # не должен скрывать варианты или заменять подтверждённый формат.
                            if f.source_type == "Polyline" or f.format_from_source:
                                continue
                            fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
                            w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                            h = min(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
                            curr_sc = round(w / fw) if fw > 0 else 1
                            if curr_sc != common_scale:
                                corrected_fmt = detect_paper_format(w, h, scale=common_scale)
                                if corrected_fmt in ALL_FORMATS:
                                    cfw, cfh = ALL_FORMATS[corrected_fmt]
                                    err_curr = abs(w - fw * curr_sc) + abs(h - fh * curr_sc)
                                    err_corr = abs(w - cfw * common_scale) + abs(h - cfh * common_scale)
                                    # Меняем только если формат при доминирующем масштабе садится не хуже текущего
                                    if err_corr <= err_curr + 1.0:
                                        f.paper_format = corrected_fmt
                                        f.scale = common_scale
                                        f.format_reason = f"Доминирующий масштаб проекта 1:{common_scale}"
                                        f.is_ambiguous = False
                            elif getattr(f, "scale", 1) == common_scale and getattr(f, "is_ambiguous", False):
                                f.format_reason = f"Подтверждено проектом (М1:{common_scale})"
                                f.is_ambiguous = False
            except Exception as e:
                print(f"Ошибка при согласовании масштабов: {e}")
                log_warn("Ошибка при согласовании масштабов", exc=e, module="Scanner")

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



    def scan_layouts(self, doc, frame_type: str = "all", custom_block_name: str = "") -> List[Frame]:
        """
        Сканирует вкладки пространства листа (Layouts), исключая пространство модели (Model).
        Приоритетно выполняет поиск блоков рамок (и СПДС) в пространстве листа (Paper Space).
        Если на конкретной вкладке Layout найдены блоки рамок, извлекает их атрибуты
        (номер, наименование, шифр, формат).
        Если на вкладке блоков рамок нет, создает резервную рамку на базе параметров самой вкладки.
        Возвращает список Frame, упорядоченный по визуальному порядку вкладок (TabOrder).
        """
        import re
        from core.models import detect_format_from_media_name
        
        doc_path = ""
        doc_name = ""
        try:
            doc_path = getattr(doc, "FullName", "") or ""
            doc_name = getattr(doc, "Name", "") or ""
        except Exception:
            pass

        # 1. Собираем все вкладки Layout (исключая Model)
        layouts_info = []
        try:
            layouts = doc.Layouts
            for i in range(layouts.Count):
                layout = layouts.Item(i)
                if getattr(layout, "ModelType", False) or layout.Name.lower() == "model":
                    continue
                tab_order = getattr(layout, "TabOrder", i)
                layouts_info.append((tab_order, layout.Name, layout))
        except Exception as e:
            print(f"Ошибка при получении списка Layouts: {e}")
            log_error("Ошибка при получении списка Layouts", exc=e, module="Scanner")

        layouts_info.sort(key=lambda x: x[0])

        # 2. Ищем рамки-блоки и СПДС на листах через активные парсеры
        frames_by_layout = {}
        if frame_type != FRAME_TYPE_POLYLINE:
            active_parsers = self.get_parsers_for_mode(frame_type, custom_block_name)
            paper_parsers = [p for p in active_parsers if not isinstance(p, PolylineParser)]
            for parser in paper_parsers:
                try:
                    frames = parser.find_frames(doc)
                    if frames:
                        for f in frames:
                            lyt_n = getattr(f, "layout_name", "Model")
                            if lyt_n.lower() != "model":
                                frames_by_layout.setdefault(lyt_n.lower(), []).append(f)
                except Exception as e:
                    print(f"Предупреждение: ошибка поиска рамок на листах в {parser.__class__.__name__}: {e}")
                    log_warn(f"Ошибка поиска рамок на листах в {parser.__class__.__name__}", exc=e, module="Scanner")

        # Дедупликация рамок на каждом листе (если SPDS и Block зацепили один объект)
        for lyt_k in frames_by_layout:
            lyt_frames = frames_by_layout[lyt_k]
            if len(lyt_frames) > 1:
                uniq = []
                for f in lyt_frames:
                    dup = False
                    for u in uniq:
                        if (abs(f.min_point[0] - u.min_point[0]) < 10.0 and
                            abs(f.min_point[1] - u.min_point[1]) < 10.0 and
                            abs(f.max_point[0] - u.max_point[0]) < 10.0 and
                            abs(f.max_point[1] - u.max_point[1]) < 10.0):
                            dup = True
                            break
                    if not dup:
                        uniq.append(f)
                frames_by_layout[lyt_k] = uniq

        # 3. Сопоставляем вкладки и рамки
        result_frames = []
        handled_layout_keys = set()

        for tab_order, lyt_name, lyt_obj in layouts_info:
            lyt_key = lyt_name.lower()
            handled_layout_keys.add(lyt_key)
            blks = frames_by_layout.get(lyt_key, [])
            if blks:
                # На этой вкладке есть блоки рамок
                for blk in blks:
                    if not blk.layout_name:
                        blk.layout_name = lyt_name
                    if not blk.sheet_name or blk.sheet_name.lower() == "unknown":
                        blk.sheet_name = lyt_name
                    if not blk.sheet_number or blk.sheet_number.lower() == "unknown":
                        num_match = re.search(r'\d+', lyt_name)
                        blk.sheet_number = num_match.group(0) if num_match else str(tab_order)
                    if not blk.dwg_path and doc_path:
                        blk.dwg_path = doc_path
                    if not blk.dwg_name and doc_name:
                        blk.dwg_name = doc_name
                    result_frames.append(blk)
            else:
                # Резервный лист Layout целиком
                raw_media = getattr(lyt_obj, "CanonicalMediaName", "")
                media_name = str(raw_media) if isinstance(raw_media, str) else ""
                raw_handle = getattr(lyt_obj, "Handle", "")
                handle = str(raw_handle) if isinstance(raw_handle, str) else ""
                raw_id = getattr(lyt_obj, "ObjectID", 0)
                obj_id = raw_id if isinstance(raw_id, int) else 0
                paper_fmt = detect_format_from_media_name(media_name)
                num_match = re.search(r'\d+', lyt_name)
                sheet_num = num_match.group(0) if num_match else str(tab_order)

                fallback_frame = Frame(
                    object_id=obj_id,
                    sheet_number=sheet_num,
                    sheet_name=lyt_name,
                    min_point=(0.0, 0.0, 0.0),
                    max_point=(0.0, 0.0, 0.0),
                    source_type="Layout",
                    paper_format=paper_fmt,
                    handle=handle,
                    dwg_path=doc_path,
                    dwg_name=doc_name,
                    layout_name=lyt_name
                )
                result_frames.append(fallback_frame)

        # 4. Если нашлись блоки на листах, не вошедших в doc.Layouts (редкий случай)
        for lyt_k, blks in frames_by_layout.items():
            if lyt_k not in handled_layout_keys:
                for blk in blks:
                    if not blk.dwg_path and doc_path:
                        blk.dwg_path = doc_path
                    if not blk.dwg_name and doc_name:
                        blk.dwg_name = doc_name
                    result_frames.append(blk)

        return result_frames

    def scan_files(
        self,
        connector,
        file_paths: List[str],
        source_mode: str = "Модель",
        frame_type: str = "all",
        custom_block_name: str = "",
        progress_callback=None,
        is_cancelled=None
    ) -> List[Frame]:
        """
        Пакетное сканирование нескольких DWG-файлов.
        Для каждого файла открывает чертеж в AutoCAD (если не открыт),
        извлекает рамки или листы, и закрывает чертеж, если он был открыт процедурой.
        
        progress_callback: callable(current_file_idx, total_files, file_name, status_text)
        is_cancelled: callable() -> bool
        """
        import os
        import time
        
        t_start = time.perf_counter()
        scan_report = ScanReport(total_files=len(file_paths) if file_paths else 0)
        self.last_scan_report = scan_report

        all_frames: List[Frame] = []
        if not file_paths:
            scan_report.duration_seconds = time.perf_counter() - t_start
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

        state_guard = AutoCADStateGuard(connector=connector, doc=initial_doc, target_bg_plot=None)
        state_guard.__enter__()

        try:
            for idx, fpath in enumerate(file_paths):
                if is_cancelled and is_cancelled():
                    scan_report.cancelled = True
                    break
                    
                abs_path = os.path.abspath(fpath)
                fname = os.path.basename(abs_path)
                
                if progress_callback:
                    progress_callback(idx, total_files, fname, f"Открытие чертежа {idx + 1} из {total_files}: {fname}...")
                    
                doc = None
                was_opened = False
                file_success = False
                file_error = ""
                file_frames_count = 0
                try:
                    doc, was_opened = connector.open_document(abs_path, read_only=True)
                    state_guard.register_doc(doc)
                    
                    if progress_callback:
                        status_act = "Поиск листов (Layouts)" if is_layouts else "Поиск рамок чертежа"
                        progress_callback(idx, total_files, fname, f"{status_act} ({idx + 1}/{total_files}): {fname}...")
                        
                    if is_layouts:
                        doc_frames = self.scan_layouts(doc, frame_type=frame_type, custom_block_name=custom_block_name)
                    else:
                        doc_frames = self.scan_document(doc, frame_type=frame_type, custom_block_name=custom_block_name, space="model")
                        
                    for fr in doc_frames:
                        if not fr.dwg_path:
                            fr.dwg_path = abs_path
                        if not fr.dwg_name:
                            fr.dwg_name = fname
                            
                    all_frames.extend(doc_frames)
                    file_success = True
                    file_frames_count = len(doc_frames)
                    
                except Exception as e:
                    file_error = str(e)
                    print(f"Ошибка при обработке файла '{abs_path}': {e}")
                    log_error(f"Ошибка при обработке файла '{abs_path}'", exc=e, module="Scanner")
                finally:
                    if file_success:
                        scan_report.file_results.append(ScanFileResult(
                            file_path=abs_path,
                            file_name=fname,
                            success=True,
                            frames_count=file_frames_count
                        ))
                        scan_report.success_files_count += 1
                        if file_frames_count == 0:
                            scan_report.empty_files_count += 1
                    else:
                        scan_report.file_results.append(ScanFileResult(
                            file_path=abs_path,
                            file_name=fname,
                            success=False,
                            error=file_error,
                            frames_count=0
                        ))
                        scan_report.failed_files_count += 1

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
        finally:
            try:
                state_guard.restore()
            except Exception as e:
                log_warn("Ошибка при восстановлении состояния AutoCAD после сканирования", exc=e, module="Scanner")
                
        # Сквозная сортировка всех рамок по номеру листа (для модели)
        if not is_layouts:
            all_frames.sort(key=frame_natural_sort_key)

        scan_report.total_frames_found = len(all_frames)
        scan_report.duration_seconds = time.perf_counter() - t_start
        return all_frames



