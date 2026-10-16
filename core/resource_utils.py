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
