from core.autocad_connector import AutoCADConnector

def test_spds_hidden_data():
    connector = AutoCADConnector()
    try:
        connector.connect()
        ms = connector.get_model_space()
        
        for i in range(ms.Count):
            obj = ms.Item(i)
            entity_name = getattr(obj, 'EntityName', '').lower()
            
            if "mcsdbobject" in entity_name or "spdbobject" in entity_name:
                print(f"\nНайдена СПДС Рамка! (ID: {obj.ObjectID})")
                
                # 1. Читаем XData
                print("\n--- Проверка XData ---")
                try:
                    # Пустая строка значит "читать всё"
                    xtype, xdata = obj.GetXData("")
                    if xtype and xdata:
                        for t, d in zip(xtype, xdata):
                            # Тип 1000 - это обычно строки
                            print(f"XData [Type {t}]: {d}")
                    else:
                        print("XData пуст.")
                except Exception as e:
                    print(f"Нет XData или ошибка чтения: {e}")
                    
                # 2. Читаем Extension Dictionary
                print("\n--- Проверка Extension Dictionary ---")
                try:
                    ext_dict = obj.GetExtensionDictionary()
                    print(f"Словарь найден! Количество записей: {ext_dict.Count}")
                    for j in range(ext_dict.Count):
                        dict_item = ext_dict.Item(j)
                        dict_name = getattr(dict_item, 'Name', f'Item_{j}')
                        print(f"Запись словаря: {dict_name}")
                        # Если это XRecord, можно попытаться его прочитать
                        if getattr(dict_item, 'ObjectName', '') == 'AcDbXrecord':
                            try:
                                xt, xd = dict_item.GetXRecordData()
                                if xt and xd:
                                    for rt, rd in zip(xt, xd):
                                        if rt in [1, 2, 3, 300, 301, 302]: # Коды строк
                                            print(f"  -> Содержимое: {rd}")
                            except:
                                pass
                except Exception as e:
                    print(f"Словаря нет или ошибка чтения: {e}")
                    
                # 3. Динамические свойства (через COM-интерфейс СПДС, если он доступен)
                print("\n--- Проверка динамических свойств ---")
                try:
                    # У объектов СПДС иногда есть свойство Properties или Fields
                    props = getattr(obj, 'Properties', None)
                    if props:
                        print(f"Найдено свойство Properties! Тип: {type(props)}")
                except:
                    print("Свойство Properties недоступно.")
                    
                break # Проверяем только первую рамку
                
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    test_spds_hidden_data()
