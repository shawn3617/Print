import win32com.client
import pythoncom

class AutoCADConnector:
    """
    Класс для подключения и базового взаимодействия с активным процессом AutoCAD.
    """
    def __init__(self):
        self.app = None
        self.doc = None

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
            self.doc = self.app.ActiveDocument
            return True
            
        except pythoncom.com_error as e:
            # Если AutoCAD не запущен, будет выброшено COM-исключение
            raise ConnectionError("Не удалось подключиться к AutoCAD. Убедитесь, что программа запущена и открыт чертеж.") from e
            
    def get_active_document_name(self) -> str:
        """
        Возвращает имя текущего активного чертежа.
        """
        if not self.doc:
            raise ValueError("Нет активного подключения к документу. Сначала вызовите connect().")
        return self.doc.Name

    def disconnect(self):
        """
        Освобождает COM-ресурсы.
        """
        self.doc = None
        self.app = None
        pythoncom.CoUninitialize()

    def get_model_space(self):
        """
        Возвращает объект пространства модели (Model Space) текущего чертежа.
        """
        if not self.doc:
            raise ValueError("Нет активного подключения к документу. Сначала вызовите connect().")
        return self.doc.ModelSpace


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

