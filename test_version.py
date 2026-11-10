"""Версия программы задаётся в одном месте — core/version.py."""
import os
import re
import unittest

from core.version import APP_VERSION
from core.updater import parse_version

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(rel_path: str) -> str:
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        return f.read()


class TestSingleVersionSource(unittest.TestCase):
    def test_version_format(self):
        self.assertRegex(APP_VERSION, r"^\d+\.\d+\.\d+(\.\d+)?$")
        self.assertIn(len(parse_version(APP_VERSION)), (3, 4))

    def test_no_hardcoded_version_in_build_files(self):
        """В build.bat и setup.iss версия не прописана вручную — только из core/version.py."""
        self.assertIsNone(re.search(r"set\s+\"?APP_VER=\d", _read("build.bat"), re.I))
        self.assertIsNone(re.search(r"#define\s+MyAppVersion\s+\"", _read(os.path.join("installer", "setup.iss"))))
        self.assertIn("/DMyAppVersion=%APP_VER%", _read("build.bat"))

    def test_about_dialog_uses_core_version(self):
        src = _read(os.path.join("ui", "about_dialog.py"))
        self.assertIn("from core.version import APP_VERSION", src)
        self.assertIsNone(re.search(r"^APP_VERSION\s*=", src, re.M))


if __name__ == "__main__":
    unittest.main()
