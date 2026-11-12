import os
import logging
from typing import Optional, List, Dict, Tuple, Any
import win32com.client
import pythoncom

logging.getLogger("pypdf").setLevel(logging.ERROR)

class PrintCancelledError(Exception):
    """Исключение, возникающее при отмене печати пользователем."""
    pass


# Повтор, когда AutoCAD занят. В exe занятость AutoCAD проявляется как AttributeError
# вида "Item.ModelSpace" / "Open.ModelSpace" — старый com_retry такое не повторял.
from core.autocad_connector import _retry_busy
from core.plotter_installer import install_bundled_plotters
from core.logger import log_warn, log_error
from core.report_models import PrintReport, PrintItemResult
from core.filename_template import render_filename, resolve_duplicates, get_default_template
from core.autocad_state import AutoCADStateGuard


def _safe_file_part(text, max_len: int) -> str:
    """Часть имени PDF-файла: только буквы, цифры, пробел, «-», «_», «.»; не длиннее max_len.
    Недопустимые символы (/ \\ : * ? " < > |) и слишком длинный путь AutoCAD отклоняет при печати."""
    cleaned = "".join(c for c in str(text or "") if c.isalpha() or c.isdigit() or c in " -_.").strip()
    return cleaned[:max_len].rstrip(" .")


def _warn(what: str, e: Exception = None) -> None:
    """Не прерывает печать, но оставляет в консоли и логе причину (правило: ошибки не глотать молча)."""
    if e is not None:
        msg = f"[Печать] Предупреждение: {what}: {type(e).__name__}: {e}"
        print(msg)
        log_warn(msg, exc=e, module="Печать")
    else:
        msg = f"[Печать] Предупреждение: {what}"
        print(msg)
        log_warn(msg, module="Печать")


def format_bookmark_title(sheet_number: str, sheet_name: str, page_index: int = 0) -> str:
    """
    Формирует понятное название закладки для оглавления многостраничного PDF:
    Например: '03 — Ведомость марок' или 'Титульный лист'.
    """
    s_num = str(sheet_number or "").strip()
    s_name = str(sheet_name or "").strip()

    if s_name.lower() in ("unknown", "без имени", "нет"):
        s_name = ""

    # Если номер чисто числовой, дополняем ведущим нулём до 2 цифр (ГОСТ: 01, 02, 03...)
    if s_num.isdigit():
        formatted_num = f"{int(s_num):02d}"
    else:
        formatted_num = s_num

    if formatted_num and s_name:
        return f"{formatted_num} — {s_name}"
    elif formatted_num:
        return f"Лист {formatted_num}"
    elif s_name:
        return s_name
    else:
        return f"Лист {page_index + 1}"


def build_pdf_metadata(frames: list, doc_name: str = "") -> dict:
    """
    Собирает метаданные документа для записи в PDF:
    - /Title: наименование объекта строительства и шифр
    - /Author: обозначение документа (шифр)
    - /Subject: здание/сооружение или назначение тома
    - /Creator: версия программы PrintPDF
    - /Producer: PrintPDF
    """
    try:
        from core.version import APP_VERSION
    except Exception:
        APP_VERSION = "1.3.5.1"

    object_names = [f.object_name.strip() for f in frames if getattr(f, "object_name", None) and f.object_name.strip()]
    building_names = [f.building_name.strip() for f in frames if getattr(f, "building_name", None) and f.building_name.strip()]
    doc_codes = [f.doc_code.strip() for f in frames if getattr(f, "doc_code", None) and f.doc_code.strip()]

    obj_name = object_names[0] if object_names else ""
    bld_name = building_names[0] if building_names else ""
    doc_code = doc_codes[0] if doc_codes else ""

    title_parts = []
    if obj_name:
        title_parts.append(obj_name)
    if bld_name and bld_name != obj_name:
        title_parts.append(bld_name)
    if doc_code:
        title_parts.append(f"({doc_code})")
    elif not title_parts and doc_name:
        title_parts.append(os.path.splitext(os.path.basename(doc_name))[0])

    title = " — ".join(title_parts) if title_parts else "Комплект проектной документации"

    metadata = {
        "/Title": title,
        "/Creator": f"PrintPDF v{APP_VERSION}",
        "/Producer": f"PrintPDF v{APP_VERSION}"
    }
    if doc_code:
        metadata["/Author"] = doc_code
    if bld_name:
        metadata["/Subject"] = bld_name
    elif obj_name:
        metadata["/Subject"] = obj_name

    keywords = []
    if doc_code:
        keywords.append(doc_code)
    if obj_name:
        keywords.append(obj_name)
    if bld_name:
        keywords.append(bld_name)
    if keywords:
        metadata["/Keywords"] = ", ".join(keywords)

    return metadata


class BatchPrinter:
    def __init__(self, doc, connector=None):
        self.doc = doc
        self.connector = connector
        self._plotters_checked = False
        self.last_report = None
        self.available_paper_formats = None

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
        except Exception as e:
            _warn("не удалось получить список плоттеров из AutoCAD, показан стандартный", e)
            return ["DWG To PDF.pc3", "AutoCAD PDF (High Quality Print).pc3"]

    def get_media_names(self, printer_name: str):
        """Возвращает словарь {Локализованное_Имя: Системное_Имя} для выбранного плоттера"""
        self.available_paper_formats = None
        try:
            media_names = list(self._iter_media_names(printer_name))
            if media_names:
                self.available_paper_formats = self._map_media_names(media_names)
            return dict(media_names)
        except Exception as e:
            _warn(f"не удалось получить форматы бумаги плоттера «{printer_name}», показан запасной", e)
            return {"ISO full bleed A2 (594.00 x 420.00 MM)": "ISO_full_bleed_A2_(594.00_x_420.00_MM)"}

    def get_plot_styles(self):
        """Возвращает список стилей печати (ctb/stb)"""
        layout = self.doc.ModelSpace.Layout
        try:
            return list(layout.GetPlotStyleTableNames())
        except Exception as e:
            _warn("не удалось получить список стилей печати из AutoCAD, показан стандартный", e)
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
        """Строит соответствие форматов ГОСТ бумаге выбранного плоттера."""
        media_names = []
        try:
            media_names.extend(self._iter_media_names(printer_name))
        except Exception as e:
            print(f"Ошибка при построении media_map: {e}")
        return self._map_media_names(media_names)

    def _iter_media_names(self, printer_name: str):
        layout = _retry_busy(lambda: self.doc.ModelSpace.Layout)
        self._apply_printer(layout, printer_name)
        for sys_name in _retry_busy(layout.GetCanonicalMediaNames):
            local_name = _retry_busy(lambda: layout.GetLocaleMediaName(sys_name))
            yield local_name, sys_name

    @staticmethod
    def _map_media_names(media_names) -> dict:
        import re
        from core.models import ALL_FORMATS

        result = {}
        for local_name, sys_name in media_names:
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

        return result

    def _resolve_media_name(self, name: str, media_map: dict) -> str:
        """
        Возвращает системное (canonical) имя резервного формата для текущего плоттера.
        Принимает системное или локальное имя («ISO без полей A3 (420.00 x 297.00 мм)»).
        Пустое имя — берётся A3, затем A1 из media_map.
        """
        if not name:
            fallback = media_map.get("A3") or media_map.get("A1") or ""
            if fallback:
                print(f"[Печать] Резервный формат не задан — используется «{fallback}»")
            return fallback
        try:
            layout = _retry_busy(lambda: self.doc.ModelSpace.Layout)
            names = list(_retry_busy(layout.GetCanonicalMediaNames))
            if name in names:
                return name
            for sys_name in names:
                if _retry_busy(lambda s=sys_name: layout.GetLocaleMediaName(s)) == name:
                    return sys_name
            _warn(f"резервный формат «{name}» не найден у плоттера", LookupError(name))
        except Exception as e:
            _warn(f"не удалось проверить резервный формат «{name}»", e)
        return name

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
        except Exception as e:
            _warn("не удалось прочитать папку плоттеров из настроек AutoCAD", e)
            
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
                     close_opened_docs: bool = False, continue_on_error: bool = True,
                     filename_template: Optional[str] = None) -> PrintReport:
        """
        Отправляет выбранные рамки на печать в PDF.
        canonical_media_name используется как фолбэк, если не удалось подобрать формат.
        progress_callback: callable(current_step, total_steps, status_text)
        is_cancelled: callable() -> bool
        close_opened_docs: закрывать ли после печати чертежи, которые программа открыла сама.
            По умолчанию False — открытые чертежи остаются в AutoCAD (как в REVERS): повторная
            печать не открывает их заново, а вкладки — наглядно, что печаталось.
        continue_on_error: продолжать ли печать следующих листов при сбое одного из них.
        """
        import time
        import tempfile
        import shutil
        
        t_start = time.perf_counter()
        report = PrintReport(
            total_requested=len(frames) if frames else 0,
            output_path=output_path,
            is_merged=merge_pdf,
            printer_name=printer_name,
            style_name=style_name
        )
        self.last_report = report

        if not frames:
            report.duration_seconds = time.perf_counter() - t_start
            return report

        # Чертежи, уже открытые в AutoCAD до печати (их не закрываем)
        initially_open_files = set()
        if self.connector:
            try:
                for full_path, _ in self.connector.get_open_documents():
                    if full_path:
                        initially_open_files.add(os.path.abspath(full_path).lower())
            except Exception as e:
                _warn("не удалось получить список уже открытых чертежей", e)
        # Чертежи, открытые только для печати: {путь_в_нижнем_регистре: COM-документ}.
        # COM-объекты нельзя класть в set (CDispatch не хешируется) — ключом служит путь.
        opened_docs_to_close = {}
        initial_active_doc = self.doc if self._doc_alive(self.doc) else None

        state_guard = AutoCADStateGuard(connector=self.connector, doc=self.doc, target_bg_plot=0)
        state_guard.__enter__()

        try:
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
                state_guard.register_doc(doc)
                if was_opened and target_path.lower() not in initially_open_files:
                    opened_docs_to_close[target_path.lower()] = doc

            # Отключаем автооткрытие каждого листа в PDF-просмотрщике
            try:
                if self._disable_pc3_view_file(printer_name):
                    self.doc.ModelSpace.Layout.RefreshPlotDeviceInfo()
            except Exception as e:
                print(f"Предупреждение: не удалось проверить PC3 настройки: {e}")
            
            self._ensure_plotters()
            # Если есть рамки из Model Space, предварительно активируем ModelSpace
            has_model_frames = any(
                getattr(f, "layout_name", "Model").lower() == "model" and getattr(f, "source_type", "") != "Layout"
                for f in frames
            )
            if has_model_frames:
                try:
                    def switch_init_model():
                        model_layout = self.doc.ModelSpace.Layout
                        if getattr(self.doc.ActiveLayout, "Name", "") != getattr(model_layout, "Name", "Model"):
                            self.doc.ActiveLayout = model_layout
                    _retry_busy(switch_init_model)
                except Exception as e:
                    _warn("не удалось переключиться на вкладку «Модель» (возможен пустой лист)", e)
                self._setup_model_layout(printer_name, style_name)

            # Строим словарь {формат -> canonical_name} из доступных форматов принтера
            media_map = self._build_media_map(printer_name)
            # Резервный формат мог прийти локальным именем (настройки из config.json без открытого
            # чертежа) или пустым — приводим к системному имени этого плоттера
            canonical_media_name = self._resolve_media_name(canonical_media_name, media_map)
            
            # Проверяем, содержат ли рамки несколько разных DWG
            unique_dwgs = {os.path.abspath(f.dwg_path).lower() for f in frames if getattr(f, "dwg_path", "")}
            has_multiple_dwgs = len(unique_dwgs) > 1

            active_template = filename_template or get_default_template()
            raw_filenames = []
            for idx, frame in enumerate(frames):
                fn = render_filename(active_template, frame, dwg_name=getattr(frame, "dwg_name", ""), index=idx + 1)
                if has_multiple_dwgs and "{DWG}" not in active_template and getattr(frame, "dwg_name", ""):
                    raw_dwg_base = os.path.splitext(frame.dwg_name)[0]
                    clean_dwg_base = _safe_file_part(raw_dwg_base, 40)
                    if clean_dwg_base:
                        fn = f"[{clean_dwg_base}] {fn}"
                raw_filenames.append(fn)

            batch_filenames = resolve_duplicates(raw_filenames)

            # Создаем временную папку для temp-файлов (если режим merge)
            temp_dir = None
            if merge_pdf:
                temp_dir = tempfile.mkdtemp(prefix="acad_print_")
                
            temp_files = []
            temp_entries = []
            total_steps = len(frames) + (1 if merge_pdf else 0)
            
            for i, frame in enumerate(frames):
                if is_cancelled and is_cancelled():
                    report.cancelled = True
                    for rem_frame in frames[i:]:
                        report.items.append(PrintItemResult(
                            frame=rem_frame,
                            success=False,
                            skipped=True,
                            dwg_name=getattr(rem_frame, "dwg_name", ""),
                            sheet_number=str(getattr(rem_frame, "sheet_number", "")),
                            sheet_name=str(getattr(rem_frame, "sheet_name", ""))
                        ))
                    report.skipped_count = len(report.skipped_frames)
                    report.duration_seconds = time.perf_counter() - t_start
                    raise PrintCancelledError("Печать отменена пользователем.")
                    
                safe_name = _safe_file_part(frame.sheet_name, 80) or "Без_Имени"
                safe_num = _safe_file_part(frame.sheet_number, 20) or "б-н"
                    
                if progress_callback:
                    status = f"Печать листа {i + 1} из {len(frames)}: Лист {frame.sheet_number} ({safe_name})..."
                    progress_callback(i, total_steps, status)
                
                fallback_info = {"used": False, "format": ""}
                frame_success = False
                frame_error = ""
                cur_layout = None
                filepath = ""

                try:
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
                            state_guard.register_doc(doc)
                            if was_opened and target_path.lower() not in initially_open_files:
                                opened_docs_to_close[target_path.lower()] = doc
                            if has_model_frames:
                                self._setup_model_layout(printer_name, style_name)

                    is_paper_space = (getattr(frame, "layout_name", "Model").lower() != "model") or (getattr(frame, "source_type", "") == "Layout")
                    
                    if is_paper_space:
                        if getattr(frame, "source_type", "") == "Layout":
                            target_layout_name = frame.sheet_name
                        else:
                            target_layout_name = getattr(frame, "layout_name", "") or frame.sheet_name
                        try:
                            cur_layout = self.doc.Layouts.Item(target_layout_name)
                        except Exception:
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
                        
                        # Сохраняем исходную ориентацию до смены плоттера и бумаги.
                        original_paper = None
                        if getattr(frame, "source_type", "") == "Layout":
                            try:
                                original_w, original_h = _retry_busy(cur_layout.GetPaperSize)
                                original_rotation = _retry_busy(lambda: cur_layout.PlotRotation)
                                original_paper = (original_w > original_h, original_rotation)
                            except (AttributeError, ValueError, TypeError, pythoncom.com_error) as e:
                                _warn(f"не удалось прочитать исходную ориентацию листа {frame.sheet_number}", e)

                        # 2. Настраиваем параметры листа Layout
                        def setup_layout_params():
                            cur_layout.ConfigName = printer_name
                            cur_layout.StyleSheet = style_name
                            cur_layout.PlotWithPlotStyles = True
                            cur_layout.PlotWithLineweights = True
                            
                            media_name = media_map.get(frame.paper_format)
                            if not media_name:
                                media_name = canonical_media_name
                                fallback_info["used"] = True
                                fallback_info["format"] = canonical_media_name
                                warn_msg = (f"У плоттера «{printer_name}» нет бумаги для формата {frame.paper_format} "
                                            f"(лист {frame.sheet_number}) — применен резервный формат «{canonical_media_name}»")
                                frame.fallback_warning = warn_msg
                                _warn(warn_msg)
                            if media_name:
                                try:
                                    cur_layout.CanonicalMediaName = media_name
                                except Exception as e:
                                    _warn(f"плоттер не принял формат бумаги «{media_name}» (лист {frame.sheet_number}) "
                                          f"— печать на текущем формате листа", e)

                            has_window = (
                                getattr(frame, "source_type", "") != "Layout"
                                and frame.min_point
                                and frame.max_point
                                and (abs(frame.max_point[0] - frame.min_point[0]) > 1.0 or abs(frame.max_point[1] - frame.min_point[1]) > 1.0)
                            )
                            if has_window:
                                # Определение ориентации
                                is_paper_landscape = False
                                try:
                                    local_name = cur_layout.GetLocaleMediaName(media_name)
                                    import re
                                    nums = [float(x) for x in re.findall(r'\d+(?:\.\d+)?', local_name)]
                                    dims = [n for n in nums if n >= 100]
                                    if len(dims) >= 2:
                                        paper_w, paper_h = dims[-2], dims[-1]
                                        is_paper_landscape = paper_w > paper_h
                                except Exception as e:
                                    _warn(f"не удалось определить ориентацию бумаги (лист {frame.sheet_number})", e)
                                frame_w = abs(frame.max_point[0] - frame.min_point[0])
                                frame_h = abs(frame.max_point[1] - frame.min_point[1])
                                is_frame_landscape = frame_w > frame_h

                                target_rot = 1 if is_frame_landscape != is_paper_landscape else 0
                                if getattr(cur_layout, "PlotRotation", -1) != target_rot:
                                    cur_layout.PlotRotation = target_rot

                                p1 = win32com.client.VARIANT(
                                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                                    (frame.min_point[0], frame.min_point[1])
                                )
                                p2 = win32com.client.VARIANT(
                                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                                    (frame.max_point[0], frame.max_point[1])
                                )
                                cur_layout.SetWindowToPlot(p1, p2)
                                if getattr(cur_layout, "PlotType", -1) != 4:
                                    cur_layout.PlotType = 4  # acWindow
                                if getattr(cur_layout, "StandardScale", -1) != 0:
                                    cur_layout.StandardScale = 0
                                if not getattr(cur_layout, "CenterPlot", False):
                                    cur_layout.CenterPlot = True
                            else:
                                cur_layout.PlotType = 5  # acLayout
                                if original_paper is not None:
                                    was_landscape, rotation = original_paper
                                    paper_w, paper_h = cur_layout.GetPaperSize()
                                    if was_landscape != (paper_w > paper_h):
                                        rotation = (1, 0, 3, 2)[rotation]
                                    if cur_layout.PlotRotation != rotation:
                                        cur_layout.PlotRotation = rotation
                        _retry_busy(setup_layout_params)
                    else:
                        # 1. Активируем вкладку Модель, только если в AutoCAD был активен лист Layout
                        model_layout = self.doc.ModelSpace.Layout
                        if getattr(self.doc.ActiveLayout, "Name", "") != getattr(model_layout, "Name", "Model"):
                            def switch_model_tab():
                                self.doc.ActiveLayout = model_layout
                            _retry_busy(switch_model_tab)
                            time.sleep(0.3)

                        # 2. Настраиваем параметры печати рамки в пространстве модели
                        def setup_model_params():
                            cur_layout = self.doc.ModelSpace.Layout
                            if getattr(cur_layout, "ConfigName", "").lower() != printer_name.lower():
                                cur_layout.ConfigName = printer_name
                            if getattr(cur_layout, "StyleSheet", "").lower() != style_name.lower():
                                cur_layout.StyleSheet = style_name
                            if not getattr(cur_layout, "PlotWithPlotStyles", False):
                                cur_layout.PlotWithPlotStyles = True
                            if not getattr(cur_layout, "PlotWithLineweights", False):
                                cur_layout.PlotWithLineweights = True

                            # Автоподбор формата бумаги по формату рамки
                            media_name = media_map.get(frame.paper_format)
                            if not media_name:
                                fallback_info["used"] = True
                                fallback_info["format"] = canonical_media_name
                                warn_msg = (f"У плоттера «{printer_name}» нет бумаги для формата "
                                            f"{frame.paper_format} (лист {frame.sheet_number}) — печать на резервном "
                                            f"формате «{canonical_media_name}»")
                                frame.fallback_warning = warn_msg
                                print(f"Предупреждение: {warn_msg}")
                                _warn(warn_msg)
                                media_name = canonical_media_name
                            if getattr(cur_layout, "CanonicalMediaName", "") != media_name:
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
                            except Exception as e:
                                _warn(f"не удалось определить ориентацию бумаги (лист {frame.sheet_number})", e)
                            frame_w = abs(frame.max_point[0] - frame.min_point[0])
                            frame_h = abs(frame.max_point[1] - frame.min_point[1])
                            is_frame_landscape = frame_w > frame_h
                        
                            target_rot = 1 if is_frame_landscape != is_paper_landscape else 0
                            if getattr(cur_layout, "PlotRotation", -1) != target_rot:
                                cur_layout.PlotRotation = target_rot
                        
                            view_name = "_SHT_PLOT_VIEW"
                            view = None
                            try:
                                view = self.doc.Views.Item(view_name)
                            except Exception:
                                try:
                                    view = self.doc.Views.Add(view_name)
                                except Exception as e:
                                    _warn("не удалось создать вид печати, печать по окну (acWindow)", e)

                            if view:
                                cx = (frame.min_point[0] + frame.max_point[0]) / 2.0
                                cy = (frame.min_point[1] + frame.max_point[1]) / 2.0
                                center_pt = win32com.client.VARIANT(
                                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8,
                                    (cx, cy)
                                )
                                view.Center = center_pt
                                view.Width = frame_w
                                view.Height = frame_h
                                if getattr(cur_layout, "ViewToPlot", "") != view_name:
                                    cur_layout.ViewToPlot = view_name
                                if getattr(cur_layout, "PlotType", -1) != 3:
                                    cur_layout.PlotType = 3  # acView
                            else:
                                p1 = win32com.client.VARIANT(
                                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                                    (frame.min_point[0], frame.min_point[1])
                                )
                                p2 = win32com.client.VARIANT(
                                    win32com.client.pythoncom.VT_ARRAY | win32com.client.pythoncom.VT_R8, 
                                    (frame.max_point[0], frame.max_point[1])
                                )
                                cur_layout.SetWindowToPlot(p1, p2)
                                if getattr(cur_layout, "PlotType", -1) != 4:
                                    cur_layout.PlotType = 4  # acWindow

                            if getattr(cur_layout, "StandardScale", -1) != 0:
                                cur_layout.StandardScale = 0
                            if not getattr(cur_layout, "CenterPlot", False):
                                cur_layout.CenterPlot = True
                    
                        _retry_busy(setup_model_params)

                    if merge_pdf:
                        filename = f"{i:04d}_{batch_filenames[i]}"
                        filepath = os.path.join(temp_dir, filename)
                    else:
                        filename = batch_filenames[i]
                        filepath = os.path.abspath(os.path.join(output_path, filename))
                    
                    # Печать листа через PlotToFile с обработкой занятости AutoCAD (RPC_E_CALL_REJECTED)
                    def do_plot():
                        self.doc.Plot.PlotToFile(filepath, printer_name)
                    _retry_busy(do_plot)
                    frame_success = True

                except PrintCancelledError:
                    raise
                except pythoncom.com_error as e:
                    def _get(obj, attr):
                        try:
                            return getattr(obj, attr)
                        except Exception:
                            return "?"
                    try:
                        frame_size = (f"{abs(frame.max_point[0] - frame.min_point[0]):.1f} x "
                                      f"{abs(frame.max_point[1] - frame.min_point[1]):.1f}")
                    except Exception:
                        frame_size = "?"
                    details = (
                        f"лист {frame.sheet_number} «{frame.sheet_name}», формат рамки {frame.paper_format}, "
                        f"чертеж {getattr(frame, 'dwg_name', '') or _get(self.doc, 'Name')}, "
                        f"вкладка {_get(cur_layout, 'Name') if cur_layout else '?'}, бумага «{_get(cur_layout, 'CanonicalMediaName') if cur_layout else '?'}"
                    )
                    err_msg = f"AutoCAD отказался печатать ({details}): {e}"
                    frame_error = err_msg
                    log_error(err_msg, exc=e, module="Печать")
                    if not continue_on_error:
                        raise RuntimeError(err_msg) from e
                except Exception as e:
                    err_msg = f"Ошибка печати листа {frame.sheet_number} ({frame.sheet_name}): {e}"
                    frame_error = err_msg
                    log_error(err_msg, exc=e, module="Печать")
                    if not continue_on_error:
                        raise

                if frame_success:
                    if merge_pdf and filepath:
                        temp_files.append(filepath)
                        temp_entries.append((filepath, frame))
                    report.items.append(PrintItemResult(
                        frame=frame,
                        success=True,
                        output_file=filepath,
                        fallback_used=fallback_info["used"],
                        fallback_format=fallback_info["format"],
                        dwg_name=getattr(frame, "dwg_name", ""),
                        sheet_number=str(getattr(frame, "sheet_number", "")),
                        sheet_name=str(getattr(frame, "sheet_name", ""))
                    ))
                    report.success_count += 1
                    if fallback_info["used"]:
                        report.fallback_count += 1
                else:
                    report.items.append(PrintItemResult(
                        frame=frame,
                        success=False,
                        error=frame_error,
                        output_file="",
                        fallback_used=fallback_info["used"],
                        fallback_format=fallback_info["format"],
                        dwg_name=getattr(frame, "dwg_name", ""),
                        sheet_number=str(getattr(frame, "sheet_number", "")),
                        sheet_name=str(getattr(frame, "sheet_name", ""))
                    ))
                    report.failed_count += 1
                
                if is_cancelled and is_cancelled():
                    report.cancelled = True
                    for rem_frame in frames[i + 1:]:
                        report.items.append(PrintItemResult(
                            frame=rem_frame,
                            success=False,
                            skipped=True,
                            dwg_name=getattr(rem_frame, "dwg_name", ""),
                            sheet_number=str(getattr(rem_frame, "sheet_number", "")),
                            sheet_name=str(getattr(rem_frame, "sheet_name", ""))
                        ))
                    report.skipped_count = len(report.skipped_frames)
                    report.duration_seconds = time.perf_counter() - t_start
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
                for page_idx, (pdf_file, f_obj) in enumerate(temp_entries):
                    bm_title = format_bookmark_title(f_obj.sheet_number, f_obj.sheet_name, page_idx)
                    merger.append(pdf_file, outline_item=bm_title)

                doc_name_str = getattr(self.doc, "Name", "") if self.doc else ""
                metadata = build_pdf_metadata([f for _, f in temp_entries], doc_name=doc_name_str)
                merger.add_metadata(metadata)
                    
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

            report.duration_seconds = time.perf_counter() - t_start
            return report
                
        finally:
            if report and report.duration_seconds == 0.0:
                report.duration_seconds = time.perf_counter() - t_start

            # Закрываем чертежи, открытые для печати, — только если так попросили
            for d in (opened_docs_to_close.values() if close_opened_docs else []):
                try:
                    if self.connector:
                        self.connector.close_document(d, save_changes=False)
                except Exception as e:
                    _warn("не удалось закрыть чертеж, открытый для печати", e)

            # Гарантированно восстанавливаем системные переменные, удаляем временные виды
            # и возвращаем исходный чертеж и лист
            try:
                state_guard.restore()
            except Exception as e:
                _warn("ошибка при восстановлении состояния AutoCAD", e)

            # Дальше восстанавливаем ссылку self.doc на исходный чертеж
            if initial_active_doc is not None:
                self.doc = initial_active_doc
            else:
                try:
                    self.doc = self.connector.app.ActiveDocument if self.connector else None
                except Exception:
                    self.doc = None

            # Удаляем всю временную папку целиком
            if temp_dir and os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    _warn(f"не удалось удалить временную папку {temp_dir}", e)

