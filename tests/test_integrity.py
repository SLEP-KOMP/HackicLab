"""Тесты контроля целостности кэша (SHA-256 манифест)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder.integrity import load_manifest, record, sha256_file, verify


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_sha256_matches_known_value(self):
        f = self.root / "a.bin"
        f.write_bytes(b"abc")
        self.assertEqual(
            sha256_file(f),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")

    def test_record_then_verify_ok(self):
        f = self.root / "k.zip"
        f.write_bytes(b"payload")
        digest = record(self.root, "k.zip", f)
        self.assertEqual(len(digest), 64)
        self.assertTrue(verify(self.root, "k.zip", f))
        self.assertEqual(load_manifest(self.root)["k.zip"], digest)

    def test_verify_detects_tampered_file(self):
        f = self.root / "k.zip"
        f.write_bytes(b"payload")
        record(self.root, "k.zip", f)
        f.write_bytes(b"payload-changed")
        self.assertFalse(verify(self.root, "k.zip", f))

    def test_verify_false_without_manifest_entry(self):
        f = self.root / "k.zip"
        f.write_bytes(b"payload")
        self.assertFalse(verify(self.root, "k.zip", f))

    def test_verify_false_for_missing_file(self):
        self.assertFalse(verify(self.root, "nope.zip", self.root / "nope.zip"))

    def test_manifest_is_json_and_survives_reload(self):
        f = self.root / "k.zip"
        f.write_bytes(b"payload")
        record(self.root, "k.zip", f)
        self.assertTrue((self.root / "manifest.json").is_file())
        self.assertEqual(load_manifest(self.root), {"k.zip": sha256_file(f)})


if __name__ == "__main__":
    unittest.main()
