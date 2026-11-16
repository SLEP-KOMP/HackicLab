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

    def test_all_builtin_themes_have_palettes(self):
        for name in (*themes.BUILTIN_THEMES, "light", "dark", "custom"):
            self.assertIn(name, themes.PALETTES)
        # «system» не палитра, а ссылка на текущую схему ОС
        self.assertIn(themes.resolve("system"), ("light", "dark"))

    def test_qss_contains_palette_colors(self):
        qss = themes.get_qss("dark")
        self.assertIn("#14151f", qss)
        self.assertIn("#8b5cf6", qss)

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


class SystemSchemeTests(unittest.TestCase):
    def test_high_contrast_wins_over_apps_light(self):
        """HC-схема с чёрным окном важнее AppsUseLightTheme=1."""
        with mock.patch.object(themes, "_hc_enabled", return_value=True), \
             mock.patch.object(themes, "_hc_scheme", return_value="dark"), \
             mock.patch.object(themes, "_apps_light", return_value=True):
            self.assertEqual(themes.detect_system_scheme(), "dark")

    def test_high_contrast_light_scheme(self):
        with mock.patch.object(themes, "_hc_enabled", return_value=True), \
             mock.patch.object(themes, "_hc_scheme", return_value="light"), \
             mock.patch.object(themes, "_apps_light", return_value=False):
            self.assertEqual(themes.detect_system_scheme(), "light")

    def test_apps_theme_without_high_contrast(self):
        with mock.patch.object(themes, "_hc_enabled", return_value=False), \
             mock.patch.object(themes, "_apps_light", return_value=True):
            self.assertEqual(themes.detect_system_scheme(), "light")

    def test_qt_scheme_fallback(self):
        with mock.patch.object(themes, "_hc_enabled", return_value=False), \
             mock.patch.object(themes, "_apps_light", return_value=None), \
             mock.patch.object(themes, "_qt_color_scheme", return_value="dark"):
            self.assertEqual(themes.detect_system_scheme(), "dark")

    def test_default_is_dark(self):
        with mock.patch.object(themes, "_hc_enabled", return_value=False), \
             mock.patch.object(themes, "_apps_light", return_value=None), \
             mock.patch.object(themes, "_qt_color_scheme", return_value=None), \
             mock.patch.object(themes, "_palette_scheme", return_value=None):
            self.assertEqual(themes.detect_system_scheme(), "dark")


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
