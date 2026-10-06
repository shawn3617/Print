from core.autocad_connector import AutoCADConnector
from parsers.block_parser import BlockParser

def run_test():
    connector = AutoCADConnector()
    try:
        # 1. Подключаемся к AutoCAD
        connector.connect()
        print(f"Подключено к чертежу: {connector.get_active_document_name()}")
        
        # 2. Получаем Model Space
        ms = connector.get_model_space()
        print(f"Объектов в пространстве модели: {ms.Count}")
        
        # 3. Настраиваем парсер блоков
        # ВНИМАНИЕ: укажи здесь маску имени блоков рамок из твоего чертежа
        target_block_name = "SHT_*" # Теперь мы можем использовать звездочку!
        attr_tag_name = "SHEET"     # Замени на тег атрибута с номером листа
        
        parser = BlockParser(
            block_names=[target_block_name], 
            sheet_attr_tags=[attr_tag_name]
        )
        
        # 4. Запускаем поиск
        print(f"\nИщем блоки с именем '{target_block_name}'...")
        frames = parser.find_frames(connector.doc)
        
        print(f"Найдено рамок (блоков): {len(frames)}")
        for i, frame in enumerate(frames):
            print(f"[{i+1}] Лист: {frame.sheet_number} | Имя: {frame.sheet_name} | Габариты: {frame.min_point} - {frame.max_point}")
            
    except Exception as e:
        print(f"Ошибка при выполнении: {e}")
    finally:
        connector.disconnect()

if __name__ == "__main__":
    run_test()
