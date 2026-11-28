"""Драйверы OpenCore: ResetNvram/ToggleSip всегда, OpenCanopy по флагу."""

from __future__ import annotations

import plistlib
import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.builder import want_drivers
from hackiclab.builder.config_gen import BuildOptions, generate_config_plist
from hackiclab.scanner.models import AudioInfo, CPUInfo, HardwareProfile


def _desktop() -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core i7-8700", vendor="intel", generation=8)
    return p


class DriverListTests(unittest.TestCase):
    def test_base_drivers_include_reset_and_sip(self):
        names = want_drivers(BuildOptions())
        self.assertIn("OpenRuntime.efi", names)
        self.assertIn("OpenHfsPlus.efi", names)
        self.assertIn("ResetNvramEntry.efi", names)
        self.assertIn("ToggleSipEntry.efi", names)
        self.assertNotIn("OpenCanopy.efi", names)

    def test_gui_picker_adds_opencanopy(self):
        names = want_drivers(BuildOptions(gui_picker=True))
        self.assertIn("OpenCanopy.efi", names)

    def test_linux_dual_boot_adds_driver(self):
        names = want_drivers(BuildOptions(dual_boot="linux"))
        self.assertIn("OpenLinuxBoot.efi", names)


class PickerConfigTests(unittest.TestCase):
    def test_default_picker_is_builtin(self):
        cfg = plistlib.loads(generate_config_plist(_desktop(), BuildOptions()))
        self.assertEqual(cfg["Misc"]["Boot"]["PickerMode"], "Builtin")

    def test_gui_picker_switches_to_external(self):
        cfg = plistlib.loads(
            generate_config_plist(_desktop(), BuildOptions(gui_picker=True)))
        boot = cfg["Misc"]["Boot"]
        self.assertEqual(boot["PickerMode"], "External")
        self.assertIn("Acidanthera", boot["PickerVariant"])


class DriverEntriesTests(unittest.TestCase):
    """UEFI/Drivers: OpenCanopy попадает в config только с внешним меню."""

    def _entries(self, gui: bool) -> list:
        import tempfile
        from pathlib import Path

        from hackiclab.builder.efi_layout import EFILayout

        root = Path(tempfile.mkdtemp())
        (root / "EFI" / "OC").mkdir(parents=True, exist_ok=True)
        layout = EFILayout(root)
        data = generate_config_plist(_desktop(), BuildOptions(gui_picker=gui))
        names = want_drivers(BuildOptions(gui_picker=gui))
        path = layout.write_plist_with_kexts(data, [], driver_names=names,
                                             gui_picker=gui)
        cfg = plistlib.loads(path.read_bytes())
        return [d["Path"] for d in cfg["UEFI"]["Drivers"]]

    def test_canopy_requires_external_picker(self):
        without = self._entries(gui=False)
        with_gui = self._entries(gui=True)
        self.assertNotIn("OpenCanopy.efi", without)
        self.assertIn("OpenCanopy.efi", with_gui)
        self.assertIn("OpenRuntime.efi", with_gui)
        self.assertIn("ResetNvramEntry.efi", with_gui)


class ExtraDriverTests(unittest.TestCase):
    """Дополнительные драйверы загрузчика: AudioDxe и сеть."""

    def test_audio_dxe_flag_adds_driver(self):
        self.assertIn("AudioDxe.efi", want_drivers(BuildOptions(audio_dxe=True)))

    def test_legacy_boot_driver_is_not_offered(self):
        # OpenLegacyBoot не работает без CSM/OpenDuet, поэтому опции нет вовсе.
        self.assertFalse(hasattr(BuildOptions(), "legacy_boot"))
        self.assertNotIn("OpenLegacyBoot.efi", want_drivers(BuildOptions()))

    def test_network_boot_adds_stack_and_plugin_last(self):
        names = want_drivers(BuildOptions(network_boot=True))
        for drv in ("SnpDxe.efi", "Ip4Dxe.efi", "HttpBootDxe.efi", "TlsDxe.efi"):
            self.assertIn(drv, names)
        self.assertEqual(names[-1], "OpenNetworkBoot.efi")

    def test_flags_off_add_nothing(self):
        names = want_drivers(BuildOptions())
        for drv in ("AudioDxe.efi", "OpenLegacyBoot.efi", "OpenNetworkBoot.efi"):
            self.assertNotIn(drv, names)


class AudioConfigTests(unittest.TestCase):
    def test_audio_dxe_enables_audio_support(self):
        cfg = plistlib.loads(
            generate_config_plist(_desktop(), BuildOptions(audio_dxe=True)))
        aud = cfg["UEFI"]["Audio"]
        self.assertTrue(aud["AudioSupport"])
        self.assertEqual(aud["PlayChime"], "Auto")

    def test_audio_device_uses_scanned_pci_path(self):
        profile = _desktop()
        profile.audio = AudioInfo(pci_path="PciRoot(0x0)/Pci(0x1f,0x3)")
        cfg = plistlib.loads(
            generate_config_plist(profile, BuildOptions(audio_dxe=True)))
        self.assertEqual(cfg["UEFI"]["Audio"]["AudioDevice"],
                         "PciRoot(0x0)/Pci(0x1f,0x3)")


if __name__ == "__main__":
    unittest.main()
