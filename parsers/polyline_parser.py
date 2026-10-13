from typing import List, Any
from core.models import Frame, detect_paper_format
from parsers.base_parser import BaseParser

class PolylineParser(BaseParser):
    def __init__(self, target_layer: str = "0000_Формат"):
        """
        :param target_layer: Имя слоя, на котором лежат рамки и тексты
        """
        self.target_layer = target_layer.lower()

    def _get_scale(self, width: float, height: float) -> float:
        """Определяет масштаб рамки на основе стандартных ГОСТ форматов (в мм)"""
        dims = [210, 297, 420, 594, 841, 1189]
        best_scale = 1.0
        min_diff = float('inf')
        for d in dims:
            for actual in (width, height):
                scale = actual / d
                diff = abs(round(scale) - scale)
                if diff < 0.05 and diff < min_diff:
                    min_diff = diff
                    best_scale = round(scale)
        return max(1.0, float(best_scale))

    def find_frames(self, doc: Any) -> List[Frame]:
        frames = []
        model_space = doc.ModelSpace
        
        # 1. Собираем все полилинии и тексты с нужного слоя за один проход
        polylines = []
        texts = []
        
        for i in range(model_space.Count):
            obj = model_space.Item(i)
            layer = getattr(obj, 'Layer', '').lower()
            
            if layer == self.target_layer:
                ent_name = getattr(obj, 'EntityName', '')
                # Замкнутые рамки это обычно AcDbPolyline
                if 'Polyline' in ent_name:
                    polylines.append(obj)
                elif ent_name in ['AcDbText', 'AcDbMText']:
                    texts.append(obj)
                    
        # 2. Обрабатываем каждую полилинию как отдельную рамку
        for poly in polylines:
            try:
                min_pt, max_pt = poly.GetBoundingBox()
                # Правый нижний угол рамки (базовая точка штампа)
                br_x = max_pt[0]
                br_y = min_pt[1]
                
                # Вычисляем размеры рамки (ширину и высоту)
                width = max_pt[0] - min_pt[0]
                height = max_pt[1] - min_pt[1]
                
                sheet_number = "Unknown"
                stamp_texts = []
                # Сохраняем не только строки, но и сами COM-объекты текста для точного поиска
                texts_in_zone = []
                
                # Пространственный поиск текста штампа
                for text_obj in texts:
                    try:
                        # Получаем реальные габариты текста, чтобы избежать проблем с выравниванием (Alignment)
                        t_min, t_max = text_obj.GetBoundingBox()
                        # Вычисляем геометрический центр текста
                        tx = (t_min[0] + t_max[0]) / 2
                        ty = (t_min[1] + t_max[1]) / 2
                        
                        search_width = width * 0.35
                        search_height = height * 0.35
                        
                        if (br_x - search_width) <= tx <= br_x and br_y <= ty <= (br_y + search_height):
                            val = getattr(text_obj, 'TextString', '').strip()
                            if val:
                                stamp_texts.append(val)
                                texts_in_zone.append({
                                    'obj': text_obj,
                                    'text': val,
                                    'x': tx,
                                    'y': ty
                                })
                    except:
                        pass
                
                # Умная логика поиска номера листа (ГОСТ штамп)
                # 1. Находим слово "Лист"
                list_texts = [t for t in texts_in_zone if t['text'].lower() == 'лист']
                
                if list_texts:
                    # Нам нужен тот "Лист", который правее (с максимальным X)
                    rightmost_list = max(list_texts, key=lambda t: t['x'])
                    lx, ly = rightmost_list['x'], rightmost_list['y']
                    
                    # 2. По ГОСТу номер листа пишется СНИЗУ под словом "Лист" в той же колонке.
                    candidates = []
                    x_tolerance = width * 0.02 # Допуск по ширине колонки (примерно 12-15 мм)
                    
                    for t in texts_in_zone:
                        tx, ty, val = t['x'], t['y'], t['text']
                        
                        # Если X примерно равен X "Листа", а Y меньше Y "Листа" (ниже)
                        if val.lower() not in ['лист', 'листов'] and abs(tx - lx) < x_tolerance and ty < ly:
                            candidates.append(t)
                            
                    if candidates:
                        # Берем тот текст, который ближе всего СНИЗУ к заголовку "Лист" (максимальный Y)
                        closest = max(candidates, key=lambda t: t['y'])
                        sheet_number = closest['text']
                        
                # 3. Находим название листа в жестких координатах ГОСТ штампа
                # Судя по диагностике, текст лежит на X = -45.0 мм, Y = 6.1 мм.
                scale = self._get_scale(width, height)
                sheet_name = "Unknown"
                name_texts = []
                
                # Зона поиска: X от -65мм до -25мм (избегаем даты на -65 и столбца 'Стадия' на -23)
                # Y от 2мм до 25мм (чтобы захватить многострочный текст)
                for t in texts_in_zone:
                    tx, ty, val = t['x'], t['y'], t['text']
                    if (br_x - 65 * scale) <= tx <= (br_x - 25 * scale) and (br_y + 2 * scale) <= ty <= (br_y + 25 * scale):
                        if val and val.lower() not in ['стадия', 'р', 'п', 'дата']: # Исключаем служебные слова
                            name_texts.append((ty, val)) # Сохраняем с координатой Y для сортировки
                            
                if name_texts:
                    # Сортируем тексты сверху вниз (от большего Y к меньшему) для многострочных названий
                    name_texts.sort(key=lambda x: x[0], reverse=True)
                    sheet_name = " ".join([txt for y, txt in name_texts])
                            
                scale = self._get_scale(width, height)
                frame = Frame(
                    object_id=poly.ObjectID,
                    sheet_number=sheet_number,
                    sheet_name=sheet_name,
                    min_point=min_pt,
                    max_point=max_pt,
                    source_type="Polyline",
                    paper_format=detect_paper_format(width, height, scale=scale),
                    handle=getattr(poly, 'Handle', '')
                )
                
                # Сохраним найденные тексты прямо в объект для отладки
                frame._debug_texts = stamp_texts
                
                frames.append(frame)
                
            except Exception as e:
                print(f"Ошибка при обработке полилинии: {e}")
                
        return frames
