import os
import time
import win32com.client
import pythoncom

# HRESULT-ы «AutoCAD занят / вызов отклонён» — только их имеет смысл повторять.
RPC_E_CALL_REJECTED = -2147418111          # 0x80010001 «Вызов был отклонён»
RPC_E_SERVERCALL_RETRYLATER = -2147417846  # 0x8001010A «Сервер занят, повторите позже»
RPC_E_DISCONNECTED = -2147417848           # 0x80010108 объект временно отключён
DISP_E_EXCEPTION = -2147352567             # 0x80020009 ошибка внутри AutoCAD (настоящий код — в excepinfo)
BUSY_HRESULTS = (RPC_E_CALL_REJECTED, RPC_E_SERVERCALL_RETRYLATER, RPC_E_DISCONNECTED)


def _is_busy_com_error(e: Exception) -> bool:
    """
    True, если COM-ошибка означает «AutoCAD занят» (стоит повторить).
    Настоящие ошибки («Неверный ввод», «Файл не найден» и т.п.) — False: их повтор не поможет.
    """
    args = getattr(e, "args", ()) or ()
    hresult = getattr(e, "hresult", None)
    if hresult is None and args and isinstance(args[0], int):
        hresult = args[0]
    if hresult in BUSY_HRESULTS:
        return True
    # Ошибка изнутри AutoCAD: настоящий код лежит в excepinfo (args[2]), последний элемент — scode
    if hresult == DISP_E_EXCEPTION and len(args) > 2 and isinstance(args[2], tuple) and args[2]:
        if args[2][-1] in BUSY_HRESULTS:
            return True
    text = " ".join(str(a) for a in args if isinstance(a, (str, tuple))).lower()
    return "отклонен" in text or "отклонён" in text or "rejected" in text


def _retry_busy(func, max_attempts: int = 20, delay: float = 0.25):
    """
    Повторяет вызов, пока AutoCAD занят.
    Особенность win32com без кэша типов (так работает exe): если AutoCAD занят и отклоняет вызов,
    ошибка приходит не как com_error, а как AttributeError '<unknown>.Count' / 'Open.ModelSpace'.
    Поэтому повторяем при AttributeError и при COM-ошибках занятости (_is_busy_com_error).
    Настоящие COM-ошибки («Неверный ввод» и т.п.) сразу пробрасываются наверх — без лишнего ожидания.
    """
    last = None
    for _ in range(max(1, max_attempts)):
        try:
            return func()
        except AttributeError as e:
            last = e
        except pythoncom.com_error as e:
            if not _is_busy_com_error(e):
                # Печатаем код — если это всё же «занятость», которой нет в списке, её легко добавить
                hr = e.args[0] if getattr(e, "args", None) else "?"
                print(f"[AutoCAD] COM-ошибка без повтора (HRESULT {hr}): {e}")
                raise
            last = e
        time.sleep(delay)
    raise last


class AutoCADConnector:
    """
    Класс для подключения и базового взаимодействия с активным процессом AutoCAD.
    """
    def __init__(self):
        self.app = None
        self.doc = None
        self._last_highlighted_handle = None
        self._opened_by_us = set()

    def connect(self):
        """
        Подключается к запущенному экземпляру AutoCAD.
        Возвращает True в случае успеха, иначе генерирует исключение.
        """
        try:
            # Гарантируем подключение к интерактивной оконной станции и рабочему столу Windows
            try:
                import ctypes
                hwinsta = ctypes.windll.user32.OpenWindowStationW("WinSta0", False, 0x037F)
                if hwinsta:
                    ctypes.windll.user32.SetProcessWindowStation(hwinsta)
                hDesk = ctypes.windll.user32.OpenDesktopW("Default", 0, False, 0x01FF)
                if hDesk:
                    ctypes.windll.user32.SetThreadDesktop(hDesk)
            except Exception:
                pass

            # Инициализация COM (необходимо для работы в разных потоках)
            pythoncom.CoInitialize()
            
            # Пытаемся получить доступ к уже запущенному процессу AutoCAD
            self.app = win32com.client.GetActiveObject("AutoCAD.Application")
            self._ensure_trusted_paths()
            try:
                self.doc = _retry_busy(lambda: self.app.ActiveDocument, max_attempts=12, delay=0.25)
            except Exception:
                try:
                    self.doc = self.app.ActiveDocument
                except Exception:
                    self.doc = None
            return True
            
        except pythoncom.com_error as e:
            # Если AutoCAD не запущен, будет выброшено COM-исключение
            raise ConnectionError("Не удалось подключиться к AutoCAD. Убедитесь, что программа запущена.") from e

    def _ensure_trusted_paths(self):
        """
        Добавляет папку lisp программы в доверенные пути AutoCAD (TRUSTEDPATHS),
        чтобы исключить блокировку выполнения скомпилированных .fas при SECURELOAD > 0.
        """
        try:
            from core.resource_utils import get_resource_path
            lisp_dir = os.path.dirname(os.path.abspath(get_resource_path("core/lisp/spds_export.lsp")))
            files_prefs = self.app.Preferences.Files
            current_paths = files_prefs.TrustedPaths or ""
            norm_lisp = os.path.normpath(lisp_dir).lower()
            existing = [os.path.normpath(p.strip()).lower() for p in current_paths.split(";") if p.strip()]
            if norm_lisp not in existing:
                new_paths = (current_paths.rstrip(";") + ";" + lisp_dir) if current_paths else lisp_dir
                files_prefs.TrustedPaths = new_paths
        except Exception:
            pass
            
    def get_active_document_name(self) -> str:
        """
        Возвращает имя текущего активного чертежа.
        """
        if not self.doc:
            return "Нет открытого чертежа"
        try:
            return self.doc.Name
        except Exception:
            return "Неизвестный чертеж"

    def find_open_document(self, filepath_or_name: str):
        """
        Ищет уже открытый документ среди открытых в AutoCAD по полному пути или имени файла.
        Возвращает COM-объект документа или None.
        """
        if not self.app:
            return None
            
        norm_target = os.path.abspath(filepath_or_name).lower() if os.path.isabs(filepath_or_name) else filepath_or_name.lower()
        target_basename = os.path.basename(filepath_or_name).lower()
        
        def _check():
            docs = self.app.Documents
            for i in range(docs.Count):
                try:
                    d = docs.Item(i)
                    d_fullname = getattr(d, "FullName", "")
                    d_name = getattr(d, "Name", "")
                    
                    if d_fullname and os.path.abspath(d_fullname).lower() == norm_target:
                        return d
                    if d_name and d_name.lower() == target_basename:
                        return d
                except Exception:
                    continue
            return None

        try:
            return _retry_busy(_check, max_attempts=40, delay=0.25)
        except Exception as e:
            print(f"Предупреждение при поиске открытого документа: {e}")
            return None

    def get_open_documents(self):
        """
        Возвращает список кортежей (full_path, name) для всех открытых в AutoCAD чертежей.
        """
        result = []
        if not self.app:
            return result

        def _fetch():
            res = []
            docs = self.app.Documents
            for i in range(docs.Count):
                try:
                    d = docs.Item(i)
                    res.append((getattr(d, "FullName", ""), getattr(d, "Name", "")))
                except Exception:
                    continue
            return res

        try:
            return _retry_busy(_fetch, max_attempts=40, delay=0.25)
        except Exception:
            return []

    def open_document(self, filepath: str, read_only: bool = True):
        """
        Открывает DWG-файл в AutoCAD или возвращает уже открытый документ.
        Возвращает кортеж (doc, was_opened_by_us: bool).
        """
        if not self.app:
            self.connect()

        abs_path = os.path.abspath(filepath)
        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"Файл чертежа не найден: {abs_path}")

        # Проверяем, не открыт ли чертеж уже в AutoCAD
        existing_doc = self.find_open_document(abs_path)
        if existing_doc:
            self.doc = existing_doc
            return existing_doc, False

        # Открываем через коллекцию Documents с защитой от временной занятости AutoCAD.
        # Если прошлая попытка упала, но AutoCAD всё же успел открыть чертеж,
        # повторно не открываем (иначе появится вторая копия «только чтение»).
        attempt = {"n": 0}

        def _do_open():
            attempt["n"] += 1
            if attempt["n"] > 1:
                already = self.find_open_document(abs_path)
                if already is not None:
                    return already
            return self.app.Documents.Open(abs_path, read_only)

        opened = _retry_busy(_do_open, max_attempts=20, delay=0.35)
        doc = self._wait_document_ready(abs_path, opened)
        self.doc = doc
        self._opened_by_us.add(abs_path.lower())
        return doc, True

    @staticmethod
    def _doc_usable(d) -> bool:
        """Документ отвечает на обращения (не «полуоткрытый»)."""
        try:
            d.Name
            d.ModelSpace.Count
            return True
        except Exception:
            return False

    def _wait_document_ready(self, abs_path: str, opened, timeout: float = 30.0):
        """
        Documents.Open возвращает объект, когда AutoCAD ещё догружает чертеж.
        В exe (без кэша типов win32com) такой объект часто «пустой»: любое свойство даёт
        AttributeError 'Open.ModelSpace' / 'Open.Close'. Поэтому ждём, пока AutoCAD освободится,
        и берём документ заново из коллекции Documents по пути — этот объект полноценный.
        """
        end = time.perf_counter() + timeout
        while time.perf_counter() < end:
            try:
                if not self.app.GetAcadState().IsQuiescent:
                    time.sleep(0.1)
                    continue
            except Exception:
                time.sleep(0.1)
                continue
            d = self.find_open_document(abs_path)
            if d is not None and self._doc_usable(d):
                return d
            if opened is not None and self._doc_usable(opened):
                return opened
            time.sleep(0.2)
        raise RuntimeError(f"AutoCAD не успел открыть чертеж за {timeout:.0f} сек: {abs_path}")

    def close_document(self, doc, save_changes: bool = False):
        """
        Безопасно закрывает документ AutoCAD.
        """
        if not doc:
            return

        doc_path = ""
        try:
            doc_path = getattr(doc, "FullName", "")
        except Exception:
            pass

        def _do_close():
            doc.Close(save_changes)

        try:
            _retry_busy(_do_close, max_attempts=15, delay=0.25)
        except Exception as e:
            print(f"Предупреждение при закрытии документа: {e}")
        finally:
            if doc_path:
                self._opened_by_us.discard(os.path.abspath(doc_path).lower())
            if self.doc == doc:
                self._last_highlighted_handle = None
            # Обновляем активный документ
            try:
                self.doc = self.app.ActiveDocument
            except Exception:
                self.doc = None

    def close_opened_documents(self) -> int:
        """
        Закрывает все документы AutoCAD, которые были открыты этой программой,
        не затрагивая документы, открытые пользователем до или во время работы программы.
        Возвращает количество успешно закрытых чертежей.
        """
        if not self._opened_by_us:
            return 0
        if not self.app:
            try:
                self.connect()
            except Exception:
                return 0

        closed_count = 0
        paths = list(self._opened_by_us)
        for path in paths:
            doc = self.find_open_document(path)
            if doc:
                try:
                    self.close_document(doc, save_changes=False)
                    closed_count += 1
                except Exception as e:
                    print(f"Предупреждение при закрытии открытого программой чертежа '{path}': {e}")
            else:
                self._opened_by_us.discard(path)

        try:
            self.doc = self.app.ActiveDocument
        except Exception:
            self.doc = None

        return closed_count

    def get_opened_by_us_count(self) -> int:
        """
        Возвращает актуальное количество открытых программой чертежей,
        которые все еще открыты в AutoCAD.
        """
        if not self._opened_by_us or not self.app:
            return len(self._opened_by_us)

        open_docs = self.get_open_documents()
        open_paths = {os.path.abspath(p).lower() for p, _ in open_docs if p}
        self._opened_by_us = {p for p in self._opened_by_us if p in open_paths}
        return len(self._opened_by_us)

    def activate_document(self, doc):
        """
        Активирует указанный документ в окне AutoCAD.
        """
        if not doc:
            return

        def _do_activate():
            self.app.ActiveDocument = doc

        try:
            _retry_busy(_do_activate, max_attempts=15, delay=0.25)
            self.doc = doc
        except Exception as e:
            print(f"Предупреждение: не удалось активировать документ: {e}")


    def disconnect(self):
        """
        Освобождает COM-ресурсы.
        """
        self.clear_highlight()
        self.doc = None
        self.app = None
        self._opened_by_us.clear()
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def get_model_space(self):
        """
        Возвращает объект пространства модели (Model Space) текущего чертежа.
        """
        if not self.doc:
            raise ValueError("Нет активного подключения к документу. Сначала вызовите connect().")
        return self.doc.ModelSpace

    def zoom_window(self, min_point, max_point, margin_percent: float = 0.05):
        """
        Центрирует окно AutoCAD на заданных координатах с комфортным отступом (margin_percent).
        """
        try:
            if not self.app or not self.doc:
                self.connect()
            else:
                try:
                    self.doc = self.app.ActiveDocument
                except Exception:
                    self.connect()

            # Переключаемся в пространство модели, если открыт Layout
            try:
                if getattr(self.doc, 'ActiveSpace', 1) != 1:
                    self.doc.ActiveSpace = 1
            except Exception:
                pass

            min_x, min_y = float(min_point[0]), float(min_point[1])
            max_x, max_y = float(max_point[0]), float(max_point[1])

            dx = abs(max_x - min_x)
            dy = abs(max_y - min_y)
            margin_x = dx * margin_percent
            margin_y = dy * margin_percent

            p1 = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                (min_x - margin_x, min_y - margin_y, 0.0)
            )
            p2 = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                (max_x + margin_x, max_y + margin_y, 0.0)
            )

            self.app.ZoomWindow(p1, p2)
        except Exception as e:
            print(f"Предупреждение: не удалось центрировать окно в AutoCAD: {e}")

    def highlight_object(self, handle: str = "", object_id: int = 0):
        """
        Подсвечивает объект рамки в AutoCAD. Снимает подсветку с ранее подсвеченного объекта.
        """
        self.clear_highlight()

        try:
            if not self.doc:
                self.connect()

            obj = None
            if handle:
                try:
                    obj = self.doc.HandleToObject(handle)
                except Exception:
                    pass

            if not obj and object_id:
                try:
                    obj = self.doc.ObjectIdToObject(object_id)
                except Exception:
                    pass

            if obj:
                try:
                    obj.Highlight(True)
                    self._last_highlighted_handle = handle or getattr(obj, 'Handle', '')
                except Exception:
                    # Некоторые сторонние ARX объекты могут не поддерживать метод Highlight
                    pass
        except Exception as e:
            print(f"Предупреждение: не удалось подсветить объект в AutoCAD: {e}")

    def clear_highlight(self):
        """
        Снимает подсветку с ранее подсвеченного объекта.
        """
        if self._last_highlighted_handle and self.doc:
            try:
                old_obj = self.doc.HandleToObject(self._last_highlighted_handle)
                old_obj.Highlight(False)
            except Exception:
                pass
            self._last_highlighted_handle = None

    def activate_layout(self, layout_name: str):
        """
        Переключает активный лист в документе AutoCAD на указанную вкладку Layout.
        """
        try:
            if not self.app or not self.doc:
                self.connect()
            else:
                try:
                    self.doc = self.app.ActiveDocument
                except Exception:
                    self.connect()
                    
            self.doc.ActiveLayout = self.doc.Layouts.Item(layout_name)
        except Exception as e:
            print(f"Предупреждение: не удалось активировать Layout '{layout_name}': {e}")

    def show_frame(self, frame, zoom: bool = True, highlight: bool = True):
        """
        Отображает рамку в AutoCAD: если это вкладка Layout, переключает на нее;
        если это рамка в Модели — центрирует вид и включает подсветку.
        Если рамка принадлежит другому DWG-файлу, переключает активный документ.
        """
        if getattr(frame, "dwg_path", ""):
            cur_fullname = ""
            try:
                cur_fullname = getattr(self.doc, "FullName", "")
            except Exception:
                pass
            if not cur_fullname or os.path.abspath(cur_fullname).lower() != os.path.abspath(frame.dwg_path).lower():
                try:
                    doc, _ = self.open_document(frame.dwg_path)
                    self.activate_document(doc)
                except Exception as e:
                    print(f"Предупреждение: не удалось переключиться на чертеж {frame.dwg_path}: {e}")

        target_layout = getattr(frame, "layout_name", "Model") or "Model"
        if getattr(frame, "source_type", "") == "Layout":
            self.activate_layout(frame.sheet_name or target_layout)
            return
        elif target_layout.lower() != "model":
            self.activate_layout(target_layout)
        else:
            try:
                model_layout = self.doc.ModelSpace.Layout
                if getattr(self.doc.ActiveLayout, "Name", "") != getattr(model_layout, "Name", "Model"):
                    self.doc.ActiveLayout = model_layout
            except Exception:
                pass

        if zoom and frame.min_point and frame.max_point:
            self.zoom_window(frame.min_point, frame.max_point)

        if highlight:
            self.highlight_object(handle=frame.handle, object_id=frame.object_id)


    def activate_autocad_window(self):
        """
        Разворачивает окно AutoCAD на передний план, если оно было свернуто.
        """
        if not self.app:
            return
        try:
            if getattr(self.app, 'WindowState', 1) == 2:  # acMin = 2
                self.app.WindowState = 3  # acMax = 3
            self.app.Visible = True
        except Exception:
            pass


if __name__ == "__main__":
    # Простой блок для тестирования коннектора
    print("Попытка подключения к AutoCAD...")
    connector = AutoCADConnector()
    
    try:
        connector.connect()
        doc_name = connector.get_active_document_name()
        print(f"Успешное подключение!")
        print(f"Активный чертеж: {doc_name}")
        
        # Тестируем получение Model Space
        ms = connector.get_model_space()
        print(f"Объектов в пространстве модели: {ms.Count}")
        
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

