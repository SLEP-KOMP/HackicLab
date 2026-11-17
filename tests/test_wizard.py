"""Тесты нового интерфейса: меню с группами, мастер сборки, карточка железа."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.i18n import tr
from hackiclab.scanner.models import (
    AudioInfo,
    CPUInfo,
    GPUInfo,
    HardwareProfile,
    NetInfo,
    StorageInfo,
)
from hackiclab.ui.hwview import hardware_rows, wifi_model


def desktop_profile() -> HardwareProfile:
    profile = HardwareProfile(platform="desktop", board_vendor="ASUS", board_name="B450")
    profile.cpu = CPUInfo(name="AMD Ryzen 5 3600 6-Core Processor", vendor="amd",
                          generation=10, codename="Zen 2",
                          core_count=6, thread_count=12)
    profile.dgpu = GPUInfo(name="Radeon RX 580 2048SP", vendor="amd", device_id="6FDF")
    profile.audio = AudioInfo(name="Realtek High Definition Audio", codec="ALC1220",
                              layout_id=1)
    profile.net = NetInfo(eth_name="Intel(R) I211 Gigabit Network Connection",
                          eth_chipset="i211",
                          wifi_name="MediaTek Wi-Fi 7 MT7925 Wireless LAN Card",
                          wifi_chipset="mediatek", has_bt=True, bt_chipset="MediaTek")
    profile.storage = StorageInfo(nvme_present=True, sata_present=True)
    return profile


class HardwareRowsTests(unittest.TestCase):
    def test_wifi_model_is_extracted(self):
        self.assertEqual(
            wifi_model("MediaTek Wi-Fi 7 MT7925 Wireless LAN Card", "mediatek"), "MT7925")
        self.assertEqual(wifi_model("Intel(R) Wi-Fi 6 AX201 160MHz", "intel"), "AX201")
        self.assertEqual(wifi_model("", "broadcom"), "Broadcom")

    def test_rows_cover_all_devices(self):
        rows = {row["key"]: row for row in hardware_rows(desktop_profile(), "Sonoma")}
        self.assertIn("hw.cpu", rows)
        self.assertIn("hw.wifi", rows)
        self.assertIn("hw.ethernet", rows)
        self.assertIn("hw.audio", rows)
        self.assertIn("hw.bluetooth", rows)
        self.assertIn("hw.smbios", rows)
        self.assertIn("MT7925", rows["hw.wifi"]["value"])
        self.assertIn("gen 10", rows["hw.cpu"]["note"])
        self.assertEqual(rows["hw.audio"]["note"], "ALC1220 · layout 1")
        self.assertTrue(rows["hw.smbios"]["value"])

    def test_empty_profile_has_no_rows(self):
        self.assertEqual(hardware_rows(None), [])


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from hackiclab.ui.main_window import MainWindow
        self.win = MainWindow()
        self.addCleanup(self.win.close)
        self.addCleanup(self.win.deleteLater)

    def test_nav_has_groups_and_all_pages(self):
        titles = self.win._nav_titles()
        self.assertEqual(len(titles), 11)
        self.assertEqual(titles[0], tr.t("nav.wizard"))
        headers = [self.win.nav.item(i) for i in range(self.win.nav.count())
                   if self.win._nav_rows[i] < 0]
        self.assertEqual(len(headers), 4)

    def test_every_nav_row_opens_its_page(self):
        for page, row in self.win._page_rows.items():
            self.win.nav.setCurrentRow(row)
            self.app.processEvents()
            self.assertEqual(self.win.stack.currentIndex(), page)

    def test_wizard_has_six_steps(self):
        self.assertEqual(self.win.wiz_stack.count(), 6)
        self.assertEqual(len(self.win.wiz_chips), 6)
        self.assertEqual(self.win._wiz_state()["step"], 0)

    def test_next_requires_scan(self):
        self.win._wiz_next()
        self.assertEqual(self.win._wiz_state()["step"], 0)
        self.assertEqual(self.win.wiz_hint.text(), tr.t("wizard.hw.need_scan"))

    def test_wizard_flow_collects_choices(self):
        self.win._wiz_state()["profile"] = desktop_profile()
        self.win._wiz_fill_hw()
        self.win._wiz_show(1)
        self.assertGreater(self.win.wiz_macos_box.count(), 0)
        self.win._wiz_show(2)
        self.win._wiz_state().update({"folder": "C:/EFI", "kind": "folder"})
        self.win._wiz_fill_target()
        self.assertEqual(self.win._wiz_target_label(), "C:/EFI")
        self.win._wiz_state().update({"macos": "macOS Sonoma"})
        self.win._wiz_show(5)
        self.assertGreater(self.win.wiz_sum_rows.count(), 0)

    def test_macos_list_respects_generation(self):
        self.win._wiz_state()["profile"] = desktop_profile()
        self.win._wiz_show(1)
        from PySide6.QtWidgets import QPushButton
        labels: list[str] = []
        for index in range(self.win.wiz_macos_box.count()):
            item = self.win.wiz_macos_box.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                labels.append(widget.text())
        self.assertTrue(labels)
        self.assertFalse(any("Tahoe" in label for label in labels))
