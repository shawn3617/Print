import os
import win32com.client

class BatchPrinter:
    def __init__(self, doc):
        self.doc = doc

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

    def print_frames(self, frames, printer_name: str, canonical_media_name: str, style_name: str, output_path: str, merge_pdf: bool = False):
        """
        Отправляет выбранные рамки на печать в PDF.
        canonical_media_name используется как фолбэк, если не удалось подобрать формат.
        """
        import time
        import tempfile
        import shutil
        
        layout = self.doc.ModelSpace.Layout
        
        # Базовые настройки
        layout.ConfigName = printer_name
        layout.StyleSheet = style_name
        
        # Строим словарь {формат -> canonical_name} из доступных форматов принтера
        media_map = self._build_media_map(printer_name)
        
        # Включаем печать толщин линий и стилей
        layout.PlotWithPlotStyles = True
        layout.PlotWithLineweights = True
        
        # Отключаем фоновую печать
        try:
            original_bg_plot = self.doc.GetVariable("BACKGROUNDPLOT")
            self.doc.SetVariable("BACKGROUNDPLOT", 0)
        except:
            original_bg_plot = 0
        
        # Создаем временную папку для temp-файлов (если режим merge)
        temp_dir = None
        if merge_pdf:
            temp_dir = tempfile.mkdtemp(prefix="acad_print_")
            
        temp_files = []
        
        try:
            for frame in frames:
                # Автоподбор формата бумаги по формату рамки
                media_name = media_map.get(frame.paper_format, canonical_media_name)
                layout.CanonicalMediaName = media_name
                
                # Подбор ориентации листа
                is_paper_landscape = False
                try:
                    local_name = layout.GetLocaleMediaName(media_name)
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
                    layout.PlotRotation = 1 # ac90degrees
                else:
                    layout.PlotRotation = 0 # ac0degrees
                
                p1 = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                    (frame.min_point[0], frame.min_point[1])
                )
                p2 = win32com.client.VARIANT(
                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                    (frame.max_point[0], frame.max_point[1])
                )
                layout.SetWindowToPlot(p1, p2)
                layout.PlotType = 4
                layout.StandardScale = 0
                layout.CenterPlot = True
                
                safe_name = "".join([c for c in frame.sheet_name if c.isalpha() or c.isdigit() or c in ' -_']).strip()
                if not safe_name:
                    safe_name = "Без_Имени"
                    
                filename = f"Лист {frame.sheet_number} - {safe_name}.pdf"
                
                if merge_pdf:
                    filepath = os.path.join(temp_dir, filename)
                    temp_files.append(filepath)
                else:
                    filepath = os.path.abspath(os.path.join(output_path, filename))
                
                self.doc.Plot.PlotToFile(filepath, printer_name)
                
            # Объединяем файлы, если нужно
            if merge_pdf and temp_files:
                from pypdf import PdfWriter
                
                # Ждём, пока AutoCAD запишет все файлы на диск
                for pdf_file in temp_files:
                    for _ in range(30):  # до 15 секунд
                        if os.path.exists(pdf_file) and os.path.getsize(pdf_file) > 0:
                            break
                        time.sleep(0.5)
                
                # Небольшая пауза для гарантии
                time.sleep(1)
                
                merger = PdfWriter()
                for pdf_file in temp_files:
                    merger.append(pdf_file)
                    
                merger.write(output_path)
                merger.close()
                
        finally:
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
