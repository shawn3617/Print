from core.autocad_connector import AutoCADConnector

def test_explode_spds():
    connector = AutoCADConnector()
    try:
        connector.connect()
        ms = connector.get_model_space()
        print(f"Подключено к чертежу: {connector.get_active_document_name()}")
        
        found = False
        for i in range(ms.Count):
            obj = ms.Item(i)
            entity_name = getattr(obj, 'EntityName', '').lower()
            
            # Ищем нашу СПДС/nanoCAD рамку
            if "mcsdbobject" in entity_name or "spdbobject" in entity_name:
                found = True
                print(f"\nНайдена СПДС Рамка! (ID: {obj.ObjectID})")
                
                try:
                    print(f"COM-метод не сработал. Используем хак через SendCommand!")
                    handle = obj.Handle
                    
                    # 1. Ставим метку для отмены (UNDO MARK)
                    connector.doc.SendCommand("UNDO\nMARK\n")
                    
                    # 2. Посылаем команду расчленить (EXPLODE) по хэндлу объекта
                    connector.doc.SendCommand(f'EXPLODE\n(handent "{handle}")\n\n')
                    
                    # 3. Теперь объекты лежат прямо в ModelSpace. Переберем последние объекты
                    # Так как мы не знаем точно их индексы, переберем все тексты в чертеже
                    texts = []
                    for j in range(ms.Count):
                        exp_obj = ms.Item(j)
                        exp_name = getattr(exp_obj, 'EntityName', '')
                        if exp_name in ['AcDbText', 'AcDbMText']:
                            texts.append(getattr(exp_obj, 'TextString', ''))
                            
                    print(f"\n--- Найденные тексты после принудительного разбиения ({len(texts)} шт.) ---")
                    for idx, t in enumerate(texts):
                        clean_text = t.replace('\n', ' ').replace('\r', '').strip()
                        if clean_text:
                            print(f"[{idx}] {clean_text}")
                            
                except Exception as e:
                    print(f"Ошибка при принудительном Explode: {e}")
                finally:
                    # 4. Откатываем чертеж к метке, чтобы вернуть рамку и удалить мусор
                    print("\nОткатываем чертеж (UNDO BACK)...")
                    connector.doc.SendCommand("UNDO\nBACK\n")
                    
        if not found:
            print("Объекты СПДС не найдены.")
            
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    test_explode_spds()
