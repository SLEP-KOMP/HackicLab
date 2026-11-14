"""Главное окно HackicLab (PySide6): тёмная тема, RU/EN, 4 вкладки."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit, QGroupBox,
    QCheckBox, QComboBox, QPlainTextEdit, QSplitter, QFrame, QLineEdit,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QColor

from ..i18n import tr, LANGS
from ..themes import get_qss, THEMES
from ..scanner import WindowsScanner, HardwareProfile
from ..builder import (
    BuildPlan, BuildOptions, generate_config_plist, EFIBuilder,
    generate_smbios,
)
from ..knowledge.kexts import smbios_model_for, select_kexts
from ..analyzer import Analyzer

# ---- Тёмная тема (QSS) ----
DARK_QSS = """
QWidget { background-color: #1e1e2e; color: #cdd6f4; font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow { background-color: #1e1e2e; }
#sidebar { background-color: #181825; border-right: 1px solid #313244; }
#sidebar QLabel#logo { color: #f5c2e7; font-size: 22px; font-weight: 800; padding: 16px 12px 4px 12px; }
#sidebar QLabel#sub { color: #7f849c; font-size: 11px; padding: 0 12px 12px 12px; }
#navList { background: transparent; border: none; outline: none; }
#navList::item { padding: 12px 16px; margin: 2px 8px; border-radius: 8px; color: #a6adc8; }
#navList::item:hover { background: #313244; color: #cdd6f4; }
#navList::item:selected { background: #8839ef; color: white; font-weight: 600; }
QPushButton { background: #8839ef; color: white; border: none; border-radius: 8px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #9d4ef0; }
QPushButton:disabled { background: #45475a; color: #7f849c; }
QPushButton#ghost { background: transparent; border: 1px solid #45475a; color: #cdd6f4; }
QPushButton#ghost:hover { background: #313244; }
#card { background: #181825; border: 1px solid #313244; border-radius: 12px; padding: 14px; }
QLabel#h1 { font-size: 20px; font-weight: 700; color: #cdd6f4; }
QLabel#h2 { font-size: 14px; font-weight: 600; color: #a6adc8; }
QLabel#val { font-size: 13px; color: #e1e3ec; }
QLabel#muted { color: #7f849c; font-size: 12px; }
QLabel#kv { color: #7f849c; font-size: 12px; }
QGroupBox { border: 1px solid #313244; border-radius: 10px; margin-top: 14px; padding: 12px 10px; color: #a6adc8; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; }
QProgressBar { background: #313244; border: none; border-radius: 6px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #8839ef; border-radius: 6px; }
QTextEdit, QPlainTextEdit { background: #11111b; border: 1px solid #313244; border-radius: 8px; color: #cdd6f4; font-family: 'Cascadia Code','Consolas'; font-size: 12px; }
QListWidget { background: #181825; border: 1px solid #313244; border-radius: 8px; }
QListWidget::item { padding: 8px; }
QListWidget#issueList::item { border-bottom: 1px solid #252536; padding: 6px; }
QComboBox { background: #181825; border: 1px solid #313244; border-radius: 8px; padding: 6px 10px; }
QComboBox QAbstractItemView { background: #181825; selection-background-color: #8839ef; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator { width: 18px; height: 18px; border-radius: 5px; border: 2px solid #45475a; background: #181825; }
QCheckBox::indicator:checked { background: #8839ef; border-color: #8839ef; }
QSplitter::handle { background: #313244; }
"""


def _h1(parent, text): 
    l = QLabel(text, parent); l.setObjectName("h1"); return l
def _h2(parent, text): 
    l = QLabel(text, parent); l.setObjectName("h2"); return l
def _muted(parent, text): 
    l = QLabel(text, parent); l.setObjectName("muted"); return l
def _kv(parent, text): 
    l = QLabel(text, parent); l.setObjectName("kv"); return l
def _val(parent, text): 
    l = QLabel(text, parent); l.setObjectName("val"); return l


class ScanWorker(QThread):
    """Сканирование железа в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def run(self):
        try:
            p = WindowsScanner().scan()
            self.done.emit(p)
        except Exception as e:
            self.failed.emit(str(e))


class BuildWorker(QThread):
    """Сборка EFI в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, plan: BuildPlan, target: Path):
        super().__init__()
        self.plan = plan
        self.target = target

    def run(self):
        try:
            res = EFIBuilder(self.plan).build(self.target)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))


class USBWriteWorker(QThread):
    """Запись EFI на флешку в фоне."""
    done = Signal(object)
    failed = Signal(str)
    signal = Signal(str)

    def __init__(self, source_efi: Path, device: str, skip_format: bool,
                 recovery_macos: str = ""):
        super().__init__()
        self.source_efi = source_efi
        self.device = device
        self.skip_format = skip_format
        self.recovery_macos = recovery_macos

    def run(self):
        try:
            from ..builder.usb_writer import write_efi_to_usb
            res = write_efi_to_usb(self.source_efi, self.device,
                                   skip_format=self.skip_format,
                                   recovery_macos=self.recovery_macos,
                                   log=self._log)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))

    def _log(self, msg: str):
        self.signal.emit(msg)


class AnalyzeWorker(QThread):
    """Анализ файлов в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, profile, folder):
        super().__init__()
        self.profile = profile
        self.folder = folder

    def run(self):
        try:
            issues = Analyzer(self.profile).analyze_folder(self.folder)
            self.done.emit(issues)
        except Exception as e:
            self.failed.emit(str(e))


def _macos_newer(a: str, b: str) -> bool:
    """Версия a новее b? (по имени macOS). Для подсказки о несовместимости."""
    order = ["High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
             "Ventura", "Sonoma", "Sequoia", "Tahoe"]

    def idx(x):
        for i, n in enumerate(order):
            if n.lower() in (x or "").lower():
                return i
        return -1
    ia, ib = idx(a), idx(b)
    if ia == -1 or ib == -1:
        return False
    return ia > ib


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HackicLab")
        self.resize(1180, 760)
        self.profile: HardwareProfile | None = None
        self._theme = "dark"
        self._build()

    def apply_theme(self, theme: str = None):
        """Применяет тему оформления."""
        if theme is not None:
            self._theme = theme
        qss = get_qss(self._theme)
        app = QApplication.instance()
        if app:
            app.setStyleSheet(qss)

    # ---- layout ----
    def _build(self):
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.setCentralWidget(central)

        # Sidebar
        side = QWidget()
        side.setObjectName("sidebar")
        side.setFixedWidth(240)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        logo = QLabel("HackicLab"); logo.setObjectName("logo")
        sub = QLabel(tr.t("app.tagline")); sub.setObjectName("sub"); sub.setWordWrap(True)
        side_layout.addWidget(logo)
        side_layout.addWidget(sub)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        nav_items = [
            ("nav.scan", "🖥"),
            ("nav.build", "⚙"),
            ("nav.usb", "💾"),
            ("nav.analyze", "🔍"),
            ("nav.settings", "⚙"),
            ("nav.about", "ℹ"),
        ]
        self._nav_keys = [k for k, _ in nav_items]
        for key, icon in nav_items:
            it = QListWidgetItem(f"{icon}  {tr.t(key)}")
            it.setData(Qt.UserRole, key)
            self.nav.addItem(it)
        self.nav.currentRowChanged.connect(self._on_nav)
        side_layout.addWidget(self.nav)
        side_layout.addStretch()

        # Языковой переключатель внизу сайдбара
        langbar = QHBoxLayout()
        langbar.addWidget(_muted(self, "🌐"))
        self.lang_combo = QComboBox()
        for l in LANGS:
            self.lang_combo.addItem(l.native, l.code)
        idx = next((i for i in range(self.lang_combo.count()) if self.lang_combo.itemData(i) == tr.current), 0)
        self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_lang)
        langbar.addWidget(self.lang_combo, 1)
        side_layout.addLayout(langbar)
        side_layout.addSpacing(12)

        root.addWidget(side)

        # Stack
        self.stack = QStackedWidget()
        self.page_scan = self._build_scan()
        self.page_build = self._build_build()
        self.page_usb = self._build_usb()
        self.page_analyze = self._build_analyze()
        self.page_settings = self._build_settings()
        self.page_about = self._build_about()
        self.stack.addWidget(self.page_scan)
        self.stack.addWidget(self.page_build)
        self.stack.addWidget(self.page_usb)
        self.stack.addWidget(self.page_analyze)
        self.stack.addWidget(self.page_settings)
        self.stack.addWidget(self.page_about)
        root.addWidget(self.stack, 1)

    # ---- pages ----
    def _card(self, parent):
        w = QFrame(parent); w.setObjectName("card"); return w

    def _build_scan(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("scan.title")))
        btn = QPushButton(tr.t("scan.button"))
        btn.clicked.connect(self._do_scan)
        v.addWidget(btn, alignment=Qt.AlignLeft)

        self.scan_progress = QProgressBar(); self.scan_progress.setMaximum(0); self.scan_progress.setVisible(False)
        v.addWidget(self.scan_progress)

        self.hw_grid = QVBoxLayout()
        self.hw_grid.setSpacing(10)
        v.addLayout(self.hw_grid)
        v.addStretch()

        self.scan_save_btn = QPushButton(tr.t("scan.save"))
        self.scan_save_btn.setObjectName("ghost")
        self.scan_save_btn.setVisible(False)
        self.scan_save_btn.clicked.connect(self._save_profile)
        v.addWidget(self.scan_save_btn)
        return page

    def _build_build(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("build.title")))

        # options with description cards
        gb = QGroupBox(tr.t("build.options"))
        opts = QVBoxLayout(gb)
        self.opt_usb = QCheckBox(tr.t("build.usb_toolbox")); self.opt_usb.setChecked(True)
        usb_desc = _muted(page, tr.t("build.usb_toolbox_desc")); usb_desc.setWordWrap(True)
        opts.addWidget(self.opt_usb)
        opts.addWidget(usb_desc)
        opts.addSpacing(8)
        self.opt_sip = QCheckBox(tr.t("build.disable_sip"))
        sip_desc = _muted(page, tr.t("build.sip_desc")); sip_desc.setWordWrap(True)
        opts.addWidget(self.opt_sip)
        opts.addWidget(sip_desc)
        opts.addSpacing(8)
        wmode_row = QHBoxLayout()
        wmode_row.addWidget(_h2(page, tr.t("build.wifi_mode")))
        self.wifi_mode = QComboBox()
        self.wifi_mode.addItem(tr.t("build.wifi_itlwm"), "itlwm")
        self.wifi_mode.addItem(tr.t("build.wifi_airport"), "airport")
        wmode_row.addWidget(self.wifi_mode, 1)
        opts.addLayout(wmode_row)
        wifi_desc = _muted(page, tr.t("build.wifi_mode_desc")); wifi_desc.setWordWrap(True)
        opts.addWidget(wifi_desc)
        v.addWidget(gb)

        # macOS version selection
        mb = QGroupBox(tr.t("build.macos"))
        mv = QVBoxLayout(mb)
        mrow = QHBoxLayout()
        mrow.addWidget(_h2(page, tr.t("build.macos")))
        self.macos_combo = QComboBox()
        from ..knowledge.oc_platforms import MACOS_VERSIONS, MAX_MACOS_BY_GEN
        self.macos_combo.addItem(tr.t("build.macos_auto"), "")
        for mver in MACOS_VERSIONS:
            self.macos_combo.addItem(mver["name"], mver["name"])
        # пометим подсказкой о возможной несовместимости (tooltip)
        mrow.addWidget(self.macos_combo, 1)
        mv.addLayout(mrow)
        mac_desc = _muted(page, tr.t("build.macos_desc")); mac_desc.setWordWrap(True)
        mv.addWidget(mac_desc)
        self.macos_incompat = _muted(page, ""); self.macos_incompat.setWordWrap(True)
        self.macos_incompat.setStyleSheet("color:#f9e2af;")
        self.macos_incompat.setVisible(False)
        mv.addWidget(self.macos_incompat)
        self.macos_combo.currentIndexChanged.connect(self._on_macos_change)
        v.addWidget(mb)

        # destination with explicit button
        dest_card = self._card(page)
        dv = QVBoxLayout(dest_card)
        dv.addWidget(_h2(page, tr.t("build.pick")))
        dest_row = QHBoxLayout()
        self.build_dest = QLabel("—"); self.build_dest.setObjectName("muted")
        self.build_dest.setWordWrap(True)
        dest_row.addWidget(self.build_dest, 1)
        dest_btn = QPushButton(tr.t("analyze.browse"))
        dest_btn.clicked.connect(self._pick_build_dir)
        dest_row.addWidget(dest_btn)
        dv.addLayout(dest_row)
        dest_desc = _muted(page, tr.t("build.dest_desc")); dest_desc.setWordWrap(True)
        dv.addWidget(dest_desc)
        note = _muted(page, tr.t("build.note_online")); note.setWordWrap(True)
        note.setStyleSheet("color:#a6e3a1;")
        dv.addWidget(note)
        v.addWidget(dest_card)

        build_btn = QPushButton(tr.t("build.button"))
        build_btn.clicked.connect(self._do_build)
        v.addWidget(build_btn, alignment=Qt.AlignLeft)

        self.build_progress = QProgressBar(); self.build_progress.setMaximum(0); self.build_progress.setVisible(False)
        v.addWidget(self.build_progress)

        lbl = _h2(page, tr.t("build.log"))
        v.addWidget(lbl)
        self.build_log = QPlainTextEdit(); self.build_log.setReadOnly(True); self.build_log.setMinimumHeight(200)
        v.addWidget(self.build_log, 1)
        return page

    def _build_usb(self):
        """Мастер записи EFI на флешку (аналог Build Mode в hackmate, современнее)."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("usb.title")))

        # --- 1. Выбор USB-флешки ---
        usb_card = self._card(page)
        uv = QVBoxLayout(usb_card)
        row1 = QHBoxLayout()
        row1.addWidget(_h2(page, tr.t("usb.choose")))
        refresh_btn = QPushButton(tr.t("usb.refresh")); refresh_btn.setObjectName("ghost")
        refresh_btn.clicked.connect(self._usb_refresh)
        row1.addWidget(refresh_btn)
        row1.addStretch()
        uv.addLayout(row1)

        self.usb_combo = QComboBox()
        self.usb_combo.setMinimumHeight(40)
        uv.addWidget(self.usb_combo)
        self.usb_empty = _muted(page, tr.t("usb.no_devices")); self.usb_empty.setWordWrap(True)
        uv.addWidget(self.usb_empty)

        # description под выделенным диском
        self.usb_selected_desc = _muted(page, ""); self.usb_selected_desc.setWordWrap(True)
        uv.addWidget(self.usb_selected_desc)
        v.addWidget(usb_card)

        # --- 2. Режим записи ---
        mode_card = self._card(page)
        mv = QVBoxLayout(mode_card)
        mv.addWidget(_h2(page, tr.t("usb.mode_title")))
        self.usb_mode = QComboBox()
        self.usb_mode.addItem(tr.t("usb.full"), "full")
        self.usb_mode.addItem(tr.t("usb.formatted"), "formatted")
        self.usb_mode.addItem(tr.t("usb.repair"), "repair")
        mv.addWidget(self.usb_mode)
        self.usb_mode_desc = _muted(page, tr.t("usb.mode_full")); self.usb_mode_desc.setWordWrap(True)
        mv.addWidget(self.usb_mode_desc)
        self.usb_mode.currentIndexChanged.connect(self._usb_mode_change)
        v.addWidget(mode_card)

        # --- 3. Источник EFI ---
        src_card = self._card(page)
        sv = QVBoxLayout(src_card)
        srow = QHBoxLayout()
        srow.addWidget(_h2(page, tr.t("usb.source")))
        self.usb_source = QLabel("—"); self.usb_source.setObjectName("muted")
        self.usb_source.setWordWrap(True)
        srow.addWidget(self.usb_source, 1)
        src_btn = QPushButton(tr.t("usb.browse_source"))
        src_btn.clicked.connect(self._pick_efi_source)
        srow.addWidget(src_btn)
        sv.addLayout(srow)
        src_hint = _muted(page, tr.t("usb.source_hint")); src_hint.setWordWrap(True)
        sv.addWidget(src_hint)
        v.addWidget(src_card)

        # --- 3.5. macOS Recovery (полноценный установщик) ---
        rec_card = self._card(page)
        rcv = QVBoxLayout(rec_card)
        rec_row = QHBoxLayout()
        self.usb_recovery_chk = QCheckBox(tr.t("usb.include_recovery"))
        self.usb_recovery_chk.setChecked(True)
        rec_row.addWidget(self.usb_recovery_chk)
        rec_row.addStretch()
        rcv.addLayout(rec_row)
        rec_desc = _muted(page, tr.t("usb.include_recovery_desc")); rec_desc.setWordWrap(True)
        rcv.addWidget(rec_desc)
        ver_row = QHBoxLayout()
        ver_row.addWidget(_h2(page, tr.t("usb.recovery_version")))
        self.usb_recovery_ver = QComboBox()
        from ..builder.recovery import MACOS_VERSIONS
        for ver in MACOS_VERSIONS:
            self.usb_recovery_ver.addItem(ver.name, ver.name)
        # по умолчанию выделим версию из сборки, если выбрана
        target = self.macos_combo.currentData() or ""
        if target:
            for i in range(self.usb_recovery_ver.count()):
                if target in self.usb_recovery_ver.itemText(i):
                    self.usb_recovery_ver.setCurrentIndex(i)
                    break
        ver_row.addWidget(self.usb_recovery_ver, 1)
        rcv.addLayout(ver_row)
        self.usb_recovery_chk.toggled.connect(self._usb_recovery_toggle)
        v.addWidget(rec_card)

        v.addStretch()

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        self.usb_write_btn = QPushButton(tr.t("usb.start"))
        self.usb_write_btn.clicked.connect(self._usb_start)
        btn_row.addWidget(self.usb_write_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self.usb_progress = QProgressBar(); self.usb_progress.setMaximum(0); self.usb_progress.setVisible(False)
        v.addWidget(self.usb_progress)

        lbl = _h2(page, tr.t("usb.log"))
        v.addWidget(lbl)
        self.usb_log = QPlainTextEdit(); self.usb_log.setReadOnly(True); self.usb_log.setMinimumHeight(180)
        v.addWidget(self.usb_log, 1)

        # сразу просканируем флешки
        self._usb_refresh()
        return page

    def _usb_refresh(self):
        """Обновляет список USB-флешек."""
        from ..builder.usb_writer import get_usb_devices
        self.usb_combo.clear()
        try:
            self.usb_devices = get_usb_devices()
        except Exception:
            self.usb_devices = []
        if not self.usb_devices:
            self.usb_empty.setText(tr.t("usb.no_devices"))
            self.usb_empty.setVisible(True)
            self.usb_selected_desc.setText("")
            self.usb_combo.setEnabled(False)
            return
        self.usb_empty.setVisible(False)
        self.usb_combo.setEnabled(True)
        for d in self.usb_devices:
            label = f"{d.device}   {d.size}   {d.label or ''}".strip()
            self.usb_combo.addItem(label, d.device)
        self.usb_combo.currentIndexChanged.connect(self._usb_select)
        self._usb_select()
        self.statusBar().showMessage(
            f"{tr.t('usb.detected')}: {len(self.usb_devices)}", 3000)

    def _usb_select(self):
        idx = self.usb_combo.currentIndex()
        if idx < 0 or not getattr(self, "usb_devices", None):
            self.usb_selected_desc.setText("")
            return
        d = self.usb_devices[idx]
        self.usb_selected_desc.setText(
            f"{tr.t('usb.selected')}: {d.device} {d.size} — {d.label or ''}".strip())

    def _usb_mode_change(self):
        mode = self.usb_mode.currentData() or "full"
        key = {
            "full": "usb.mode_full",
            "formatted": "usb.mode_formatted",
            "repair": "usb.mode_repair",
        }.get(mode, "usb.mode_full")
        self.usb_mode_desc.setText(tr.t(key))

    def _usb_recovery_toggle(self, on: bool):
        self.usb_recovery_ver.setEnabled(bool(on))

    def _pick_efi_source(self):
        d = QFileDialog.getExistingDirectory(self, tr.t("usb.source"))
        if d:
            self.usb_source.setText(d)

    def _usb_start(self):
        """Проверка входных данных и запуск подтверждения."""
        if not self.profile:
            QMessageBox.information(self, tr.t("usb.title"), tr.t("usb.need_scan"))
            return
        if self.usb_source.text() == "—":
            QMessageBox.warning(self, tr.t("usb.title"), tr.t("usb.need_source"))
            return
        idx = self.usb_combo.currentIndex()
        if idx < 0 or not getattr(self, "usb_devices", None):
            QMessageBox.warning(self, tr.t("usb.title"), tr.t("usb.need_source"))
            return
        device = self.usb_combo.itemData(idx)
        self._usb_confirm(device)

    def _usb_confirm(self, device: str):
        """Экран/диалог подтверждения: ввод фразы WRITE <device>."""
        from PySide6.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QPushButton, QLabel
        mode = self.usb_mode.currentData() or "full"

        dlg = QDialog(self)
        dlg.setWindowTitle(tr.t("usb.confirm_title"))
        dlg.setMinimumWidth(460)
        dlgv = QVBoxLayout(dlg)

        dev = next((x for x in getattr(self, "usb_devices", []) if x.device == device), None)
        dev_txt = f"{device} {dev.size if dev else ''}".strip()

        dlgv.addWidget(_h2(dlg, f"{tr.t('usb.confirm_target')}: {dev_txt}"))

        action = {"full": tr.t("usb.mode_full"),
                  "formatted": tr.t("usb.mode_formatted"),
                  "repair": tr.t("usb.mode_repair")}.get(mode, "")
        dlgv.addWidget(_h2(dlg, f"{tr.t('usb.confirm_action')}: {action}"))

        if mode == "full":
            warn = _val(dlg, "⚠  " + tr.t("usb.warn_erase")); warn.setStyleSheet("color:#f38ba8; font-weight:bold;")
            dlgv.addWidget(warn)
        elif mode == "repair":
            dlgv.addWidget(_muted(dlg, tr.t("usb.warn_repair")))
        else:
            dlgv.addWidget(_muted(dlg, tr.t("usb.warn_formatted")))

        phrase = f"WRITE {device}"
        dlgv.addWidget(_val(dlg, f"{tr.t('usb.confirm_phrase')}:  {phrase}"))
        inp = QLineEdit(dlg)
        inp.setPlaceholderText(phrase)
        dlgv.addWidget(inp)

        self._usb_mismatch = _muted(dlg, "")
        dlgv.addWidget(self._usb_mismatch)

        btns = QDialogButtonBox()
        ok_btn = QPushButton(tr.t("usb.proceed"))
        cancel_btn = QPushButton(tr.t("usb.cancel"))
        btns.addButton(ok_btn, QDialogButtonBox.AcceptRole)
        btns.addButton(cancel_btn, QDialogButtonBox.RejectRole)
        dlgv.addWidget(btns)

        def _try_accept():
            if inp.text().strip() == phrase:
                dlg.accept()
            else:
                self._usb_mismatch.setText(f"{tr.t('usb.confirm_mismatch')} {phrase}")
                self._usb_mismatch.setStyleSheet("color:#f38ba8;")

        ok_btn.clicked.connect(_try_accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            self._usb_run(device, mode)

    def _usb_run(self, device: str, mode: str):
        """Запуск записи EFI на флешку в фоновом потоке."""
        self.usb_progress.setVisible(True)
        self.usb_log.clear()
        self.usb_log.appendPlainText(tr.t("usb.running"))
        source = Path(self.usb_source.text())
        from ..builder.usb_writer import write_efi_to_usb
        skip_format = (mode in ("formatted", "repair"))
        recovery_macos = ""
        if getattr(self, "usb_recovery_chk", None) and self.usb_recovery_chk.isChecked():
            recovery_macos = self.usb_recovery_ver.currentData() or ""
        self._usb_worker = USBWriteWorker(source, device, skip_format, recovery_macos)
        self._usb_worker.signal.connect(self._usb_worker_log)
        self._usb_worker.done.connect(self._usb_done)
        self._usb_worker.failed.connect(self._usb_failed)
        self._usb_worker.start()

    def _usb_worker_log(self, msg):
        self.usb_log.appendPlainText(msg)

    def _usb_done(self, res):
        self.usb_progress.setVisible(False)
        self._usb_finish(res.ok, res.target_letter, res.error)

    def _usb_failed(self, err):
        self.usb_progress.setVisible(False)
        self.usb_log.appendPlainText(f"ERROR: {err}")
        QMessageBox.critical(self, tr.t("usb.failed"), str(err))

    def _usb_finish(self, ok: bool, target_letter: str, error: str):
        if not ok:
            QMessageBox.critical(self, tr.t("usb.failed"), error or "?")
            return
        self.statusBar().showMessage(
            f"{tr.t('usb.done')} → {target_letter}", 5000)
        # BIOS-чеклист
        warn = "⚠  " + tr.t("usb.warn_erase") if False else ""
        self._usb_bios_dialog()

    def _usb_bios_dialog(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QDialogButtonBox, QListWidgetItem
        dlg = QDialog(self)
        dlg.setWindowTitle(tr.t("usb.bios_title"))
        dlg.setMinimumWidth(520)
        dlgv = QVBoxLayout(dlg)
        dlgv.addWidget(_h2(dlg, tr.t("usb.bios_desc")))
        lst = QListWidget(dlg)
        for key in ("usb.bios1", "usb.bios2", "usb.bios3", "usb.bios4", "usb.bios5"):
            it = QListWidgetItem("→  " + tr.t(key))
            lst.addItem(it)
        lst.setSelectionMode(QListWidget.NoSelection)
        dlgv.addWidget(lst)
        btn = QPushButton(tr.t("usb.bios_finish"))
        btn.clicked.connect(dlg.accept)
        dlgv.addWidget(btn, alignment=Qt.AlignRight)
        dlg.exec()

    def _build_analyze(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("analyze.title")))

        # Пояснение что это
        hint_card = self._card(page)
        hv = QVBoxLayout(hint_card)
        hv.addWidget(_h2(page, tr.t("analyze.steps_title")))
        st1 = _muted(page, tr.t("analyze.step1")); st1.setWordWrap(True)
        st2 = _muted(page, tr.t("analyze.step2")); st2.setWordWrap(True)
        hv.addWidget(st1)
        hv.addWidget(st2)
        v.addWidget(hint_card)

        # Явный выбор папки
        row = QHBoxLayout()
        row.addWidget(_h2(page, tr.t("analyze.pick")))
        self.an_folder = QLabel("—"); self.an_folder.setObjectName("muted")
        self.an_folder.setWordWrap(True)
        row.addWidget(self.an_folder, 1)
        browse = QPushButton(tr.t("analyze.browse"))
        browse.clicked.connect(self._pick_analyze_dir)
        row.addWidget(browse)
        v.addLayout(row)

        desc = _muted(page, tr.t("analyze.hint")); desc.setWordWrap(True)
        v.addWidget(desc)

        run = QPushButton(tr.t("analyze.button"))
        run.clicked.connect(self._do_analyze)
        v.addWidget(run, alignment=Qt.AlignLeft)

        self.an_progress = QProgressBar(); self.an_progress.setMaximum(0); self.an_progress.setVisible(False)
        v.addWidget(self.an_progress)

        splitter = QSplitter(Qt.Horizontal)
        self.issue_list = QListWidget(); self.issue_list.setObjectName("issueList")
        self.issue_detail = QTextEdit(); self.issue_detail.setReadOnly(True)
        splitter.addWidget(self.issue_list)
        splitter.addWidget(self.issue_detail)
        splitter.setSizes([540, 380])
        self.issue_list.currentItemChanged.connect(self._on_issue)
        v.addWidget(splitter, 1)
        return page

    def _build_settings(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("settings.title")))

        # Язык
        gb_lang = QGroupBox(tr.t("settings.language"))
        lg = QHBoxLayout(gb_lang)
        lg.addWidget(_h2(page, tr.t("settings.language")))
        self.settings_lang = QComboBox()
        for l in LANGS:
            self.settings_lang.addItem(l.native, l.code)
        idx = next((i for i in range(self.settings_lang.count()) if self.settings_lang.itemData(i) == tr.current), 0)
        self.settings_lang.setCurrentIndex(idx)
        self.settings_lang.currentIndexChanged.connect(self._on_lang)
        lg.addWidget(self.settings_lang, 1)
        v.addWidget(gb_lang)

        # Тема оформления
        gb_theme = QGroupBox(tr.t("settings.theme"))
        tv = QVBoxLayout(gb_theme)
        theme_row = QHBoxLayout()
        theme_row.addWidget(_h2(page, tr.t("settings.theme")))
        self.theme_combo = QComboBox()
        self.theme_combo.addItem(tr.t("settings.theme_dark"), "dark")
        self.theme_combo.addItem(tr.t("settings.theme_light"), "light")
        self.theme_combo.addItem(tr.t("settings.theme_system"), "system")
        self.theme_combo.addItem(tr.t("settings.theme_custom"), "custom")
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self._theme)))
        self.theme_combo.currentIndexChanged.connect(self._on_theme)
        theme_row.addWidget(self.theme_combo, 1)
        tv.addLayout(theme_row)
        theme_desc = _muted(page, tr.t("settings.theme_descr")); theme_desc.setWordWrap(True)
        tv.addWidget(theme_desc)
        v.addWidget(gb_theme)

        # Поведение приложения
        gb_behavior = QGroupBox(tr.t("settings.app_behavior"))
        bv = QVBoxLayout(gb_behavior)
        self.set_autoscan = QCheckBox(tr.t("settings.autoscan")); self.set_autoscan.setChecked(True)
        self.set_hints = QCheckBox(tr.t("settings.show_welcome")); self.set_hints.setChecked(True)
        self.set_updates = QCheckBox(tr.t("settings.check_updates")); self.set_updates.setChecked(True)
        self.set_logs = QCheckBox(tr.t("settings.keep_builds")); self.set_logs.setChecked(True)
        bv.addWidget(self.set_autoscan)
        bv.addWidget(self.set_hints)
        bv.addWidget(self.set_updates)
        bv.addWidget(self.set_logs)
        v.addWidget(gb_behavior)

        # Дополнительно
        gb_adv = QGroupBox(tr.t("settings.advanced"))
        av = QVBoxLayout(gb_adv)
        conc_row = QHBoxLayout()
        conc_row.addWidget(_h2(page, tr.t("settings.download_concurrent")))
        self.dl_concurrent = QComboBox()
        for n in ("1", "2", "3", "4"):
            self.dl_concurrent.addItem(n, int(n))
        self.dl_concurrent.setCurrentIndex(1)
        conc_row.addWidget(self.dl_concurrent, 1)
        av.addLayout(conc_row)
        v.addWidget(gb_adv)

        # Лицензия / Premium (переводится через i18n)
        gb_lic = QGroupBox(tr.t("settings.premium"))
        lv = QVBoxLayout(gb_lic)
        from ..license import license_manager as lm
        st = lm.status()
        edition_txt = tr.t("settings.premium_edition_premium") if st["is_premium"] else tr.t("settings.premium_edition_free")
        self.lic_status = _val(page, f"{tr.t('settings.premium_edition')}: {edition_txt}")
        lv.addWidget(self.lic_status)
        lv.addWidget(_muted(page, tr.t("settings.premium_features")))
        key_row = QHBoxLayout()
        self.lic_key = QLineEdit(); self.lic_key.setPlaceholderText("HILC-XXXX-XXXX-XXXX")
        key_row.addWidget(self.lic_key, 1)
        act_btn = QPushButton(tr.t("settings.premium_activate")); act_btn.setObjectName("ghost")
        act_btn.clicked.connect(self._activate_license)
        key_row.addWidget(act_btn)
        lv.addLayout(key_row)
        v.addWidget(gb_lic)

        v.addStretch()
        return page

    def _on_theme(self):
        theme = self.theme_combo.currentData() or "dark"
        self._theme = theme
        self.apply_theme(theme)

    def _activate_license(self):
        from ..license import LicenseManager
        mgr = LicenseManager()
        ok, res = mgr.activate_premium(self.lic_key.text())
        if ok:
            self.statusBar().showMessage(tr.t("settings.premium_activated"), 4000)
            self.lic_status.setText(f"{tr.t('settings.premium_edition')}: {tr.t('settings.premium_edition_premium')}")
            QMessageBox.information(self, tr.t("settings.premium"), tr.t("settings.premium_activated"))
        else:
            QMessageBox.warning(self, tr.t("settings.premium"), tr.t("settings.premium_invalid"))

    def _on_theme(self):
        theme = self.theme_combo.currentData() or "dark"
        self._theme = theme
        self.apply_theme(theme)

    def _activate_license(self):
        from ..license import LicenseManager
        mgr = LicenseManager()
        ok, res = mgr.activate_premium(self.lic_key.text())
        if ok:
            self.statusBar().showMessage("Premium activated", 4000)
            self.lic_status.setText("HackicLab Premium")
            QMessageBox.information(self, "HackicLab Premium", "Активировано")
        else:
            QMessageBox.warning(self, "HackicLab Premium", "Неверный ключ")

    def _build_about(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("about.title")))

        # Что это
        c_what = self._card(page)
        wv = QVBoxLayout(c_what)
        wv.addWidget(_h2(page, tr.t("about.whatis")))
        wv.addWidget(_muted(page, tr.t("about.whatis_text")))
        v.addWidget(c_what)

        # Возможности
        c_feat = self._card(page)
        fv = QVBoxLayout(c_feat)
        fv.addWidget(_h2(page, tr.t("about.features_title")))
        for key in ("about.feature1", "about.feature2", "about.feature3", "about.feature4", "about.feature5"):
            fv.addWidget(_muted(page, tr.t(key)))
        v.addWidget(c_feat)

        # Технологии
        c_tech = self._card(page)
        tv = QVBoxLayout(c_tech)
        tv.addWidget(_h2(page, tr.t("about.tech_title")))
        tv.addWidget(_muted(page, tr.t("about.tech_text")))
        tv.addSpacing(6)
        tv.addWidget(_muted(page, f"{tr.t('about.version')} 0.1.0 · {tr.t('about.license')}"))
        v.addWidget(c_tech)

        # Дисклеймер
        c_disc = self._card(page)
        dv = QVBoxLayout(c_disc)
        dv.addWidget(_h2(page, tr.t("about.disc")))
        disc = _muted(page, tr.t("about.disc_text")); disc.setWordWrap(True)
        dv.addWidget(disc)
        v.addWidget(c_disc)

        v.addStretch()
        return page

    # ---- nav / lang ----
    def _on_nav(self, row):
        if row >= 0:
            self.stack.setCurrentIndex(row)

    def _on_lang(self):
        code = self.lang_combo.currentData() or "ru"
        tr.set_lang(code)
        self._retranslate()

    def _retranslate(self):
        self.nav.clear()
        icons = ["🖥", "⚙", "💾", "🔍", "⚙", "ℹ"]
        for i, key in enumerate(self._nav_keys):
            self.nav.addItem(QListWidgetItem(f"{icons[i]}  {tr.t(key)}"))
        self.nav.setCurrentRow(self.stack.currentIndex())
        # обновим заголовки страниц
        self._refresh_dynamic()

    def _refresh_dynamic(self):
        if self.profile is None:
            return

    # ---- scan ----
    def _do_scan(self):
        # очистим сетку
        while self.hw_grid.count():
            it = self.hw_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        self.scan_progress.setVisible(True)
        self._worker_scan = ScanWorker()
        self._worker_scan.done.connect(self._scan_done)
        self._worker_scan.failed.connect(self._scan_failed)
        self._worker_scan.start()

    def _scan_done(self, profile):
        self.scan_progress.setVisible(False)
        self.profile = profile
        while self.hw_grid.count():
            it = self.hw_grid.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        rows = [
            ("scan.cpu", f"{profile.cpu.name} / {profile.cpu.codename} / {profile.cpu.generation} gen" if profile.cpu.name else "—"),
            ("scan.gpu", ", ".join([g.name for g in [profile.igpu, profile.dgpu] if g]) or "—"),
            ("scan.audio", profile.audio.name or "—"),
            ("scan.net", f"LAN: {profile.net.eth_name or '—'}\nWiFi: {profile.net.wifi_name or '—'}"),
            ("scan.storage", "NVMe" if profile.storage.nvme_present else "SATA"),
            ("scan.platform", profile.platform),
            ("scan.board", f"{profile.board_vendor} {profile.board_name}".strip() or "—"),
        ]
        for key, val in rows:
            c = self._card(self.page_scan)
            cv = QVBoxLayout(c); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(2)
            cv.addWidget(_h2(self.page_scan, tr.t(key)))
            vv = _val(self.page_scan, val); vv.setWordWrap(True)
            cv.addWidget(vv)
            self.hw_grid.addWidget(c)
        self.scan_save_btn.setVisible(True)
        self.statusBar().showMessage(tr.t("scan.done"), 3000)

    def _scan_failed(self, err):
        self.scan_progress.setVisible(False)
        QMessageBox.critical(self, tr.t("scan.title"), str(err))

    def _save_profile(self):
        if not self.profile:
            return
        try:
            import json
            from ..builder.cache_manager import profiles_dir
            p = profiles_dir() / "profile.json"
            p.write_text(json.dumps(self.profile.to_dict(), ensure_ascii=False, indent=2))
            self.statusBar().showMessage(f"{tr.t('scan.saved')}: {p}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "HackicLab", str(e))

    # ---- build ----
    def _on_macos_change(self):
        """Подсвечивает возможную несовместимость выбранной macOS-версии с железом."""
        target = self.macos_combo.currentData() or ""
        p = self.profile
        if not p:
            self.macos_incompat.setVisible(False)
            return
        from ..knowledge.oc_platforms import MAX_MACOS_BY_GEN
        max_ver = MAX_MACOS_BY_GEN.get(p.cpu.generation, "Sonoma")
        if "unsupported" in max_ver.lower():
            txt = tr.t("build.macos_maybe_incompat")
        elif target and target != max_ver and _macos_newer(target, max_ver):
            txt = tr.t("build.macos_maybe_incompat")
        else:
            txt = ""
        self.macos_incompat.setText(txt)
        self.macos_incompat.setVisible(bool(txt))

    def _pick_build_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr.t("build.pick"))
        if d:
            self.build_dest.setText(d)

    def _do_build(self):
        if not self.profile:
            QMessageBox.information(self, "HackicLab", tr.t("scan.button"))
            return
        if self.build_dest.text() == "—":
            QMessageBox.warning(self, "HackicLab", tr.t("build.pick"))
            return
        opts = BuildOptions(
            usb_toolbox=self.opt_usb.isChecked(),
            disable_sip=self.opt_sip.isChecked(),
            wifi_kext_mode=self.wifi_mode.currentData() or "itlwm",
            target_macos=self.macos_combo.currentData() or "",
        )
        plan = BuildPlan(profile=self.profile, options=opts)
        target = Path(self.build_dest.text())
        self.build_progress.setVisible(True)
        self.build_log.clear()
        self.build_log.appendPlainText(tr.t("build.building"))
        self._worker_build = BuildWorker(plan, target)
        self._worker_build.done.connect(self._build_done)
        self._worker_build.failed.connect(self._build_failed)
        self._worker_build.start()

    def _build_done(self, res):
        self.build_progress.setVisible(False)
        log = f"target: {res.root}\n" + "\n".join(res.log)
        if res.stats:
            log += f"\n\n--- Итог ---"
            log += f"\nOpenCore: {res.stats.get('opencore', '—')}"
            log += f"\nKexts (скачано {len(res.stats.get('kexts_downloaded', []))}): {', '.join(res.stats.get('kexts_downloaded', []))}"
            log += f"\nSSDT: {', '.join(res.stats.get('ssdt_placed', []) or [])}"
            log += f"\nSMBIOS: {res.stats.get('smbios', '')}"
            # ocvalidate
            ocv_ok = res.stats.get("ocvalidate_ok")
            ocv_err = res.stats.get("ocvalidate_errors", [])
            ocv_warn = res.stats.get("ocvalidate_warnings", [])
            log += f"\n\n--- ocvalidate ---"
            if ocv_ok is None:
                log += "\nне запускался"
            elif ocv_ok:
                log += "\nOK — config.plist валиден"
            else:
                log += f"\nПРОБЛЕМЫ ({len(ocv_err)} error, {len(ocv_warn)} warn)"
                for e in ocv_err[:25]:
                    log += f"\n  [err] {e}"
                for w in ocv_warn[:15]:
                    log += f"\n  [warn] {w}"
        self.build_log.setPlainText(log)
        # статус
        if res.stats and res.stats.get("ocvalidate_ok") is False:
            self.statusBar().showMessage(f"ocvalidate: {len(res.stats.get('ocvalidate_errors', []))} ошибок", 6000)
        else:
            self.statusBar().showMessage(tr.t("build.done"), 4000)

    def _build_failed(self, err):
        self.build_progress.setVisible(False)
        self.build_log.setPlainText(str(err))
        QMessageBox.critical(self, tr.t("build.title"), str(err))

    # ---- analyze ----
    def _pick_analyze_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr.t("analyze.pick"))
        if d:
            self.an_folder.setText(d)

    def _do_analyze(self):
        if not self.profile:
            QMessageBox.information(self, "HackicLab", tr.t("scan.button"))
            return
        if self.an_folder.text() == "—":
            QMessageBox.warning(self, "HackicLab", tr.t("analyze.no_folder"))
            return
        folder = Path(self.an_folder.text())
        self.an_progress.setVisible(True)
        self.issue_list.clear()
        self.issue_detail.clear()
        self._worker_an = AnalyzeWorker(self.profile, folder)
        self._worker_an.done.connect(self._analyze_done)
        self._worker_an.failed.connect(self._analyze_failed)
        self._worker_an.start()

    _SEV = {0: "ℹ", 1: "⚠", 2: "✖"}
    _SEV_COLOR = {0: "#7f849c", 1: "#f9e2af", 2: "#f38ba8"}

    def _analyze_done(self, issues):
        self.an_progress.setVisible(False)
        self._issues = issues
        self.issue_list.clear()
        for iss in issues:
            icon = self._SEV.get(int(iss.severity), "ℹ")
            it = QListWidgetItem(f"{icon} {iss.title}")
            it.setData(Qt.UserRole, iss)
            it.setForeground(QColor(self._SEV_COLOR.get(int(iss.severity), "#cdd6f4")))
            self.issue_list.addItem(it)
        n_err = sum(1 for i in issues if int(i.severity) == 2)
        n_warn = sum(1 for i in issues if int(i.severity) == 1)
        self.statusBar().showMessage(
            f"{tr.t('analyze.issues')}: {len(issues)} ({tr.t('analyze.error')}: {n_err}, {tr.t('analyze.warning')}: {n_warn})",
            6000)

    def _analyze_failed(self, err):
        self.an_progress.setVisible(False)
        QMessageBox.critical(self, tr.t("analyze.title"), str(err))

    def _on_issue(self, cur, _prev):
        if cur:
            iss = cur.data(Qt.UserRole)
            txt = f"{cur.text()}\n\n{iss.detail}\n\n→ {iss.suggestion}" if iss else ""
            self.issue_detail.setPlainText(txt)


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    return app.exec()