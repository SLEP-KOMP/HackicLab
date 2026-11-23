"""Тесты дополнения AMD-патчей вариантами для ядра 26.x (macOS Tahoe)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.amd_patches import extend_for_tahoe

TEN_BIT = {
    "Comment": "CaseySJ | probeBusGated | Disable 10 bit tags | 12.0+",
    "Identifier": "com.apple.iokit.IOPCIFamily",
    "MinKernel": "21.0.0",
    "MaxKernel": "25.99.99",
    "Find": b"\xe0\x11r\x00",
    "Replace": b"\x00\x00\x03\x00",
    "Mask": b"\xf0\xff\xff\xf0",
    "ReplaceMask": b"\x00\x00\x0f\x00",
}
PANIC = {
    "Comment": "Visual | thread_invoke, thread_dispatch | "
               "Remove non-monotonic time panic | 12.0+",
    "Identifier": "kernel",
    "MinKernel": "21.0.0",
    "MaxKernel": "25.99.99",
    "Find": b"H\x00\x00\x80\x04\x00\x00\x0f\x00\x00\x00\x00\x00",
    "Replace": b"\x00\x00\x00\x00\x00\x00\x00f\x90f\x90f\x90",
}


class TahoeVariantTests(unittest.TestCase):
    def test_ten_bit_patch_split(self):
        patches = extend_for_tahoe([dict(TEN_BIT)])
        self.assertEqual(len(patches), 2)
        old, new = patches
        self.assertEqual(old["MaxKernel"], "24.99.99")
        self.assertEqual(new["MinKernel"], "25.0.0")
        self.assertEqual(new["MaxKernel"], "25.99.99")
        self.assertEqual(new["Find"], b"\xe0\x11s@")
        self.assertIn("26.0+", new["Comment"])

    def test_panic_patch_split(self):
        patches = extend_for_tahoe([dict(PANIC)])
        self.assertEqual(len(patches), 2)
        old, new = patches
        self.assertEqual(old["MaxKernel"], "25.3.99")
        self.assertEqual(new["MinKernel"], "25.4.0")
        self.assertEqual(new["Find"][3:4], b"\x90")

    def test_other_patches_untouched(self):
        other = {"Comment": "Ryzen | something", "MinKernel": "21.0.0",
                 "MaxKernel": "25.99.99", "Find": b"\x01"}
        self.assertEqual(extend_for_tahoe([other]), [other])

    def test_empty_input(self):
        self.assertEqual(extend_for_tahoe([]), [])


if __name__ == "__main__":
    unittest.main()

