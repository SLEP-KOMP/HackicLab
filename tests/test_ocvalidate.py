"""Тесты разбора вывода ocvalidate: версия и категории замечаний."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.builder import ocvalidate


class VersionTests(unittest.TestCase):
    def _run(self, output: str):
        fake = mock.Mock()
        fake.stdout = output
        fake.stderr = ""
        fake.returncode = 0
        with mock.patch.object(ocvalidate, "ensure_ocvalidate", return_value=Path("ocvalidate.exe")), \
                mock.patch.object(ocvalidate, "hidden_run", return_value=fake):
            return ocvalidate.run_ocvalidate(Path(__file__))

    def test_version_from_note_line(self):
        res = self._run(
            "NOTE: This version of ocvalidate is only compatible with "
            "OpenCore version 1.0.8!\n\nCompleted validating X in 2 ms. No issues found.\n"
        )
        self.assertEqual(res.tool_version, "1.0.8")
        self.assertTrue(res.ok)

    def test_version_from_explicit_line(self):
        res = self._run("ocvalidate 0.9.9\nNOTE: compatible with OpenCore 1.0.2\n")
        self.assertEqual(res.tool_version, "0.9.9")

    def test_missing_tool_is_not_an_error(self):
        with mock.patch.object(ocvalidate, "ensure_ocvalidate", return_value=None):
            res = ocvalidate.run_ocvalidate(Path(__file__))
        self.assertTrue(res.ok)
        self.assertTrue(res.tool_missing)


if __name__ == "__main__":
    unittest.main()

