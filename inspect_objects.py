from core.autocad_connector import AutoCADConnector

def inspect_model_space():
    connector = AutoCADConnector()
    try:
        connector.connect()
        ms = connector.get_model_space()
        print(f"--- Сканирование пространства модели ---")
        print(f"Всего объектов: {ms.Count}\n")
        
        for i in range(ms.Count):
            obj = ms.Item(i)
            entity_name = getattr(obj, 'EntityName', 'Unknown')
            object_name = getattr(obj, 'ObjectName', 'Unknown')
            
            print(f"[{i+1}] ObjectName: {object_name} | EntityName: {entity_name}")
            
            # Если это объект СПДС (mcsDbObjectFormat или spDbFormat)
            if "mcsdbobject" in entity_name.lower() or "spdbobject" in entity_name.lower():
                print(f"    -> СПДС Рамка найдена!")
                # Пытаемся получить габариты
                try:
                    min_pt, max_pt = obj.GetBoundingBox()
                    print(f"    -> Габариты успешно прочитаны: {min_pt} - {max_pt}")
                except Exception as e:
                    print(f"    -> Не удалось прочитать габариты: {e}")
                    
                # Пытаемся прочитать возможные свойства, где может лежать номер листа
                props_to_try = ["Sheet", "SheetNumber", "Page", "Number", "Номер", "Лист", "TextString", "Name"]
                for prop in props_to_try:
                    try:
                        val = getattr(obj, prop)
                        print(f"    -> Свойство '{prop}': {val}")
                    except:
                        pass
                    
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    inspect_model_space()
