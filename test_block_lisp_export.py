import os
import sys
import time
import json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core.autocad_connector import AutoCADConnector
from parsers.block_parser import BlockParser


def test_block_lisp_export():
    print("=" * 60)
    print("ТЕСТ БЫСТРОГО ЭКСПОРТА РАМОК-БЛОКОВ ЧЕРЕЗ LISP")
    print("=" * 60)

    connector = AutoCADConnector()
    try:
        print("Подключение к AutoCAD...")
        connector.connect()
        doc_name = connector.get_active_document_name()
        print(f"Подключено к чертежу: {doc_name}")

        parser = BlockParser(
            block_names=["SHT_*", "Формат*", "*Рамка*", "*Штамп*", "A0*", "A1*", "A2*", "A3*", "A4*"],
            sheet_attr_tags=["SHEET", "ЛИСТ", "НОМЕР", "НОМЕР_ЛИСТА", "SH_NUM"]
        )

        print("\nЗапуск поиска блоков...")
        t_start = time.perf_counter()
        frames = parser.find_frames(connector.doc)
        t_elapsed = time.perf_counter() - t_start

        print(f"\n[OK] Поиск завершен за {t_elapsed:.3f} сек.")
        print(f"Найдено рамок-блоков: {len(frames)}")

        for i, f in enumerate(frames, 1):
            print("-" * 60)
            print(f"[{i:02d}] Лист: '{f.sheet_number}' | Имя: '{f.sheet_name}'")
            print(f"     Handle: {f.handle} | Формат: {f.paper_format}")
            w = abs(f.max_point[0] - f.min_point[0])
            h = abs(f.max_point[1] - f.min_point[1])
            print(f"     Габариты: {w:.1f} x {h:.1f}")

    except Exception as e:
        print(f"[ERROR] Исключение: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_block_lisp_export()
