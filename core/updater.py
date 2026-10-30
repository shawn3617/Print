"""
Модуль проверки и автоматической установки обновлений PrintPDF через GitHub Releases API.
"""

import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, Callable

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
        portable_size: int = 0,
    ):
        self.version = version
        self.title = title
        self.changelog = changelog
        self.published_at = published_at
        self.html_url = html_url
        self.installer_url = installer_url
        self.installer_name = installer_name
        self.installer_size = installer_size
        self.portable_url = portable_url
        self.portable_size = portable_size

    @property
    def formatted_size_mb(self) -> str:
        """Размер установщика в мегабайтах."""
        if self.installer_size <= 0:
            return ""
        return f"{self.installer_size / (1024 * 1024):.1f} МБ"


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
        portable_url = None
        portable_size = 0

        for asset in data.get("assets", []):
            name = asset.get("name", "")
            download_url = asset.get("browser_download_url", "")
            size = asset.get("size", 0)

            if name.lower().endswith(".exe") and "setup" in name.lower():
                installer_url = download_url
                installer_name = name
                installer_size = size
            elif name.lower().endswith(".zip") and "portable" in name.lower():
                portable_url = download_url
                portable_size = size

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
            portable_size=portable_size
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
