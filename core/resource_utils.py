import os
import sys

def get_resource_path(relative_path: str) -> str:
    """
    Возвращает абсолютный путь к ресурсу (файлу LISP, иконке, шаблону).
    Корректно работает как при обычном запуске из исходников Python,
    так и при запуске из автономного исполняемого файла (.exe), созданного PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    full_path = os.path.join(base_dir, relative_path)
    return os.path.abspath(full_path).replace("\\", "/")


def get_lisp_path(relative_path: str) -> str:
    """
    Возвращает путь к LISP-файлу.
    Если рядом существует скомпилированный бинарный .fas, возвращает его;
    иначе возвращает исходный .lsp.
    """
    path = get_resource_path(relative_path)
    if path.lower().endswith(".lsp"):
        fas_candidate = path[:-4] + ".fas"
        if os.path.isfile(fas_candidate):
            return fas_candidate
    elif path.lower().endswith(".fas"):
        if os.path.isfile(path):
            return path
        lsp_candidate = path[:-4] + ".lsp"
        if os.path.isfile(lsp_candidate):
            return lsp_candidate
    return path
