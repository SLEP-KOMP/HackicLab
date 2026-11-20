"""Ресурсы OpenCanopy: пустые папки в архиве OpenCore и докачка иконок."""

from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path

import _bootstrap  # noqa: F401

from hackiclab.builder.canopy import (
    count_files,
    ensure_resources,
    extract_resources,
    fetch_resources,
    has_real_files,
)


def _tar(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buf.getvalue()


class HasRealFilesTests(unittest.TestCase):
    def test_missing_folder(self):
        self.assertFalse(has_real_files(None))
        self.assertFalse(has_real_files(Path("out/definitely-not-here")))

    def test_empty_dirs_from_opencore_archive(self):
        root = Path(tempfile.mkdtemp()) / "Resources"
        for name in ("Font", "Image", "Label", "Audio"):
            (root / name).mkdir(parents=True)
        self.assertFalse(has_real_files(root))

    def test_folder_with_icons(self):
        root = Path(tempfile.mkdtemp()) / "Resources"
        (root / "Image").mkdir(parents=True)
        (root / "Image" / "icon.icns").write_bytes(b"x")
        self.assertTrue(has_real_files(root))


class ExtractTests(unittest.TestCase):
    def test_only_font_image_label_kept(self):
        data = _tar({
            "OcBinaryData-master/Resources/Font/OpenCore.efi.font": b"F",
            "OcBinaryData-master/Resources/Image/Acidanthera/icon.icns": b"I",
            "OcBinaryData-master/Resources/Label/OpenCore.label": b"L",
            "OcBinaryData-master/Resources/Audio/beep.wav": b"A",
            "OcBinaryData-master/Other/file.txt": b"O",
        })
        dest = Path(tempfile.mkdtemp()) / "Resources"
        written = extract_resources(data, dest)
        self.assertEqual(written, 3)
        self.assertTrue((dest / "Font" / "OpenCore.efi.font").is_file())
        self.assertTrue((dest / "Image" / "Acidanthera" / "icon.icns").is_file())
        self.assertTrue((dest / "Label" / "OpenCore.label").is_file())
        self.assertFalse((dest / "Audio").exists())

    def test_path_traversal_is_skipped(self):
        data = _tar({"OcBinaryData-master/Resources/../../evil.txt": b"bad"})
        dest = Path(tempfile.mkdtemp()) / "Resources"
        messages = []
        self.assertEqual(extract_resources(data, dest, log=messages.append), 0)
        self.assertFalse((dest.parent.parent / "evil.txt").exists())


class FetchTests(unittest.TestCase):
    def test_download_failure_returns_zero(self):
        def boom(url):
            raise RuntimeError("нет сети")

        messages = []
        dest = Path(tempfile.mkdtemp()) / "Resources"
        self.assertEqual(fetch_resources(dest, log=messages.append, downloader=boom), 0)
        self.assertTrue(any("не удалось" in m for m in messages))

    def test_broken_archive_returns_zero(self):
        messages = []
        dest = Path(tempfile.mkdtemp()) / "Resources"
        self.assertEqual(fetch_resources(dest, log=messages.append,
                                         downloader=lambda url: b"not a tarball"), 0)
        self.assertTrue(any("не распакован" in m for m in messages))

    def test_successful_download(self):
        data = _tar({"OcBinaryData-master/Resources/Font/OpenCore.efi.font": b"F"})
        messages = []
        dest = Path(tempfile.mkdtemp()) / "Resources"
        written = fetch_resources(dest, log=messages.append, downloader=lambda url: data)
        self.assertEqual(written, 1)
        self.assertTrue((dest / "Font" / "OpenCore.efi.font").is_file())
        self.assertTrue(any("OcBinaryData" in m for m in messages))


class EnsureTests(unittest.TestCase):
    def test_cache_is_reused_without_network(self):
        data = _tar({"OcBinaryData-master/Resources/Image/x/icon.icns": b"I"})
        root = Path(tempfile.mkdtemp())
        cache = root / "cache" / "Resources"
        first = ensure_resources(root / "efi1" / "Resources", cache=cache,
                                 downloader=lambda url: data)
        self.assertEqual(first, 1)

        def no_network(url):
            raise AssertionError("кэш должен был отменить скачивание")

        messages = []
        second = ensure_resources(root / "efi2" / "Resources", cache=cache,
                                  downloader=no_network, log=messages.append)
        self.assertEqual(second, 1)
        self.assertTrue((root / "efi2" / "Resources" / "Image" / "x" / "icon.icns").is_file())
        self.assertTrue(any("кэш" in m for m in messages))

    def test_kexts_modules_stay_out_of_cache(self):
        self.assertEqual(count_files(Path(tempfile.mkdtemp())), 0)


if __name__ == "__main__":
    unittest.main()
