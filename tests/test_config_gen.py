"""Тесты генерации config.plist: структура, сериализация, SMBIOS."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.scanner.models import CPUInfo, GPUInfo, HardwareProfile


def desktop_profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop", board_vendor="ASUS", board_name="Z390")
    p.cpu = CPUInfo(name="Intel Core i5-9400", vendor="intel", generation=9,
                    codename="Coffee Lake", oc_platform="Coffee Lake",
                    family="desktop", core_count=6, thread_count=6)
    p.igpu = GPUInfo(name="UHD 630", vendor="intel", device_id="3E92", is_integrated=True)
    return p


class ConfigGenTests(unittest.TestCase):
    def test_plist_is_valid_and_complete(self):
        data = generate_config_plist(desktop_profile(), BuildOptions())
        cfg = plistlib.loads(data)
        for section in ("ACPI", "Booter", "DeviceProperties", "Kernel", "Misc",
                        "NVRAM", "PlatformInfo", "UEFI"):
            self.assertIn(section, cfg)
        self.assertIsInstance(cfg["Kernel"]["Add"], list)
        self.assertIsInstance(cfg["ACPI"]["Add"], list)
        self.assertTrue(cfg["ACPI"]["Add"], "ACPI Add пуст")

    def test_intel_gets_ssdt_plug(self):
        cfg = plistlib.loads(generate_config_plist(desktop_profile(), BuildOptions()))
        paths = [x["Path"] for x in cfg["ACPI"]["Add"]]
        self.assertIn("SSDT-PLUG.aml", paths)

    def test_laptop_gets_backlight_and_no_fake_ec(self):
        p = desktop_profile()
        p.platform = "laptop"
        cfg = plistlib.loads(generate_config_plist(p, BuildOptions()))
        paths = [x["Path"] for x in cfg["ACPI"]["Add"]]
        self.assertIn("SSDT-PNLF.aml", paths)
        self.assertNotIn("SSDT-EC.aml", paths)

    def test_ig_platform_id_uses_data_type(self):
        cfg = plistlib.loads(generate_config_plist(desktop_profile(), BuildOptions()))
        props = cfg["DeviceProperties"]["Add"].get("PciRoot(0x0)/Pci(0x2,0x0)")
        self.assertIsNotNone(props)
        self.assertIsInstance(props["AAPL,ig-platform-id"], bytes)
        self.assertEqual(len(props["AAPL,ig-platform-id"]), 4)

    def test_amd_profile_has_no_intel_igpu_props(self):
        p = desktop_profile()
        p.cpu.vendor = "amd"
        p.cpu.generation = 10
        p.igpu = None
        cfg = plistlib.loads(generate_config_plist(p, BuildOptions()))
        self.assertNotIn("PciRoot(0x0)/Pci(0x2,0x0)", cfg["DeviceProperties"]["Add"])
        paths = [x["Path"] for x in cfg["ACPI"]["Add"]]
        self.assertNotIn("SSDT-PLUG.aml", paths)


if __name__ == "__main__":
    unittest.main()
