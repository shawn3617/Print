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
import zlib
import struct
import re

from core.resource_utils import get_resource_path
from core.logger import log_info, log_warn, log_error


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


def _fix_pc3_pmp_reference(pc3_path: str, pmp_dir: str) -> bool:
    """
    Проверяет и исправляет абсолютный путь к .pmp файлу внутри .pc3.
    В AutoCAD в .pc3 зашит абсолютный путь (user_defined_model_pathname).
    При переносе профиля или работе с разных компьютеров путь становится недействительным,
    и AutoCAD перестает загружать форматы ГОСТ из .pmp файла.
    """
    if not os.path.isfile(pc3_path):
        return False

    try:
        with open(pc3_path, "rb") as f:
            data = f.read()

        prefix_v2 = b"PIAFILEVERSION_2.0,PC3VER1,compress\r\npmzlibcodec"
        prefix_v3 = b"PIAFILEVERSION_3.0,json"

        # 1. Формат AutoCAD 2021 (PC3VER1 со сжатием zlib)
        if data.startswith(prefix_v2) and len(data) > 60:
            body = data[60:]
            txt = zlib.decompress(body).decode("cp1251", errors="replace")
            m = re.search(r'user_defined_model_pathname="([^"\r\n]+)', txt)
            if not m:
                return False
            old_pmp = m.group(1).strip()
            pmp_name = os.path.basename(old_pmp)
            new_pmp = os.path.join(pmp_dir, pmp_name)

            if (not os.path.exists(old_pmp) or old_pmp.lower() != new_pmp.lower()) and os.path.exists(new_pmp):
                txt_new = txt.replace(f'user_defined_model_pathname="{old_pmp}', f'user_defined_model_pathname="{new_pmp}')
                decomp_new = txt_new.encode("cp1251", errors="replace")
                comp_new = zlib.compress(decomp_new)
                adler_new = zlib.adler32(comp_new)
                hdr_new = prefix_v2 + struct.pack("<III", adler_new, len(decomp_new), len(comp_new))
                with open(pc3_path, "wb") as f:
                    f.write(hdr_new + comp_new)
                print(f"[Плоттеры] Исправлен путь к PMP в {os.path.basename(pc3_path)}: {new_pmp}")
                return True

        # 2. Формат AutoCAD 2024+ (JSON)
        elif data.startswith(prefix_v3):
            txt = data.decode("utf-8", errors="replace")
            m = re.search(r'"user_defined_model_pathname"\s*:\s*"([^"\r\n]+)"', txt)
            if not m:
                return False
            old_pmp = m.group(1).replace(r"\\", "\\").strip()
            pmp_name = os.path.basename(old_pmp)
            new_pmp = os.path.join(pmp_dir, pmp_name)
            if (not os.path.exists(old_pmp) or old_pmp.lower() != new_pmp.lower()) and os.path.exists(new_pmp):
                escaped_new = new_pmp.replace("\\", "\\\\")
                escaped_old = m.group(1)
                txt_new = txt.replace(f'"user_defined_model_pathname" : "{escaped_old}"',
                                      f'"user_defined_model_pathname" : "{escaped_new}"')
                with open(pc3_path, "w", encoding="utf-8") as f:
                    f.write(txt_new)
                print(f"[Плоттеры] Исправлен путь к PMP в {os.path.basename(pc3_path)}: {new_pmp}")
                log_info(f"Исправлен путь к PMP в {os.path.basename(pc3_path)}: {new_pmp}", module="Plotters")
                return True
    except Exception as e:
        print(f"Предупреждение: не удалось проверить/исправить PMP путь в {pc3_path}: {e}")
        log_warn(f"Не удалось проверить/исправить PMP путь в {pc3_path}", exc=e, module="Plotters")
    return False


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
            log_info("Не удалось определить версию AutoCAD — установка пропущена", module="Plotters")
            return installed
        src_dir = os.path.join(get_resource_path("plotters"), year)
        if not os.path.isdir(src_dir):
            return installed
        pc3_files = glob.glob(os.path.join(src_dir, "*.pc3"))
        pmp_files = glob.glob(os.path.join(src_dir, "*.pmp"))
        if not pc3_files and not pmp_files:
            return installed

        for pc3_dir, pmp_dir in _acad_plotter_dirs(app):
            os.makedirs(pc3_dir, exist_ok=True)
            os.makedirs(pmp_dir, exist_ok=True)

            for f in pmp_files:
                try:
                    if _copy_if_needed(f, pmp_dir):
                        installed.append(os.path.join(pmp_dir, os.path.basename(f)))
                except Exception as e:
                    print(f"Предупреждение: не удалось установить {os.path.basename(f)} в {pmp_dir}: {e}")
                    log_warn(f"Не удалось установить {os.path.basename(f)} в {pmp_dir}", exc=e, module="Plotters")

            for f in pc3_files:
                try:
                    if _copy_if_needed(f, pc3_dir):
                        installed.append(os.path.join(pc3_dir, os.path.basename(f)))
                except Exception as e:
                    print(f"Предупреждение: не удалось установить {os.path.basename(f)} в {pc3_dir}: {e}")
                    log_warn(f"Не удалось установить {os.path.basename(f)} в {pc3_dir}", exc=e, module="Plotters")

            # Проверяем и правим пути к PMP для всех PC3 (включая скопированные и DWG To PDF)
            for f in os.listdir(pc3_dir):
                if f.lower().endswith(".pc3"):
                    _fix_pc3_pmp_reference(os.path.join(pc3_dir, f), pmp_dir)

        for path in installed:
            print(f"[Плоттеры] Установлен/обновлён: {path}")
            log_info(f"Установлен/обновлён плоттер: {path}", module="Plotters")
    except Exception as e:
        print(f"Предупреждение: установка плоттеров не удалась: {e}")
        log_warn("Установка плоттеров не удалась", exc=e, module="Plotters")
    return installed
