import os
import sys
import time
import json
import tempfile
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core.autocad_connector import AutoCADConnector
from core.models import detect_paper_format, ALL_FORMATS

def load_sanitized_spds_json(filepath: str):
    """Считывает JSON, заменяя спецсимволы AutoCAD (\\U+2205 и др.) на реальный Unicode и экранируя слэши"""
    with open(filepath, "r", encoding="cp1251") as f:
        text = f.read()
    import re
    # Заменяем автокадовские спецсимволы вида \U+2205 на реальный Unicode символ
    clean = re.sub(r'\\U\+([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), text)
    # Заменяем любые оставшиеся недопустимые обратные слэши на двойные
    clean = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', clean)
    return json.loads(clean)

def test_spds_lisp_export():
    print("=" * 60)
    print("ТЕСТ БЫСТРОГО ЭКСПОРТА СПДС РАМОК ЧЕРЕЗ LISP (SHEETS.lsp)")
    print("=" * 60)
    
    connector = AutoCADConnector()
    try:
        print("Подключение к AutoCAD...")
        connector.connect()
        doc_name = connector.get_active_document_name()
        print(f"Подключено к чертежу: {doc_name}")
        
        # Используем предсказуемый файл в папке проекта
        temp_json = os.path.abspath("spds_export_result.json")
        if os.path.exists(temp_json):
            try:
                os.remove(temp_json)
            except Exception:
                pass
                
        lisp_path = os.path.abspath("core/lisp/spds_export.lsp").replace("\\", "/")
        out_path = temp_json.replace("\\", "/")
        
        # Формируем команду вызова LISP (без управляющих символов \x1b, которые вызывают OLE ошибку)
        lisp_cmd = f'(progn (load "{lisp_path}") (sht-export-spds "{out_path}"))\n'
        
        print("\nЗапуск LISP-экспортера в AutoCAD...")
        t_start = time.perf_counter()
        connector.doc.SendCommand(lisp_cmd)
        
        # Ожидание создания файла
        data = None
        attempts = 0
        max_attempts = 300 # до 15 секунд с шагом 0.05с
        while attempts < max_attempts:
            time.sleep(0.05)
            if os.path.exists(temp_json) and os.path.getsize(temp_json) > 0:
                try:
                    data = load_sanitized_spds_json(temp_json)
                    break
                except (json.JSONDecodeError, PermissionError):
                    # Файл еще может дописываться AutoCAD
                    pass
            attempts += 1
            if attempts % 20 == 0:
                print(f"  Ожидание ответа от AutoCAD... ({attempts * 0.05:.1f} сек)")
            
        t_elapsed = time.perf_counter() - t_start
        
        if data is None:
            print(f"[ERROR] AutoCAD не вернул JSON файл за {t_elapsed:.2f} сек.")
            if os.path.exists(temp_json):
                print(f"Файл создан, но пуст или некорректен (размер: {os.path.getsize(temp_json)} байт).")
            else:
                print(f"Файл '{temp_json}' не был создан.")
            print("Возможные причины: в AutoCAD открыто модальное диалоговое окно или чертеж заблокирован.")
            return
            
        print(f"[OK] Экспорт завершен за {t_elapsed:.3f} сек.")
        print(f"Найдено СПДС рамок: {len(data)}")
        print("-" * 60)
        
        for idx, item in enumerate(data, 1):
            hdl = item.get("handle", "")
            num = item.get("sheet_number", "Unknown")
            name = item.get("sheet_name", "")
            raw_fmt = item.get("format", "")
            mult = item.get("multiplicity", 1)
            sc = item.get("scale", 1.0)
            ori = item.get("orientation", "")
            min_x, min_y = item.get("min_x", 0.0), item.get("min_y", 0.0)
            max_x, max_y = item.get("max_x", 0.0), item.get("max_y", 0.0)
            w = max_x - min_x
            h = max_y - min_y
            
            # Определение формата по геометрическим размерам и данным СПДС
            fmt_label = f"{raw_fmt}x{mult}" if mult > 1 else raw_fmt
            calc_fmt = detect_paper_format(w, h, scale=sc)
            
            print(f"[{idx:02d}] Лист: '{num}' | Имя: '{name}'")
            print(f"     Handle: {hdl} | Формат СПДС: {fmt_label} (Масштаб: 1:{sc:g}, Ориент: {ori})")
            print(f"     Габариты: {w:.1f} x {h:.1f} мм -> Определен формат: {calc_fmt}")
            print("-" * 60)
            
    except ConnectionError as e:
        print(f"[ERROR] {e}")
        print("Пожалуйста, откройте AutoCAD с чертежом, содержащим СПДС рамки, и запустите тест снова.")
    except Exception as e:
        print(f"[ERROR] Исключение: {e}")
    finally:
        connector.disconnect()
        # Файл spds_export_result.json оставляем на диске для визуальной проверки

if __name__ == "__main__":
    test_spds_lisp_export()
