import os
import logging
import win32com.client
import pythoncom

logging.getLogger("pypdf").setLevel(logging.ERROR)

class PrintCancelledError(Exception):
    """Исключение, возникающее при отмене печати пользователем."""
    pass


from core.com_utils import com_retry
# Повтор, когда AutoCAD занят. В exe занятость AutoCAD проявляется как AttributeError
# вида "Item.ModelSpace" / "Open.ModelSpace" — обычный com_retry такое не повторяет.
from core.autocad_connector import _retry_busy
from core.plotter_installer import install_bundled_plotters


class BatchPrinter:
    def __init__(self, doc, connector=None):
        self.doc = doc
        self.connector = connector
        self._plotters_checked = False

    def _ensure_plotters(self):
        """Один раз за запуск: свои плоттеры (папка plotters программы) -> в AutoCAD."""
        if self._plotters_checked:
            return
        self._plotters_checked = True
        try:
            app = self.doc.Application if self.doc is not None else None
        except Exception:
            app = None
        install_bundled_plotters(app)


    def get_printers(self):
        """Возвращает список доступных плоттеров/принтеров"""
        self._ensure_plotters()   # до обновления списка — тогда новые плоттеры сразу в нём
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

    def _apply_printer(self, layout, printer_name: str) -> str:
        """
        Назначает плоттер листу и возвращает его точное имя.
        Если такого плоттера в AutoCAD нет — понятная ошибка со списком доступных
        (вместо непонятного «Неверный ввод» от AutoCAD).
        """
        _retry_busy(layout.RefreshPlotDeviceInfo)
        try:
            names = [str(n) for n in _retry_busy(layout.GetPlotDeviceNames)]
        except Exception:
            names = []
        exact = next((n for n in names if n.lower() == printer_name.lower()), None)
        if names and exact is None:
            shown = ", ".join(n for n in names if n.lower() != "нет") [:600]
            raise RuntimeError(
                f"Плоттер «{printer_name}» не найден в AutoCAD на этом компьютере.\n"
                f"Выберите другой в списке принтеров. Доступные: {shown}")
        name = exact or printer_name
        try:
            _retry_busy(lambda: setattr(layout, "ConfigName", name))
        except pythoncom.com_error:
            # Иногда AutoCAD принимает плоттер только у активного чертежа — активируем и пробуем снова
            try:
                _retry_busy(lambda: setattr(self.doc.Application, "ActiveDocument", self.doc))
                _retry_busy(layout.RefreshPlotDeviceInfo)
                _retry_busy(lambda: setattr(layout, "ConfigName", name))
            except pythoncom.com_error as e:
                raise RuntimeError(
                    f"AutoCAD не принял плоттер «{name}» для чертежа «{getattr(self.doc, 'Name', '?')}»: "
                    f"{e.args[2][2] if len(e.args) > 2 and e.args[2] else e}")
        _retry_busy(layout.RefreshPlotDeviceInfo)
        return name

    def _build_media_map(self, printer_name: str) -> dict:
        """Строит словарь {формат (A0..A4, A3x5 и т.д.) -> canonical_media_name} для выбранного принтера."""
        import re
        from core.models import ALL_FORMATS
        
        result = {}
        try:
            layout = _retry_busy(lambda: self.doc.ModelSpace.Layout)
            self._apply_printer(layout, printer_name)
            names = layout.GetCanonicalMediaNames()
            for sys_name in names:
                local_name = layout.GetLocaleMediaName(sys_name)
                
                # Извлекаем все числа из названия формата
                nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', local_name)]
                dims = [n for n in nums if n >= 100] # Размеры бумаги всегда > 100 мм
                
                matched_fmt = None
                
                # Вариант 1: Размеры указаны прямо в имени (например, 1682 x 594 или 1485 x 420)
                if len(dims) >= 2:
                    pw, ph = max(dims[-2:]), min(dims[-2:])
                    for fmt, (fw, fh) in ALL_FORMATS.items():
                        if abs(pw - max(fw, fh)) <= 4.0 and abs(ph - min(fw, fh)) <= 4.0:
                            matched_fmt = fmt
                            break
                            
                # Вариант 2: Имя формата содержит название ГОСТ (например, "A2x4" или "A3x5")
                # Сортируем по убыванию длины имени, чтобы A2x4 находился раньше A2
                if not matched_fmt:
                    for fmt in sorted(ALL_FORMATS.keys(), key=len, reverse=True):
                        fmt_regex = re.escape(fmt).replace('A', '[AAАа]').replace('x', '[xXхХ]')
                        if re.search(r'\b' + fmt_regex + r'\b', local_name, re.IGNORECASE):
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

    def _setup_model_layout(self, printer_name: str, style_name: str) -> None:
        """Плоттер и стиль печати для пространства модели текущего чертежа."""
        ms_layout = _retry_busy(lambda: self.doc.ModelSpace.Layout)
        self._apply_printer(ms_layout, printer_name)   # без плоттера печатать нельзя — ошибка наверх

        def _do():
            ms_layout.StyleSheet = style_name
            ms_layout.PlotWithPlotStyles = True
            ms_layout.PlotWithLineweights = True
        try:
            _retry_busy(_do)
        except Exception as e:
            print(f"Предупреждение: не удалось назначить стиль печати «{style_name}»: {e}")

    @staticmethod
    def _doc_alive(doc) -> bool:
        """Документ есть и не закрыт (у закрытого COM-объекта обращение к свойству падает)."""
        if doc is None:
            return False
        try:
            doc.Name
            return True
        except Exception:
            return False

    def print_frames(self, frames, printer_name: str, canonical_media_name: str, style_name: str, output_path: str, merge_pdf: bool = False, progress_callback=None, is_cancelled=None,
                     close_opened_docs: bool = False):
        """
        Отправляет выбранные рамки на печать в PDF.
        canonical_media_name используется как фолбэк, если не удалось подобрать формат.
        progress_callback: callable(current_step, total_steps, status_text)
        is_cancelled: callable() -> bool
        close_opened_docs: закрывать ли после печати чертежи, которые программа открыла сама.
            По умолчанию False — открытые чертежи остаются в AutoCAD (как в REVERS): повторная
            печать не открывает их заново, а вкладки — наглядно, что печаталось.
        """
        import time
        import tempfile
        import shutil
        
        if not frames:
            return

        # Чертежи, уже открытые в AutoCAD до печати (их не закрываем)
        initially_open_files = set()
        if self.connector:
            try:
                for full_path, _ in self.connector.get_open_documents():
                    if full_path:
                        initially_open_files.add(os.path.abspath(full_path).lower())
            except Exception:
                pass
        # Чертежи, открытые только для печати: {путь_в_нижнем_регистре: COM-документ}.
        # COM-объекты нельзя класть в set (CDispatch не хешируется) — ключом служит путь.
        opened_docs_to_close = {}
        initial_active_doc = self.doc if self._doc_alive(self.doc) else None

        # Рамки из папки: их чертежи в AutoCAD могут быть закрыты, и активного документа нет.
        # Тогда сразу открываем DWG первой рамки — дальше всё настраивается на нём.
        if not self._doc_alive(self.doc):
            first_path = next((f.dwg_path for f in frames if getattr(f, "dwg_path", "")), "")
            if not (self.connector and first_path):
                raise RuntimeError("Нет открытого чертежа в AutoCAD и не указан файл DWG для печати.")
            target_path = os.path.abspath(first_path)
            doc, was_opened = self.connector.open_document(target_path, read_only=True)
            if not self._doc_alive(doc):
                raise RuntimeError(f"Не удалось открыть чертеж: {target_path}")
            self.connector.activate_document(doc)
            self.doc = doc
            if was_opened and target_path.lower() not in initially_open_files:
                opened_docs_to_close[target_path.lower()] = doc

        # Отключаем автооткрытие каждого листа в PDF-просмотрщике
        try:
            if self._disable_pc3_view_file(printer_name):
                self.doc.ModelSpace.Layout.RefreshPlotDeviceInfo()
        except Exception as e:
            print(f"Предупреждение: не удалось проверить PC3 настройки: {e}")
        
        self._ensure_plotters()
        # Строим словарь {формат -> canonical_name} из доступных форматов принтера
        media_map = self._build_media_map(printer_name)
        
        # Если есть рамки из Model Space, предварительно настраиваем ModelSpace.Layout
        has_model_frames = any(getattr(f, "source_type", "") != "Layout" for f in frames)
        if has_model_frames:
            self._setup_model_layout(printer_name, style_name)
        
        # Отключаем фоновую печать
        try:
            original_bg_plot = self.doc.GetVariable("BACKGROUNDPLOT")
            self.doc.SetVariable("BACKGROUNDPLOT", 0)
        except:
            original_bg_plot = 0
        
        # Проверяем, содержат ли рамки несколько разных DWG
        unique_dwgs = {os.path.abspath(f.dwg_path).lower() for f in frames if getattr(f, "dwg_path", "")}
        has_multiple_dwgs = len(unique_dwgs) > 1

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
                        if not self._doc_alive(doc):
                            raise RuntimeError(f"Не удалось открыть чертеж: {target_path}")
                        self.connector.activate_document(doc)
                        self.doc = doc
                        if was_opened and target_path.lower() not in initially_open_files:
                            opened_docs_to_close[target_path.lower()] = doc
                        try:
                            _retry_busy(lambda: self.doc.SetVariable("BACKGROUNDPLOT", 0))
                        except Exception:
                            pass
                        if has_model_frames:
                            self._setup_model_layout(printer_name, style_name)

                    
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
                    _retry_busy(switch_layout_tab)
                    
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
                    _retry_busy(setup_layout_params)
                else:
                    # Окно печати по рамке в модели (повторяем целиком, если AutoCAD занят)
                    def setup_model_params():
                        cur_layout = self.doc.ModelSpace.Layout
                        # Автоподбор формата бумаги по формату рамки
                        media_name = media_map.get(frame.paper_format)
                        if not media_name:
                            # Резервный формат: у плоттера нет бумаги под формат этой рамки
                            print(f"Предупреждение: у плоттера «{printer_name}» нет бумаги для формата "
                                  f"{frame.paper_format} (лист {frame.sheet_number}) — печать на резервном "
                                  f"формате «{canonical_media_name}»")
                            media_name = canonical_media_name
                        try:
                            cur_layout.CanonicalMediaName = media_name
                        except pythoncom.com_error:
                            raise RuntimeError(
                                f"Плоттер «{printer_name}» не поддерживает формат бумаги «{media_name}» "
                                f"(лист {frame.sheet_number}, формат {frame.paper_format}). "
                                f"Проверьте выбранный формат бумаги или настройки плоттера.")
                    
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
                
                    _retry_busy(setup_model_params)

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
                _retry_busy(do_plot)
                
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
            # BACKGROUNDPLOT хранится в реестре — возвращаем, пока открыт хоть один чертеж
            try:
                self.doc.SetVariable("BACKGROUNDPLOT", original_bg_plot)
            except Exception:
                pass

            # Закрываем чертежи, открытые для печати, — только если так попросили
            for d in (opened_docs_to_close.values() if close_opened_docs else []):
                try:
                    if self.connector:
                        self.connector.close_document(d, save_changes=False)
                except Exception:
                    pass

            # Дальше работаем с исходным чертежом: self.doc мог указывать на уже закрытый.
            # Исходного не было (печать из папки) — берём тот, что сейчас активен в AutoCAD (или None)
            if initial_active_doc is not None:
                self.doc = initial_active_doc
            else:
                try:
                    self.doc = self.connector.app.ActiveDocument if self.connector else None
                except Exception:
                    self.doc = None

            # Возвращаем исходный активный Layout, если он был изменен
            if original_active_layout_name and initial_active_doc is not None:
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

            # Удаляем всю временную папку целиком
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except:
                    pass

