from core.models import detect_paper_format, Frame, ALL_FORMATS
from core.scanner import DocumentScanner
from collections import Counter

def run_tests():
    print("=== ТЕСТ 1: Одиночное определение форматов ===")
    test_cases = [
        (29700, 21000, "", None, "A4"),   # A4 в масштабе 1:100
        (59400, 42000, "", None, "A2"),   # A2 в масштабе 1:100
        (42000, 29700, "", None, "A3"),   # A3 в масштабе 1:100
        (84100, 59400, "", None, "A1"),   # A1 в масштабе 1:100
        (118900, 84100, "", None, "A0"),  # A0 в масштабе 1:100
        (297, 210, "", None, "A4"),       # A4 в масштабе 1:1
        (594, 420, "", None, "A2"),       # A2 в масштабе 1:1
        (14850, 10500, "", 50.0, "A4"),   # A4 в масштабе 1:50 с переданным масштабом
        (29700, 21000, "", 100.0, "A4"),  # A4 в масштабе 1:100 с переданным масштабом
        (59400, 42000, "", 100.0, "A2"),  # A2 в масштабе 1:100 с переданным масштабом
    ]
    
    all_passed = True
    for w, h, blk, sc, expected in test_cases:
        actual = detect_paper_format(w, h, blk, scale=sc)
        passed = (actual == expected)
        all_passed = all_passed and passed
        status = "OK" if passed else f"FAIL (получено {actual})"
        print(f"  {w} x {h} (scale={sc}) -> ожидалось {expected}: {status}")
        
    print("\n=== ТЕСТ 2: Согласование масштабов чертежа (6 листов A2 + 2 листа A4) ===")
    # Моделируем ситуацию пользователя: 6 листов A2 и 2 листа A4 в пространстве модели (1:100)
    mock_frames = []
    # 6 листов A2
    for i in range(1, 7):
        mock_frames.append(Frame(
            object_id=i,
            sheet_number=str(i),
            sheet_name=f"План {i}",
            min_point=(0, 0, 0),
            max_point=(59400, 42000, 0),
            source_type="SPDS",
            paper_format="A2" # 59400 x 42000 -> A2
        ))
    # 2 листа A4 (даже если какой-то парсер изначально вернул A2)
    for i in range(7, 9):
        mock_frames.append(Frame(
            object_id=i,
            sheet_number=str(i),
            sheet_name=f"Спецификация {i}",
            min_point=(0, 0, 0),
            max_point=(21000, 29700, 0),
            source_type="SPDS",
            paper_format="A2" # Ошибка старого алгоритма
        ))
        
    # Применяем логику DocumentScanner
    scales = []
    for f in mock_frames:
        fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
        w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
        sc = round(w / fw)
        if sc > 0:
            scales.append(sc)
            
    common_scale, count = Counter(scales).most_common(1)[0]
    print(f"  Обнаружен доминирующий масштаб: 1:{common_scale} (для {count} из {len(mock_frames)} рамок)")
    
    for f in mock_frames:
        fw, fh = ALL_FORMATS.get(f.paper_format, (594, 420))
        w = max(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
        h = min(abs(f.max_point[0] - f.min_point[0]), abs(f.max_point[1] - f.min_point[1]))
        if round(w / fw) != common_scale:
            f.paper_format = detect_paper_format(w, h, scale=common_scale)
            
    res_a2 = sum(1 for f in mock_frames if f.paper_format == "A2")
    res_a4 = sum(1 for f in mock_frames if f.paper_format == "A4")
    print(f"  Результат после согласования: A2={res_a2} шт., A4={res_a4} шт.")
    assert res_a2 == 6, f"Ожидалось 6 листов A2, получено {res_a2}"
    assert res_a4 == 2, f"Ожидалось 2 листа A4, получено {res_a4}"
    print("  Тест согласования: OK!")
    
    if all_passed:
        print("\n ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")

if __name__ == "__main__":
    run_tests()
