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


class GpuAndDualBootTests(unittest.TestCase):
    def _profile_with_dgpu(self):
        p = desktop_profile()
        p.dgpu = GPUInfo(name="GeForce RTX 3060", vendor="nvidia", device_id="2504")
        return p

    def test_disable_dgpu_adds_boot_arg(self):
        cfg = plistlib.loads(generate_config_plist(
            self._profile_with_dgpu(), BuildOptions(disable_dgpu=True)))
        boot_args = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
        self.assertIn("-wegnoegpu", boot_args)

    def test_no_boot_arg_without_dgpu(self):
        cfg = plistlib.loads(generate_config_plist(
            desktop_profile(), BuildOptions(disable_dgpu=True)))
        boot_args = cfg["NVRAM"]["Add"]["7C436110-AB2A-4BBB-A880-FE41995C9F82"]["boot-args"]
        self.assertNotIn("-wegnoegpu", boot_args)

    def test_linux_dual_boot_keeps_driver_entry(self):
        import tempfile
        from pathlib import Path

        from hackiclab.builder.efi_layout import EFILayout
        data = generate_config_plist(desktop_profile(), BuildOptions(dual_boot="both"))
        with tempfile.TemporaryDirectory() as tmp:
            layout = EFILayout(Path(tmp))
            layout.create()
            path = layout.write_plist_with_kexts(
                data, [], driver_names=["OpenRuntime.efi", "OpenLinuxBoot.efi"])
            cfg = plistlib.loads(Path(path).read_bytes())
        drivers = [d["Path"] for d in cfg["UEFI"]["Drivers"]]
        self.assertIn("OpenLinuxBoot.efi", drivers)


class DevicePropertiesTests(unittest.TestCase):
    AUDIO = "PciRoot(0x0)/Pci(0x8,0x1)/Pci(0x0,0x4)"
    ETH = "PciRoot(0x0)/Pci(0x1,0x3)/Pci(0x0,0x2)/Pci(0x3,0x0)/Pci(0x0,0x0)"
    WIFI = "PciRoot(0x0)/Pci(0x1,0x3)/Pci(0x0,0x2)/Pci(0x0,0x0)/Pci(0x0,0x0)"

    def _profile(self):
        from hackiclab.scanner.models import AudioInfo, NetInfo

        p = desktop_profile()
        p.audio = AudioInfo(codec="ALC1220", layout_id=1, pci_path=self.AUDIO)
        p.net = NetInfo(eth_chipset="i211", wifi_chipset="broadcom",
                        eth_pci_path=self.ETH, wifi_pci_path=self.WIFI)
        return p

    def test_audio_layout_id_is_written_by_path(self):
        cfg = plistlib.loads(generate_config_plist(self._profile(), BuildOptions()))
        self.assertEqual(cfg["DeviceProperties"]["Add"][self.AUDIO]["layout-id"], 1)

    def test_network_controllers_are_built_in(self):
        cfg = plistlib.loads(generate_config_plist(self._profile(), BuildOptions()))
        props = cfg["DeviceProperties"]["Add"]
        self.assertEqual(props[self.ETH]["built-in"], b"\x01")
        self.assertEqual(props[self.WIFI]["built-in"], b"\x01")

    def test_no_paths_means_no_entries(self):
        cfg = plistlib.loads(generate_config_plist(desktop_profile(), BuildOptions()))
        keys = [k for k in cfg["DeviceProperties"]["Add"] if k != "PciRoot(0x0)/Pci(0x2,0x0)"]
        self.assertEqual(keys, [])
