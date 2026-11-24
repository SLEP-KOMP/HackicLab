"""Тесты предупреждений совместимости (по итогам тем сообщество)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge.compat import warnings_for
from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile


def _profile(gen: int = 9, vendor: str = "intel"):
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="Intel Core", vendor=vendor, generation=gen)
    return p


class CompatWarningsTests(unittest.TestCase):
    def test_old_cpu_on_monterey_needs_patch(self):
        ru = [r for r, _ in warnings_for(_profile(2), "Monterey")]
        self.assertTrue(any("CryptexFixup" in r for r in ru))

    def test_turing_needs_no_web_driver(self):
        p = _profile()
        p.dgpu = GPUInfo(name="NVIDIA GeForce RTX 2060", vendor="nvidia",
                         device_id="1F08")
        ru = [r for r, _ in warnings_for(p, "Sonoma")]
        self.assertTrue(any("Web Driver" in r for r in ru))

    def test_audio_without_layout(self):
        p = _profile()
        p.audio = AudioInfo(codec="ALC892", layout_id=0)
        ru = [r for r, _ in warnings_for(p, "Ventura")]
        self.assertTrue(any("alcid" in r for r in ru))

    def test_clean_profile_has_no_extra_warnings(self):
        p = _profile(9)
        p.dgpu = GPUInfo(name="RX 580", vendor="amd", device_id="67DF")
        self.assertEqual(warnings_for(p, "Sonoma"), [])


if __name__ == "__main__":
    unittest.main()
