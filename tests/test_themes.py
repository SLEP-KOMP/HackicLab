"""Тесты тем оформления и сохранения состояния интерфейса."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab import themes, uistate


class ThemeTests(unittest.TestCase):
    def test_system_scheme_is_known_value(self):
        self.assertIn(themes.detect_system_scheme(), ("light", "dark"))

    def test_resolve_system_returns_concrete_palette(self):
        resolved = themes.resolve("system")
        self.assertIn(resolved, ("light", "dark"))

    def test_all_builtin_themes_have_palettes(self):
        for name in (*themes.BUILTIN_THEMES, "light", "dark", "custom"):
            self.assertIn(name, themes.PALETTES)
        # «system» не палитра, а ссылка на текущую схему ОС
        self.assertIn(themes.resolve("system"), ("light", "dark"))

    def test_qss_contains_palette_colors(self):
        qss = themes.get_qss("dark")
        self.assertIn("#1e1e2e", qss)
        self.assertIn("#8839ef", qss)

    def test_unknown_theme_falls_back_to_dark(self):
        self.assertEqual(themes.get_qss("nonsense"), themes.get_qss("dark"))

    def test_background_applies_only_to_custom_theme(self):
        path = r"C:\pics\wall.png"
        custom = themes.get_qss("custom", path)
        self.assertIn("background-image", custom)
        self.assertIn("wall.png", custom)
        dark = themes.get_qss("dark", path)
        self.assertNotIn("background-image: url", dark)

    def test_background_path_is_escaped(self):
        qss = themes.get_qss("custom", r'C:\pics\my "wall".png')
        self.assertIn("my \\\"wall\\\".png", qss)
        self.assertNotIn('url("C:\\pics', qss)

    def test_preview_colors_are_hex(self):
        for name in (*themes.BASE_THEMES, *themes.BUILTIN_THEMES):
            top, bottom = themes.preview(name)
            self.assertTrue(top.startswith("#"))
            self.assertTrue(bottom.startswith("#"))


class UiStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)
        self.patch = mock.patch("hackiclab.uistate.app_home", return_value=self.home)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_defaults_use_system_theme(self):
        state = uistate.load()
        self.assertEqual(state["theme"], "system")
        self.assertEqual(state["background"], "")
        self.assertTrue(state["check_updates"])

    def test_save_and_reload(self):
        uistate.save(theme="aqua", background="C:/bg.png")
        state = uistate.load()
        self.assertEqual(state["theme"], "aqua")
        self.assertEqual(state["background"], "C:/bg.png")

    def test_unknown_keys_are_ignored(self):
        uistate.save(theme="dark", evil="payload")
        self.assertNotIn("evil", uistate.load())

    def test_broken_file_falls_back_to_defaults(self):
        (self.home / "ui.json").write_text("{ not json", encoding="utf-8")
        self.assertEqual(uistate.load()["theme"], "system")

    def test_get_and_set_value(self):
        uistate.set_value("postponed_update", "1.0.2")
        self.assertEqual(uistate.get("postponed_update"), "1.0.2")


if __name__ == "__main__":
    unittest.main()
