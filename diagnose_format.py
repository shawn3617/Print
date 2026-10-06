from core.autocad_connector import AutoCADConnector
from core.scanner import DocumentScanner
from core.models import detect_paper_format, GOST_FORMATS

connector = AutoCADConnector()
connector.connect()
print(f"Чертеж: {connector.get_active_document_name()}")

scanner = DocumentScanner()
frames = scanner.scan_document(connector.doc)

print(f"\nНайдено рамок: {len(frames)}")
for i, f in enumerate(frames):
    w = f.max_point[0] - f.min_point[0]
    h = f.max_point[1] - f.min_point[1]
    
    # Определяем масштаб вручную
    dims = [210, 297, 420, 594, 841, 1189]
    print(f"\n--- Рамка {i+1} ({f.source_type}) ---")
    print(f"  Размеры в ед. чертежа: {w:.1f} x {h:.1f}")
    print(f"  Определённый формат: {f.paper_format}")
    
    # Показываем все возможные масштабы
    print(f"  Варианты масштабов:")
    for d in dims:
        sw = w / d
        sh = h / d
        print(f"    {d}мм -> масштаб по W: {sw:.2f}, по H: {sh:.2f}")
    
    # Показываем реальные мм при разных масштабах
    for scale in [1, 10, 25, 50, 100, 200]:
        wm = w / scale
        hm = h / scale
        # Ищем ближайший формат
        best = "?"
        best_diff = 9999
        for fmt, (fw, fh) in GOST_FORMATS.items():
            d1 = abs(wm - fw) + abs(hm - fh)
            d2 = abs(wm - fh) + abs(hm - fw)
            d = min(d1, d2)
            if d < best_diff:
                best_diff = d
                best = fmt
        print(f"    Масштаб 1:{scale} -> {wm:.1f} x {hm:.1f} мм -> ближайший {best} (отклонение {best_diff:.1f}мм)")

connector.disconnect()
