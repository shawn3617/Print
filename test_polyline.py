from core.autocad_connector import AutoCADConnector
from parsers.polyline_parser import PolylineParser

def test_polyline_frames():
    connector = AutoCADConnector()
    try:
        connector.connect()
        print(f"Подключено к чертежу: {connector.get_active_document_name()}")
        
        # Слой из твоего сообщения
        layer_name = "0000_Формат"
        
        parser = PolylineParser(target_layer=layer_name)
        
        print(f"\nСканируем чертеж на полилинии со слоя '{layer_name}'...")
        frames = parser.find_frames(connector.doc)
        
        print(f"Найдено рамок (полилиний): {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"\n[{i+1}] Лист: {frame.sheet_number} | Имя: {frame.sheet_name} | Габариты: {frame.min_point} - {frame.max_point}")
            
            # Выводим весь текст, который попал в зону штампа, для отладки
            if hasattr(frame, '_debug_texts') and frame._debug_texts:
                print(f"    Тексты в зоне штампа: {frame._debug_texts}")
            else:
                print("    В нижнем правом углу тексты не найдены.")
            
    except Exception as e:
        print(f"Ошибка при выполнении: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    test_polyline_frames()
