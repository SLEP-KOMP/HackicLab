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


class TranslationContentTests(unittest.TestCase):
    """RU и EN не должны подменять друг друга: русский текст только в RU."""

    CYRILLIC = re.compile(r"[А-Яа-яЁё]")

    def test_russian_text_not_copied_into_english(self):
        copied = []
        for key, ru in T["ru"].items():
            en = T["en"].get(key, "")
            if self.CYRILLIC.search(ru) and self.CYRILLIC.search(en):
                copied.append(key)
        self.assertEqual(sorted(copied), [], f"в EN остался русский текст: {sorted(copied)}")

    #: значения совпадают осознанно: имена продуктов, типов файлов и темы
    SAME_ON_PURPOSE = {
        "build.wifi_itlwm", "file.json", "file.markdown", "file.plist",
        "settings.premium", "settings.theme_bigsur",
    }

    def test_english_text_not_copied_into_russian(self):
        """Русский перевод не должен быть английской фразой целиком."""
        suspicious = []
        for key, ru in T["ru"].items():
            en = T["en"].get(key, "")
            if not ru.strip() or not en.strip():
                continue
            if self.CYRILLIC.search(ru):
                continue
            if key in self.SAME_ON_PURPOSE:
                continue
            if ru.strip() == en.strip() and len(ru.strip()) > 3 and " " in ru.strip():
                suspicious.append(f"{key}={ru!r}")
        self.assertEqual(sorted(suspicious), [],
                         f"в RU английский текст: {sorted(suspicious)}")


class UiLiteralTests(unittest.TestCase):
    """Строки интерфейса берутся только из i18n, а не из литералов в коде."""

    ROOT = _bootstrap.ROOT / "hackiclab" / "ui"
    WIDGET_CALLS = (
        "setText(", "showMessage(", "setToolTip(", "setPlaceholderText(",
        "setWindowTitle(", "QLabel(", "QPushButton(", "QCheckBox(", "QGroupBox(",
        "QRadioButton(", "addItem(", "addTab(", "setTitle(",
    )
    #: бренд, аргументы OpenCore и серийный шаблон — не переводятся
    ALLOWED = {"HackicLab", "MacPro7,1", "HILC-XXXX-XXXX-XXXX", "-v debug=0x100 keepsyms=1"}

    @classmethod
    def setUpClass(cls):
        cls.files = sorted(cls.ROOT.rglob("*.py"))

    def _lines(self):
        for path in self.files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                stripped = line.strip()
                if stripped.startswith("#") or '"""' in line:
                    continue
                yield path.name, number, line

    def test_no_hardcoded_russian_in_ui(self):
        pattern = re.compile(r'"[^"\n]*[А-Яа-яЁё][^"\n]*"')
        hits = [f"{name}:{number}: {line.strip()[:80]}" for name, number, line in self._lines()
                if pattern.search(line)]
        self.assertEqual(hits, [], "русский текст вне i18n: " + "; ".join(hits))

    def test_widget_labels_come_from_i18n(self):
        calls = "|".join(re.escape(c) for c in self.WIDGET_CALLS)
        literal = re.compile(r'(?:%s)\s*f?"([^"\n]*[A-Za-z]{3,}[^"\n]*)"' % calls)
        hits = []
        for name, number, line in self._lines():
            for match in literal.finditer(line):
                text = match.group(1)
                if "tr.t(" in text or "{" in text or text.startswith("%"):
                    continue
                if text.strip() in self.ALLOWED:
                    continue
                hits.append(f"{name}:{number}: {text[:60]}")
        self.assertEqual(hits, [], "подписи вне i18n: " + "; ".join(hits))


class PageColumnLayoutTests(unittest.TestCase):
    """Все вкладки стоят центральной колонкой, как «Параметры» Windows."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def test_every_page_centered(self):
        from PySide6.QtWidgets import QScrollArea

        from hackiclab.ui.main_window import COLUMN_MAX_WIDTH, MainWindow

        window = MainWindow()
        try:
            self.assertGreater(window.stack.count(), 1)
            for index in range(window.stack.count()):
                area = window.stack.widget(index)
                if not isinstance(area, QScrollArea):
                    self.fail(f"вкладка {index}: нет прокручиваемой области")
                    continue
                shell = area.widget()
                self.assertIsNotNone(shell, f"вкладка {index}: прокрутка пуста")
                if shell is None:
                    continue
                self.assertEqual(shell.objectName(), "pageShell", f"вкладка {index}")
                layout = shell.layout()
                if layout is None:
                    self.fail(f"вкладка {index}: нет раскладки")
                    continue
                self.assertEqual(layout.count(), 3, f"вкладка {index}: колонка не по центру")
                item = layout.itemAt(1)
                column = item.widget() if item is not None else None
                if column is None:
                    self.fail(f"вкладка {index}: нет колонки")
                    continue
                self.assertEqual(column.maximumWidth(), COLUMN_MAX_WIDTH, f"вкладка {index}")
        finally:
            window.close()
            window.deleteLater()


class DialogLanguageTests(unittest.TestCase):
    """Подписи диалогов на обоих языках — как их увидит пользователь."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtWidgets import QApplication
        except Exception as exc:  # pragma: no cover - Qt нужен для UI-тестов
            raise unittest.SkipTest(f"PySide6 недоступен: {exc}") from None
        cls.app = QApplication.instance() or QApplication([])

    def test_confirm_buttons_follow_language(self):
        from PySide6.QtWidgets import QMessageBox

        from hackiclab.i18n import tr
        from hackiclab.ui.main_window import MainWindow, install_qt_translator

        captured: list[str] = []
        original = QMessageBox.exec
        QMessageBox.exec = lambda box: captured.append(
            " > ".join(b.text() for b in box.buttons())) or 0
        try:
            for lang, yes_no, update in (("ru", "Да > Нет", "Обновить сейчас > Отложить"),
                                         ("en", "Yes > No", "Update now > Later")):
                tr.set_lang(lang)
                install_qt_translator(lang)
                window = MainWindow()
                window._confirm("t", "t", tr.t("common.yes"), tr.t("common.no"))
                window._confirm("t", "t", tr.t("settings.updates_now"),
                                tr.t("settings.updates_later"))
                window.close()
                window.deleteLater()
                self.assertEqual(captured[-2:], [yes_no, update], lang)
        finally:
            QMessageBox.exec = original
            tr.set_lang("ru")
            install_qt_translator("ru")


class BuildLogLocalizationTests(unittest.TestCase):
    """Сводка сборки и статус ocvalidate переводятся целиком."""

    def test_build_log_keys_translated(self):
        keys = ("build.log_summary", "build.log_kexts", "build.log_ocv_skipped",
                "build.log_ocv_ok", "build.log_ocv_problems", "build.ocv_status_errors")
        for lang in ("ru", "en"):
            for key in keys:
                self.assertIn(key, T[lang], f"{lang}:{key}")
        tr = Tr("ru")
        self.assertIn("Kexts (скачано 2)",
                      tr.t("build.log_kexts").format(count=2, list="Lilu, WEG"))
        tr.set_lang("en")
        self.assertIn("Kexts (downloaded 2)",
                      tr.t("build.log_kexts").format(count=2, list="Lilu, WEG"))
        self.assertIn("3", tr.t("build.ocv_status_errors").format(count=3))

    def test_no_russian_log_lines_left(self):
        source = (_bootstrap.ROOT / "hackiclab" / "ui" / "main_window.py").read_text(encoding="utf-8")
        for marker in ("--- Итог ---", "не запускался", "config.plist валиден", "ПРОБЛЕМЫ ("):
            self.assertNotIn(marker, source, marker)


class SystemDefaultLanguageTests(unittest.TestCase):
    def test_bundle_defaults_to_system_language(self):
        """Без сохранённого выбора язык берётся из системы, а не жёстко ru."""
        from unittest import mock

        with mock.patch("hackiclab.i18n.detect_system_language", return_value="en"):
            instance = Tr()
        self.assertEqual(instance.current, "en")


if __name__ == "__main__":
    unittest.main()
