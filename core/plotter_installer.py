"""
Установка «своих» плоттеров PDF (pc3 + pmp) в AutoCAD пользователя.

Файлы лежат в папке plotters рядом с программой (в exe — внутри сборки):
    plotters/PDF_ГОСТ.pc3   -> папка AutoCAD «Plotters»
    plotters/PDF_ГОСТ.pmp   -> папка AutoCAD «Plotters/PMP Files»

Копируются, если их нет у пользователя или они отличаются от тех, что в программе
(так у всех коллег одинаковые форматы, а твои обновления доходят до всех).
Старый файл перед заменой сохраняется рядом с расширением .bak.
"""
import os
import glob
import shutil
import filecmp

from core.resource_utils import get_resource_path


def _split_paths(value) -> list:
    return [p.strip() for p in str(value or "").split(";") if p.strip()]


def _acad_plotter_dirs(app=None) -> list:
    """Пары (папка pc3, папка pmp) для всех найденных AutoCAD."""
    pairs = []
    # 1. Пути из настроек запущенного AutoCAD — самые точные
    if app is not None:
        try:
            files = app.Preferences.Files
            pc3_dirs = _split_paths(files.PrinterConfigPath)
            try:
                pmp_dirs = _split_paths(files.PrinterDescPath)
            except Exception:
                pmp_dirs = []
            for d in pc3_dirs:
                pmp = pmp_dirs[0] if pmp_dirs else os.path.join(d, "PMP Files")
                pairs.append((d, pmp))
        except Exception:
            pass
    # 2. Все установленные версии AutoCAD у пользователя (2021, 2024 и т.д.)
    for d in glob.glob(os.path.expandvars(r"%APPDATA%\Autodesk\AutoCAD*\*\*\Plotters")):
        pairs.append((d, os.path.join(d, "PMP Files")))

    seen, result = set(), []
    for pc3, pmp in pairs:
        key = os.path.normcase(os.path.abspath(pc3))
        if key not in seen and os.path.isdir(pc3):
            seen.add(key)
            result.append((pc3, pmp))
    return result


def _copy_if_needed(src: str, dst_dir: str) -> bool:
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst) and filecmp.cmp(src, dst, shallow=False):
        return False
    if os.path.exists(dst):
        try:
            shutil.copy2(dst, dst + ".bak")
        except Exception:
            pass
    shutil.copy2(src, dst)
    return True


def install_bundled_plotters(app=None) -> list:
    """
    Копирует плоттеры из папки программы plotters/ в AutoCAD.
    Возвращает список установленных/обновлённых файлов (пустой — всё уже на месте).
    Ошибки не роняют программу — только сообщение в консоль.
    """
    installed = []
    try:
        src_dir = get_resource_path("plotters")
        if not os.path.isdir(src_dir):
            return installed
        pc3_files = glob.glob(os.path.join(src_dir, "*.pc3"))
        pmp_files = glob.glob(os.path.join(src_dir, "*.pmp"))
        if not pc3_files and not pmp_files:
            return installed

        for pc3_dir, pmp_dir in _acad_plotter_dirs(app):
            for f in pc3_files:
                try:
                    if _copy_if_needed(f, pc3_dir):
                        installed.append(os.path.join(pc3_dir, os.path.basename(f)))
                except Exception as e:
                    print(f"Предупреждение: не удалось установить {os.path.basename(f)} в {pc3_dir}: {e}")
            for f in pmp_files:
                try:
                    if _copy_if_needed(f, pmp_dir):
                        installed.append(os.path.join(pmp_dir, os.path.basename(f)))
                except Exception as e:
                    print(f"Предупреждение: не удалось установить {os.path.basename(f)} в {pmp_dir}: {e}")

        for path in installed:
            print(f"[Плоттеры] Установлен/обновлён: {path}")
    except Exception as e:
        print(f"Предупреждение: установка плоттеров не удалась: {e}")
    return installed
