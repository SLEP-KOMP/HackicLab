"""Главное окно HackicLab (PySide6): тёмная тема, RU/EN, 4 вкладки."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtGui import (
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
)

from .. import uistate
from ..i18n import LANG_CODES, detect_system_language, tr
from ..scanner import HardwareProfile
from ..themes import detect_system_scheme, get_qss
from ._analyze import AnalyzeMixin
from ._build import BuildPageMixin

# --- Реэкспорт для тестов: эти имена импортируются из main_window ---
from ._common import (  # noqa: F401
    _SINGLE_SERVER,
    COLUMN_MAX_WIDTH,
    SINGLE_INSTANCE,
    _efi_root_for,
    _release_notes_text,
    install_qt_translator,
)

# --- Миксины ---
from ._core import CoreMixin
from ._donate import DonateMixin
from ._manual import ManualBuildMixin
from ._ports import PortsMixin
from ._settings import SettingsMixin
from ._sources import SourcesMixin
from ._usb import UsbMixin
from ._validate import ValidateMixin
from ._wizard import WizardMixin
from ._workers import BuildWorker  # noqa: F401


class MainWindow(CoreMixin, WizardMixin, ManualBuildMixin, ValidateMixin, BuildPageMixin,
                 PortsMixin, UsbMixin, SourcesMixin, AnalyzeMixin, DonateMixin,
                 SettingsMixin, QMainWindow):
    _WIFI_INTEL = (
        ("itlwm", "wizard.wifi.itlwm", "wizard.wifi.itlwm_desc"),
        ("airport", "wizard.wifi.airport", "wizard.wifi.airport_desc"),
        ("none", "wizard.wifi.none", "wizard.wifi.none_desc"),
    )

    _WIFI_NATIVE = (
        ("none", "wizard.wifi.native", "wizard.wifi.native_desc"),
    )

    _WIFI_BRCM = (
        ("none", "wizard.wifi.brcm", "wizard.wifi.brcm_desc"),
    )

    _VENDOR_TONES = {
        "intel": "#2f6fb3",
        "amd": "#b3352f",
        "nvidia": "#3f8f4f",
        "audio": "#7a5cd6",
        "other": "#56606e",
    }

    _DONATE_URL = "https://yoomoney.ru/to/4100115796556073"

    _DONATE_WALLET = "4100115796556073"

    NAV_GROUPS = (
        ("nav.group.start", (
            ("nav.auto", "✨", "nav.auto.sub"),
        )),
        ("nav.group.build", (
            ("nav.build", "⚙", "nav.build.sub"),
            ("nav.validate", "✅", "nav.validate.sub"),
            ("usbmap.nav", "🔌", "usbmap.nav.sub"),
            ("usb.nav", "💾", "usb.nav.sub"),
        )),
        ("nav.group.more", (
            ("nav.sources", "📚", "nav.sources.sub"),
            ("donate.nav", "💛", "donate.nav.sub"),
            ("nav.settings", "⚙", "nav.settings.sub"),
            ("nav.about", "ℹ", "nav.about.sub"),
        )),
    )

    _WORKER_ATTRS = ("_worker_scan", "_worker_build", "_usb_worker", "_worker_usb",
                     "_worker_val", "_worker_audit", "_worker_an",
                     "_worker_wiz", "usb_list_worker",
                     "_upd_worker", "_upd_dl")

    _SEV = {0: "ℹ", 1: "⚠", 2: "✖"}

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HackicLab")
        self.setMinimumSize(880, 560)
        self._fit_to_screen()
        self.profile: HardwareProfile | None = None
        state = uistate.load()
        self._theme = str(state.get("theme") or "system")
        self._theme_bg = str(state.get("background") or "")
        self._system_hooked = False
        self._build()
        self.apply_theme()
        self._hook_system_theme()
        QTimer.singleShot(3000, self._auto_check_updates)
        # системная тема может смениться без сигнала Qt (например, при
        # включении высокой контрастности) — сверяемся с реестром
        self._last_system_scheme = detect_system_scheme()
        self._sys_timer = QTimer(self)
        self._sys_timer.setInterval(5000)
        self._sys_timer.timeout.connect(self._poll_system_theme)
        self._sys_timer.start()

    def apply_theme(self, theme: str | None = None):
        """Применяет тему оформления и сохраняет выбор пользователя."""
        if theme is not None:
            self._theme = theme
            uistate.save(theme=theme)
        qss = get_qss(getattr(self, "_theme", "system"), getattr(self, "_theme_bg", ""))
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(qss)
            for badge in app.allWidgets():
                if badge.objectName() == "badge":
                    badge.style().unpolish(badge)
                    badge.style().polish(badge)
        self._sync_theme_tiles()

    def _sync_theme_tiles(self):
        """Отмечает плитку, соответствующую текущей теме."""
        tiles = getattr(self, "_theme_tiles", None)
        if not tiles:
            return
        for key, btn in tiles.items():
            btn.blockSignals(True)
            btn.setChecked(key == self._theme)
            btn.update()
            btn.blockSignals(False)

    def _hook_system_theme(self):
        """Следит за сменой системной темы Windows, если выбрана «Системная»."""
        if getattr(self, "_system_hooked", False):
            return
        try:
            hints = QGuiApplication.styleHints()
            hints.colorSchemeChanged.connect(self._on_system_scheme_changed)
            self._system_hooked = True
        except Exception:
            self._system_hooked = False

    def _on_system_scheme_changed(self, *_args):
        self._last_system_scheme = detect_system_scheme()
        if self._theme == "system":
            self.apply_theme()

    def _poll_system_theme(self):
        """Сверяется с системной схемой: Qt не всегда сообщает о смене контраста."""
        if self._theme != "system":
            return
        scheme = detect_system_scheme()
        if scheme != getattr(self, "_last_system_scheme", ""):
            self._last_system_scheme = scheme
            self.apply_theme()


def i18n_report() -> dict[str, object]:
    """Снимок подписей интерфейса на обоих языках — для проверки сборки.

    Запускается флагом ``--check-i18n``: окно создаётся программно, каждый
    язык пересобирает страницы, подписи кнопок диалогов считываются с
    реального QMessageBox.
    """
    report: dict[str, object] = {}
    for lang in ("ru", "en"):
        tr.set_lang(lang)
        install_qt_translator(lang)
        win = MainWindow()
        page = win.stack.currentWidget()
        titles = [w.text() for w in page.findChildren(QLabel) if w.objectName() == "h1"] if page else []
        captured: list[str] = []

        def capture(box: QMessageBox, sink: list[str] = captured) -> int:
            sink.append(" > ".join(b.text() for b in box.buttons()))
            return 0

        original_exec = QMessageBox.exec
        QMessageBox.exec = capture
        try:
            win._confirm("t", "t", tr.t("common.yes"), tr.t("common.no"))
            win._confirm("t", "t", tr.t("settings.updates_now"), tr.t("settings.updates_later"))
        finally:
            QMessageBox.exec = original_exec
        report[lang] = {
            "nav": win._nav_titles(),
            "h1": titles,
            "dialogs": captured,
            "qt_yes": QCoreApplication.translate("QPlatformTheme", "&Yes"),
            "filters": [tr.t("file.all_files"), tr.t("file.images"), tr.t("file.opencore_log")],
        }
        win.close()
        win.deleteLater()
    tr.set_lang(detect_system_language())
    install_qt_translator(tr.current)
    return report


def run_app() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    from .. import updater

    updater.cleanup_old_binaries()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Язык: явный выбор пользователя, иначе — язык системы. Определяем его
    # только после создания QApplication: до этого QLocale отдаёт «C»/en-US
    # и русская Windows получала английский интерфейс.
    saved_lang = str(uistate.get("language", "") or "")
    tr.set_lang(saved_lang if saved_lang in LANG_CODES else detect_system_language())
    install_qt_translator(tr.current)

    # Диагностика локализации: печатает подписи обоих языков и выходит.
    # Форма с путём нужна для сборки без консоли: --check-i18n=<файл>.
    flag = next((a for a in sys.argv if a.startswith("--check-i18n")), "")
    if flag:
        import json

        payload = json.dumps(i18n_report(), ensure_ascii=False, indent=2)
        target = flag.split("=", 1)[1] if "=" in flag else ""
        if target:
            Path(target).write_text(payload, encoding="utf-8")
        else:
            # В сборке без консоли stdout бывает в cp866: без явного UTF-8
            # перенаправленный вывод превращается в мусор.
            reconfigure = getattr(sys.stdout, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(encoding="utf-8")
                except (ValueError, OSError):
                    pass
            print(payload)
        return 0

    # Один экземпляр: второй процесс мешает обновлению и удалению временной
    # папки PyInstaller («Failed to remove temporary directory»).
    from PySide6.QtNetwork import QLocalServer, QLocalSocket

    probe = QLocalSocket()
    probe.connectToServer(SINGLE_INSTANCE)
    if probe.waitForConnected(300):
        probe.disconnectFromServer()
        return 0
    global _SINGLE_SERVER

    QLocalServer.removeServer(SINGLE_INSTANCE)
    server = QLocalServer()
    server.listen(SINGLE_INSTANCE)
    _SINGLE_SERVER = server

    state = uistate.load()
    app.setStyleSheet(
        get_qss(str(state.get("theme") or "system"), str(state.get("background") or ""))
    )
    win = MainWindow()
    win.show()
    return app.exec()
