import os
import unittest
from unittest.mock import MagicMock
from core.resource_utils import get_resource_path, get_lisp_path
from core.autocad_connector import AutoCADConnector
from parsers.spds_parser import SPDSParser
from parsers.block_parser import BlockParser


class TestLispCompilationAndResolution(unittest.TestCase):
    def test_get_lisp_path_fas_priority(self):
        # При наличии .fas get_lisp_path возвращает путь к .fas
        with unittest.mock.patch("os.path.isfile", side_effect=lambda p: str(p).endswith(".fas")):
            spds_path = get_lisp_path("core/lisp/spds_export.lsp")
            block_path = get_lisp_path("core/lisp/block_export.lsp")

            self.assertTrue(spds_path.endswith(".fas"), f"Ожидался .fas, получен: {spds_path}")
            self.assertTrue(block_path.endswith(".fas"), f"Ожидался .fas, получен: {block_path}")

        # При отсутствии .fas возвращает исходный .lsp
        with unittest.mock.patch("os.path.isfile", return_value=False):
            spds_lsp = get_lisp_path("core/lisp/spds_export.lsp")
            self.assertTrue(spds_lsp.endswith(".lsp"), f"Ожидался .lsp, получен: {spds_lsp}")

    def test_parsers_use_fas_when_available(self):
        with unittest.mock.patch("os.path.isfile", side_effect=lambda p: str(p).endswith(".fas")):
            spds_p = SPDSParser()
            block_p = BlockParser()

            self.assertTrue(spds_p.lisp_path.endswith(".fas"))
            self.assertTrue(block_p.lisp_path.endswith(".fas"))

    def test_ensure_trusted_paths(self):
        connector = AutoCADConnector()
        mock_app = MagicMock()
        mock_prefs = MagicMock()
        mock_files = MagicMock()
        mock_files.TrustedPaths = "C:\\Existing\\Path;D:\\Other\\Folder"
        mock_prefs.Files = mock_files
        mock_app.Preferences = mock_prefs
        connector.app = mock_app

        connector._ensure_trusted_paths()

        updated = mock_files.TrustedPaths
        self.assertIn("lisp", updated.lower())
        self.assertIn("C:\\Existing\\Path", updated)


if __name__ == "__main__":
    unittest.main()
