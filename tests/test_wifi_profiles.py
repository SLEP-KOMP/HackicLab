"""Тесты экспорта Wi-Fi-профилей Windows в WiFiConfig.plist для itlwm."""

from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder.wifi_profiles import build_plist, parse_profile, write_wifi_config

_PROFILE = """<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
  <name>HomeNet</name>
  <SSIDConfig><SSID><name>HomeNet</name></SSID></SSIDConfig>
  <MSM><security>
    <authEncryption><authentication>WPA2PSK</authentication></authEncryption>
    <sharedKey><keyType>passPhrase</keyType><keyMaterial>secret123</keyMaterial></sharedKey>
  </security></MSM>
</WLANProfile>
"""


class ParseProfileTests(unittest.TestCase):
    def test_reads_ssid_and_password(self):
        self.assertEqual(parse_profile(_PROFILE), ("HomeNet", "secret123"))

    def test_open_network_has_empty_password(self):
        xml = _PROFILE.replace("<keyMaterial>secret123</keyMaterial>", "")
        self.assertEqual(parse_profile(xml), ("HomeNet", ""))

    def test_broken_xml_returns_none(self):
        self.assertIsNone(parse_profile("<WLANProfile"))

    def test_profile_without_ssid_returns_none(self):
        self.assertIsNone(parse_profile("<WLANProfile><name>x</name></WLANProfile>"))


class BuildPlistTests(unittest.TestCase):
    def test_plist_is_itlwm_format(self):
        data = plistlib.loads(build_plist([("HomeNet", "secret123"), ("Work", "pw")]))
        self.assertEqual(data, [
            {"ssid": "HomeNet", "password": "secret123"},
            {"ssid": "Work", "password": "pw"},
        ])

    def test_empty_entries_give_empty_array(self):
        self.assertEqual(plistlib.loads(build_plist([])), [])


class WriteConfigTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.kext = Path(self._tmp.name) / "itlwm.kext"
        (self.kext / "Contents").mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def test_writes_into_kext_contents(self):
        target = write_wifi_config(self.kext, [("HomeNet", "secret123")])
        self.assertIsNotNone(target)
        assert target is not None
        self.assertEqual(target.name, "WiFiConfig.plist")
        data = plistlib.loads(target.read_bytes())
        self.assertEqual(data[0]["ssid"], "HomeNet")

    def test_no_entries_writes_nothing(self):
        self.assertIsNone(write_wifi_config(self.kext, []))
        self.assertFalse((self.kext / "Contents" / "WiFiConfig.plist").exists())

    def test_missing_contents_dir_is_skipped(self):
        other = Path(self._tmp.name) / "broken.kext"
        other.mkdir()
        self.assertIsNone(write_wifi_config(other, [("HomeNet", "x")]))


if __name__ == "__main__":
    unittest.main()
