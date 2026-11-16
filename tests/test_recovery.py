"""Тесты recovery: ключи кэша, аргументы macrecovery, проверка скачанного скрипта."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder import recovery as rec


class VersionTests(unittest.TestCase):
    def test_versions_list_is_sane(self):
        self.assertTrue(rec.MACOS_VERSIONS)
        for v in rec.MACOS_VERSIONS:
            self.assertTrue(v.name)
            self.assertTrue(v.version)
            self.assertTrue(v.board_id)
            self.assertTrue(v.mlb)

    def test_lookup_by_name_and_version(self):
        self.assertIsNotNone(rec.macos_version_by_name("macOS Sonoma"))
        self.assertIsNotNone(rec.macos_version_by_name("14"))
        self.assertIsNone(rec.macos_version_by_name("Windows 11"))

    def test_cache_key_is_deterministic(self):
        v = rec.MACOS_VERSIONS[0]
        self.assertEqual(v.cache_key, v.cache_key)
        another = rec.MacOSVersion(v.name, v.version, v.board_id, v.mlb, v.os_flag)
        self.assertEqual(another.cache_key, v.cache_key)

    def test_cache_key_differs_for_other_version(self):
        a, b = rec.MACOS_VERSIONS[0], rec.MACOS_VERSIONS[1]
        self.assertNotEqual(a.cache_key, b.cache_key)

    def test_args_include_board_and_mlb(self):
        v = rec.macos_version_by_name("macOS Sonoma")
        args = rec.macrecovery_args(v)
        self.assertIn("-b", args)
        self.assertIn(v.board_id, args)
        self.assertIn("-m", args)
        self.assertIn(v.mlb, args)
        self.assertIn("download", args)


class ScriptValidationTests(unittest.TestCase):
    def test_good_script_passes(self):
        body = ("import argparse\n"
                "parser = argparse.ArgumentParser()\n"
                "parser.add_argument('-b', dest='board-id')\n"
                "parser.add_argument('-m')\n") * 40
        self.assertTrue(rec._validate_script(body.encode("utf-8")))

    def test_empty_payload_fails(self):
        self.assertFalse(rec._validate_script(b""))
        self.assertFalse(rec._validate_script(b"<html>404</html>" * 100))

    def test_broken_python_fails(self):
        self.assertFalse(rec._validate_script(("def broken(:\n" * 200).encode("utf-8")))


if __name__ == "__main__":
    unittest.main()
