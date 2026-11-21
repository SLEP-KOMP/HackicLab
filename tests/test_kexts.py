"""Тесты подбора кекстов: версии под macOS, целостность архивов, iGPU."""

from __future__ import annotations

import io
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.builder import downloader as dl_mod
from hackiclab.builder import fetcher
from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.builder.downloader import Downloader
from hackiclab.knowledge.kexts import (
    KEXT_DB,
    asset_variant,
    macos_in_range,
    select_kexts,
)
from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo

ASSET_NAMES = [
    "AirportItlwm_v2.3.0_stable_BigSur.kext.zip",
    "AirportItlwm_v2.3.0_stable_Monterey.kext.zip",
    "AirportItlwm_v2.3.0_stable_Sonoma14.0.kext.zip",
    "AirportItlwm_v2.3.0_stable_Sonoma14.4.kext.zip",
    "AirportItlwm_v2.3.0_stable_Ventura.kext.zip",
]
RELEASE_HTML = "\n".join(
    f'<a href="/OpenIntelWireless/itlwm/releases/download/v2.3.0/{name}">{name}</a>'
    for name in ASSET_NAMES
)


def laptop_intel(gen: int = 8, wifi: str = "intel") -> HardwareProfile:
    profile = HardwareProfile(platform="laptop")
    profile.cpu = CPUInfo(name="Intel Core i7-8550U", vendor="intel", generation=gen,
                          codename="Kaby Lake-R")
    profile.net = NetInfo(wifi_chipset=wifi, has_bt=False)
    return profile


class VariantTests(unittest.TestCase):
    def test_variant_follows_target_macos(self):
        entry = KEXT_DB["AirportItlwm"]
        self.assertEqual(asset_variant(entry, "Monterey"), "Monterey")
        self.assertEqual(asset_variant(entry, "Ventura"), "Ventura")
        self.assertEqual(asset_variant(entry, "Sonoma"), "Sonoma")
        self.assertEqual(asset_variant(entry, ""), "")

    def test_variant_uses_newest_fitting_build(self):
        entry = KEXT_DB["AirportItlwm"]
        self.assertEqual(asset_variant(entry, "Sequoia"), "Sonoma")

    def test_macos_range(self):
        entry = KEXT_DB["AirportItlwm"]
        self.assertTrue(macos_in_range(entry, "Monterey"))
        self.assertTrue(macos_in_range(entry, "Sonoma"))
        self.assertFalse(macos_in_range(entry, "Sequoia"))
        self.assertFalse(macos_in_range(entry, "High Sierra"))
        self.assertTrue(macos_in_range(entry, ""))

    def test_selection_falls_back_to_itlwm_on_sequoia(self):
        names = [e.name for e in select_kexts(laptop_intel(), "airport",
                                              target_macos="Sequoia")]
        self.assertIn("itlwm", names)
        self.assertNotIn("AirportItlwm", names)

    def test_selection_keeps_airport_on_monterey(self):
        names = [e.name for e in select_kexts(laptop_intel(), "airport",
                                              target_macos="Monterey")]
        self.assertIn("AirportItlwm", names)


class ReleaseFileTests(unittest.TestCase):
    def test_picks_build_for_target_macos(self):
        d = Downloader()
        with mock.patch.object(Downloader, "_fetch_release_html", return_value=RELEASE_HTML):
            for target, expected in (
                ("Monterey", "AirportItlwm_v2.3.0_stable_Monterey.kext.zip"),
                ("Ventura", "AirportItlwm_v2.3.0_stable_Ventura.kext.zip"),
                ("Sonoma", "AirportItlwm_v2.3.0_stable_Sonoma14.4.kext.zip"),
            ):
                self.assertEqual(
                    d.kext_release_file(KEXT_DB["AirportItlwm"], "v2.3.0",
                                        target_macos=target),
                    expected)

    def test_release_builds_prefer_latest_sonoma(self):
        d = Downloader()
        with mock.patch.object(Downloader, "_fetch_release_html", return_value=RELEASE_HTML):
            picked = d.kext_release_file(KEXT_DB["AirportItlwm"], "v2.3.0",
                                         target_macos="Sonoma")
        self.assertIn("Sonoma14.4", picked)


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        patcher = mock.patch.object(dl_mod, "cache_dir", return_value=self.tmp / "cache")
        patcher.start()
        self.addCleanup(patcher.stop)
        patch_cache = mock.patch.object(fetcher, "cache_dir",
                                        return_value=self.tmp / "cache2")
        patch_cache.start()
        self.addCleanup(patch_cache.stop)

    def _asset(self, name: str = "Test.zip", size: int = 0) -> dict:
        return {"assets": [{"name": name, "size": size,
                            "browser_download_url": f"https://example.com/{name}"}]}

    def test_download_asset_rejects_html_page(self):
        with mock.patch.object(fetcher, "download_bytes", return_value=b"<html>404</html>"):
            with self.assertRaises(IOError):
                fetcher.download_asset(self._asset(), ".zip", self.tmp / "out")

    def test_download_asset_accepts_real_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("a.txt", "x" * 2000)
        data = buf.getvalue()
        with mock.patch.object(fetcher, "download_bytes", return_value=data):
            out = fetcher.download_asset(self._asset(size=len(data)), ".zip",
                                         self.tmp / "out")
        assert out is not None
        self.assertEqual(out.read_bytes(), data)

    def test_download_asset_rejects_size_mismatch(self):
        with mock.patch.object(fetcher, "download_bytes", return_value=b"x" * 100):
            with self.assertRaises(IOError):
                fetcher.download_asset(self._asset(size=5000), ".zip", self.tmp / "out")

    def test_download_kext_rejects_non_zip(self):
        entry = KEXT_DB["AirportItlwm"]
        with mock.patch.object(dl_mod.GitHubFetcher, "latest_tag", return_value="v2.3.0"), \
                mock.patch.object(Downloader, "_fetch_release_html", return_value=RELEASE_HTML), \
                mock.patch.object(dl_mod, "download_bytes", return_value=b"not a zip" * 100):
            result = Downloader().download_kext(entry, self.tmp / "kexts",
                                                target_macos="Ventura")
        self.assertIsNone(result)


class IgpuTests(unittest.TestCase):
    def _props(self, gen: int, platform: str, name: str) -> dict:
        profile = HardwareProfile(platform=platform)
        profile.cpu = CPUInfo(name="Intel", vendor="intel", generation=gen)
        profile.igpu = GPUInfo(name=name, vendor="intel", is_integrated=True)
        cfg = plistlib.loads(generate_config_plist(profile, BuildOptions()))
        return cfg["DeviceProperties"]["Add"].get("PciRoot(0x0)/Pci(0x2,0x0)", {})

    def test_kaby_lake_laptop_uses_recommended_id(self):
        props = self._props(7, "laptop", "Intel HD Graphics 630")
        self.assertEqual(props["AAPL,ig-platform-id"], bytes([0x00, 0x00, 0x1B, 0x59]))

    def test_kaby_lake_laptop_gets_framebuffer_patches(self):
        props = self._props(7, "laptop", "Intel HD Graphics 620")
        self.assertEqual(props["framebuffer-patch-enable"], bytes([0x01, 0x00, 0x00, 0x00]))
        self.assertEqual(props["framebuffer-stolenmem"], bytes([0x00, 0x00, 0x30, 0x01]))
        self.assertEqual(props["framebuffer-fbmem"], bytes([0x00, 0x00, 0x90, 0x00]))

    def test_kaby_lake_desktop_uses_desktop_id(self):
        props = self._props(7, "desktop", "Intel HD Graphics 630")
        self.assertEqual(props["AAPL,ig-platform-id"], bytes([0x00, 0x00, 0x12, 0x59]))
        self.assertNotIn("framebuffer-stolenmem", props)

    def test_comet_lake_laptop_uses_mobile_id(self):
        props = self._props(10, "laptop", "Intel UHD Graphics 620")
        self.assertEqual(props["AAPL,ig-platform-id"], bytes([0x00, 0x00, 0x9B, 0x3E]))

    def test_comet_lake_desktop_uses_coffee_lake_id(self):
        props = self._props(10, "desktop", "Intel UHD Graphics 630")
        self.assertEqual(props["AAPL,ig-platform-id"], bytes([0x07, 0x00, 0x9B, 0x3E]))


class AudioSelectionTests(unittest.TestCase):
    def test_applealc_kept_with_unknown_codec(self):
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        profile.audio = AudioInfo(name="Realtek High Definition Audio", codec="",
                                  pci_device=31, pci_function=3)
        self.assertIn("AppleALC", [e.name for e in select_kexts(profile)])

    def test_no_applealc_without_audio_hardware(self):
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        self.assertNotIn("AppleALC", [e.name for e in select_kexts(profile)])

    def test_realtek_nic_gets_driver(self):
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        profile.net = NetInfo(eth_chipset="rtl8111", eth_name="Realtek PCIe GbE")
        self.assertIn("RealtekRTL8111", [e.name for e in select_kexts(profile)])


class WifiNoneModeTests(unittest.TestCase):
    def test_none_mode_drops_wifi_and_bt(self):
        names = [e.name for e in select_kexts(laptop_intel(), "none", target_macos="Sonoma")]
        self.assertNotIn("itlwm", names)
        self.assertNotIn("AirportItlwm", names)
        self.assertNotIn("IntelBluetoothFirmware", names)


class HeliPortTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def test_heliport_is_downloaded_and_saved(self):
        release = {"assets": [{"name": "HeliPort.dmg", "size": 8601948,
                               "browser_download_url": "https://example.com/HeliPort.dmg"}]}
        data = b"x" * 1_100_000
        with mock.patch.object(dl_mod.GitHubFetcher, "latest_release", return_value=release), \
                mock.patch.object(dl_mod, "download_bytes", return_value=data):
            out = Downloader().download_heliport(self.tmp)
        assert out is not None
        self.assertEqual(out.name, "HeliPort.dmg")
        self.assertEqual(out.stat().st_size, len(data))

    def test_heliport_rejects_truncated_file(self):
        release = {"assets": [{"name": "HeliPort.dmg", "size": 8601948,
                               "browser_download_url": "https://example.com/HeliPort.dmg"}]}
        with mock.patch.object(dl_mod.GitHubFetcher, "latest_release", return_value=release), \
                mock.patch.object(dl_mod, "download_bytes", return_value=b"<html>"):
            self.assertIsNone(Downloader().download_heliport(self.tmp))

    def test_heliport_missing_asset(self):
        with mock.patch.object(dl_mod.GitHubFetcher, "latest_release",
                               return_value={"assets": []}):
            self.assertIsNone(Downloader().download_heliport(self.tmp))


class SmbiosDefaultTargetTests(unittest.TestCase):
    def test_empty_target_matches_built_model(self):
        """Карточка без выбранной macOS должна обещать ту же модель, что сборка."""
        from hackiclab.knowledge.kexts import smbios_model_for
        from hackiclab.scanner.models import CPUInfo, HardwareProfile, NetInfo
        p = HardwareProfile(cpu=CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10))
        p.net = NetInfo(eth_chipset="i211", wifi_chipset="broadcom")
        self.assertEqual(
            smbios_model_for(p, ""),
            smbios_model_for(p, "macOS Sequoia"),
        )


def _amd_profile(nvme: bool = True, wifi: str = "broadcom", bt_native: bool = True):
    """Профиль этой машины: Ryzen 5 3600, RX 580, ALC1220, I211, NVMe."""
    from hackiclab.scanner.models import StorageInfo

    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10, codename="Zen 2")
    p.audio = AudioInfo(codec="ALC1220")
    p.net = NetInfo(eth_chipset="i211", wifi_chipset=wifi, bt_native_apple=bt_native)
    p.storage = StorageInfo(nvme_present=nvme)
    p.dgpu = GPUInfo(name="AMD Radeon RX 580 2048SP", vendor="amd")
    return p


class AmdAndLegacyWifiTests(unittest.TestCase):
    def test_amd_gets_mce_disabler(self):
        names = [k.name for k in select_kexts(_amd_profile(), target_macos="Sonoma")]
        self.assertIn("AppleMCEReporterDisabler", names)

    def test_nvme_fix_follows_storage(self):
        with_nvme = [k.name for k in select_kexts(_amd_profile(nvme=True),
                                                  target_macos="Sonoma")]
        without = [k.name for k in select_kexts(_amd_profile(nvme=False),
                                                target_macos="Sonoma")]
        self.assertIn("NVMeFix", with_nvme)
        self.assertNotIn("NVMeFix", without)

    def test_broadcom_legacy_set_from_ventura(self):
        for target in ("Ventura", "Sonoma", "Tahoe"):
            names = [k.name for k in select_kexts(_amd_profile(), target_macos=target)]
            for kext in ("AMFIPass", "IOSkywalkFamily", "IO80211FamilyLegacy"):
                self.assertIn(kext, names, target)

    def test_broadcom_on_monterey_needs_no_legacy_set(self):
        names = [k.name for k in select_kexts(_amd_profile(), target_macos="Monterey")]
        self.assertNotIn("IOSkywalkFamily", names)
        self.assertNotIn("IO80211FamilyLegacy", names)

    def test_non_native_broadcom_also_gets_fixup(self):
        names = [k.name for k in select_kexts(_amd_profile(bt_native=False),
                                              target_macos="Ventura")]
        self.assertIn("AirportBrcmFixup", names)

    def test_config_blocks_stock_ioskywalk_on_ventura_plus(self):
        cfg = plistlib.loads(generate_config_plist(_amd_profile(),
                                                   BuildOptions(target_macos="Sonoma")))
        blocks = cfg["Kernel"]["Block"]
        self.assertIn("com.apple.iokit.IOSkywalkFamily",
                      [b["Identifier"] for b in blocks])
        self.assertEqual(blocks[0]["Strategy"], "Exclude")

    def test_config_keeps_block_empty_on_monterey(self):
        cfg = plistlib.loads(generate_config_plist(_amd_profile(),
                                                   BuildOptions(target_macos="Monterey")))
        self.assertEqual(cfg["Kernel"]["Block"], [])

    def test_direct_url_skips_release_lookup(self):
        entry = KEXT_DB["IO80211FamilyLegacy"]
        self.assertTrue(entry.url.startswith("https://"))
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        with mock.patch.object(dl_mod.GitHubFetcher, "latest_tag",
                               side_effect=AssertionError("тег не нужен")), \
                mock.patch.object(dl_mod, "download_bytes", return_value=b"<html>"):
            self.assertIsNone(Downloader().download_kext(entry, Path(tmp.name)))

    def test_i211_uses_legacy_kext_before_monterey(self):
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
        profile.net = NetInfo(eth_chipset="i211")

        old = [e.name for e in select_kexts(profile, target_macos="Big Sur")]
        self.assertIn("AppleIntelI210Ethernet", old)
        self.assertNotIn("AppleIGB", old)

        new = [e.name for e in select_kexts(profile, target_macos="Sonoma")]
        self.assertIn("AppleIGB", new)
        self.assertNotIn("AppleIntelI210Ethernet", new)

class OclpPayloadEntriesTests(unittest.TestCase):
    """Кексты без GitHub-релизов берутся прямой ссылкой из payloads OCLP.

    У этих проектов нет страницы releases/latest: тег не резолвится, и до
    правки кекст молча выпадал из сборки (Warn «не скачались» появился позже).
    """

    NAMES = ("AMFIPass", "IOSkywalkFamily", "AppleMCEReporterDisabler",
             "AppleIntelI210Ethernet")

    def test_entries_have_direct_payload_url(self):
        for name in self.NAMES:
            entry = KEXT_DB[name]
            with self.subTest(name=name):
                self.assertTrue(
                    entry.url.startswith(
                        "https://github.com/dortania/OpenCore-Legacy-Patcher/raw/"),
                    f"{name}: {entry.url}")


class AmdApuKextTests(unittest.TestCase):
    """NootedRed нужен AMD APU без дискретки, но не при наличии dGPU."""

    def test_apu_laptop_gets_nootedred(self):
        profile = HardwareProfile(platform="laptop")
        profile.cpu = CPUInfo(name="AMD Ryzen 5 4500U", vendor="amd",
                              generation=2, codename="Renoir")
        profile.igpu = GPUInfo(name="Radeon Vega 6", vendor="amd",
                               device_id="1636", is_integrated=True)
        names = [e.name for e in select_kexts(profile, target_macos="Ventura")]
        self.assertIn("NootedRed", names)
        self.assertIn("ECEnabler", names)

    def test_desktop_with_dgpu_skips_nootedred(self):
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="AMD Ryzen 7 2700", vendor="amd", generation=2)
        profile.igpu = GPUInfo(name="Radeon Vega", vendor="amd", is_integrated=True)
        profile.dgpu = GPUInfo(name="Radeon RX 580", vendor="amd", device_id="67DF")
        names = [e.name for e in select_kexts(profile, target_macos="Sonoma")]
        self.assertNotIn("NootedRed", names)

    def test_apu_skips_whatevergreen(self):
        """NootedRed конфликтует с WhateverGreen — на APU остаётся только он."""
        profile = HardwareProfile(platform="laptop")
        profile.cpu = CPUInfo(name="AMD Ryzen 5 4500U", vendor="amd",
                              generation=2, codename="Renoir")
        profile.igpu = GPUInfo(name="Radeon Vega 6", vendor="amd",
                               device_id="1636", is_integrated=True)
        names = [e.name for e in select_kexts(profile, target_macos="Ventura")]
        self.assertIn("NootedRed", names)
        self.assertNotIn("WhateverGreen", names)


class AmdNaviKextTests(unittest.TestCase):
    """Navi 2x: NootRX вместо WhateverGreen — вместе они конфликтуют."""

    def _profile(self, name: str, device_id: str) -> HardwareProfile:
        profile = HardwareProfile(platform="desktop")
        profile.cpu = CPUInfo(name="AMD Ryzen 5 5600X", vendor="amd", generation=10)
        profile.dgpu = GPUInfo(name=name, vendor="amd", device_id=device_id)
        return profile

    def test_navi21_takes_nootrx_instead_of_whatevergreen(self):
        names = [e.name for e in select_kexts(
            self._profile("AMD Radeon RX 6800 XT", "73BF"), target_macos="Sonoma")]
        self.assertIn("NootRX", names)
        self.assertNotIn("WhateverGreen", names)

    def test_navi23_takes_nootrx_on_tahoe(self):
        names = [e.name for e in select_kexts(
            self._profile("AMD Radeon RX 6600", "73FF"), target_macos="Tahoe")]
        self.assertIn("NootRX", names)
        self.assertNotIn("WhateverGreen", names)

    def test_polaris_still_takes_whatevergreen(self):
        names = [e.name for e in select_kexts(
            self._profile("AMD Radeon RX 580", "67DF"), target_macos="Sonoma")]
        self.assertIn("WhateverGreen", names)
        self.assertNotIn("NootRX", names)

    def test_navi_2x_never_pairs_both_plugins(self):
        for target in ("Ventura", "Sonoma", "Sequoia", "Tahoe"):
            with self.subTest(target=target):
                names = [e.name for e in select_kexts(
                    self._profile("AMD Radeon RX 6750 XT", "73DF"), target_macos=target)]
                self.assertFalse({"NootRX", "WhateverGreen"} <= set(names), target)


if __name__ == "__main__":
    unittest.main()
