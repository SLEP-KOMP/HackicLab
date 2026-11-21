"""Профиль переживает перезапуск с правами администратора."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.builder import cache_manager
from hackiclab.scanner.models import CPUInfo, GPUInfo, HardwareProfile
from hackiclab.ui.main_window import MainWindow


class _Stub:
    """Минимальная замена окна: методы работают только с self.profile."""

    _PENDING_PROFILE = MainWindow._PENDING_PROFILE

    def __init__(self, profile=None):
        self.profile = profile


def _profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop")
    p.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10)
    p.dgpu = GPUInfo(name="AMD Radeon RX 580 2048SP", vendor="amd",
                     device_id="6FDF")
    return p


class PendingProfileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        patcher = mock.patch.object(cache_manager, "profiles_dir",
                                    return_value=self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_stash_writes_profile_file(self):
        MainWindow._stash_profile_for_admin(_Stub(_profile()))
        path = self.dir / MainWindow._PENDING_PROFILE
        self.assertTrue(path.exists())
        self.assertIn("Ryzen 5 3600", path.read_text(encoding="utf-8"))

    def test_restore_brings_profile_back_and_cleans_up(self):
        MainWindow._stash_profile_for_admin(_Stub(_profile()))
        fresh = _Stub()
        MainWindow._restore_pending_profile(fresh)
        assert fresh.profile is not None
        self.assertEqual(fresh.profile.cpu.name, "AMD Ryzen 5 3600")
        self.assertEqual(fresh.profile.dgpu.device_id, "6FDF")
        self.assertFalse((self.dir / MainWindow._PENDING_PROFILE).exists())

    def test_no_profile_no_file(self):
        MainWindow._stash_profile_for_admin(_Stub())
        self.assertFalse((self.dir / MainWindow._PENDING_PROFILE).exists())

    def test_restore_without_file_keeps_none(self):
        fresh = _Stub()
        MainWindow._restore_pending_profile(fresh)
        self.assertIsNone(fresh.profile)


if __name__ == "__main__":
    unittest.main()
