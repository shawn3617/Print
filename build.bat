@echo off
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate

REM Режим окна: --windowed (чистый релиз без консоли) или --console (с консолью для отладки)
set WINDOW_MODE=--windowed
REM Версия программы — единственный источник core\version.py (здесь не менять)
set "APP_VER="
for /f "delims=" %%V in ('python -c "from core.version import APP_VERSION; print(APP_VERSION)"') do set "APP_VER=%%V"
if "%APP_VER%"=="" (
  echo [ОШИБКА] Не удалось прочитать версию из core\version.py
  pause
  exit /b 1
)

echo ========================================================
echo Сборка релизного дистрибутива PrintPDF v%APP_VER%
echo ========================================================

REM Поиск компилятора Inno Setup 6 (ISCC.exe)
set "ISCC_EXE="
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe" set "ISCC_EXE=%LOCALAPPDATA%\Programs\Antigravity IDE\resources\app\node_modules\innosetup\bin\ISCC.exe"

if "%ISCC_EXE%"=="" (
  for /f "delims=" %%I in ('where iscc 2^>nul') do set "ISCC_EXE=%%I"
)

echo.
echo ========================================================
echo Шаг 1/5: Компиляция AutoLISP в защищенные бинарники .fas
echo ========================================================
python scripts\compile_lisp.py
if %ERRORLEVEL% NEQ 0 (
  echo [ПРЕДУПРЕЖДЕНИЕ] Компиляция LISP завершилась с кодом %ERRORLEVEL%. Проверяем готовые fas...
)

echo.
echo ========================================================
echo Шаг 2/5: Сборка автономного приложения PyInstaller
echo Режим окна: %WINDOW_MODE%
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

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ОШИБКА] Сборка PyInstaller завершилась с ошибкой %ERRORLEVEL%.
  pause
  exit /b %ERRORLEVEL%
)

REM В дистрибутив входят как .fas (приоритет), так и .lsp (резерв при несовпадении версий AutoCAD)
if exist "core\lisp\*.lsp" (
  copy /y "core\lisp\*.lsp" "dist\PrintPDF\_internal\core\lisp\" >nul
)

REM Добавляем инструкцию по запуску в папку дистрибутива
if exist "ИНСТРУКЦИЯ_ПО_ЗАПУСКУ.txt" (
  copy /y "ИНСТРУКЦИЯ_ПО_ЗАПУСКУ.txt" "dist\PrintPDF\" >nul
)

echo.
echo ========================================================
echo Шаг 3/5: Создание Portable ZIP-архива для коллег
echo ========================================================
python -c "import shutil; shutil.make_archive('dist/PrintPDF_v%APP_VER%_Portable', 'zip', 'dist', 'PrintPDF')"
if %ERRORLEVEL% EQU 0 (
  echo [OK] Создан портативный архив: dist\PrintPDF_v%APP_VER%_Portable.zip
) else (
  echo [ПРЕДУПРЕЖДЕНИЕ] Не удалось создать ZIP-архив.
)

echo.
echo ========================================================
echo Шаг 4/5: Сборка инсталлятора Windows Inno Setup
echo ========================================================

if "%ISCC_EXE%"=="" (
  echo [ПРЕДУПРЕЖДЕНИЕ] Компилятор Inno Setup не найден. Создание инсталлятора пропущено.
) else (
  echo Используется компилятор: "%ISCC_EXE%"
  "%ISCC_EXE%" /DMyAppVersion=%APP_VER% "installer\setup.iss"
  if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ОШИБКА] Не удалось собрать инсталлятор Inno Setup. Код ошибки: %ERRORLEVEL%
    goto END
  )
)

echo.
echo ========================================================
echo Шаг 5/5: Цифровая подпись исполняемых файлов (Authenticode)
echo ========================================================
python scripts\sign_binary.py "dist\PrintPDF\PrintPDF.exe" "dist\PrintPDF_Setup_v%APP_VER%.exe"
if %ERRORLEVEL% NEQ 0 (
  echo [ПРЕДУПРЕЖДЕНИЕ] Ошибки при цифровой подписи файлов.
)

echo.
echo ========================================================
echo [УСПЕХ] Полный цикл сборки успешно завершен!
echo.
if exist "dist\PrintPDF_Setup_v%APP_VER%.exe" (
  echo 1. Установочный пакет: dist\PrintPDF_Setup_v%APP_VER%.exe
)
echo 2. Портативный ZIP:    dist\PrintPDF_v%APP_VER%_Portable.zip
echo 3. Портативная папка:  dist\PrintPDF\
echo ========================================================
goto END

:NO_ISCC
echo [ПРЕДУПРЕЖДЕНИЕ] Компилятор Inno Setup не найден. Создание инсталлятора пропущено.
echo.
echo 1. Портативный ZIP:   dist\PrintPDF_v%APP_VER%_Portable.zip
echo 2. Портативная папка: dist\PrintPDF\

:END
echo.
pause
