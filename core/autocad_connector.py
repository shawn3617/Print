import os
import win32com.client
import pythoncom

class AutoCADConnector:
    """
    Класс для подключения и базового взаимодействия с активным процессом AutoCAD.
    """
    def __init__(self):
        self.app = None
        self.doc = None
        self._last_highlighted_handle = None

    def connect(self):
        """
        Подключается к запущенному экземпляру AutoCAD.
        Возвращает True в случае успеха, иначе генерирует исключение.
        """
        try:
            # Инициализация COM (необходимо для работы в разных потоках)
            pythoncom.CoInitialize()
            
            # Пытаемся получить доступ к уже запущенному процессу AutoCAD
            self.app = win32com.client.GetActiveObject("AutoCAD.Application")
            try:
                self.doc = self.app.ActiveDocument
            except Exception:
                self.doc = None
            return True
            
        except pythoncom.com_error as e:
            # Если AutoCAD не запущен, будет выброшено COM-исключение
            raise ConnectionError("Не удалось подключиться к AutoCAD. Убедитесь, что программа запущена.") from e
            
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
        
        try:
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
        except Exception as e:
            print(f"Ошибка при поиске открытого документа: {e}")
            
        return None

    def get_open_documents(self):
        """
        Возвращает список кортежей (full_path, name) для всех открытых в AutoCAD чертежей.
        """
        result = []
        if not self.app:
            return result
        try:
            docs = self.app.Documents
            for i in range(docs.Count):
                try:
                    d = docs.Item(i)
                    result.append((getattr(d, "FullName", ""), getattr(d, "Name", "")))
                except Exception:
                    continue
        except Exception:
            pass
        return result

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

        # Открываем через коллекцию Documents
        doc = self.app.Documents.Open(abs_path, read_only)
        self.doc = doc
        return doc, True

    def close_document(self, doc, save_changes: bool = False):
        """
        Безопасно закрывает документ AutoCAD.
        """
        if not doc:
            return
        try:
            doc.Close(save_changes)
        except Exception as e:
            print(f"Предупреждение при закрытии документа: {e}")
        finally:
            # Обновляем активный документ
            try:
                self.doc = self.app.ActiveDocument
            except Exception:
                self.doc = None

    def activate_document(self, doc):
        """
        Активирует указанный документ в окне AutoCAD.
        """
        if not doc:
            return
        try:
            self.app.ActiveDocument = doc
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

        if getattr(frame, "source_type", "") == "Layout":
            self.activate_layout(frame.sheet_name)
            return

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

