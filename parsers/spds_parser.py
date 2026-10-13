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
                    
                    # Извлекаем номер листа, название, формат и масштаб через LISP-мост
                    sheet_number = "Unknown"
                    sheet_name = "Unknown"
                    raw_fmt = "Unknown"
                    raw_scale = "Unknown"
                    doc.SetVariable("USERS1", "WAIT")
                    doc.SetVariable("USERS2", "WAIT")
                    doc.SetVariable("USERS3", "WAIT")
                    doc.SetVariable("USERS4", "WAIT")
                    
                    lisp_code = (
                        f'(progn '
                        f'(setq ed (entget (handent "{obj.Handle}"))) '
                        f'(setq fsh nil fnm nil ffmt nil fsc nil) '
                        f'(setq sh "Unknown" nm "Unknown" fmt "Unknown" sc "Unknown") '
                        f'(foreach item ed '
                        f'(if (= (car item) 301) (cond '
                        f'((= (cdr item) "Sheet") (setq fsh T fnm nil ffmt nil fsc nil)) '
                        f'((= (cdr item) "Drawing type") (setq fnm T fsh nil ffmt nil fsc nil)) '
                        f'((member (strcase (cdr item)) \'("FORMAT" "ФОРМАТ" "SHEET FORMAT" "PAPER FORMAT" "ОБОЗНАЧЕНИЕ ФОРМАТА")) (setq ffmt T fsh nil fnm nil fsc nil)) '
                        f'((member (strcase (cdr item)) \'("SCALE" "МАСШТАБ" "SHEET SCALE" "VIEW SCALE")) (setq fsc T fsh nil fnm nil ffmt nil)) '
                        f'(T (setq fsh nil fnm nil ffmt nil fsc nil)))) '
                        f'(if (= (car item) 300) (cond '
                        f'(fsh (setq sh (cdr item) fsh nil)) '
                        f'(fnm (setq nm (cdr item) fnm nil)) '
                        f'(ffmt (setq fmt (cdr item) ffmt nil)) '
                        f'(fsc (setq sc (cdr item) fsc nil))))) '
                        f'(setvar "USERS1" (substr sh 1 250)) '
                        f'(setvar "USERS2" (substr nm 1 250)) '
                        f'(setvar "USERS3" (substr fmt 1 250)) '
                        f'(setvar "USERS4" (substr sc 1 250)) '
                        f'(princ)) '
                    )
                    doc.SendCommand(lisp_code + "\n")
                    
                    attempts = 0
                    while attempts < 15:
                        time.sleep(0.1)
                        res1 = doc.GetVariable("USERS1")
                        res2 = doc.GetVariable("USERS2")
                        res3 = doc.GetVariable("USERS3")
                        res4 = doc.GetVariable("USERS4")
                        if res1 != "WAIT" and res2 != "WAIT" and res3 != "WAIT" and res4 != "WAIT":
                            sheet_number = res1
                            sheet_name = res2.replace("\r", " ").replace("\n", " ") # Убираем переносы
                            raw_fmt = res3
                            raw_scale = res4
                            break
                        attempts += 1
                                
                    w = max_pt[0] - min_pt[0]
                    h = max_pt[1] - min_pt[1]
                    
                    # 1. Проверяем, удалось ли извлечь формат напрямую из свойств СПДС
                    detected_fmt = None
                    if raw_fmt and raw_fmt != "Unknown":
                        import re
                        from core.models import ALL_FORMATS
                        clean_fmt = raw_fmt.strip().upper().replace('А', 'A').replace('Х', 'X')
                        m_fmt = re.search(r'\b(A[0-4](?:X\d+)?)\b', clean_fmt)
                        if m_fmt and m_fmt.group(1) in ALL_FORMATS:
                            detected_fmt = m_fmt.group(1)
                            
                    # 2. Проверяем масштаб из СПДС
                    spds_scale = None
                    if raw_scale and raw_scale != "Unknown":
                        import re
                        m_sc = re.search(r'(?:1\s*:\s*)?(\d+(?:\.\d+)?)', raw_scale)
                        if m_sc:
                            try:
                                spds_scale = float(m_sc.group(1))
                            except:
                                pass
                                
                    # 3. Если формат не был указан строкой, определяем математически с учётом масштаба
                    if not detected_fmt:
                        detected_fmt = detect_paper_format(w, h, scale=spds_scale)

                    frame = Frame(
                        object_id=obj.ObjectID,
                        sheet_number=sheet_number,
                        sheet_name=sheet_name,
                        min_point=min_pt,
                        max_point=max_pt,
                        source_type="SPDS",
                        paper_format=detected_fmt,
                        handle=getattr(obj, 'Handle', '')
                    )
                    frames.append(frame)
                except Exception as e:
                    print(f"Ошибка при чтении СПДС объекта: {e}")
                        
        return frames
