@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate

python -m pip install --upgrade pyinstaller

python -m PyInstaller --noconfirm --clean ^
  --onedir ^
  --name PrintPDF ^
  --icon autocad_to_pdf_icon.ico ^
  --paths . ^
  --collect-submodules ui ^
  --collect-submodules core ^
  --collect-submodules parsers ^
  --add-data "core\lisp;core\lisp" ^
  --add-data "plotters;plotters" ^
  --add-data "config.json;." ^
  --add-data "autocad_to_pdf_icon.ico;." ^
  run_app.py

echo.
echo Готово: dist\PrintPDF\PrintPDF.exe
pause
