import time
from typing import List, Any
from core.models import Frame, detect_paper_format
from parsers.base_parser import BaseParser

class SPDSParser(BaseParser):
    def __init__(self, spds_names: List[str] = None):
        """
        :param spds_names: Список имен EntityName объектов, которые считаются рамками (по умолчанию mcsDbObjectFormat)
        """
        self.spds_names = [name.lower() for name in (spds_names or ["mcsdbobjectformat", "spdbformat"])]

    def find_frames(self, doc: Any) -> List[Frame]:
        frames = []
        model_space = doc.ModelSpace
        
        for i in range(model_space.Count):
            obj = model_space.Item(i)
            
            # Проверяем EntityName объекта
            entity_name = getattr(obj, 'EntityName', '').lower()
            
            if entity_name in self.spds_names:
                try:
                    # Получаем габариты СПДС-рамки
                    min_pt, max_pt = obj.GetBoundingBox()
                    
                    # Извлекаем номер листа и название через LISP-мост
                    sheet_number = "Unknown"
                    sheet_name = "Unknown"
                    doc.SetVariable("USERS1", "WAIT")
                    doc.SetVariable("USERS2", "WAIT")
                    
                    lisp_code = f'(progn (setq ed (entget (handent "{obj.Handle}"))) (setq fsh nil fnm nil sh "Unknown" nm "Unknown") (foreach item ed (if (= (car item) 301) (cond ((= (cdr item) "Sheet") (setq fsh T fnm nil)) ((= (cdr item) "Drawing type") (setq fnm T fsh nil)) (T (setq fsh nil fnm nil)))) (if (= (car item) 300) (cond (fsh (setq sh (cdr item) fsh nil)) (fnm (setq nm (cdr item) fnm nil))))) (setvar "USERS1" (substr sh 1 250)) (setvar "USERS2" (substr nm 1 250)) (princ)) '
                    doc.SendCommand(lisp_code + "\n")
                    
                    attempts = 0
                    while attempts < 15:
                        time.sleep(0.1)
                        res1 = doc.GetVariable("USERS1")
                        res2 = doc.GetVariable("USERS2")
                        if res1 != "WAIT" and res2 != "WAIT":
                            sheet_number = res1
                            sheet_name = res2.replace("\r", " ").replace("\n", " ") # Убираем переносы
                            break
                        attempts += 1
                                
                    w = max_pt[0] - min_pt[0]
                    h = max_pt[1] - min_pt[1]
                    frame = Frame(
                        object_id=obj.ObjectID,
                        sheet_number=sheet_number,
                        sheet_name=sheet_name,
                        min_point=min_pt,
                        max_point=max_pt,
                        source_type="SPDS",
                        paper_format=detect_paper_format(w, h)
                    )
                    frames.append(frame)
                except Exception as e:
                    print(f"Ошибка при чтении СПДС объекта: {e}")
                        
        return frames
