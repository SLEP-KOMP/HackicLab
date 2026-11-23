"""Тесты проверки EFI в QEMU: разбор снимка экрана и оценка меню."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from vm_boot_test import menu_score, parse_ppm


def ppm(width: int, height: int, pixel: bytes) -> bytes:
    body = (bytes([0]) * (width * height * 3))
    return f"P6\n{width} {height}\n255\n".encode() + (pixel * (width * height) if len(pixel) == 3 else body)


class ParseTests(unittest.TestCase):
    def test_header_and_size(self):
        data = ppm(4, 2, b"\x00\x00\x00")
        width, height, pixels = parse_ppm(data)
        self.assertEqual((width, height), (4, 2))
        self.assertEqual(len(pixels), 4 * 2 * 3)

    def test_not_ppm(self):
        with self.assertRaises(ValueError):
            parse_ppm(b"P3\n1 1\n255\n0 0 0\n")


class ScoreTests(unittest.TestCase):
    def test_black_screen_has_no_score(self):
        width, height, pixels = parse_ppm(ppm(40, 20, b"\x00\x00\x00"))
        self.assertEqual(menu_score(pixels, width, height), 0.0)

    def test_grey_menu_text_is_detected(self):
        """QEMU отдаёт текст меню серым (около 190), а не белым."""
        data = bytearray(b"P6\n10 10\n255\n")
        data += b"\xbe\xbe\xbe" * (10 * 10)      # серый «текст» по всему кадру
        width, height, pixels = parse_ppm(bytes(data))
        self.assertGreater(menu_score(pixels, width, height), 0.9)

    def test_black_below_text_area_does_not_matter(self):
        data = bytearray(b"P6\n10 10\n255\n")
        data += b"\xbe\xbe\xbe" * (10 * 3)      # первые 3 строки — текст
        data += b"\x00\x00\x00" * (10 * 7)      # остальное — чёрный фон
        width, height, pixels = parse_ppm(bytes(data))
        self.assertGreater(menu_score(pixels, width, height), 0.5)

    def test_threshold_ignores_dark_pixels(self):
        data = bytearray(b"P6\n10 10\n255\n")
        data += b"\x64\x64\x64" * 100           # 100 — темнее порога
        width, height, pixels = parse_ppm(bytes(data))
        self.assertEqual(menu_score(pixels, width, height), 0.0)


if __name__ == "__main__":
    unittest.main()
