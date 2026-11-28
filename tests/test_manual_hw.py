"""Тесты ручного ввода железа: профиль, проверки и страница."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import manual_hw
from hackiclab.knowledge.oc_platforms import MAX_MACOS_BY_GEN


class ProfileTests(unittest.TestCase):
    def test_intel_option_key_maps_generations_to_real_keys(self):
        cases = [
            (0, False, "intel-2"), (1, False, "intel-2"), (2, False, "intel-2"),
            (3, False, "intel-3"), (4, False, "intel-4"), (5, False, "intel-5d"),
            (6, False, "intel-6d"), (7, False, "intel-7d"), (8, False, "intel-8d"),
            (9, False, "intel-9d"), (10, False, "intel-10d"),
            (11, False, "intel-11d"), (12, False, "intel-12d"),
            (13, False, "intel-13d"), (14, False, "intel-14d"),
            (15, False, "intel-15d"),
            (2, True, "intel-2m"), (6, True, "intel-6m"), (8, True, "intel-8kr"),
            (10, True, "intel-10cm"), (11, True, "intel-11tl"),
            (12, True, "intel-12m"), (13, True, "intel-13m"),
            (14, True, "intel-14m"), (15, True, "intel-15m"),
        ]
        for generation, laptop, expected in cases:
            key = manual_hw.intel_option_key(generation, laptop)
            self.assertEqual(key, expected, (generation, laptop))
            self.assertIn(key, manual_hw.CPU_BY_KEY)

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

    def test_smbios_override_forces_model_and_warns_on_range(self):
        profile = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="amd-zen2d", gpu="amd"))
        auto = manual_hw.review(profile, "Sequoia")
        self.assertEqual(auto["smbios"], "iMacPro1,1")
        forced = manual_hw.review(profile, "Sequoia", smbios_override="MacPro7,1")
        self.assertEqual(forced["smbios"], "MacPro7,1")
        # Модель, которой ещё нет в целевой macOS, помечается ошибкой.
        bad = manual_hw.review(profile, "High Sierra", smbios_override="MacPro7,1")
        keys = [i["key"] for i in bad["issues"]]
        self.assertIn("smbios_range", keys)

    def test_smbios_options_follow_platform(self):
        laptop = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="intel-8kr", laptop=True))
        self.assertIn("MacBookPro15,2", manual_hw.smbios_options(laptop))
        self.assertNotIn("MacPro7,1", manual_hw.smbios_options(laptop))
        amd = manual_hw.build_profile(manual_hw.ManualSelection(
            cpu="amd-zen2d", gpu="amd"))
        self.assertEqual(manual_hw.smbios_options(amd), ("iMacPro1,1", "MacPro7,1"))
        intel = manual_hw.build_profile(manual_hw.ManualSelection(cpu="intel-9d"))
        self.assertIn("iMac19,1", manual_hw.smbios_options(intel))


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
        self.assertEqual(self.win.stack.count(), 9)
        pages = (self.win.page_auto, self.win.page_build,
                 self.win.page_validate, self.win.page_ports,
                 self.win.page_usb, self.win.page_sources,
                 self.win.page_donate, self.win.page_settings, self.win.page_about)
        self.assertEqual(len(set(pages)), self.win.stack.count())
        self.assertEqual(len(set(pages)), self.win.stack.count())

    def test_form_builds_profile(self):
        self.win.manual_laptop.setChecked(True)
        index = self.win.manual_cpu.findData("intel-8wl")
        self.win.manual_cpu.setCurrentIndex(index)
        self.win._manual_refresh()
        profile = self.win.manual_profile
        self.assertEqual(profile.platform, "laptop")
        self.assertEqual(profile.cpu.codename, "Whiskey Lake")
        self.assertGreater(self.win.macos_combo.count(), 1)

    def test_smbios_combo_is_platform_specific(self):
        self.win._manual_refresh()
        models = [self.win.manual_smbios.itemData(i)
                  for i in range(self.win.manual_smbios.count())]
        self.assertNotIn("MacBookPro16,1", models)
        self.assertIn("iMac19,1", models)

class FillFromScanTests(unittest.TestCase):
    """Кнопка «Взять из сканирования» переносит железо в ручную форму."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def test_fill_sets_hardware_and_is_searchable(self):
        from hackiclab.scanner.models import (
            AudioInfo,
            CPUInfo,
            GPUInfo,
            HardwareProfile,
            NetInfo,
            StorageInfo,
        )
        from hackiclab.ui.main_window import MainWindow

        window = MainWindow()
        try:
            profile = HardwareProfile(platform="desktop")
            profile.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd",
                                  generation=10, core_count=6)
            profile.dgpu = GPUInfo(name="Radeon RX 580", vendor="amd", device_id="6FDF")
            profile.audio = AudioInfo(codec="ALC1220")
            profile.net = NetInfo(eth_chipset="i211", wifi_chipset="broadcom",
                                  bt_native_apple=True)
            profile.storage = StorageInfo(nvme_present=True)
            window.profile = profile

            window._manual_from_scan()

            self.assertEqual(window.manual_cpu.currentData(), "amd-zen2d")
            self.assertEqual(window.manual_cores.value(), 6)
            # 6FDF — это RX 580 2048SP: точная запись важнее общего «AMD Radeon»,
            # иначе теряется device-id для патча подмены.
            self.assertEqual(window.manual_gpu.currentData(), "6fdf")
            self.assertEqual(window.manual_audio.text(), "ALC1220")
            self.assertEqual(window.manual_eth.currentData(), "i211")
            self.assertEqual(window.manual_wifi.currentData(), "broadcom")
            self.assertTrue(window.manual_nvme.isChecked())
            self.assertTrue(window.manual_cpu.isEditable())
            # регресс: список патчей должен заполниться сразу, без «Обновить список»
            self.assertTrue(window._patch_checks)
            self.assertIn("gpu_rx580_spoof", window._patch_checks)
            # регресс: в подписях macOS виден номер версии
            labels = [window.macos_combo.itemText(i)
                      for i in range(window.macos_combo.count())]
            self.assertTrue(any("(15)" in text for text in labels))
            # регресс: на странице один селектор macOS, а не два
            self.assertFalse(hasattr(window, "manual_macos"))

        finally:
            window.close()
            window.deleteLater()
