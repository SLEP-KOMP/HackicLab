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
    def setUp(self):
        """Qt-ветку проверяем отдельно: на Windows приоритет у системного API."""
        from unittest import mock

        patcher = mock.patch("hackiclab.i18n._windows_ui_language", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

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


class LocalizationAuditTests(unittest.TestCase):
    """Диалоги и файловые фильтры не должны оставаться на английском."""

    @classmethod
    def setUpClass(cls):
        from pathlib import Path

        cls.ui_source = (
            Path(__file__).resolve().parents[1] / "hackiclab" / "ui" / "main_window.py"
        ).read_text(encoding="utf-8")

    def test_no_standard_yes_no_buttons(self):
        self.assertNotIn("StandardButton.Yes", self.ui_source)
        self.assertNotIn("QMessageBox.question(", self.ui_source)

    def test_confirm_dialog_is_localized(self):
        self.assertIn("def _confirm(", self.ui_source)
        self.assertIn('tr.t("settings.updates_now")', self.ui_source)
        self.assertIn('tr.t("settings.updates_later")', self.ui_source)

    def test_file_dialog_filters_come_from_i18n(self):
        self.assertNotIn('"All files (*)"', self.ui_source)
        for key in ("file.all_files", "file.plist", "file.opencore_log",
                    "file.images", "file.markdown", "file.json", "file.text"):
            self.assertIn(key, self.ui_source, key)

    def test_qt_translator_installed_on_start_and_switch(self):
        self.assertIn("def install_qt_translator(", self.ui_source)
        self.assertGreaterEqual(self.ui_source.count("install_qt_translator("), 3,
                                "переводчик должен ставиться при старте и смене языка")


class FileFilterKeyTests(unittest.TestCase):
    """Ключи фильтров есть на обоих языках и не пустые."""

    def test_filters_present_in_ru_and_en(self):
        from hackiclab import i18n

        for lang in ("ru", "en"):
            i18n.tr.set_lang(lang)
            for key in ("file.all_files", "file.plist", "file.images", "file.opencore_log"):
                self.assertTrue(i18n.tr.t(key).strip(), f"{lang}:{key}")
        i18n.tr.set_lang("ru")


class WindowsLanguageTests(unittest.TestCase):
    """Windows-детект не зависит от Qt и срабатывает до создания QApplication."""

    def _fake_win(self, lang_id):
        from unittest import mock

        class _Kernel:
            @staticmethod
            def GetUserDefaultUILanguage():
                return lang_id

            @staticmethod
            def GetSystemDefaultUILanguage():
                return lang_id

        class _Windll:
            kernel32 = _Kernel

        class _Ctypes:
            windll = _Windll

        return mock.patch.dict("sys.modules", {"ctypes": _Ctypes}), \
            mock.patch("hackiclab.i18n.sys.platform", "win32")

    def test_russian_ui_language_id(self):
        from hackiclab import i18n

        p1, p2 = self._fake_win(0x419)
        with p1, p2:
            self.assertEqual(i18n._windows_ui_language(), "ru")

    def test_english_ui_language_id(self):
        from hackiclab import i18n

        p1, p2 = self._fake_win(0x409)
        with p1, p2:
            self.assertEqual(i18n._windows_ui_language(), "en")

    def test_non_windows_returns_none(self):
        from unittest import mock

        from hackiclab import i18n

        with mock.patch("hackiclab.i18n.sys.platform", "linux"):
            self.assertIsNone(i18n._windows_ui_language())


class SystemDefaultLanguageTests(unittest.TestCase):
    def test_bundle_defaults_to_system_language(self):
        """Без сохранённого выбора язык берётся из системы, а не жёстко ru."""
        from unittest import mock

        with mock.patch("hackiclab.i18n.detect_system_language", return_value="en"):
            instance = Tr()
        self.assertEqual(instance.current, "en")


if __name__ == "__main__":
    unittest.main()
