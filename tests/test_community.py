"""Тесты базы отчётов: запись, чтение, статистика и ссылка на GitHub."""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

import _bootstrap  # noqa: F401

from hackiclab.knowledge import community
from hackiclab.scanner.models import AudioInfo, CPUInfo, GPUInfo, HardwareProfile, NetInfo


def profile() -> HardwareProfile:
    p = HardwareProfile(platform="desktop", board_vendor="Gigabyte",
                        board_name="X470 AORUS")
    p.cpu = CPUInfo(name="AMD Ryzen 5 3600", vendor="amd", generation=10, codename="Zen 2")
    p.dgpu = GPUInfo(name="Radeon RX 580 2048SP", vendor="amd")
    p.audio = AudioInfo(codec="ALC1220", layout_id=11)
    p.net = NetInfo(eth_chipset="i211", eth_name="Intel I211", wifi_chipset="broadcom")
    return p


class _Store(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        patcher = mock.patch.object(community, "store_dir", return_value=self.dir)
        patcher.start()
        self.addCleanup(patcher.stop)


class RecordTests(_Store):
    def test_record_has_hardware_and_verdict(self):
        class Result:
            ok = False
            errors = ["ocvalidate: Missing key"]
            warnings: list = []

        rec = community.make_record(profile(), None, Result(), kexts=["Lilu.kext", "AppleALC.kext"],
                                    config=b"<plist/>")
        self.assertFalse(rec["ok"])
        self.assertEqual(rec["hardware"]["cpu"], "AMD Ryzen 5 3600")
        self.assertEqual(rec["hardware"]["audio_layout"], 11)
        self.assertEqual(rec["kexts"], ["AppleALC.kext", "Lilu.kext"])
        self.assertEqual(len(rec["config_sha256"]), 64)

    def test_no_personal_fields_are_stored(self):
        rec = community.make_record(profile(), None, None, config=b"x")
        flat = json.dumps(rec, ensure_ascii=False).lower()
        for forbidden in ("serial", "mlb", "uuid", "systemuuid"):
            self.assertNotIn(forbidden, flat)

    def test_save_and_load_roundtrip(self):
        rec = community.make_record(profile(), None, None, config=b"x")
        path = community.save_record(rec)
        self.assertTrue(path.exists())
        self.assertEqual(community.load(path)["hardware"], rec["hardware"])

    def test_stats_count_builds_and_hardware(self):
        class Good:
            ok = True
            errors: list = []
            warnings: list = []

        community.save_record(community.make_record(profile(), None, Good()))
        community.save_record(community.make_record(profile(), None, Good()))
        data = community.stats()
        self.assertEqual(data["total"], 2)
        self.assertEqual(data["ok"], 2)
        self.assertEqual(data["hardware"], 1)

    def test_broken_file_is_skipped(self):
        community.save_record(community.make_record(profile(), None, None))
        (self.dir / "broken.json").write_text("{не json", encoding="utf-8")
        self.assertEqual(community.stats()["total"], 1)


class IssueUrlTests(_Store):
    def test_url_points_to_new_issue_with_label(self):
        rec = community.make_record(profile(), None, None)
        url = community.issue_url(rec)
        self.assertTrue(url.startswith(f"https://github.com/{community.REPO}/issues/new?"))
        query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        self.assertEqual(query["labels"][0], community.LABEL)
        self.assertIn("AMD Ryzen 5 3600", query["title"][0])
        self.assertIn("ALC1220", query["body"][0])

    def test_verdict_is_in_title(self):
        class Good:
            ok = True
            errors: list = []
            warnings: list = []

        url = community.issue_url(community.make_record(profile(), None, Good()))
        self.assertIn("%5Bok%5D", url)

    def test_body_is_limited(self):
        rec = community.make_record(profile(), None, None)
        rec["kexts"] = [f"Kext{i}.kext" for i in range(2000)]
        url = community.issue_url(rec)
        self.assertLess(len(url), 16000)


class IssueParsingTests(unittest.TestCase):
    BODY = "Отчёт\n\n```json\n{\"hardware\": {\"cpu\": \"Ryzen\"}, \"ok\": true}\n```\n"

    def test_record_is_extracted_from_body(self):
        record = community.parse_issue_body(self.BODY)
        assert record is not None
        self.assertEqual(record["hardware"]["cpu"], "Ryzen")

    def test_body_without_json_gives_none(self):
        self.assertIsNone(community.parse_issue_body("просто текст"))

    def test_broken_json_gives_none(self):
        self.assertIsNone(community.parse_issue_body("```json\n{битый\n```"))

    def test_issues_payload_is_parsed(self):
        import json

        payload = json.dumps([{
            "number": 7, "title": "t", "html_url": "https://example/7",
            "body": self.BODY,
        }, {"number": 8, "title": "no report", "body": "текст"}])
        records = community.parse_issues(payload)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["issue"], 7)
        self.assertEqual(records[0]["issue_url"], "https://example/7")

    def test_fetch_reports_survives_network_error(self):
        with mock.patch("hackiclab.builder.fetcher.download_bytes",
                        side_effect=OSError("нет сети")):
            self.assertEqual(community.fetch_reports(), [])

    def test_fetch_reports_reads_payload(self):
        import json

        payload = json.dumps([{"number": 1, "body": self.BODY, "html_url": "",
                               "title": "t"}]).encode("utf-8")
        with mock.patch("hackiclab.builder.fetcher.download_bytes", return_value=payload):
            records = community.fetch_reports()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["issue"], 1)


if __name__ == "__main__":
    unittest.main()
