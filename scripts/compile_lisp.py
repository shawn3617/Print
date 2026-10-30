"""
Скрипт компиляции исходных AutoLISP-файлов (.lsp) в защищенный бинарный байткод (.fas).
Использует автономный консольный движок AutoCAD (accoreconsole.exe) или активный AutoCAD через COM.
"""

import os
import sys
import subprocess
import tempfile
import winreg
from typing import Optional, List

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def find_accoreconsoles() -> List[str]:
    """Ищет все доступные accoreconsole.exe через реестр Windows и стандартные пути установки AutoCAD."""
    found = []

    # 1. Сначала проверяем современные версии в Program Files в порядке убывания
    candidate_dirs = [
        r"C:\Program Files\Autodesk\AutoCAD 2025",
        r"C:\Program Files\Autodesk\AutoCAD 2024",
        r"C:\Program Files\Autodesk\AutoCAD 2023",
        r"C:\Program Files\Autodesk\AutoCAD 2022",
        r"C:\Program Files\Autodesk\AutoCAD 2021",
        r"C:\Program Files\Autodesk\AutoCAD 2020",
    ]
    for d in candidate_dirs:
        exe = os.path.join(d, "accoreconsole.exe")
        if os.path.isfile(exe) and exe not in found:
            found.append(exe)

    # 2. Поиск через реестр HKLM\SOFTWARE\Autodesk\AutoCAD
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Autodesk\AutoCAD") as root_key:
            num_subkeys = winreg.QueryInfoKey(root_key)[0]
            for i in range(num_subkeys):
                ver_name = winreg.EnumKey(root_key, i)
                try:
                    with winreg.OpenKey(root_key, ver_name) as ver_key:
                        num_prods = winreg.QueryInfoKey(ver_key)[0]
                        for j in range(num_prods):
                            prod_name = winreg.EnumKey(ver_key, j)
                            try:
                                with winreg.OpenKey(ver_key, prod_name) as prod_key:
                                    loc, _ = winreg.QueryValueEx(prod_key, "AcadLocation")
                                    if loc and os.path.isdir(loc):
                                        exe = os.path.join(loc, "accoreconsole.exe")
                                        if os.path.isfile(exe) and exe not in found:
                                            found.append(exe)
                            except OSError:
                                pass
                except OSError:
                    pass
    except OSError:
        pass

    return found


def compile_via_accoreconsole(accoreconsole_path: str, files_to_compile: List[tuple]) -> bool:
    """Компилирует список пар (src_lsp, dst_fas) через accoreconsole.exe."""
    commands = [
        "(vl-load-com)",
        '(setvar "CMDECHO" 0)',
        '(setvar "SECURELOAD" 0)',
    ]

    for src_lsp, dst_fas in files_to_compile:
        src_norm = src_lsp.replace("\\", "/")
        dst_norm = dst_fas.replace("\\", "/")
        commands.append(f'(setq res (vlisp-compile \'st "{src_norm}" "{dst_norm}"))')
        commands.append(f'(if res (princ "\\nCOMPILED_OK: {dst_norm}\\n") (princ "\\nCOMPILED_FAIL: {dst_norm}\\n"))')

    commands.append("QUIT\n")
    script_content = "\n".join(commands)

    with tempfile.NamedTemporaryFile("w", suffix=".scr", delete=False, encoding="ascii") as f:
        f.write(script_content)
        scr_path = f.name

    try:
        # Удаляем старые .fas перед компиляцией для чистоты проверки
        for _, dst_fas in files_to_compile:
            if os.path.exists(dst_fas):
                try:
                    os.remove(dst_fas)
                except OSError:
                    pass

        cmd = [accoreconsole_path, "/s", scr_path]
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
        raw = proc.stdout + proc.stderr
        if b"\x00" in raw:
            output = raw.decode("utf-16le", errors="ignore")
        else:
            output = raw.decode("utf-8", errors="ignore")

        all_ok = True
        for _, dst_fas in files_to_compile:
            dst_norm = dst_fas.replace("\\", "/")
            if (f"COMPILED_OK: {dst_norm}" in output or "FASDUMPING" in output) and os.path.isfile(dst_fas) and os.path.getsize(dst_fas) > 0:
                print(f"[OK] Скомпилирован: {os.path.basename(dst_fas)} ({os.path.getsize(dst_fas)} байт)")
            else:
                all_ok = False
        if not all_ok:
            print("[DEBUG accoreconsole output]:\n", output)
        return all_ok
    except Exception as e:
        print(f"[ERROR] Сбой выполнения accoreconsole: {e}")
        return False
    finally:
        if os.path.exists(scr_path):
            try:
                os.remove(scr_path)
            except OSError:
                pass


def compile_via_active_autocad(files_to_compile: List[tuple]) -> bool:
    """Резервный метод: компиляция через активный процесс AutoCAD по COM."""
    try:
        import win32com.client
        acad = win32com.client.GetActiveObject("AutoCAD.Application")
        doc = acad.ActiveDocument
        if not doc:
            print("[WARN] В активном AutoCAD нет открытого документа для компиляции.")
            return False

        all_ok = True
        for src_lsp, dst_fas in files_to_compile:
            src_norm = src_lsp.replace("\\", "/")
            dst_norm = dst_fas.replace("\\", "/")
            cmd = f'(progn (vl-load-com) (vlisp-compile \'st "{src_norm}" "{dst_norm}"))\n'
            doc.SendCommand(cmd)
            # Даем небольшую паузу на запись файла
            import time
            time.sleep(0.5)
            if os.path.isfile(dst_fas):
                print(f"[OK] Скомпилирован через активный AutoCAD: {os.path.basename(dst_fas)}")
            else:
                all_ok = False
        if not all_ok:
            print("[DEBUG accoreconsole output]:\n", output)
        return all_ok
    except Exception as e:
        print(f"[WARN] Не удалось скомпилировать через активный AutoCAD COM: {e}")
        return False


def main() -> int:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    lisp_dir = os.path.join(base_dir, "core", "lisp")

    files_to_compile = [
        (os.path.join(lisp_dir, "spds_export.lsp"), os.path.join(lisp_dir, "spds_export.fas")),
        (os.path.join(lisp_dir, "block_export.lsp"), os.path.join(lisp_dir, "block_export.fas")),
    ]

    print("========================================================")
    print("Компиляция AutoLISP-скриптов в бинарные .fas")
    print("========================================================")

    for src, _ in files_to_compile:
        if not os.path.isfile(src):
            print(f"[ERROR] Исходный файл не найден: {src}")
            return 1

    consoles = find_accoreconsoles()
    for accoreconsole in consoles:
        print(f"Пробуем компилятор AutoCAD: {accoreconsole}")
        if compile_via_accoreconsole(accoreconsole, files_to_compile):
            print("[УСПЕХ] Все LISP-файлы успешно скомпилированы в .fas!")
            return 0

    print("Ни один accoreconsole не сработал, пробуем через активный AutoCAD...")
    if compile_via_active_autocad(files_to_compile):
        print("[УСПЕХ] Все LISP-файлы скомпилированы через активный AutoCAD!")
        return 0

    # Если уже есть готовые .fas, не ломаем сборку
    existing_fas = [dst for _, dst in files_to_compile if os.path.isfile(dst)]
    if len(existing_fas) == len(files_to_compile):
        print("[INFO] Не удалось перекомпилировать, но существующие .fas файлы найдены и будут использованы.")
        return 0

    print("[ERROR] Не удалось скомпилировать LISP-файлы в .fas!")
    return 1


if __name__ == "__main__":
    sys.exit(main())
