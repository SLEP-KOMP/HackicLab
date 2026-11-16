"""Тесты полноты локализации RU/EN."""

from __future__ import annotations

import re
import unittest

import _bootstrap

from hackiclab.i18n import ISSUE_EN, T, Tr


class TranslationTests(unittest.TestCase):
    def test_same_keys_in_both_languages(self):
        ru, en = set(T["ru"]), set(T["en"])
        self.assertEqual(ru - en, set(), f"нет в EN: {sorted(ru - en)}")
        self.assertEqual(en - ru, set(), f"нет в RU: {sorted(en - ru)}")

    def test_all_used_keys_exist(self):
        used = set()
        for path in (_bootstrap.ROOT / "hackiclab").rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="ignore")
            used |= set(re.findall(r"""\.t\(\s*['"]([^'"]+)['"]""", text))
        # ключи вида "sources.cat." + category собираются на месте:
        # проверяем только полные ключи, префиксы пропускаем
        used = {k for k in used if not k.endswith(".")}
        missing = sorted(k for k in used if k not in T["ru"] or k not in T["en"])
        self.assertEqual(missing, [], f"ключи без перевода: {missing}")

    def test_no_empty_translations(self):
        for lang in ("ru", "en"):
            empty = [k for k, v in T[lang].items() if not str(v).strip()]
            self.assertEqual(empty, [], f"пустые переводы ({lang}): {empty}")

    def test_unknown_key_returns_key(self):
        self.assertEqual(Tr("ru").t("no.such.key"), "no.such.key")

    def test_fallback_to_russian_for_english(self):
        tr = Tr("en")
        self.assertTrue(tr.t("app.title"))
        self.assertTrue(tr.t("usb.admin_title"))

    def test_issue_texts_are_pairs(self):
        for code, pair in ISSUE_EN.items():
            self.assertEqual(len(pair), 2, code)
            self.assertTrue(pair[0].strip() and pair[1].strip(), code)


if __name__ == "__main__":
    unittest.main()
