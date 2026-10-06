import time
from core.autocad_connector import AutoCADConnector

def test_spds_lisp_bridge():
    connector = AutoCADConnector()
    try:
        connector.connect()
        ms = connector.get_model_space()
        
        for i in range(ms.Count):
            obj = ms.Item(i)
            entity_name = getattr(obj, 'EntityName', '').lower()
            
            if "mcsdbobject" in entity_name or "spdbobject" in entity_name:
                print(f"\nНайдена СПДС Рамка! (ID: {obj.ObjectID}, Handle: {obj.Handle})")
                
                # Обнуляем системные переменные
                connector.doc.SetVariable("USERS1", "WAIT")
                connector.doc.SetVariable("USERS2", "WAIT")
                
                # Формируем AutoLISP код для Sheet и Drawing type
                lisp_code = f'(progn (setq ed (entget (handent "{obj.Handle}"))) (setq fsh nil fnm nil sh "Unknown" nm "Unknown") (foreach item ed (if (= (car item) 301) (cond ((= (cdr item) "Sheet") (setq fsh T fnm nil)) ((= (cdr item) "Drawing type") (setq fnm T fsh nil)) (T (setq fsh nil fnm nil)))) (if (= (car item) 300) (cond (fsh (setq sh (cdr item) fsh nil)) (fnm (setq nm (cdr item) fnm nil))))) (setvar "USERS1" (substr sh 1 250)) (setvar "USERS2" (substr nm 1 250)) (princ)) '
                
                print("Отправляем LISP-код в AutoCAD...")
                connector.doc.SendCommand(lisp_code + "\n")
                
                # Ждем ответа
                attempts = 0
                res1 = "WAIT"
                res2 = "WAIT"
                while attempts < 10:
                    time.sleep(0.2)
                    res1 = connector.doc.GetVariable("USERS1")
                    res2 = connector.doc.GetVariable("USERS2")
                    if res1 != "WAIT" and res2 != "WAIT":
                        break
                    attempts += 1
                
                if res1 == "WAIT":
                    print("AutoCAD не ответил вовремя. Попробуй запустить еще раз.")
                else:
                    name_clean = res2.replace("\r", " ").replace("\n", " ")
                    print(f"\n🎉 БИНГО! \nНомер листа: '{res1}' \nНазвание листа: '{name_clean}'")
                
                break # Только для первой рамки
                
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    test_spds_lisp_bridge()
