@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate

REM Режим окна: --console (с консолью для тестов) или --windowed (чистое окно без консоли)
set WINDOW_MODE=--console

echo ========================================================
echo Сборка PrintPDF в dist\PrintPDF
echo Режим: %WINDOW_MODE%
echo ========================================================

python -m PyInstaller --noconfirm --clean ^
  --onedir ^
  %WINDOW_MODE% ^
  --name PrintPDF ^
  --icon autocad_to_pdf_icon.ico ^
  --paths . ^
  --collect-submodules ui ^
  --collect-submodules core ^
  --collect-submodules parsers ^
  --hidden-import win32timezone ^
  --add-data "core\lisp;core\lisp" ^
  --add-data "plotters;plotters" ^
  --add-data "config.json;." ^
  --add-data "autocad_to_pdf_icon.ico;." ^
  main.py

if %ERRORLEVEL% EQU 0 (
  echo.
  echo [УСПЕХ] Сборка завершена: dist\PrintPDF\PrintPDF.exe
) else (
  echo.
  echo [ОШИБКА] Сборка завершилась с ошибкой (%ERRORLEVEL%).
)
pause