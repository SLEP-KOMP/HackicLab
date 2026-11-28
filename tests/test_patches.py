"""Патчи: план по железу, отчёт и применение в config.plist.

Тесты разбиты на независимые миксы, чтобы падение одного блока не маскировало
остальные: план → отчёт → конфиг.
"""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.knowledge import patches as pb
from hackiclab.scanner.models import (
    AudioInfo,
    CPUInfo,
    GPUInfo,
    HardwareProfile,
    NetInfo,
)


def _ryzen_rx580() -> HardwareProfile:
    """Наш случай: Ryzen, RX 580 2048SP, Broadcom Wi-Fi, ALC1220."""
    p = HardwareProfile()
    p.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd")
    p.net = NetInfo(wifi_chipset="broadcom", eth_chipset="i211",
                    bt_native_apple=True)
    p.dgpu = GPUInfo(name="AMD Radeon RX 580 2048SP", vendor="amd",
                     device_id="6fdf",
                     pci_path="PciRoot(0x0)/Pci(0x3,0x1)/Pci(0x0,0x0)")
    p.audio = AudioInfo(codec="ALC1220", layout_id=11)
    return p


class PatchPlanMixin(unittest.TestCase):
    """Кому какой патч положен."""

    def ids(self, profile, target=""):
        return [p.id for p in pb.plan(profile, target)]

    def test_ryzen_needs_amd_kernel(self):
        self.assertIn("cpu_amd", self.ids(_ryzen_rx580(), "Sequoia"))

    def test_broadcom_set_only_from_sonoma(self):
        p = _ryzen_rx580()
        self.assertNotIn("wifi_broadcom_efi", self.ids(p, "Ventura"))
        for target in ("Sonoma", "Sequoia", "Tahoe"):
            self.assertIn("wifi_broadcom_efi", self.ids(p, target), target)

    def test_rx580_2048sp_gets_both_gpu_patches(self):
        ids = self.ids(_ryzen_rx580(), "Sonoma")
        self.assertIn("gpu_rx580_spoof", ids)
        self.assertIn("gpu_rx580_vbios", ids)

    def test_plain_rx580_needs_no_spoof(self):
        p = _ryzen_rx580()
        p.dgpu.device_id = "67df"
        ids = self.ids(p, "Sonoma")
        self.assertNotIn("gpu_rx580_spoof", ids)
        self.assertNotIn("gpu_rx580_vbios", ids)

    def test_audio_patch_requires_known_layout(self):
        p = _ryzen_rx580()
        self.assertIn("audio_alcid", self.ids(p, "Sequoia"))
        p.audio.layout_id = 0
        self.assertNotIn("audio_alcid", self.ids(p, "Sequoia"))

    def test_security_patch_only_with_system_patches(self):
        p = _ryzen_rx580()
        self.assertIn("security_root", self.ids(p, "Sequoia"))
        # Intel + Intel Wi-Fi: системных патчей нет, значит и ослаблять защиту незачем
        plain = HardwareProfile()
        plain.cpu = CPUInfo(name="Intel Core i5", vendor="intel", generation=9)
        plain.net = NetInfo(wifi_chipset="intel")
        self.assertEqual([], self.ids(plain, "Sequoia"))

    def test_auto_skips_unsafe_patches(self):
        auto = pb.auto_ids(pb.plan(_ryzen_rx580(), "Sequoia"))
        self.assertIn("wifi_broadcom_efi", auto)
        self.assertNotIn("gpu_rx580_spoof", auto)
        self.assertNotIn("gpu_rx580_vbios", auto)


class PatchReportMixin(unittest.TestCase):
    """Текст отчёта для пользователя."""

    def test_report_marks_auto_choice(self):
        text = pb.report(_ryzen_rx580(), "Sequoia")
        self.assertIn("[x] Патчи ядра AMD Vanilla", text)
        self.assertIn("[ ] RX 580 2048SP: подмена device-id", text)

    def test_report_lists_root_steps(self):
        text = pb.report(_ryzen_rx580(), "Sequoia")
        self.assertIn("Post-Install Root Patch", text)
        self.assertIn("Reset NVRAM", text)

    def test_report_explicit_selection(self):
        text = pb.report(_ryzen_rx580(), "Sequoia", enabled={"cpu_amd"})
        self.assertIn("[x] Патчи ядра AMD Vanilla", text)
        self.assertIn("[ ] Broadcom Wi-Fi: набор OCLP в EFI", text)

    def test_report_english(self):
        text = pb.report(_ryzen_rx580(), "Sequoia", lang="en")
        self.assertIn("On macOS (root patches", text)
        self.assertIn("AMD Vanilla", text)


class PatchConfigMixin(unittest.TestCase):
    """Что попадает в config.plist при включённых и выключенных патчах."""

    def cfg(self, patches):
        data = generate_config_plist(
            _ryzen_rx580(), BuildOptions(target_macos="Sequoia", patches=patches))
        return plistlib.loads(data)

    def dp(self, cfg):
        return cfg["DeviceProperties"]["Add"].get(
            "PciRoot(0x0)/Pci(0x3,0x1)/Pci(0x0,0x0)", {})

    def nv(self, cfg):
        return cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]

    def test_auto_injects_device_id(self):
        self.assertEqual(b"\xdf\x67\x00\x00",
                         self.dp(self.cfg(None)).get("device-id"))

    def test_disabled_patch_leaves_no_device_id(self):
        self.assertNotIn("device-id", self.dp(self.cfg(set())))

    def test_only_selected_patch_applies(self):
        cfg = self.cfg({"gpu_rx580_spoof"})
        self.assertEqual(b"\xdf\x67\x00\x00", self.dp(cfg).get("device-id"))
        self.assertEqual(bytes([0x67, 0, 0, 0]), self.nv(cfg)["csr-active-config"])
        self.assertEqual([], cfg["Kernel"].get("Block", []))

    def test_security_patch_sets_oclp_csr(self):
        cfg = self.cfg({"security_root"})
        self.assertEqual(bytes([0x00, 0x08, 0x03, 0x00]),
                         self.nv(cfg)["csr-active-config"])

    def test_wifi_patch_adds_ioskywalk_block(self):
        cfg = self.cfg({"wifi_broadcom_efi"})
        self.assertIn("com.apple.iokit.IOSkywalkFamily",
                      [b["Identifier"] for b in cfg["Kernel"]["Block"]])

    def test_wifi_block_absent_without_patch(self):
        cfg = self.cfg({"cpu_amd"})
        self.assertEqual([], cfg["Kernel"].get("Block", []))

    def test_audio_patch_adds_alcid(self):
        self.assertIn("alcid=11", self.nv(self.cfg(None))["boot-args"])
        self.assertNotIn("alcid=", self.nv(self.cfg(set()))["boot-args"])


class PatchManualMixin(unittest.TestCase):
    """Ручной профиль: device-id и UEFI-пути не должны теряться."""

    def test_manual_option_keeps_device_id(self):
        from hackiclab.knowledge import manual_hw
        sel = manual_hw.ManualSelection(cpu="amd-zen2d", gpu="6fdf")
        p = manual_hw.build_profile(sel)
        self.assertEqual("6FDF", p.dgpu.device_id)
        ids = [x.id for x in pb.plan(p, "Sequoia")]
        self.assertIn("gpu_rx580_spoof", ids)
        self.assertIn("gpu_rx580_vbios", ids)

    def test_name_only_detection_without_device_id(self):
        p = _ryzen_rx580()
        p.dgpu.device_id = ""
        ids = [x.id for x in pb.plan(p, "Sequoia")]
        self.assertIn("gpu_rx580_spoof", ids)

    def test_merge_copies_pci_path_from_scan(self):
        manual = _ryzen_rx580()
        manual.dgpu.pci_path = ""
        manual.dgpu.device_id = ""
        pb.merge_scan_paths(manual, _ryzen_rx580())
        self.assertEqual("PciRoot(0x0)/Pci(0x3,0x1)/Pci(0x0,0x0)",
                         manual.dgpu.pci_path)
        self.assertEqual("6fdf", manual.dgpu.device_id.lower())

    def test_merge_keeps_existing_path(self):
        manual = _ryzen_rx580()
        manual.dgpu.pci_path = "PciRoot(0x0)/Pci(0x1,0x0)"
        pb.merge_scan_paths(manual, _ryzen_rx580())
        self.assertEqual("PciRoot(0x0)/Pci(0x1,0x0)", manual.dgpu.pci_path)

    def test_merge_ignores_other_vendor(self):
        manual = _ryzen_rx580()
        manual.dgpu.pci_path = ""
        scan = _ryzen_rx580()
        scan.dgpu.vendor = "nvidia"
        pb.merge_scan_paths(manual, scan)
        self.assertEqual("", manual.dgpu.pci_path)


if __name__ == "__main__":
    unittest.main()
