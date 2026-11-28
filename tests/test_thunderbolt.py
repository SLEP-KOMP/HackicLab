"""База контроллеров Thunderbolt и авто-звук в меню загрузчика."""
from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.knowledge import thunderbolt as tb
from hackiclab.knowledge.manual_hw import ManualSelection, build_profile
from hackiclab.builder.config_gen import BuildOptions
from hackiclab.builder.builder import BuildPlan


class ThunderboltTests(unittest.TestCase):
    def test_known_controllers(self):
        self.assertIn("Titan Ridge", tb.model_name(tb.find_controller(["15EA"])))
        self.assertIn("Alpine Ridge", tb.model_name(tb.find_controller(["15d3"])))
        self.assertIn("Maple Ridge", tb.model_name(tb.find_controller(["1137"])))

    def test_unknown_id(self):
        self.assertIsNone(tb.find_controller(["ffff"]))
        self.assertEqual("", tb.model_name(None))

    def test_statuses(self):
        titan = tb.find_controller(["15ea"])
        self.assertEqual("native", tb.status_for(titan))
        maple = tb.find_controller(["1136"])
        self.assertEqual("cold", tb.status_for(maple))


class AudioAutoTests(unittest.TestCase):
    def _profile(self, codec: str = "ALC892"):
        return build_profile(ManualSelection(cpu="intel-10d", audio_codec=codec))

    def test_audio_enabled_with_codec(self):
        plan = BuildPlan(profile=self._profile())
        self.assertTrue(plan.options.audio_dxe)

    def test_audio_off_without_codec(self):
        plan = BuildPlan(profile=self._profile(""))
        self.assertFalse(plan.options.audio_dxe)

    def test_audio_off_with_windows_dual_boot(self):
        plan = BuildPlan(profile=self._profile(),
                         options=BuildOptions(dual_boot="both"))
        self.assertFalse(plan.options.audio_dxe)

    def test_audio_explicit_override(self):
        plan = BuildPlan(profile=self._profile(),
                         options=BuildOptions(audio_dxe=False))
        self.assertFalse(plan.options.audio_dxe)


if __name__ == "__main__":
    unittest.main()
