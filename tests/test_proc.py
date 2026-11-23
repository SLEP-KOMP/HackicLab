"""Тесты запуска внешних процессов без всплывающих консольных окон."""

from __future__ import annotations

import re
import unittest
from unittest import mock

import _bootstrap

from hackiclab import proc


class HiddenProcessTests(unittest.TestCase):
    def test_windows_kwargs_hide_window(self):
        with mock.patch.object(proc, "_WINDOWS", True):
            kwargs = proc.hidden_kwargs()
        self.assertIn("creationflags", kwargs)
        self.assertNotEqual(kwargs["creationflags"], 0)
        info = kwargs["startupinfo"]
        self.assertIsNotNone(info)
        self.assertTrue(info.dwFlags & 0x00000001)  # STARTF_USESHOWWINDOW
        self.assertEqual(info.wShowWindow, 0)        # SW_HIDE

    def test_non_windows_has_no_flags(self):
        with mock.patch.object(proc, "_WINDOWS", False):
            self.assertEqual(proc.hidden_kwargs(), {})

    def test_run_passes_hidden_flags(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured["args"] = args
            captured.update(kwargs)
            return "result"

        with mock.patch.object(proc, "_WINDOWS", True), \
                mock.patch.object(proc.subprocess, "run", fake_run):
            result = proc.run(["powershell", "-Command", "1"], capture_output=True)
        self.assertEqual(result, "result")
        self.assertIn("creationflags", captured)
        self.assertIn("startupinfo", captured)
        self.assertTrue(captured["capture_output"])

    def test_caller_flags_win(self):
        captured = {}

        def fake_run(args, **kwargs):
            captured.update(kwargs)
            return None

        with mock.patch.object(proc, "_WINDOWS", True), \
                mock.patch.object(proc.subprocess, "run", fake_run):
            proc.run(["x"], creationflags=123)
        self.assertEqual(captured["creationflags"], 123)

    def test_popen_passes_hidden_flags(self):
        captured = {}

        def fake_popen(args, **kwargs):
            captured.update(kwargs)
            return "proc"

        with mock.patch.object(proc, "_WINDOWS", True), \
                mock.patch.object(proc.subprocess, "Popen", fake_popen):
            self.assertEqual(proc.popen(["x"]), "proc")
        self.assertIn("creationflags", captured)


class NoRawSubprocessTests(unittest.TestCase):
    """Все внешние команды идут через hackiclab.proc — иначе появится окно."""

    ALLOWED = {"proc.py", "updater.py"}

    def test_no_direct_subprocess_in_package(self):
        pattern = re.compile(r"subprocess\.(run|Popen|call|check_output|check_call)\(")
        hits = []
        for path in (_bootstrap.ROOT / "hackiclab").rglob("*.py"):
            if path.name in self.ALLOWED:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for match in pattern.finditer(text):
                line = text[:match.start()].count("\n") + 1
                hits.append(f"{path.name}:{line}")
        self.assertEqual(hits, [], "прямой subprocess вместо proc: " + ", ".join(hits))

    def test_no_console_shell_helpers(self):
        hits = []
        for path in (_bootstrap.ROOT / "hackiclab").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            for marker in ("os.system(", "os.popen(", '"cmd.exe"', "tasklist", "taskkill"):
                if marker in text:
                    hits.append(f"{path.name}:{marker}")
        self.assertEqual(hits, [], "консольные вызовы: " + ", ".join(hits))


if __name__ == "__main__":
    unittest.main()
