import os
import logging
import win32com.client

logging.getLogger("pypdf").setLevel(logging.ERROR)

class PrintCancelledError(Exception):
    """Исключение, возникающее при отмене печати пользователем."""
    pass


from core.com_utils import com_retry


class BatchPrinter:
    def __init__(self, doc, connector=None):
        self.doc = doc
        self.connector = connector


    def get_printers(self):
        """Возвращает список доступных плоттеров/принтеров"""
        layout = self.doc.ModelSpace.Layout
        layout.RefreshPlotDeviceInfo()
        # Возвращаем список устройств (может потребовать преобразования из COM-кортежа)
        try:
            return list(layout.GetPlotDeviceNames())
        except:
            return ["DWG To PDF.pc3", "AutoCAD PDF (High Quality Print).pc3"]

    def get_media_names(self, printer_name: str):
        """Возвращает словарь {Локализованное_Имя: Системное_Имя} для выбранного плоттера"""
        layout = self.doc.ModelSpace.Layout
        try:
            layout.ConfigName = printer_name
            layout.RefreshPlotDeviceInfo()
            system_names = layout.GetCanonicalMediaNames()
            result = {}
            for sys_name in system_names:
                local_name = layout.GetLocaleMediaName(sys_name)
                result[local_name] = sys_name
            return result
        except:
            return {"ISO full bleed A2 (594.00 x 420.00 MM)": "ISO_full_bleed_A2_(594.00_x_420.00_MM)"}

    def get_plot_styles(self):
        """Возвращает список стилей печати (ctb/stb)"""
        layout = self.doc.ModelSpace.Layout
        try:
            return list(layout.GetPlotStyleTableNames())
        except:
            return ["monochrome.ctb", "acad.ctb"]

    def _build_media_map(self, printer_name: str) -> dict:
        """Строит словарь {формат (A0..A4, A3x5 и т.д.) -> canonical_media_name} для выбранного принтера."""
        import re
        from core.models import ALL_FORMATS
        
        result = {}
        try:
            layout = self.doc.ModelSpace.Layout
            layout.ConfigName = printer_name
            layout.RefreshPlotDeviceInfo()
            names = layout.GetCanonicalMediaNames()
            for sys_name in names:
                local_name = layout.GetLocaleMediaName(sys_name)
                
                # Извлекаем все числа из названия формата
                nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', local_name)]
                dims = [n for n in nums if n >= 100] # Размеры бумаги всегда > 100 мм
                
                matched_fmt = None
                
                # Вариант 1: Размеры указаны прямо в имени (например, 1485 x 420)
                if len(dims) >= 2:
                    pw, ph = max(dims[-2:]), min(dims[-2:])
                    for fmt, (fw, fh) in ALL_FORMATS.items():
                        if abs(pw - max(fw, fh)) < 2 and abs(ph - min(fw, fh)) < 2:
                            matched_fmt = fmt
                            break
                            
                # Вариант 2: Имя формата просто содержит название ГОСТ (например, "A3x5")
                if not matched_fmt:
                    for fmt in ALL_FORMATS.keys():
                        # Ищем точное совпадение (например "A3x5" или "A2")
                        if re.search(r'\b' + re.escape(fmt) + r'\b', local_name, re.IGNORECASE):
                            matched_fmt = fmt
                            break
                            
                if matched_fmt:
                    # Если формат найден, сохраняем. 
                    # Но предпочитаем "full bleed" (без полей), если есть несколько вариантов
                    is_full_bleed = "full bleed" in local_name.lower() or "без полей" in local_name.lower()
                    
                    if matched_fmt not in result or is_full_bleed:
                        result[matched_fmt] = sys_name

        except Exception as e:
            print(f"Ошибка при построении media_map: {e}")
        return result

    def _disable_pc3_view_file(self, printer_name: str) -> bool:
        """
        Проверяет и отключает опцию 'View_New_File' (Просмотр результатов в программе просмотра)
        в PC3-файлах AutoCAD, чтобы при пакетной печати не открывался каждый отдельный лист.
        """
        if not printer_name.lower().endswith(".pc3"):
            return False
            
        import glob
        import struct
        import zlib
        import re
        
        search_dirs = []
        try:
            pref_path = self.doc.Application.Preferences.Files.PrinterConfigPath
            if pref_path:
                search_dirs.extend([p.strip() for p in pref_path.split(";") if p.strip()])
        except:
            pass
            
        appdata_patterns = [
            os.path.expandvars(r"%APPDATA%\Autodesk\**\Plotters"),
        ]
        for pat in appdata_patterns:
            search_dirs.extend(glob.glob(pat, recursive=True))
            
        prefix = b"PIAFILEVERSION_2.0,PC3VER1,compress\r\npmzlibcodec"
        modified_any = False
        
        pc3_paths = []
        for sdir in search_dirs:
            if not os.path.isdir(sdir):
                continue
            for f in os.listdir(sdir):
                if f.lower() == printer_name.lower() or "pdf" in f.lower():
                    if f.lower().endswith(".pc3"):
                        pc3_paths.append(os.path.join(sdir, f))
                        
        for pc3_path in set(pc3_paths):
            try:
                with open(pc3_path, "rb") as f:
                    data = f.read()
                if not data.startswith(prefix) or len(data) < 60:
                    continue
                body = data[60:]
                decomp = zlib.decompress(body)
                txt = decomp.decode("latin1")
                pattern = r'(name="View_New_File\s*\r?\n\s*value=)TRUE'
                if re.search(pattern, txt):
                    txt_new = re.sub(pattern, r'\g<1>FALSE', txt)
                    decomp_new = txt_new.encode("latin1")
                    comp_new = zlib.compress(decomp_new)
                    adler_new = zlib.adler32(comp_new)
                    hdr_new = prefix + struct.pack("<III", adler_new, len(decomp_new), len(comp_new))
                    with open(pc3_path, "wb") as f:
                        f.write(hdr_new + comp_new)
                    modified_any = True
            except Exception as e:
                print(f"Ошибка при патчинге PC3 {pc3_path}: {e}")
                
        return modified_any

    def print_frames(self, frames, printer_name: str, canonical_media_name: str, style_name: str, output_path: str, merge_pdf: bool = False, progress_callback=None, is_cancelled=None):
        """
        Отправляет выбранные рамки на печать в PDF.
        canonical_media_name используется как фолбэк, если не удалось подобрать формат.
        progress_callback: callable(current_step, total_steps, status_text)
        is_cancelled: callable() -> bool
        """
        import time
        import tempfile
        import shutil
        
        if not frames:
            return
            
        layout = self.doc.ModelSpace.Layout
        
        # Отключаем автооткрытие каждого листа в PDF-просмотрщике
        try:
            if self._disable_pc3_view_file(printer_name):
                self.doc.ModelSpace.Layout.RefreshPlotDeviceInfo()
        except Exception as e:
            print(f"Предупреждение: не удалось проверить PC3 настройки: {e}")
        
        # Строим словарь {формат -> canonical_name} из доступных форматов принтера
        media_map = self._build_media_map(printer_name)
        
        # Если есть рамки из Model Space, предварительно настраиваем ModelSpace.Layout
        has_model_frames = any(getattr(f, "source_type", "") != "Layout" for f in frames)
        if has_model_frames:
            try:
                ms_layout = self.doc.ModelSpace.Layout
                ms_layout.ConfigName = printer_name
                ms_layout.StyleSheet = style_name
                ms_layout.PlotWithPlotStyles = True
                ms_layout.PlotWithLineweights = True
            except Exception as e:
                print(f"Предупреждение: не удалось настроить ModelSpace: {e}")
        
        # Отключаем фоновую печать
        try:
            original_bg_plot = self.doc.GetVariable("BACKGROUNDPLOT")
            self.doc.SetVariable("BACKGROUNDPLOT", 0)
        except:
            original_bg_plot = 0
        
        # Проверяем, содержат ли рамки несколько разных DWG
        unique_dwgs = {os.path.abspath(f.dwg_path).lower() for f in frames if getattr(f, "dwg_path", "")}
        has_multiple_dwgs = len(unique_dwgs) > 1

        initially_open_files = set()
        if self.connector:
            try:
                for full_path, _ in self.connector.get_open_documents():
                    if full_path:
                        initially_open_files.add(os.path.abspath(full_path).lower())
            except Exception:
                pass
        opened_docs_to_close = set()
        initial_active_doc = self.doc

        # Создаем временную папку для temp-файлов (если режим merge)
        temp_dir = None
        if merge_pdf:
            temp_dir = tempfile.mkdtemp(prefix="acad_print_")
            
        temp_files = []
        total_steps = len(frames) + (1 if merge_pdf else 0)
        original_active_layout_name = None
        try:
            original_active_layout_name = self.doc.ActiveLayout.Name
        except Exception:
            pass
        
        try:
            for i, frame in enumerate(frames):
                if is_cancelled and is_cancelled():
                    raise PrintCancelledError("Печать отменена пользователем.")
                    
                # Если рамка из другого DWG-файла, открываем/переключаем документ
                if self.connector and getattr(frame, "dwg_path", ""):
                    cur_doc_path = ""
                    try:
                        cur_doc_path = getattr(self.doc, "FullName", "") or ""
                    except Exception:
                        pass
                    target_path = os.path.abspath(frame.dwg_path)
                    if not cur_doc_path or os.path.abspath(cur_doc_path).lower() != target_path.lower():
                        doc, was_opened = self.connector.open_document(target_path, read_only=True)
                        self.connector.activate_document(doc)
                        self.doc = doc
                        if was_opened and target_path.lower() not in initially_open_files:
                            opened_docs_to_close.add(doc)
                        try:
                            self.doc.SetVariable("BACKGROUNDPLOT", 0)
                        except Exception:
                            pass
                        if has_model_frames:
                            try:
                                ms_layout = self.doc.ModelSpace.Layout
                                ms_layout.ConfigName = printer_name
                                ms_layout.StyleSheet = style_name
                                ms_layout.PlotWithPlotStyles = True
                                ms_layout.PlotWithLineweights = True
                            except Exception:
                                pass

                    
                safe_name = "".join([c for c in frame.sheet_name if c.isalpha() or c.isdigit() or c in ' -_']).strip()
                if not safe_name:
                    safe_name = "Без_Имени"
                    
                if progress_callback:
                    status = f"Печать листа {i + 1} из {len(frames)}: Лист {frame.sheet_number} ({safe_name})..."
                    progress_callback(i, total_steps, status)
                
                is_layout = getattr(frame, "source_type", "") == "Layout"
                
                if is_layout:
                    try:
                        cur_layout = self.doc.Layouts.Item(frame.sheet_name)
                    except Exception:
                        cur_layout = self.doc.ActiveLayout
                    
                    # 1. Активируем вкладку Layout с повторными попытками при занятости AutoCAD
                    def switch_layout_tab():
                        if getattr(self.doc.ActiveLayout, "Name", "") != cur_layout.Name:
                            self.doc.ActiveLayout = cur_layout
                    com_retry(switch_layout_tab)
                    
                    # Даем AutoCAD время на регенерацию Paper Space
                    time.sleep(0.4)
                    
                    # 2. Настраиваем параметры листа Layout (для acLayout масштабирование и центрирование не меняются)
                    def setup_layout_params():
                        cur_layout.ConfigName = printer_name
                        cur_layout.StyleSheet = style_name
                        cur_layout.PlotWithPlotStyles = True
                        cur_layout.PlotWithLineweights = True
                        
                        media_name = media_map.get(frame.paper_format, canonical_media_name)
                        if media_name:
                            try:
                                cur_layout.CanonicalMediaName = media_name
                            except Exception:
                                pass
                                
                        cur_layout.PlotType = 5  # acLayout
                    com_retry(setup_layout_params)
                else:
                    cur_layout = self.doc.ModelSpace.Layout
                    # Автоподбор формата бумаги по формату рамки
                    media_name = media_map.get(frame.paper_format, canonical_media_name)
                    cur_layout.CanonicalMediaName = media_name
                    
                    # Подбор ориентации листа
                    is_paper_landscape = False
                    try:
                        local_name = cur_layout.GetLocaleMediaName(media_name)
                        import re
                        nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', local_name)]
                        dims = [n for n in nums if n >= 100]
                        if len(dims) >= 2:
                            paper_w, paper_h = dims[-2], dims[-1]
                            is_paper_landscape = paper_w > paper_h
                    except:
                        pass
                    frame_w = abs(frame.max_point[0] - frame.min_point[0])
                    frame_h = abs(frame.max_point[1] - frame.min_point[1])
                    is_frame_landscape = frame_w > frame_h
                    
                    if is_frame_landscape != is_paper_landscape:
                        cur_layout.PlotRotation = 1  # ac90degrees
                    else:
                        cur_layout.PlotRotation = 0  # ac0degrees
                    
                    p1 = win32com.client.VARIANT(
                        win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                        (frame.min_point[0], frame.min_point[1])
                    )
                    p2 = win32com.client.VARIANT(
                        win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                        (frame.max_point[0], frame.max_point[1])
                    )
                    cur_layout.SetWindowToPlot(p1, p2)
                    cur_layout.PlotType = 4  # acWindow
                    cur_layout.StandardScale = 0
                    cur_layout.CenterPlot = True
                
                dwg_prefix = ""
                if has_multiple_dwgs and getattr(frame, "dwg_name", ""):
                    raw_dwg_base = os.path.splitext(frame.dwg_name)[0]
                    clean_dwg_base = "".join([c for c in raw_dwg_base if c.isalpha() or c.isdigit() or c in ' -_']).strip()
                    if clean_dwg_base:
                        dwg_prefix = f"[{clean_dwg_base}] "

                if merge_pdf:
                    filename = f"{i:04d}_{dwg_prefix}Лист {frame.sheet_number} - {safe_name}.pdf"
                    filepath = os.path.join(temp_dir, filename)
                    temp_files.append(filepath)
                else:
                    filename = f"{dwg_prefix}Лист {frame.sheet_number} - {safe_name}.pdf"
                    filepath = os.path.abspath(os.path.join(output_path, filename))
                
                # Печать листа через PlotToFile с обработкой занятости AutoCAD (RPC_E_CALL_REJECTED)
                def do_plot():
                    self.doc.Plot.PlotToFile(filepath, printer_name)
                com_retry(do_plot)
                
                if is_cancelled and is_cancelled():
                    raise PrintCancelledError("Печать отменена пользователем.")
                
            # Объединяем файлы, если нужно
            if merge_pdf and temp_files:
                if is_cancelled and is_cancelled():
                    raise PrintCancelledError("Печать отменена пользователем.")
                    
                if progress_callback:
                    progress_callback(len(frames), total_steps, "Объединение PDF-файлов...")
                    
                from pypdf import PdfWriter
                
                # Ждём, пока AutoCAD запишет все файлы на диск
                for pdf_file in temp_files:
                    for _ in range(30):  # до 15 секунд
                        if is_cancelled and is_cancelled():
                            raise PrintCancelledError("Печать отменена пользователем.")
                        if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
                            break
                        time.sleep(0.5)
                
                # Небольшая пауза для гарантии
                time.sleep(1)
                
                if is_cancelled and is_cancelled():
                    raise PrintCancelledError("Печать отменена пользователем.")
                    
                merger = PdfWriter()
                for pdf_file in temp_files:
                    merger.append(pdf_file)
                    
                try:
                    merger.write(output_path)
                except PermissionError:
                    raise PermissionError(
                        f"Не удалось записать файл '{os.path.basename(output_path)}'.\n"
                        f"Он уже открыт в программе просмотра (например, PDF-XChange).\n"
                        f"Пожалуйста, закройте вкладку с этим файлом и повторите печать."
                    )
                finally:
                    merger.close()
                    
            if progress_callback:
                progress_callback(total_steps, total_steps, "Готово!")
                
        finally:
            # Закрываем чертежи, открытые исключительно для пакетной печати
            for d in opened_docs_to_close:
                try:
                    if self.connector:
                        self.connector.close_document(d, save_changes=False)
                except Exception:
                    pass

            # Возвращаем исходный активный Layout, если он был изменен
            if original_active_layout_name:
                try:
                    self.doc.ActiveLayout = self.doc.Layouts.Item(original_active_layout_name)
                except Exception:
                    pass

            # Возвращаем исходный активный документ
            if initial_active_doc and self.connector:
                try:
                    self.connector.activate_document(initial_active_doc)
                except Exception:
                    pass

            # Возвращаем BACKGROUNDPLOT
            try:
                self.doc.SetVariable("BACKGROUNDPLOT", original_bg_plot)
            except:
                pass
            # Удаляем всю временную папку целиком
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass

