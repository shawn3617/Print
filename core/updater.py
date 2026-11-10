"""
Модуль проверки и автоматической установки обновлений PrintPDF через GitHub Releases API.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Callable, Tuple

GITHUB_REPO = "shawn3617/Print"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
CHECK_INTERVAL_SECONDS = 4 * 3600  # Проверять не чаще одного раза в 4 часа


def parse_version(ver_str: str) -> tuple:
    """
    Преобразует строку версии (например, 'v1.3.0', '1.3.1', '1.2') в кортеж чисел (1, 3, 0).
    """
    if not ver_str:
        return (0,)
    cleaned = re.sub(r'^[vV]', '', str(ver_str).strip())
    parts = []
    for chunk in cleaned.split('.'):
        m = re.match(r'^\d+', chunk)
        if m:
            parts.append(int(m.group()))
        else:
            break
    return tuple(parts) if parts else (0,)


def is_newer_version(latest_ver: str, current_ver: str) -> bool:
    """Возвращает True, если latest_ver строго новее current_ver."""
    return parse_version(latest_ver) > parse_version(current_ver)


class UpdateInfo:
    """Сведения о доступном обновлении."""
    def __init__(
        self,
        version: str,
        title: str,
        changelog: str,
        published_at: str,
        html_url: str,
        installer_url: Optional[str] = None,
        installer_name: Optional[str] = None,
        installer_size: int = 0,
        portable_url: Optional[str] = None,
        portable_name: Optional[str] = None,
        portable_size: int = 0,
        installer_sha256: Optional[str] = None,
        portable_sha256: Optional[str] = None,
    ):
        self.version = version
        self.title = title
        self.changelog = changelog
        self.published_at = published_at
        self.html_url = html_url
        self.installer_url = installer_url
        self.installer_name = installer_name
        self.installer_size = installer_size
        # SHA-256 установщика, который GitHub сам считает для файлов релиза (поле asset.digest)
        self.installer_sha256 = installer_sha256
        self.portable_url = portable_url
        self.portable_name = portable_name
        self.portable_size = portable_size
        self.portable_sha256 = portable_sha256

    @property
    def formatted_size_mb(self) -> str:
        """Размер установщика в мегабайтах."""
        if self.installer_size <= 0:
            return ""
        return f"{self.installer_size / (1024 * 1024):.1f} МБ"

    @property
    def formatted_portable_size_mb(self) -> str:
        """Размер портативного архива в мегабайтах."""
        if self.portable_size <= 0:
            return ""
        return f"{self.portable_size / (1024 * 1024):.1f} МБ"


def _parse_sha256_digest(digest: Optional[str]) -> Optional[str]:
    """Из поля GitHub 'sha256:<hex>' возвращает <hex> в нижнем регистре, иначе None."""
    if not digest or not isinstance(digest, str):
        return None
    algo, _, value = digest.partition(":")
    value = value.strip().lower()
    if algo.strip().lower() != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", value):
        return None
    return value


def verify_download(
    file_path: str,
    expected_size: int = 0,
    expected_sha256: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Проверяет скачанный установщик перед запуском.
    Размер сверяется, если он известен (> 0); SHA-256 — если GitHub его сообщил.
    Возвращает (True, "") или (False, понятная причина).
    """
    if not os.path.isfile(file_path):
        return False, "файл обновления не найден после скачивания"

    actual_size = os.path.getsize(file_path)
    if actual_size == 0:
        return False, "скачан пустой файл"
    if expected_size and actual_size != expected_size:
        return False, (f"файл скачан не полностью: {actual_size} байт из {expected_size}")

    if expected_sha256:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest().lower() != expected_sha256.lower():
            return False, "контрольная сумма SHA-256 не совпала (файл повреждён)"
    else:
        print("[Updater] GitHub не сообщил SHA-256 установщика — проверен только размер")

    return True, ""


def check_for_updates(
    current_version: str,
    timeout: float = 4.0,
    api_url: str = GITHUB_API_URL
) -> Optional[UpdateInfo]:
    """
    Проверяет наличие новой версии на GitHub Releases.
    Если доступна более новая версия — возвращает UpdateInfo, иначе None.
    При ошибках сети или таймауте возвращает None без выброса исключений.
    """
    try:
        req = urllib.request.Request(
            api_url,
            headers={
                "User-Agent": "PrintPDF-App/1.0",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")
        clean_tag = tag_name.lstrip("vV")

        if not is_newer_version(clean_tag, current_version):
            return None

        # Ищем установщик и архив среди вложенных файлов (assets)
        installer_url = None
        installer_name = None
        installer_size = 0
        installer_sha256 = None
        portable_url = None
        portable_name = None
        portable_size = 0
        portable_sha256 = None

        for asset in data.get("assets", []):
            name = asset.get("name", "")
            download_url = asset.get("browser_download_url", "")
            size = asset.get("size", 0)

            if name.lower().endswith(".exe") and "setup" in name.lower():
                installer_url = download_url
                installer_name = name
                installer_size = size
                installer_sha256 = _parse_sha256_digest(asset.get("digest"))
            elif name.lower().endswith(".zip") and "portable" in name.lower():
                portable_url = download_url
                portable_name = name
                portable_size = size
                portable_sha256 = _parse_sha256_digest(asset.get("digest"))

        return UpdateInfo(
            version=clean_tag,
            title=data.get("name", f"Версия {clean_tag}"),
            changelog=data.get("body", "").strip(),
            published_at=data.get("published_at", ""),
            html_url=data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases"),
            installer_url=installer_url,
            installer_name=installer_name,
            installer_size=installer_size,
            portable_url=portable_url,
            portable_name=portable_name,
            portable_size=portable_size,
            installer_sha256=installer_sha256,
            portable_sha256=portable_sha256,
        )

    except Exception as e:
        # Сетевые ошибки, блокировки, таймаут — глушим, чтобы не мешать пользователю
        return None


def download_file(
    url: str,
    target_path: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    is_cancelled_callback: Optional[Callable[[], bool]] = None,
    timeout: float = 30.0
) -> bool:
    """
    Скачивает файл по прямой ссылке с отслеживанием прогресса.
    Возвращает True в случае успеха, False при ошибке или отмене.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "PrintPDF-App/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 64 * 1024

            with open(target_path, "wb") as f:
                while True:
                    if is_cancelled_callback and is_cancelled_callback():
                        f.close()
                        try:
                            os.remove(target_path)
                        except Exception:
                            pass
                        return False

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        if total_size and downloaded != total_size:
            raise IOError(f"соединение оборвалось: получено {downloaded} байт из {total_size}")

        return True
    except Exception as e:
        print(f"[Updater] Ошибка скачивания {url}: {e}")
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
        except Exception:
            pass
        return False


def is_running_as_installed_app() -> bool:
    """
    Проверяет, запущено ли приложение из папки стандартной установки
    (%LocalAppData%\\Programs\\PrintPDF) в скомпилированном виде.
    """
    if not getattr(sys, "frozen", False):
        return False
    exe_dir = os.path.abspath(os.path.dirname(sys.executable)).lower()
    local_appdata = os.environ.get("LOCALAPPDATA", "").lower()
    expected_dir = os.path.abspath(os.path.join(local_appdata, "programs", "printpdf")).lower()
    return exe_dir == expected_dir


def apply_update_and_restart(installer_path: str, silent: bool = True) -> bool:
    """
    Запускает скачанный инсталлятор в фоновом процессе с автоперезапуском программы.
    После запуска инсталлятора текущая программа должна завершить работу.
    """
    if not os.path.exists(installer_path):
        return False

    local_appdata = os.environ.get("LOCALAPPDATA", "")
    target_exe = os.path.join(local_appdata, "Programs", "PrintPDF", "PrintPDF.exe")

    # Inno Setup аргументы: /SILENT (тихий интерфейс), /SUPPRESSMSGBOXES, /NORESTART
    silent_args = "/SILENT /SUPPRESSMSGBOXES /NORESTART" if silent else ""

    # Командная строка: ждём 1.5 сек пока завершится текущий процесс, запускаем инсталлятор с ожиданием, запускаем обновленный exe
    batch_cmd = (
        f'powershell.exe -NoProfile -Command "'
        f'Start-Sleep -Milliseconds 1200; '
        f'$p = Start-Process -FilePath \'{installer_path}\' -ArgumentList \'{silent_args}\' -PassThru -Wait; '
        f'if (Test-Path \'{target_exe}\') {{ Start-Process -FilePath \'{target_exe}\' }}"'
    )

    try:
        # Запускаем отсоединенный процесс, который продолжит жить после выхода программы
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            batch_cmd,
            shell=False,
            creationflags=flags,
            close_fds=True
        )
        return True
    except Exception as e:
        print(f"[Updater] Ошибка запуска установщика: {e}")
        return False


def apply_portable_update_and_restart(zip_path: str, target_dir: str) -> bool:
    """
    Автоматически обновляет портативную версию программы на месте:
    1. Ждет завершения текущего процесса PrintPDF.exe.
    2. Сохраняет пользовательский config.json (если есть).
    3. Распаковывает новый ZIP во временную папку.
    4. Копирует файлы в target_dir с перезаписью.
    5. Восстанавливает config.json.
    6. Запускает обновленный PrintPDF.exe.
    7. Удаляет временные файлы.
    """
    if not os.path.isfile(zip_path) or not os.path.isdir(target_dir):
        return False

    pid = os.getpid()
    target_exe = os.path.join(target_dir, "PrintPDF.exe")
    script_path = os.path.join(tempfile.gettempdir(), f"printpdf_update_portable_{pid}.ps1")

    safe_target_dir = os.path.abspath(target_dir).replace("'", "''")
    safe_target_exe = os.path.abspath(target_exe).replace("'", "''")
    safe_zip_path = os.path.abspath(zip_path).replace("'", "''")

    ps_content = f"""# Автообновление портативной версии PrintPDF
$ProcessId = {pid}
$ZipPath = '{safe_zip_path}'
$TargetDir = '{safe_target_dir}'
$TargetExe = '{safe_target_exe}'

# 1. Ждём завершения текущего процесса (до 15 секунд)
$timeoutSeconds = 15
$waited = 0
while ((Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) -and ($waited -lt $timeoutSeconds)) {{
    Start-Sleep -Milliseconds 300
    $waited += 0.3
}}

if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {{
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
}}

# 2. Сохраняем пользовательский config.json
$savedConfig = $null
$configCandidates = @(
    (Join-Path $TargetDir "config.json"),
    (Join-Path $TargetDir "_internal\\config.json")
)
foreach ($cfg in $configCandidates) {{
    if (Test-Path $cfg) {{
        $savedConfig = Get-Content $cfg -Raw -Encoding utf8
        break
    }}
}}

# 3. Распаковываем ZIP-архив во временную папку
$extractDir = Join-Path $env:TEMP ("printpdf_unpack_" + [System.Guid]::NewGuid().ToString("N"))
try {{
    Expand-Archive -Path $ZipPath -DestinationPath $extractDir -Force

    # Проверяем структуру распакованного архива: файлы могут быть внутри папки PrintPDF/ или в корне
    $sourceDir = $extractDir
    if (Test-Path (Join-Path $extractDir "PrintPDF\\PrintPDF.exe")) {{
        $sourceDir = Join-Path $extractDir "PrintPDF"
    }}

    # Копируем всё содержимое в целевую папку с заменой
    Copy-Item -Path "$sourceDir\\*" -Destination $TargetDir -Recurse -Force

    # Восстанавливаем пользовательский config.json, если был сохранён
    if ($savedConfig) {{
        $restoreCandidates = @(
            (Join-Path $TargetDir "_internal\\config.json"),
            (Join-Path $TargetDir "config.json")
        )
        foreach ($rc in $restoreCandidates) {{
            if (Test-Path (Split-Path $rc)) {{
                [System.IO.File]::WriteAllText($rc, $savedConfig, [System.Text.Encoding]::UTF8)
                break
            }}
        }}
    }}

    # Удаляем временную папку распаковки и zip
    Remove-Item -Path $extractDir -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item -Path $ZipPath -Force -ErrorAction SilentlyContinue

    # Запускаем обновлённую программу
    if (Test-Path $TargetExe) {{
        Start-Process -FilePath $TargetExe
    }}
}} catch {{
    $logFile = Join-Path $env:TEMP "printpdf_portable_update_error.log"
    $_ | Out-File $logFile -Encoding utf8
}} finally {{
    # Скрипт удаляет сам себя
    Remove-Item -Path $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue
}}
"""
    try:
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(ps_content)

        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-WindowStyle", "Hidden",
                "-File", script_path
            ],
            shell=False,
            creationflags=flags,
            close_fds=True
        )
        return True
    except Exception as e:
        print(f"[Updater] Ошибка запуска скрипта обновления: {e}")
        return False
