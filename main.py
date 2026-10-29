import os
import sys

# Обеспечиваем корректное добавление корневой папки в sys.path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QIcon

from ui.main_window import PrintManagerUI
from core.resource_utils import get_resource_path


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))

    icon_path = get_resource_path("autocad_to_pdf_icon.ico")
    if os.path.exists(icon_path):
        app_icon = QIcon(icon_path)
        app.setWindowIcon(app_icon)

    window = PrintManagerUI()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
