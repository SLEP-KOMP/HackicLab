"""Тесты разрешения тега релиза без GitHub API."""

from __future__ import annotations

import unittest
from unittest import mock

from hackiclab.builder import fetcher


class LatestTagFallbackTests(unittest.TestCase):
    def test_redirect_tag_wins(self):
        with mock.patch.object(fetcher, "_tag_from_redirect", return_value="1.2.3"), \
             mock.patch.object(fetcher, "_tag_from_listing") as listing:
            self.assertEqual(fetcher.GitHubFetcher.latest_tag("owner/repo"), "1.2.3")
            listing.assert_not_called()

    def test_listing_used_when_redirect_has_no_tag(self):
        """У части проектов нет отметки «latest» — тег берётся из списка релизов."""
        with mock.patch.object(fetcher, "_tag_from_redirect", return_value=""), \
             mock.patch.object(fetcher, "_tag_from_listing", return_value="250224"):
            self.assertEqual(fetcher.GitHubFetcher.latest_tag("owner/repo"), "250224")

    def test_listing_used_when_redirect_points_to_releases_page(self):
        with mock.patch.object(fetcher, "_tag_from_redirect", return_value="releases"), \
             mock.patch.object(fetcher, "_tag_from_listing", return_value="v1.0"):
            self.assertEqual(fetcher.GitHubFetcher.latest_tag("owner/repo"), "v1.0")

    def test_listing_parses_first_tag_from_html(self):
        page = (b'<a href="/owner/repo/releases/tag/v2.1.0">v2.1.0</a>'
                b'<a href="/owner/repo/releases/tag/v1.0.0">v1.0.0</a>')
        with mock.patch.object(fetcher, "download_bytes", return_value=page):
            self.assertEqual(fetcher._tag_from_listing("owner/repo"), "v2.1.0")

    def test_listing_returns_empty_without_tags(self):
        with mock.patch.object(fetcher, "download_bytes",
                               return_value=b"<html>There aren&#39;t any releases here</html>"):
            self.assertEqual(fetcher._tag_from_listing("owner/repo"), "")

    def test_listing_survives_download_error(self):
        with mock.patch.object(fetcher, "download_bytes",
                               side_effect=RuntimeError("нет сети")):
            self.assertEqual(fetcher._tag_from_listing("owner/repo"), "")


if __name__ == "__main__":
    unittest.main()
