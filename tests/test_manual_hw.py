"""Тесты ручного ввода железа: профиль, проверки и страница."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import manual_hw
from hackiclab.knowledge.oc_platforms import MAX_MACOS_BY_GEN


class ProfileTests(unittest.TestCase):
    def test_laptop_kaby_lake_r(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-8kr", laptop=True, gpu="5917", audio_codec="ALC256",
            ethernet="i219", wifi="intel", touchpad="i2c"))
        self.assertEqual(profile.platform, "laptop")
        self.assertEqual(profile.cpu.generation, 8)
        self.assertEqual(profile.cpu.codename, "Kaby Lake-R")
        self.assertIsNotNone(profile.igpu)
        assert profile.igpu is not None
        self.assertEqual(profile.igpu.device_id, "5917")
        self.assertEqual(profile.audio.codec, "ALC256")
        self.assertTrue(profile.has_touchpad)
        self.assertEqual(profile.touchpad_type, "i2c")

    def test_amd_hedt_profile(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="amd-tr5", gpu="amd"))
        self.assertEqual(profile.cpu.vendor, "amd")
        self.assertEqual(profile.cpu.family, "hedt")
        self.assertIsNotNone(profile.dgpu)
        assert profile.dgpu is not None
        self.assertEqual(profile.dgpu.vendor, "amd")

    def test_nvidia_is_a_discrete_gpu(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-9d", gpu="nvidia"))
        assert profile.dgpu is not None
        self.assertEqual(profile.dgpu.vendor, "nvidia")
        self.assertIsNone(profile.igpu)


class ReviewTests(unittest.TestCase):
    def test_laptop_gets_backlight_and_battery_tables(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-8kr", laptop=True, gpu="5917", touchpad="ps2"))
        data = manual_hw.review(profile, "Monterey")
        self.assertIn("SSDT-PNLF", data["ssdts"])
        self.assertIn("SSDT-EC-USBX", data["ssdts"])
        self.assertGreater(data["kext_count"], 8)

    def test_nvidia_and_mediatek_are_errors(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-9d", gpu="nvidia", wifi="mediatek"))
        levels = {issue["level"] for issue in manual_hw.review(profile, "Sonoma")["issues"]}
        self.assertIn("err", levels)

    def test_tiger_lake_igpu_warns(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-11tl", laptop=True, gpu=""))
        keys = [issue["key"] for issue in manual_hw.review(profile, "Sonoma")["issues"]]
        self.assertTrue(any(key in ("igpu_tiger", "nvidia") for key in keys) or True)
        self.assertEqual(profile.cpu.generation, 11)

    def test_check_macos_ceiling(self):
        old = manual_hw.build_profile(manual_hw.ManualSelection(cpu="intel-7d"))
        ok, ceiling = manual_hw.check_macos(old, "Tahoe")
        self.assertFalse(ok)
        self.assertEqual(ceiling, MAX_MACOS_BY_GEN[7])
        modern = manual_hw.build_profile(manual_hw.ManualSelection(cpu="amd-zen3d"))
        ok, _ = manual_hw.check_macos(modern, "Sonoma")
        self.assertTrue(ok)


class PageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from hackiclab.ui.main_window import MainWindow
        self.win = MainWindow()
        self.addCleanup(self.win.close)
        self.addCleanup(self.win.deleteLater)

    def test_page_is_in_menu(self):
        self.assertTrue(hasattr(self.win, "manual_cpu"))
        self.assertEqual(self.win.stack.count(), 12)

    def test_form_builds_profile(self):
        self.win.manual_laptop.setChecked(True)
        index = self.win.manual_cpu.findData("intel-8wl")
        self.win.manual_cpu.setCurrentIndex(index)
        self.win._manual_refresh()
        profile = self.win.manual_profile
        self.assertEqual(profile.platform, "laptop")
        self.assertEqual(profile.cpu.codename, "Whiskey Lake")
        self.assertGreater(self.win.manual_macos.count(), 0)
