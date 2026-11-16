"""Тесты полноты локализации RU/EN."""

from __future__ import annotations

import re
import unittest

import _bootstrap

from hackiclab.i18n import ISSUE_EN, T, Tr, detect_system_language


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


class DetectLanguageTests(unittest.TestCase):
    def _fake_qt(self, langs):
        from unittest import mock

        class _FakeLocale:
            @staticmethod
            def system():
                class _S:
                    @staticmethod
                    def uiLanguages():
                        return langs

                    @staticmethod
                    def name():
                        return langs[0] if langs else ""
                return _S()

        return mock.patch("PySide6.QtCore.QLocale", _FakeLocale)

    def test_russian_system_gives_russian(self):
        with self._fake_qt(["ru-RU", "en-US"]):
            self.assertEqual(detect_system_language(), "ru")

    def test_english_system_gives_english(self):
        with self._fake_qt(["en-US"]):
            self.assertEqual(detect_system_language(), "en")

    def test_other_language_falls_back_to_english(self):
        with self._fake_qt(["de-DE", "en-US"]):
            self.assertEqual(detect_system_language(), "en")

    def test_locale_module_fallback_without_qt(self):
        from unittest import mock

        class _Broken:
            @staticmethod
            def system():
                raise RuntimeError("Qt недоступен")

        with mock.patch("PySide6.QtCore.QLocale", _Broken), \
                mock.patch("locale.getlocale", return_value=("ru_RU", "UTF-8")):
            self.assertEqual(detect_system_language(), "ru")


class SystemDefaultLanguageTests(unittest.TestCase):
    def test_bundle_defaults_to_system_language(self):
        """Без сохранённого выбора язык берётся из системы, а не жёстко ru."""
        from unittest import mock

        with mock.patch("hackiclab.i18n.detect_system_language", return_value="en"):
            instance = Tr()
        self.assertEqual(instance.current, "en")


if __name__ == "__main__":
    unittest.main()
