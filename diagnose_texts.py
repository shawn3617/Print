from core.autocad_connector import AutoCADConnector
from parsers.polyline_parser import PolylineParser

def diagnose_text_coords():
    connector = AutoCADConnector()
    try:
        connector.connect()
        ms = connector.doc.ModelSpace
        parser = PolylineParser(target_layer="0000_Формат")
        
        # Найдем первую полилинию
        for i in range(ms.Count):
            obj = ms.Item(i)
            if getattr(obj, 'Layer', '').lower() == "0000_формат" and 'Polyline' in getattr(obj, 'EntityName', ''):
                min_pt, max_pt = obj.GetBoundingBox()
                br_x, br_y = max_pt[0], min_pt[1]
                width = max_pt[0] - min_pt[0]
                height = max_pt[1] - min_pt[1]
                scale = parser._get_scale(width, height)
                
                print(f"Масштаб чертежа: 1:{scale}")
                print(f"Правый нижний угол: X={br_x}, Y={br_y}")
                
                # Ищем все тексты
                print("\nКООРДИНАТЫ ТЕКСТОВ (отсчет в миллиметрах от правого нижнего угла):")
                print("X: минус означает 'влево', Y: плюс означает 'вверх'")
                print("-" * 70)
                
                for j in range(ms.Count):
                    t = ms.Item(j)
                    if getattr(t, 'Layer', '').lower() == "0000_формат" and getattr(t, 'EntityName', '') in ['AcDbText', 'AcDbMText']:
                        val = getattr(t, 'TextString', '').strip()
                        if val:
                            t_min, t_max = t.GetBoundingBox()
                            tx = (t_min[0] + t_max[0]) / 2
                            ty = (t_min[1] + t_max[1]) / 2
                            
                            # Переводим в мм от угла
                            dx = (tx - br_x) / scale
                            dy = (ty - br_y) / scale
                            
                            # Ограничим вывод только зоной штампа (200x100 мм)
                            if dx >= -200 and dy <= 100:
                                val_clean = val.replace('\r', ' ').replace('\n', ' ')[:30]
                                print(f"X: {dx:7.1f} мм | Y: {dy:5.1f} мм | Текст: {val_clean}")
                break
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    diagnose_text_coords()
