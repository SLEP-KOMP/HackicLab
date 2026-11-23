"""Тесты выбора портов карты USB (сколько оставить, что фильтруется)."""

from __future__ import annotations

import unittest

import _bootstrap  # noqa: F401

from hackiclab.builder.usb_map import (
    MAX_PORTS_PER_CONTROLLER,
    build_map_plist,
    count_ports,
    filter_ports,
    port_rows,
)


def controller(name: int, count: int) -> dict:
    return {
        "identifiers": {"bdf": [0, name, 0]},
        "ports": [{"index": i, "type": 3, "class": "SuperSpeed", "guessed": 3}
                  for i in range(1, count + 1)],
    }


class PortHelpersTests(unittest.TestCase):
    def test_default_map_keeps_15_ports(self):
        plist = build_map_plist([controller(20, 20)])
        assert plist is not None
        self.assertEqual(count_ports(plist), {"0-20-0": MAX_PORTS_PER_CONTROLLER})

    def test_unlimited_map_shows_all_ports(self):
        """Вкладка портов должна видеть и те порты, что сверх лимита."""
        plist = build_map_plist([controller(20, 20)], limit=None)
        assert plist is not None
        self.assertEqual(count_ports(plist), {"0-20-0": 20})
        rows = port_rows(plist)
        self.assertEqual([row["index"] for row in rows], list(range(1, 21)))
        self.assertEqual(rows[0]["connector"], 3)

    def test_filter_keeps_only_selected_ports(self):
        plist = build_map_plist([controller(20, 5)], limit=None)
        assert plist is not None
        rows = port_rows(plist)
        keep = {(rows[0]["controller"], rows[0]["name"]),
                (rows[3]["controller"], rows[3]["name"])}
        filtered = filter_ports(plist, keep)
        assert filtered is not None
        self.assertEqual(len(port_rows(filtered)), 2)
        # исходная карта не меняется
        self.assertEqual(len(port_rows(plist)), 5)

    def test_filter_drops_empty_controller(self):
        first = build_map_plist([controller(20, 3)], limit=None)
        second = build_map_plist([controller(21, 3)], limit=None)
        assert first is not None and second is not None
        keep = {(row["controller"], row["name"]) for row in port_rows(first)}
        merged = first
        merged["IOKitPersonalities"].update(second["IOKitPersonalities"])
        filtered = filter_ports(merged, keep)
        assert filtered is not None
        self.assertEqual(list(filtered["IOKitPersonalities"]), ["0-20-0"])

    def test_filter_with_nothing_selected_returns_none(self):
        plist = build_map_plist([controller(20, 3)], limit=None)
        self.assertIsNone(filter_ports(plist, set()))


if __name__ == "__main__":
    unittest.main()
