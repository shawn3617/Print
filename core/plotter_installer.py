"""
Установка «своих» плоттеров PDF (pc3 + pmp) в AutoCAD пользователя.

Файлы лежат в папке plotters рядом с программой (в exe — внутри сборки),
по подпапкам версий AutoCAD — pc3 из новой версии старая НЕ читает
(«нераспознанная версия: не может быть прочитано»):
    plotters/2024/PDF_ГОСТ.pc3, PDF_ГОСТ.pmp   -> только в AutoCAD 2024
    plotters/2021/PDF_ГОСТ.pc3, PDF_ГОСТ.pmp   -> только в AutoCAD 2021
Ставятся только в ТОТ AutoCAD, к которому сейчас подключена программа.

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


# Внутренний номер версии AutoCAD -> год (имя подпапки в plotters/)
ACAD_YEARS = {
    "24.0": "2021", "24.1": "2022", "24.2": "2023", "24.3": "2024",
    "25.0": "2025", "25.1": "2026",
}


def _acad_year(app) -> str:
    """'2024' для AutoCAD 2024 и т.п.; '' если не удалось определить."""
    try:
        ver = str(app.Version)          # например '24.3s (LMS Tech)'
        return ACAD_YEARS.get(ver[:4], "")
    except Exception:
        return ""


def _acad_plotter_dirs(app) -> list:
    """Пары (папка pc3, папка pmp) из настроек запущенного AutoCAD."""
    pairs = []
    try:
        files = app.Preferences.Files
        pc3_dirs = _split_paths(files.PrinterConfigPath)
        try:
            pmp_dirs = _split_paths(files.PrinterDescPath)
        except Exception:
            pmp_dirs = []
        for d in pc3_dirs:
            # Пишем только в папку пользователя (Roaming), не в Program Files
            if "appdata" not in d.lower() or not os.path.isdir(d):
                continue
            pmp = next((p for p in pmp_dirs if "appdata" in p.lower()), os.path.join(d, "PMP Files"))
            pairs.append((d, pmp))
            break  # достаточно основной папки
    except Exception:
        pass
    return pairs


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
        if app is None:
            return installed
        year = _acad_year(app)
        if not year:
            print("[Плоттеры] Не удалось определить версию AutoCAD — установка пропущена")
            return installed
        src_dir = os.path.join(get_resource_path("plotters"), year)
        if not os.path.isdir(src_dir):
            # для этой версии AutoCAD своих плоттеров в программе нет — ничего не ставим
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
