"""Тесты лицензионного модуля: стабильность device_id и правила доступа."""

from __future__ import annotations

import subprocess
import sys
import unittest

import _bootstrap

from hackiclab import license as lic


class DeviceIdTests(unittest.TestCase):
    def test_deterministic_within_process(self):
        self.assertEqual(lic._device_id(), lic._device_id())

    def test_same_between_processes(self):
        code = (
            "import sys; sys.path.insert(0, r'%s');"
            "from hackiclab.license import _device_id;"
            "print(_device_id())"
        ) % _bootstrap.ROOT
        runs = [
            subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
            for _ in range(2)
        ]
        for r in runs:
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(runs[0].stdout.strip(), runs[1].stdout.strip())
        self.assertEqual(len(runs[0].stdout.strip()), 24)


class FeatureGateTests(unittest.TestCase):
    def test_free_edition_blocks_premium_candidates(self):
        free = lic.License()
        self.assertFalse(free.can("autodownload"))
        self.assertFalse(free.can("autobuild_full"))
        self.assertTrue(free.can("scan"))

    def test_premium_edition_allows_everything(self):
        premium = lic.License(edition=lic.Edition.PREMIUM, activated=True)
        self.assertTrue(premium.is_premium)
        self.assertTrue(premium.can("autodownload"))


if __name__ == "__main__":
    unittest.main()
