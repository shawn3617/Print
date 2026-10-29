import sys
import ctypes

# Гарантируем вывод в utf-8
sys.stdout.reconfigure(encoding='utf-8')

# При необходимости переключаем поток на интерактивный рабочий стол Default
try:
    user32 = ctypes.windll.user32
    hdesk = user32.OpenDesktopW('Default', 0, False, 0x10000000)
    if hdesk:
        user32.SetThreadDesktop(hdesk)
except Exception:
    pass

from core.autocad_connector import AutoCADConnector
from core.models import ALL_FORMATS
from parsers.polyline_parser import match_candidates, _clean_text

def diagnose():
    connector = AutoCADConnector()
    try:
        connector.connect()
        doc = connector.doc
        print(f"=== Активный чертеж: {connector.get_active_document_name()} ===")
        ms = doc.ModelSpace
        total_objs = ms.Count
        print(f"Всего объектов в ModelSpace: {total_objs}")

        # Соберем все полилинии
        polys = []
        for i in range(total_objs):
            try:
                obj = ms.Item(i)
                ent = getattr(obj, 'EntityName', '')
                if 'Polyline' in ent:
                    mn, mx = obj.GetBoundingBox()
                    w = mx[0] - mn[0]
                    h = mx[1] - mn[1]
                    cands = match_candidates(w, h)
                    polys.append({
                        "obj": obj,
                        "layer": getattr(obj, 'Layer', ''),
                        "handle": getattr(obj, 'Handle', ''),
                        "bbox": (mn[0], mn[1], mx[0], mx[1]),
                        "w": w, "h": h,
                        "cands": cands
                    })
            except Exception:
                continue

        print(f"\nНайдено полилиний: {len(polys)}")
        frame_candidates = [p for p in polys if p["cands"]]
        print(f"Из них похожи на рамки ГОСТ: {len(frame_candidates)}")

        if not frame_candidates:
            print("\nВнимание: ни одна полилиния не распознана как ГОСТ-формат по match_candidates!")
            print("Выводим самые большие полилинии:")
            for p in sorted(polys, key=lambda x: -x["w"]*x["h"])[:5]:
                print(f"  Слой: {p['layer']}, W={p['w']:.1f}, H={p['h']:.1f}, BBox={p['bbox']}")
            # Будем использовать самую большую как кандидат
            if polys:
                frame_candidates = [sorted(polys, key=lambda x: -x["w"]*x["x"] if "x" in x else -x["w"]*x["h"])[0]]

        for idx, fc in enumerate(frame_candidates):
            c = fc["cands"][0] if fc["cands"] else {"scale": 1.0, "format": "Unknown", "kind": "outer"}
            scale = c["scale"]
            fmt = c.get("format", "Unknown")
            kind = c.get("kind", "outer")
            bb = fc["bbox"]
            print(f"\n--- Рамка #{idx+1} ---")
            print(f"Слой рамки: {fc['layer']}")
            print(f"Формат: {fmt}, масштаб 1:{scale}, тип: {kind}")
            print(f"Габариты: {fc['w']:.1f} x {fc['h']:.1f} (в мм листа: {fc['w']/scale:.1f} x {fc['h']/scale:.1f})")
            print(f"BBox: X=[{bb[0]:.1f} .. {bb[2]:.1f}], Y=[{bb[1]:.1f} .. {bb[3]:.1f}]")

            # Правый нижний угол
            # Если это внутренняя рамка, угол прямо (bb[2], bb[1])
            # Если внешняя, правый нижний угол внутренней рамки отступает на 5 мм слева/снизу
            if kind == "inner":
                ax, ay = bb[2], bb[1]
            else:
                ax, ay = bb[2] - 5.0 * scale, bb[1] + 5.0 * scale

            print(f"Опорный угол штампа (X, Y): ({ax:.1f}, {ay:.1f})")

            # Теперь ищем ВСЕ объекты на ЛЮБЫХ слоях в окрестности штампа
            # Штамп формы 3: 185 мм влево, 55 мм вверх (возьмем запас: -220..10 мм, -10..80 мм)
            print("\nОбъекты в зоне штампа (отсчет в мм от угла внутренней рамки: X<0 влево, Y>0 вверх):")
            print(f"{'Тип':<12} | {'Слой':<16} | {'X (мм)':<8} | {'Y (мм)':<8} | Текст / Информация")
            print("-" * 80)

            found_items = 0
            for i in range(total_objs):
                try:
                    obj = ms.Item(i)
                    ent = getattr(obj, 'EntityName', '')
                    layer = getattr(obj, 'Layer', '')

                    if ent in ('AcDbText', 'AcDbMText'):
                        t_min, t_max = obj.GetBoundingBox()
                        tx = (t_min[0] + t_max[0]) / 2
                        ty = (t_min[1] + t_max[1]) / 2
                        dx = (tx - ax) / scale
                        dy = (ty - ay) / scale
                        if -220 <= dx <= 15 and -10 <= dy <= 90:
                            val = _clean_text(getattr(obj, 'TextString', ''))
                            print(f"{ent:<12} | {layer:<16} | {dx:8.1f} | {dy:8.1f} | {val}")
                            found_items += 1

                    elif ent == 'AcDbBlockReference':
                        mn, mx = obj.GetBoundingBox()
                        bx = (mn[0] + mx[0]) / 2
                        by = (mn[1] + mx[1]) / 2
                        dx = (bx - ax) / scale
                        dy = (by - ay) / scale
                        if -220 <= dx <= 15 and -10 <= dy <= 90:
                            blk_name = getattr(obj, 'EffectiveName', getattr(obj, 'Name', ''))
                            print(f"{'Блок ' + blk_name:<12} | {layer:<16} | {dx:8.1f} | {dy:8.1f} | (Блок в штампе)")
                            found_items += 1
                            if obj.HasAttributes:
                                for att in obj.GetAttributes():
                                    tag = att.TagString
                                    val = att.TextString
                                    at_min, at_max = att.GetBoundingBox()
                                    atx = (at_min[0] + at_max[0]) / 2
                                    aty = (at_min[1] + at_max[1]) / 2
                                    adx = (atx - ax) / scale
                                    ady = (aty - ay) / scale
                                    print(f"  атрибут    | {att.Layer:<16} | {adx:8.1f} | {ady:8.1f} | [{tag}] = {val}")
                except Exception:
                    continue

            if found_items == 0:
                print("  (В указанной зоне штампа тексты не обнаружены)")

    except Exception as e:
        print(f"Ошибка при диагностике: {e}")
        import traceback
        traceback.print_exc()
    finally:
        connector.disconnect()

if __name__ == "__main__":
    diagnose()
