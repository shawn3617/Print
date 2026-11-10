#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Модуль и CLI-утилита для цифровой подписи исполняемых файлов (Authenticode).

Поддерживает подпись через Windows SDK signtool.exe и fallback через PowerShell
Set-AuthenticodeSignature. Реализует отказоустойчивый перебор серверов времени RFC 3161
и корректную обработку отсутствия сертификата для локальных сборок разработчика.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Список серверов меток времени RFC 3161 по приоритету
DEFAULT_TIMESTAMP_SERVERS: List[str] = [
    "http://timestamp.digicert.com",
    "http://timestamp.sectigo.com",
    "http://timestamp.globalsign.com/scripts/timstamp.dll",
]

DEFAULT_DESCRIPTION = "PrintPDF — AutoCAD to PDF Batch Plotter"
DEV_CERT_DEFAULT_PASSWORD = "PrintPDFDev"


def _extract_version_tuple(path_str: str) -> Tuple[int, ...]:
    """Извлекает числовой кортеж версии из пути к Windows SDK (для корректной сортировки)."""
    match = re.search(r"(\d+(?:\.\d+)+)", path_str)
    if match:
        try:
            return tuple(int(x) for x in match.group(1).split("."))
        except ValueError:
            pass
    return (0,)


def find_signtool() -> Optional[str]:
    """Ищет утилиту signtool.exe в системе.

    Порядок поиска:
    1. Переменная окружения SIGNTOOL_PATH
    2. Стандартные каталоги Windows SDK (10/11) x64 (сортировка от новейшей версии к старейшей)
    3. Стандартные каталоги Windows SDK x86 и 8.1
    4. Каталоги Visual Studio и SDKs (включая ClickOnce и BuildTools)
    5. Системный PATH (shutil.which)

    Returns:
        Абсолютный путь к signtool.exe или None, если не найден.
    """
    # 1. Переменная окружения SIGNTOOL_PATH
    env_path = os.environ.get("SIGNTOOL_PATH")
    if env_path and os.path.isfile(env_path):
        return os.path.abspath(env_path)

    # 2. Windows SDK 10/11 (поиск всех версий и выбор наивысшей)
    sdk_patterns = [
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files\Windows Kits\10\bin\*\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x86\signtool.exe",
        r"C:\Program Files\Windows Kits\10\bin\*\x86\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\8.1\bin\x64\signtool.exe",
        r"C:\Program Files (x86)\Windows Kits\8.1\bin\x86\signtool.exe",
    ]

    sdk_matches: List[str] = []
    for pattern in sdk_patterns:
        sdk_matches.extend(glob.glob(pattern))

    if sdk_matches:
        # Сортируем по числовой версии папки по убыванию (10.0.22621.0 > 10.0.19041.0)
        sdk_matches.sort(key=_extract_version_tuple, reverse=True)
        return os.path.abspath(sdk_matches[0])

    # 3. Visual Studio и ClickOnce SDK
    vs_patterns = [
        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\**\signtool.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\**\signtool.exe",
        r"C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool\signtool.exe",
        r"C:\Program Files\Microsoft SDKs\ClickOnce\SignTool\signtool.exe",
        r"C:\Program Files (x86)\Microsoft SDKs\Windows\*\bin\*\signtool.exe",
    ]
    for pattern in vs_patterns:
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return os.path.abspath(matches[0])

    # 4. Поиск в PATH
    which_signtool = shutil.which("signtool.exe") or shutil.which("signtool")
    if which_signtool:
        return os.path.abspath(which_signtool)

    return None


def get_certificate_config(project_root: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Определяет параметры сертификата для подписи из окружения или локальных файлов.

    Порядок проверки:
    1. Переменная SIGN_CERT_FILE (.pfx файл) и SIGN_CERT_PASSWORD
    2. Переменная SIGN_CERT_THUMBPRINT (отпечаток в хранилище Windows)
    3. Переменная SIGN_CERT_SUBJECT (имя субъекта в хранилище Windows)
    4. Локальный тестовый файл dev_cert.pfx (в dist/dev_cert.pfx или dev_cert.pfx)

    Returns:
        Словарь параметров сертификата или None, если сертификат не найден/не настроен.
    """
    if project_root is None:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # 1. PFX файл из переменной окружения
    cert_file_env = os.environ.get("SIGN_CERT_FILE")
    if cert_file_env:
        cert_path = cert_file_env
        if not os.path.isabs(cert_path):
            candidate1 = os.path.join(project_root, cert_path)
            candidate2 = os.path.abspath(cert_path)
            cert_path = candidate1 if os.path.isfile(candidate1) else candidate2

        if os.path.isfile(cert_path):
            return {
                "type": "file",
                "path": os.path.abspath(cert_path),
                "password": os.environ.get("SIGN_CERT_PASSWORD", ""),
                "is_dev": False,
            }
        else:
            print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл сертификата из SIGN_CERT_FILE не найден: {cert_file_env}")

    # 2. Отпечаток сертификата в хранилище Windows
    thumbprint = os.environ.get("SIGN_CERT_THUMBPRINT") or os.environ.get("SIGN_CERT_SHA1")
    if thumbprint:
        clean_thumb = re.sub(r"[\s:]", "", thumbprint).upper()
        return {
            "type": "thumbprint",
            "thumbprint": clean_thumb,
            "store": os.environ.get("SIGN_CERT_STORE", "MY"),
            "is_dev": False,
        }

    # 3. Имя субъекта в хранилище Windows
    subject = os.environ.get("SIGN_CERT_SUBJECT") or os.environ.get("SIGN_CERT_NAME")
    if subject:
        return {
            "type": "subject",
            "subject": subject.strip(),
            "store": os.environ.get("SIGN_CERT_STORE", "MY"),
            "is_dev": False,
        }

    # 4. Локальный тестовый файл dev_cert.pfx
    dev_cert_candidates = [
        os.path.join(project_root, "dist", "dev_cert.pfx"),
        os.path.join(project_root, "dev_cert.pfx"),
    ]
    for cand in dev_cert_candidates:
        if os.path.isfile(cand):
            return {
                "type": "file",
                "path": os.path.abspath(cand),
                "password": os.environ.get("SIGN_CERT_PASSWORD", DEV_CERT_DEFAULT_PASSWORD),
                "is_dev": True,
            }

    return None


def build_signtool_args(
    signtool_path: str,
    cert_config: Dict[str, Any],
    target_file: str,
    timestamp_url: Optional[str] = None,
    description: str = DEFAULT_DESCRIPTION,
) -> List[str]:
    """Формирует список аргументов командной строки для вызова `signtool sign`."""
    cmd = [
        signtool_path,
        "sign",
        "/fd",
        "sha256",
    ]

    if description:
        cmd.extend(["/d", description])

    cert_type = cert_config.get("type")
    if cert_type == "file":
        cmd.extend(["/f", cert_config["path"]])
        password = cert_config.get("password")
        if password:
            cmd.extend(["/p", password])
    elif cert_type == "thumbprint":
        cmd.extend(["/s", cert_config.get("store", "MY"), "/sha1", cert_config["thumbprint"]])
    elif cert_type == "subject":
        cmd.extend(["/s", cert_config.get("store", "MY"), "/n", cert_config["subject"]])
    else:
        raise ValueError(f"Неизвестный тип сертификата: {cert_type}")

    if timestamp_url:
        cmd.extend(["/tr", timestamp_url, "/td", "sha256"])

    cmd.append(target_file)
    return cmd


def sign_file_with_signtool(
    signtool_path: str,
    cert_config: Dict[str, Any],
    target_file: str,
    timestamp_servers: Sequence[str] = DEFAULT_TIMESTAMP_SERVERS,
    description: str = DEFAULT_DESCRIPTION,
) -> bool:
    """Подписывает файл с помощью `signtool.exe` с отказоустойчивым перебором серверов времени."""
    if not os.path.isfile(target_file):
        print(f"  [ОШИБКА] Целевой файл не существует: {target_file}")
        return False

    # Перебор серверов времени
    for ts_url in timestamp_servers:
        cmd = build_signtool_args(
            signtool_path=signtool_path,
            cert_config=cert_config,
            target_file=target_file,
            timestamp_url=ts_url,
            description=description,
        )
        proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
        if proc.returncode == 0:
            print(f"  [OK] Файл успешно подписан (Метка времени: {ts_url})")
            return True
        else:
            err = (proc.stderr or proc.stdout).strip()
            first_line = err.splitlines()[-1] if err else f"код {proc.returncode}"
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] Сбой сервера времени {ts_url}: {first_line}. Пробуем следующий...")

    # Если все серверы времени недоступны, пробуем подписать без метки времени
    print("  [ПРЕДУПРЕЖДЕНИЕ] Все серверы меток времени недоступны. Попытка подписи без метки времени...")
    cmd_no_ts = build_signtool_args(
        signtool_path=signtool_path,
        cert_config=cert_config,
        target_file=target_file,
        timestamp_url=None,
        description=description,
    )
    proc_no_ts = subprocess.run(cmd_no_ts, capture_output=True, text=True, errors="replace")
    if proc_no_ts.returncode == 0:
        print("  [OK] Файл подписан БЕЗ метки времени (ограниченный режим).")
        return True

    err = (proc_no_ts.stderr or proc_no_ts.stdout).strip()
    print(f"  [ОШИБКА] Не удалось подписать файл через SignTool: {err}")
    return False


def sign_file_with_powershell(
    cert_config: Dict[str, Any],
    target_file: str,
    timestamp_servers: Sequence[str] = DEFAULT_TIMESTAMP_SERVERS,
) -> bool:
    """Fallback: подписывает файл с помощью PowerShell командлета `Set-AuthenticodeSignature`."""
    if not os.path.isfile(target_file):
        print(f"  [ОШИБКА] Целевой файл не существует: {target_file}")
        return False

    abs_target = os.path.abspath(target_file).replace("'", "''")
    cert_type = cert_config.get("type")

    # Формируем фрагмент PowerShell для получения сертификата
    if cert_type == "file":
        pfx_path = os.path.abspath(cert_config["path"]).replace("'", "''")
        pwd = (cert_config.get("password") or "").replace("'", "''")
        cert_setup = f"""
        $pwd = ConvertTo-SecureString -String '{pwd}' -Force -AsPlainText
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2('{pfx_path}', $pwd)
        """
    elif cert_type == "thumbprint":
        thumb = cert_config["thumbprint"].replace("'", "''")
        store = cert_config.get("store", "MY").replace("'", "''")
        cert_setup = f"""
        $cert = Get-Item "Cert:\\CurrentUser\\{store}\\{thumb}" -ErrorAction SilentlyContinue
        if (-not $cert) {{
            $cert = Get-Item "Cert:\\LocalMachine\\{store}\\{thumb}" -ErrorAction SilentlyContinue
        }}
        """
    elif cert_type == "subject":
        sub = cert_config["subject"].replace("'", "''")
        store = cert_config.get("store", "MY").replace("'", "''")
        cert_setup = f"""
        $cert = Get-ChildItem "Cert:\\CurrentUser\\{store}", "Cert:\\LocalMachine\\{store}" -ErrorAction SilentlyContinue |
            Where-Object {{ $_.Subject -like '*{sub}*' }} | Select-Object -First 1
        """
    else:
        raise ValueError(f"Неизвестный тип сертификата: {cert_type}")

    # Перебор серверов времени через PowerShell
    for ts_url in timestamp_servers:
        ps_script = f"""
        $ErrorActionPreference = 'Stop'
        try {{
            {cert_setup}
            if (-not $cert) {{
                Write-Error "Сертификат не найден в хранилище/файле."
                exit 2
            }}
            $sig = Set-AuthenticodeSignature -FilePath '{abs_target}' -Certificate $cert -TimestampServer '{ts_url}' -HashAlgorithm SHA256
            if ($sig.SignerCertificate -ne $null) {{
                Write-Output ("SUCCESS:" + $sig.Status)
                exit 0
            }} else {{
                Write-Error ($sig.StatusMessage)
                exit 1
            }}
        }} catch {{
            Write-Error $_.Exception.Message
            exit 1
        }}
        """
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            text=True,
            errors="replace",
        )
        if proc.returncode == 0 and "SUCCESS:" in proc.stdout:
            print(f"  [OK] Файл успешно подписан через PowerShell (Метка времени: {ts_url})")
            return True
        else:
            err = (proc.stderr or proc.stdout).strip()
            first_line = err.splitlines()[-1] if err else f"код {proc.returncode}"
            print(f"  [ПРЕДУПРЕЖДЕНИЕ] PowerShell: сбой сервера времени {ts_url}: {first_line}. Пробуем следующий...")

    # Попытка подписи без сервера времени
    print("  [ПРЕДУПРЕЖДЕНИЕ] PowerShell: попытка подписи без сервера времени...")
    ps_script_no_ts = f"""
    $ErrorActionPreference = 'Stop'
    try {{
        {cert_setup}
        if (-not $cert) {{
            Write-Error "Сертификат не найден."
            exit 2
        }}
        $sig = Set-AuthenticodeSignature -FilePath '{abs_target}' -Certificate $cert -HashAlgorithm SHA256
        if ($sig.SignerCertificate -ne $null) {{
            Write-Output ("SUCCESS:" + $sig.Status)
            exit 0
        }} else {{
            Write-Error ($sig.StatusMessage)
            exit 1
        }}
    }} catch {{
        Write-Error $_.Exception.Message
        exit 1
    }}
    """
    proc_no_ts = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_script_no_ts],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc_no_ts.returncode == 0 and "SUCCESS:" in proc_no_ts.stdout:
        print("  [OK] Файл подписан через PowerShell БЕЗ метки времени.")
        return True

    err = (proc_no_ts.stderr or proc_no_ts.stdout).strip()
    print(f"  [ОШИБКА] Не удалось подписать файл через PowerShell: {err}")
    return False


def verify_signature(
    target_file: str,
    signtool_path: Optional[str] = None,
) -> Tuple[bool, str]:
    """Проверяет цифровую подпись Authenticode целевого файла.

    Использует `signtool verify /pa` и fallback на `Get-AuthenticodeSignature` PowerShell,
    корректно распознавая как доверенные сертификаты, так и тестовые самоподписанные.

    Returns:
        Кортеж (успех/наличие подписи: bool, информативное сообщение: str).
    """
    if not os.path.isfile(target_file):
        return False, f"Файл не найден: {target_file}"

    # 1. Попытка проверки через signtool verify /pa
    if signtool_path:
        try:
            proc = subprocess.run(
                [signtool_path, "verify", "/pa", target_file],
                capture_output=True,
                text=True,
                errors="replace",
            )
            if proc.returncode == 0:
                return True, "Подпись действительна и доверена (Authenticode /pa)"
        except (FileNotFoundError, OSError):
            pass

    # 2. Проверка через PowerShell Get-AuthenticodeSignature (детальный разбор)
    abs_target = os.path.abspath(target_file).replace("'", "''")
    ps_cmd = (
        f"$sig = Get-AuthenticodeSignature -LiteralPath '{abs_target}'; "
        f"[PSCustomObject]@{{ "
        f"  Status = [int]$sig.Status; "
        f"  StatusString = [string]$sig.Status; "
        f"  StatusMessage = $sig.StatusMessage; "
        f"  HasCert = ($sig.SignerCertificate -ne $null); "
        f"  Subject = $(if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Subject }} else {{ '' }}); "
        f"  Thumbprint = $(if ($sig.SignerCertificate) {{ $sig.SignerCertificate.Thumbprint }} else {{ '' }}) "
        f"}} | ConvertTo-Json -Compress"
    )

    proc_ps = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
        capture_output=True,
        text=True,
        errors="replace",
    )

    if proc_ps.returncode == 0 and proc_ps.stdout.strip():
        try:
            info = json.loads(proc_ps.stdout.strip())
            has_cert = info.get("HasCert", False)
            status_code = info.get("Status", -1)
            status_str = info.get("StatusString", "")
            subject = info.get("Subject", "")
            status_msg = info.get("StatusMessage") or status_str

            if has_cert:
                if status_code == 0 or status_str == "Valid":
                    return True, f"Действительная доверенная подпись: {subject}"
                else:
                    return (
                        True,
                        f"Подпись присутствует, но корневой сертификат не доверен ({status_msg}): {subject}",
                    )
            else:
                return False, f"Файл не имеет цифровой подписи ({status_msg})"
        except Exception:
            pass

    return False, "Не удалось проверить цифровую подпись файла."


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="Цифровая подпись исполняемых файлов Authenticode (PrintPDF)."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Пути к исполняемым файлам (.exe, .dll) для подписи",
    )
    parser.add_argument(
        "--signtool",
        dest="signtool_path",
        default=None,
        help="Явный путь к signtool.exe",
    )
    parser.add_argument(
        "--cert",
        dest="cert_file",
        default=None,
        help="Путь к PFX файлу сертификата",
    )
    parser.add_argument(
        "--password",
        dest="cert_password",
        default=None,
        help="Пароль сертификата PFX",
    )
    parser.add_argument(
        "--verify-only",
        dest="verify_only",
        action="store_true",
        help="Только проверить существующую подпись без изменения файлов",
    )

    args = parser.parse_args(argv)

    if not args.files:
        print("[ИНФО] Не указаны файлы для подписи. Использование:")
        print("  python scripts/sign_binary.py dist/PrintPDF/PrintPDF.exe dist/PrintPDF_Setup.exe")
        return 0

    print("========================================================")
    print("Цифровая подпись исполняемых файлов (Authenticode)")
    print("========================================================")

    # Поиск SignTool
    signtool = args.signtool_path or find_signtool()
    if signtool:
        print(f"[ИНФО] Используется SignTool: {signtool}")
    else:
        print("[ИНФО] SignTool.exe не найден в системе. Используется PowerShell (Set-AuthenticodeSignature).")

    # Режим "только проверка"
    if args.verify_only:
        all_verified = True
        for target in args.files:
            if not os.path.exists(target):
                print(f"[ПРЕДУПРЕЖДЕНИЕ] Файл не найден: {target} (пропуск)")
                continue
            ok, msg = verify_signature(target, signtool)
            status_tag = "[OK]" if ok else "[ОШИБКА]"
            print(f"{status_tag} {target}: {msg}")
            if not ok:
                all_verified = False
        return 0 if all_verified else 1

    # Если заданы явные параметры сертификата в CLI
    if args.cert_file:
        cert_config = {
            "type": "file",
            "path": os.path.abspath(args.cert_file),
            "password": args.cert_password or "",
            "is_dev": False,
        }
    else:
        cert_config = get_certificate_config()

    # Graceful skip: если сертификат не настроен, выводим предупреждение и выходим с кодом 0
    if not cert_config:
        print("\n[ПРЕДУПРЕЖДЕНИЕ] Сертификат цифровой подписи Authenticode не настроен.")
        print("Процесс подписи пропущен. Локальная сборка продолжается без подписи (код 0).")
        print("\nДля включения цифровой подписи настройте один из вариантов:")
        print("  1. Переменные окружения:")
        print("       SIGN_CERT_FILE (путь к .pfx файлу) и SIGN_CERT_PASSWORD")
        print("       или SIGN_CERT_THUMBPRINT / SIGN_CERT_SUBJECT (хранилище сертификатов Windows)")
        print("  2. Локальный тестовый сертификат разработчика:")
        print("       powershell -ExecutionPolicy Bypass -File scripts\\create_dev_cert.ps1")
        print("========================================================")
        return 0

    # Информация о сертификате
    c_type = cert_config.get("type")
    if c_type == "file":
        is_dev_str = " (тестовый dev_cert.pfx)" if cert_config.get("is_dev") else ""
        print(f"[ИНФО] Сертификат: Файл {cert_config['path']}{is_dev_str}")
    elif c_type == "thumbprint":
        print(f"[ИНФО] Сертификат: Хранилище Windows (SHA1: {cert_config['thumbprint']})")
    elif c_type == "subject":
        print(f"[ИНФО] Сертификат: Хранилище Windows (Субъект: {cert_config['subject']})")

    success_count = 0
    fail_count = 0

    for target in args.files:
        if not os.path.exists(target):
            print(f"\n[ПРЕДУПРЕЖДЕНИЕ] Файл не найден: {target} (пропуск)")
            continue

        print(f"\nПодпись файла: {target}...")
        if signtool:
            signed = sign_file_with_signtool(signtool, cert_config, target)
        else:
            signed = sign_file_with_powershell(cert_config, target)

        if signed:
            # Верификация
            valid, v_msg = verify_signature(target, signtool)
            if valid:
                print(f"  [Проверка] {v_msg}")
                success_count += 1
            else:
                print(f"  [ОШИБКА ПРОВЕРКИ] {v_msg}")
                fail_count += 1
        else:
            fail_count += 1

    print("\n========================================================")
    print(f"Итог подписи: успешно: {success_count}, ошибок: {fail_count}")
    print("========================================================")

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
