"""Тесты macOS-сканера: разбор ответов system_profiler без обращения к системе."""

from __future__ import annotations

import sys
import unittest

import _bootstrap  # noqa: F401

from hackiclab.scanner.macos_scanner import (
    MacOSScanner,
    classify_cpu,
    parse_audio,
    parse_gpus,
    parse_hardware,
    parse_network,
    parse_storage,
)

INTEL_MAC = {
    "SPHardwareDataType": [{
        "machine_model": "MacBook Pro",
        "model_name": "MacBookPro16,1",
        "processor_name": "Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz",
        "number_processors": "proc 12:6:0",
        "physical_memory": "16 GB",
    }]
}

APPLE_MAC = {
    "SPHardwareDataType": [{
        "machine_model": "Mac mini",
        "model_name": "Macmini9,1",
        "chip_type": "Apple M1",
        "number_processors": "proc 8:4:4",
        "physical_memory": "8 GB",
    }]
}

DISPLAYS = {
    "SPDisplaysDataType": [
        {"sppci_model": "Intel UHD Graphics 630", "spdisplays_vendor": "Intel (0x8086)",
         "spdisplays_vram": "1536 MB"},
        {"sppci_model": "AMD Radeon Pro 5500M", "spdisplays_vendor": "AMD (0x1002)",
         "spdisplays_vram": "4 GB"},
    ]
}

AUDIO = {"SPAudioDataType": [{"_name": "Audio", "_items": [{"_name": "Realtek ALC1220"}]}]}

NETWORK = {"SPNetworkDataType": [
    {"_name": "Intel I211", "type": "Ethernet"},
    {"_name": "Broadcom BCM4360 Wi-Fi", "type": "AirPort"},
]}

STORAGE = {"SPNVMeDataType": [{"_name": "APPLE SSD AP0512", "_items": [{"_name": "disk0"}]}]}


class HardwareParseTests(unittest.TestCase):
    def test_intel_mac(self):
        hw = parse_hardware(INTEL_MAC)
        self.assertEqual(hw["model"], "MacBook Pro")
        self.assertTrue(hw["is_laptop"])
        self.assertFalse(hw["is_apple_silicon"])
        self.assertEqual(hw["cores"], 12)
        self.assertEqual(hw["memory_gb"], 16)

    def test_apple_silicon_mac(self):
        hw = parse_hardware(APPLE_MAC)
        self.assertTrue(hw["is_apple_silicon"])
        self.assertFalse(hw["is_laptop"])
        self.assertEqual(hw["cores"], 8)

    def test_empty_payload_is_safe(self):
        hw = parse_hardware({})
        self.assertEqual(hw["model"], "")
        self.assertEqual(hw["cores"], 0)


class CpuClassifyTests(unittest.TestCase):
    def test_intel_generation(self):
        cpu = classify_cpu("Intel(R) Core(TM) i7-9750H CPU @ 2.60GHz")
        self.assertEqual(cpu.vendor, "intel")
        self.assertEqual(cpu.generation, 9)
        self.assertEqual(cpu.codename, "Coffee Lake Refresh")
        self.assertEqual(cpu.oc_platform, "Coffee Lake")

    def test_amd_generation(self):
        cpu = classify_cpu("AMD Ryzen 5 3600 6-Core Processor")
        self.assertEqual(cpu.vendor, "amd")
        self.assertEqual(cpu.generation, 10)

    def test_apple_silicon_is_marked(self):
        cpu = classify_cpu("Apple M1", is_apple_silicon=True)
        self.assertEqual(cpu.vendor, "apple")
        self.assertTrue(cpu.is_apple_silicon)


class DevicesParseTests(unittest.TestCase):
    def test_gpus_are_split(self):
        igpu, dgpu = parse_gpus(DISPLAYS)
        assert igpu is not None and dgpu is not None
        self.assertEqual(igpu.vendor, "intel")
        self.assertTrue(igpu.is_integrated)
        self.assertEqual(igpu.vram_mb, 1536)
        self.assertEqual(dgpu.vendor, "amd")
        self.assertEqual(dgpu.vram_mb, 4096)

    def test_audio_codec_and_layout(self):
        audio = parse_audio(AUDIO)
        self.assertEqual(audio.codec, "ALC1220")
        self.assertIn(audio.layout_id, audio.layout_candidates)
        self.assertNotEqual(audio.layout_id, 0)

    def test_network_splits_wifi_and_ethernet(self):
        net = parse_network(NETWORK)
        self.assertEqual(net.eth_chipset, "i211")
        self.assertEqual(net.wifi_chipset, "broadcom")

    def test_storage_detects_nvme(self):
        self.assertTrue(parse_storage(STORAGE).nvme_present)
        self.assertFalse(parse_storage({}).nvme_present)


class ScannerGuardTests(unittest.TestCase):
    @unittest.skipIf(sys.platform == "darwin", "на macOS проверка не имеет смысла")
    def test_scanner_refuses_foreign_platform(self):
        with self.assertRaises(RuntimeError):
            MacOSScanner().scan()


if __name__ == "__main__":
    unittest.main()
