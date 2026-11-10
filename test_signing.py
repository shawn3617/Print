#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Модульные тесты для модуля цифровой подписи Authenticode (scripts/sign_binary.py)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, call, patch

# Импортируем тестируемый модуль
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import sign_binary


class TestFindSigntool(unittest.TestCase):
    """Тесты поиска утилиты signtool.exe."""

    def test_find_signtool_env_var(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            fake_signtool = f.name

        try:
            with patch.dict(os.environ, {"SIGNTOOL_PATH": fake_signtool}):
                found = sign_binary.find_signtool()
                self.assertEqual(found, os.path.abspath(fake_signtool))
        finally:
            if os.path.exists(fake_signtool):
                os.remove(fake_signtool)

    def test_find_signtool_windows_sdk_sorting(self):
        """Проверяет выбор наивысшей версии Windows SDK среди найденных."""
        mock_paths = [
            r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.18362.0\x64\signtool.exe",
            r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.22621.0\x64\signtool.exe",
            r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.19041.0\x64\signtool.exe",
        ]

        def fake_glob(pattern, recursive=False):
            if "10" in pattern and "x64" in pattern:
                return list(mock_paths)
            return []

        with patch.dict(os.environ, {}, clear=True):
            with patch("glob.glob", side_effect=fake_glob):
                found = sign_binary.find_signtool()
                self.assertIsNotNone(found)
                self.assertIn("10.0.22621.0", found)

    def test_find_signtool_vs_fallback(self):
        """Проверяет поиск в Visual Studio / ClickOnce при отсутствии SDK."""
        with patch.dict(os.environ, {}, clear=True):
            def fake_glob(pattern, recursive=False):
                if "ClickOnce" in pattern:
                    return [r"C:\Program Files (x86)\Microsoft SDKs\ClickOnce\SignTool\signtool.exe"]
                return []

            with patch("glob.glob", side_effect=fake_glob):
                with patch("shutil.which", return_value=None):
                    found = sign_binary.find_signtool()
                    self.assertIsNotNone(found)
                    self.assertIn("ClickOnce", found)

    def test_find_signtool_which_path(self):
        """Проверяет поиск через PATH (shutil.which)."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("glob.glob", return_value=[]):
                with patch("shutil.which", return_value=r"C:\Tools\signtool.exe"):
                    found = sign_binary.find_signtool()
                    self.assertEqual(found, os.path.abspath(r"C:\Tools\signtool.exe"))

    def test_find_signtool_not_found(self):
        """Проверяет возврат None, если утилита не найдена."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("glob.glob", return_value=[]):
                with patch("shutil.which", return_value=None):
                    self.assertIsNone(sign_binary.find_signtool())


class TestCertificateConfig(unittest.TestCase):
    """Тесты конфигурирования сертификата из окружения и файлов."""

    def test_cert_from_file_env(self):
        with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as f:
            fake_pfx = f.name

        try:
            with patch.dict(os.environ, {"SIGN_CERT_FILE": fake_pfx, "SIGN_CERT_PASSWORD": "SecretPassword123"}):
                cfg = sign_binary.get_certificate_config()
                self.assertIsNotNone(cfg)
                self.assertEqual(cfg["type"], "file")
                self.assertEqual(cfg["path"], os.path.abspath(fake_pfx))
                self.assertEqual(cfg["password"], "SecretPassword123")
                self.assertFalse(cfg["is_dev"])
        finally:
            if os.path.exists(fake_pfx):
                os.remove(fake_pfx)

    def test_cert_from_thumbprint_env(self):
        with patch.dict(os.environ, {"SIGN_CERT_THUMBPRINT": "12:34:ab:cd:56:ef", "SIGN_CERT_STORE": "Root"}):
            cfg = sign_binary.get_certificate_config()
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg["type"], "thumbprint")
            self.assertEqual(cfg["thumbprint"], "1234ABCD56EF")
            self.assertEqual(cfg["store"], "Root")
            self.assertFalse(cfg["is_dev"])

    def test_cert_from_subject_env(self):
        with patch.dict(os.environ, {"SIGN_CERT_SUBJECT": "PrintPDF Production"}):
            cfg = sign_binary.get_certificate_config()
            self.assertIsNotNone(cfg)
            self.assertEqual(cfg["type"], "subject")
            self.assertEqual(cfg["subject"], "PrintPDF Production")
            self.assertEqual(cfg["store"], "MY")
            self.assertFalse(cfg["is_dev"])

    def test_cert_from_dev_cert_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            dist_dir = os.path.join(tmp_dir, "dist")
            os.makedirs(dist_dir, exist_ok=True)
            dev_pfx = os.path.join(dist_dir, "dev_cert.pfx")
            with open(dev_pfx, "wb") as f:
                f.write(b"dummy_cert_bytes")

            with patch.dict(os.environ, {}, clear=True):
                cfg = sign_binary.get_certificate_config(project_root=tmp_dir)
                self.assertIsNotNone(cfg)
                self.assertEqual(cfg["type"], "file")
                self.assertEqual(cfg["path"], os.path.abspath(dev_pfx))
                self.assertEqual(cfg["password"], sign_binary.DEV_CERT_DEFAULT_PASSWORD)
                self.assertTrue(cfg["is_dev"])

    def test_cert_missing_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {}, clear=True):
                cfg = sign_binary.get_certificate_config(project_root=tmp_dir)
                self.assertIsNone(cfg)


class TestBuildSigntoolArgs(unittest.TestCase):
    """Тесты формирования аргументов командной строки signtool."""

    def test_build_args_pfx_with_password_and_timestamp(self):
        cert_cfg = {
            "type": "file",
            "path": r"C:\Certs\mycert.pfx",
            "password": "MyPassword",
        }
        cmd = sign_binary.build_signtool_args(
            signtool_path=r"C:\bin\signtool.exe",
            cert_config=cert_cfg,
            target_file=r"C:\dist\app.exe",
            timestamp_url="http://timestamp.digicert.com",
            description="Test Description",
        )

        expected = [
            r"C:\bin\signtool.exe",
            "sign",
            "/fd",
            "sha256",
            "/d",
            "Test Description",
            "/f",
            r"C:\Certs\mycert.pfx",
            "/p",
            "MyPassword",
            "/tr",
            "http://timestamp.digicert.com",
            "/td",
            "sha256",
            r"C:\dist\app.exe",
        ]
        self.assertEqual(cmd, expected)

    def test_build_args_thumbprint_no_timestamp(self):
        cert_cfg = {
            "type": "thumbprint",
            "thumbprint": "AABBCCDDEEFF",
            "store": "MY",
        }
        cmd = sign_binary.build_signtool_args(
            signtool_path="signtool.exe",
            cert_config=cert_cfg,
            target_file="app.exe",
            timestamp_url=None,
        )

        self.assertIn("/sha1", cmd)
        self.assertIn("AABBCCDDEEFF", cmd)
        self.assertIn("/s", cmd)
        self.assertIn("MY", cmd)
        self.assertNotIn("/tr", cmd)
        self.assertEqual(cmd[-1], "app.exe")

    def test_build_args_subject(self):
        cert_cfg = {
            "type": "subject",
            "subject": "CN=Test",
            "store": "MY",
        }
        cmd = sign_binary.build_signtool_args(
            signtool_path="signtool.exe",
            cert_config=cert_cfg,
            target_file="app.exe",
        )
        self.assertIn("/n", cmd)
        self.assertIn("CN=Test", cmd)

    def test_build_args_invalid_type(self):
        with self.assertRaises(ValueError):
            sign_binary.build_signtool_args(
                signtool_path="signtool.exe",
                cert_config={"type": "unknown"},
                target_file="app.exe",
            )


class TestTimestampFailover(unittest.TestCase):
    """Тесты отказоустойчивого перебора серверов времени при сбоях."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_first_server_succeeds(self):
        cert_cfg = {"type": "file", "path": "cert.pfx"}
        servers = ["http://server1", "http://server2", "http://server3"]

        mock_proc = MagicMock()
        mock_proc.returncode = 0

        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            ok = sign_binary.sign_file_with_signtool(
                signtool_path="signtool.exe",
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertTrue(ok)
            # Должен быть только 1 вызов (первый сервер сработал)
            self.assertEqual(mock_run.call_count, 1)
            self.assertIn("http://server1", mock_run.call_args[0][0])

    def test_failover_to_second_server(self):
        cert_cfg = {"type": "file", "path": "cert.pfx"}
        servers = ["http://server1", "http://server2", "http://server3"]

        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "Timestamp server connection timed out"

        succ_proc = MagicMock()
        succ_proc.returncode = 0

        with patch("subprocess.run", side_effect=[fail_proc, succ_proc]) as mock_run:
            ok = sign_binary.sign_file_with_signtool(
                signtool_path="signtool.exe",
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertTrue(ok)
            self.assertEqual(mock_run.call_count, 2)
            self.assertIn("http://server2", mock_run.call_args_list[1][0][0])

    def test_all_servers_fail_fallback_no_timestamp(self):
        cert_cfg = {"type": "file", "path": "cert.pfx"}
        servers = ["http://server1", "http://server2"]

        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "Error"

        succ_no_ts = MagicMock()
        succ_no_ts.returncode = 0

        # server1 fail, server2 fail, no-ts success
        with patch("subprocess.run", side_effect=[fail_proc, fail_proc, succ_no_ts]) as mock_run:
            ok = sign_binary.sign_file_with_signtool(
                signtool_path="signtool.exe",
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertTrue(ok)
            self.assertEqual(mock_run.call_count, 3)
            # В третьем вызове не должно быть параметра /tr
            self.assertNotIn("/tr", mock_run.call_args_list[2][0][0])

    def test_all_fail_returns_false(self):
        cert_cfg = {"type": "file", "path": "cert.pfx"}
        servers = ["http://server1"]

        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "SignTool Error"

        with patch("subprocess.run", side_effect=[fail_proc, fail_proc]):
            ok = sign_binary.sign_file_with_signtool(
                signtool_path="signtool.exe",
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertFalse(ok)


class TestVerification(unittest.TestCase):
    """Тесты проверки статуса верификации Authenticode."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_signtool_verify_pa_success(self):
        succ_proc = MagicMock()
        succ_proc.returncode = 0
        succ_proc.stdout = "Successfully verified: file.exe"

        with patch("subprocess.run", return_value=succ_proc):
            ok, msg = sign_binary.verify_signature(
                target_file=self.tmp_file.name,
                signtool_path="signtool.exe",
            )
            self.assertTrue(ok)
            self.assertIn("Authenticode /pa", msg)

    def test_powershell_verify_valid(self):
        signtool_fail = MagicMock()
        signtool_fail.returncode = 1

        ps_info = {
            "Status": 0,
            "StatusString": "Valid",
            "StatusMessage": "Signature verified.",
            "HasCert": True,
            "Subject": "CN=PrintPDF Production",
            "Thumbprint": "12345",
        }
        ps_proc = MagicMock()
        ps_proc.returncode = 0
        ps_proc.stdout = json.dumps(ps_info)

        with patch("subprocess.run", side_effect=[signtool_fail, ps_proc]):
            ok, msg = sign_binary.verify_signature(
                target_file=self.tmp_file.name,
                signtool_path="signtool.exe",
            )
            self.assertTrue(ok)
            self.assertIn("Действительная доверенная подпись", msg)
            self.assertIn("PrintPDF Production", msg)

    def test_powershell_verify_self_signed(self):
        """Самоподписанный сертификат (корневой сертификат не доверен, но файл подписан)."""
        signtool_fail = MagicMock()
        signtool_fail.returncode = 1

        ps_info = {
            "Status": 1,
            "StatusString": "UnknownError",
            "StatusMessage": "A certificate chain processed, but terminated in a root certificate which is not trusted.",
            "HasCert": True,
            "Subject": "CN=PrintPDF Dev Test",
            "Thumbprint": "ABCDE",
        }
        ps_proc = MagicMock()
        ps_proc.returncode = 0
        ps_proc.stdout = json.dumps(ps_info)

        with patch("subprocess.run", side_effect=[signtool_fail, ps_proc]):
            ok, msg = sign_binary.verify_signature(
                target_file=self.tmp_file.name,
                signtool_path="signtool.exe",
            )
            self.assertTrue(ok)
            self.assertIn("Подпись присутствует", msg)
            self.assertIn("PrintPDF Dev Test", msg)

    def test_not_signed(self):
        signtool_fail = MagicMock()
        signtool_fail.returncode = 1

        ps_info = {
            "Status": 2,
            "StatusString": "NotSigned",
            "StatusMessage": "The file is not signed.",
            "HasCert": False,
            "Subject": "",
            "Thumbprint": "",
        }
        ps_proc = MagicMock()
        ps_proc.returncode = 0
        ps_proc.stdout = json.dumps(ps_info)

        with patch("subprocess.run", side_effect=[signtool_fail, ps_proc]):
            ok, msg = sign_binary.verify_signature(
                target_file=self.tmp_file.name,
                signtool_path="signtool.exe",
            )
            self.assertFalse(ok)
            self.assertIn("не имеет цифровой подписи", msg)


class TestPowerShellSigning(unittest.TestCase):
    """Тесты fallback-подписи через PowerShell Set-AuthenticodeSignature."""

    def setUp(self):
        self.tmp_file = tempfile.NamedTemporaryFile(suffix=".exe", delete=False)
        self.tmp_file.close()

    def tearDown(self):
        if os.path.exists(self.tmp_file.name):
            os.remove(self.tmp_file.name)

    def test_powershell_sign_missing_file_returns_false(self):
        ok = sign_binary.sign_file_with_powershell(
            cert_config={"type": "file", "path": "dummy.pfx"},
            target_file="non_existent_file.exe",
        )
        self.assertFalse(ok)

    def test_powershell_sign_first_server_succeeds(self):
        cert_cfg = {"type": "file", "path": "cert.pfx", "password": "123"}
        servers = ["http://ts1", "http://ts2"]

        succ_proc = MagicMock()
        succ_proc.returncode = 0
        succ_proc.stdout = "SUCCESS:Valid\n"

        with patch("subprocess.run", return_value=succ_proc) as mock_run:
            ok = sign_binary.sign_file_with_powershell(
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertTrue(ok)
            self.assertEqual(mock_run.call_count, 1)

    def test_powershell_sign_failover_and_no_timestamp_fallback(self):
        cert_cfg = {"type": "file", "path": "cert.pfx"}
        servers = ["http://ts1"]

        fail_proc = MagicMock()
        fail_proc.returncode = 1
        fail_proc.stderr = "Network Error"
        fail_proc.stdout = ""

        succ_no_ts = MagicMock()
        succ_no_ts.returncode = 0
        succ_no_ts.stdout = "SUCCESS:UnknownError\n"

        # 1-й вызов с ts1 падает, 2-й вызов без ts успешен
        with patch("subprocess.run", side_effect=[fail_proc, succ_no_ts]) as mock_run:
            ok = sign_binary.sign_file_with_powershell(
                cert_config=cert_cfg,
                target_file=self.tmp_file.name,
                timestamp_servers=servers,
            )
            self.assertTrue(ok)
            self.assertEqual(mock_run.call_count, 2)


class TestGracefulSkipAndMain(unittest.TestCase):
    """Тесты корректной обработки отсутствия сертификата и CLI."""

    def test_graceful_skip_returns_zero(self):
        """Если сертификат не настроен, main возвращает код 0 (сборка не ломается)."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("sign_binary.get_certificate_config", return_value=None):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    code = sign_binary.main(["dist/PrintPDF.exe"])
                    self.assertEqual(code, 0)
                    output = fake_out.getvalue()
                    self.assertIn("Сертификат цифровой подписи Authenticode не настроен", output)
                    self.assertIn("код 0", output)

    def test_main_no_args_returns_zero(self):
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            code = sign_binary.main([])
            self.assertEqual(code, 0)
            self.assertIn("Не указаны файлы для подписи", fake_out.getvalue())

    def test_main_verify_only_mode(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            target = f.name

        try:
            with patch("sign_binary.verify_signature", return_value=(True, "Подпись проверена")):
                with patch("sys.stdout", new=io.StringIO()):
                    code = sign_binary.main(["--verify-only", target])
                    self.assertEqual(code, 0)
        finally:
            if os.path.exists(target):
                os.remove(target)

    def test_main_sign_success(self):
        with tempfile.NamedTemporaryFile(suffix=".exe", delete=False) as f:
            target = f.name

        try:
            mock_cert = {"type": "file", "path": "test.pfx", "password": ""}
            with patch("sign_binary.find_signtool", return_value=r"C:\bin\signtool.exe"):
                with patch("sign_binary.get_certificate_config", return_value=mock_cert):
                    with patch("sign_binary.sign_file_with_signtool", return_value=True):
                        with patch("sign_binary.verify_signature", return_value=(True, "OK")):
                            with patch("sys.stdout", new=io.StringIO()):
                                code = sign_binary.main([target])
                                self.assertEqual(code, 0)
        finally:
            if os.path.exists(target):
                os.remove(target)


if __name__ == "__main__":
    unittest.main()
