"""Главное окно HackicLab (PySide6): тёмная тема, RU/EN, 4 вкладки."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QListWidget, QListWidgetItem,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit, QGroupBox,
    QCheckBox, QComboBox, QPlainTextEdit, QSplitter, QFrame, QLineEdit,
    QSpinBox, QScrollArea,
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer
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
                 recovery_macos: str = "", drive_letter: str = "",
                 make_usb_map: bool = True):
        super().__init__()
        self.source_efi = source_efi
        self.device = device
        self.skip_format = skip_format
        self.recovery_macos = recovery_macos
        self.drive_letter = drive_letter
        self.make_usb_map = make_usb_map

    def run(self):
        try:
            from ..builder.usb_writer import write_efi_to_usb
            res = write_efi_to_usb(self.source_efi, self.device,
                                   skip_format=self.skip_format,
                                   recovery_macos=self.recovery_macos,
                                   drive_letter=self.drive_letter,
                                   make_usb_map=self.make_usb_map,
                                   log=self._log)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))

    def _log(self, msg: str):
        self.signal.emit(msg)


class ValidateWorker(QThread):
    """Прогон ocvalidate в фоне."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, config_path: Path):
        super().__init__()
        self.config_path = config_path

    def run(self):
        try:
            from ..builder.ocvalidate import run_ocvalidate, find_ocvalidate
            tool = find_ocvalidate()
            res = run_ocvalidate(self.config_path, ocvalidate=tool)
            res_dict = {
                "ok": res.ok,
                "warnings": res.warnings,
                "errors": res.errors,
                "missing_keys": res.missing_keys,
                "schema_errors": res.schema_errors,
                "version_note": res.version_note,
                "tool_version": res.tool_version,
                "tool_missing": res.tool_missing,
                "full_output": res.full_output,
            }
            self.done.emit(res_dict)
        except Exception as e:
            self.failed.emit(str(e))


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


class AuditWorker(QThread):
    """Структурный аудит EFI в фоне (kexts, ACPI, драйверы, SIP)."""
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, efi_root: Path):
        super().__init__()
        self.efi_root = efi_root

    def run(self):
        try:
            from ..analyzer.engine import audit_efi
            self.done.emit(audit_efi(self.efi_root))
        except Exception as e:
            self.failed.emit(str(e))


class UsbMapWorker(QThread):
    """Карта USB-портов: DSDT -> usbdump.exe -> plist."""
    done = Signal(object, str)
    failed = Signal(str)

    def run(self):
        import tempfile
        lines: list[str] = []

        def log(msg, level="info"):
            lines.append(f"[{level}] {msg}")

        try:
            from ..builder.usb_map import generate_auto_map
            tmp = Path(tempfile.mkdtemp(prefix="hackiclab_usbmap_"))
            plist = generate_auto_map(tmp, log=log)
            self.done.emit(plist, "\n".join(lines))
        except Exception as e:
            self.failed.emit(str(e))


class DiskMapWorker(QThread):
    """Скан дисков и загрузчиков в фоне (PowerShell, только чтение)."""
    done = Signal(str, list)
    failed = Signal(str)

    def run(self):
        try:
            from ..scanner.diskmap import (
                scan_disks, scan_all_bootloaders, check_conflicts, build_disk_tree)
            disks = scan_disks()
            bootloaders = scan_all_bootloaders(disks)
            self.done.emit(build_disk_tree(disks, bootloaders),
                           check_conflicts(disks, bootloaders))
        except Exception as e:
            self.failed.emit(str(e))


class OCLogWorker(QThread):
    """Разбор лога OpenCore в фоне."""
    done = Signal(list)
    failed = Signal(str)

    def __init__(self, path: Path):
        super().__init__()
        self.path = Path(path)

    def run(self):
        try:
            from ..analyzer.oc_log import parse_log_file
            self.done.emit(parse_log_file(self.path))
        except Exception as e:
            self.failed.emit(str(e))


class UsbListWorker(QThread):
    """Список USB-флешек в фоне: PowerShell не должен блокировать интерфейс."""
    done = Signal(list)
    failed = Signal(str)

    def run(self):
        try:
            from ..builder.usb_writer import get_usb_devices
            self.done.emit(get_usb_devices())
        except Exception as e:
            self.failed.emit(str(e))


def _has_cyrillic(text: str) -> bool:
    return any("\u0400" <= ch <= "\u04FF" for ch in (text or ""))


def _issue_title(issue) -> str:
    """EN-заголовок проблемы с сохранением имени файла/кекста после двоеточия."""
    title = tr.issue(issue.code, "title", issue.title)
    if title != issue.title and ":" in issue.title:
        tail = issue.title.split(":", 1)[1].strip()
        if tail and not _has_cyrillic(tail):
            title = f"{title}: {tail}"
    return title


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
        self.setMinimumSize(880, 560)
        self._fit_to_screen()
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

    def _fit_to_screen(self):
        """Подгоняет стартовое окно под экран: важно для ноутбуков и масштаба Windows."""
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1180, 760)
            return
        avail = screen.availableGeometry()
        w = max(880, min(1180, avail.width() - 60))
        h = max(560, min(760, avail.height() - 60))
        self.resize(w, h)
        self.move(avail.x() + (avail.width() - w) // 2,
                  avail.y() + (avail.height() - h) // 2)

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
        self._tagline_label = sub
        side_layout.addWidget(logo)
        side_layout.addWidget(sub)

        self.nav = QListWidget()
        self.nav.setObjectName("navList")
        nav_items = [
            ("nav.scan", "🖥"),
            ("nav.build", "⚙"),
            ("nav.validate", "✔"),
            ("usb.nav", "💾"),
            ("usbmap.nav", "🔌"),
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
        self._create_pages()
        root.addWidget(self.stack, 1)

    def _create_pages(self):
        """Создаёт страницы заново — используется при старте и смене языка."""
        self.page_scan = self._build_scan()
        self.page_build = self._build_build()
        self.page_validate = self._build_validate()
        self.page_usb = self._build_usb()
        self.page_ports = self._build_ports()
        self.page_analyze = self._build_analyze()
        self.page_settings = self._build_settings()
        self.page_about = self._build_about()
        for page in (self.page_scan, self.page_build, self.page_validate,
                     self.page_usb, self.page_ports, self.page_analyze,
                     self.page_settings, self.page_about):
            self.stack.addWidget(self._scroll_page(page))

    # ---- pages ----
    def _card(self, parent):
        w = QFrame(parent); w.setObjectName("card"); return w

    def _scroll_page(self, page: QWidget) -> QScrollArea:
        """Оборачивает страницу в прокрутку: контент не обрезается при малом окне."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        area.viewport().setAutoFillBackground(False)
        area.setWidget(page)
        return area

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
        self.opt_sip.setChecked(True)
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
        self.build_log = QPlainTextEdit(); self.build_log.setReadOnly(True); self.build_log.setMinimumHeight(160)
        v.addWidget(self.build_log, 1)

        # --- Почему так собрано (объяснение решений) ---
        rrow = QHBoxLayout()
        rrow.addWidget(_h2(page, tr.t("build.rationale")))
        rrow.addStretch()
        self.rationale_save_btn = QPushButton(tr.t("build.rationale_save"))
        self.rationale_save_btn.setObjectName("ghost")
        self.rationale_save_btn.setEnabled(False)
        self.rationale_save_btn.clicked.connect(self._save_rationale)
        rrow.addWidget(self.rationale_save_btn)
        v.addLayout(rrow)
        self.build_rationale = QPlainTextEdit(); self.build_rationale.setReadOnly(True)
        self.build_rationale.setMinimumHeight(140)
        self.build_rationale.setPlaceholderText(tr.t("build.rationale_empty"))
        v.addWidget(self.build_rationale, 1)
        return page

    def _build_validate(self):
        """Вкладка «Валидация»: детальный свод ocvalidate + состояние Wi-Fi/BT."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("validate.title")))
        sub = _muted(page, tr.t("validate.subtitle")); sub.setWordWrap(True)
        v.addWidget(sub)

        # --- источник для валидации ---
        src = self._card(page)
        sv = QVBoxLayout(src)
        last_row = QHBoxLayout()
        last_row.addWidget(_h2(page, tr.t("validate.last_build")))
        self.val_last_label = QLabel(tr.t("validate.none")); self.val_last_label.setObjectName("muted")
        self.val_last_label.setWordWrap(True)
        last_row.addWidget(self.val_last_label, 1)
        sv.addLayout(last_row)
        # ручной выбор config.plist
        pick_row = QHBoxLayout()
        self.val_config_path = None
        self.val_path_label = QLabel(tr.t("validate.none")); self.val_path_label.setObjectName("muted")
        self.val_path_label.setWordWrap(True)
        pick_row.addWidget(self.val_path_label, 1)
        pick_btn = QPushButton(tr.t("validate.browse")); pick_btn.setObjectName("ghost")
        pick_btn.clicked.connect(self._pick_config)
        pick_row.addWidget(pick_btn)
        sv.addLayout(pick_row)
        b = QPushButton(tr.t("validate.run"))
        b.clicked.connect(self._do_validate)
        audit_btn = QPushButton(tr.t("validate.audit_run"))
        audit_btn.setObjectName("ghost")
        audit_btn.clicked.connect(self._do_audit)
        btn_row = QHBoxLayout()
        btn_row.addWidget(audit_btn)
        btn_row.addStretch()
        btn_row.addWidget(b)
        sv.addLayout(btn_row)
        v.addWidget(src)

        # --- быстрые правки config.plist ---
        from ..builder.config_editor import SECURE_BOOT_MODELS
        quick = self._card(page)
        self.quick_card = quick
        qv = QVBoxLayout(quick)
        qv.addWidget(_h2(page, tr.t("validate.quick_title")))

        qargs = QHBoxLayout()
        qargs.addWidget(_val(page, tr.t("validate.quick_bootargs")))
        self.quick_bootargs = QLineEdit()
        self.quick_bootargs.setPlaceholderText("-v debug=0x100 keepsyms=1")
        qargs.addWidget(self.quick_bootargs, 1)
        qv.addLayout(qargs)

        qrow = QHBoxLayout()
        self.quick_sip = QCheckBox(tr.t("validate.quick_sip"))
        qrow.addWidget(self.quick_sip)
        qrow.addSpacing(16)
        qrow.addWidget(_val(page, tr.t("validate.quick_timeout")))
        self.quick_timeout = QSpinBox(); self.quick_timeout.setRange(0, 60)
        qrow.addWidget(self.quick_timeout)
        qrow.addSpacing(16)
        qrow.addWidget(_val(page, tr.t("validate.quick_secureboot")))
        self.quick_sbm = QComboBox(); self.quick_sbm.addItems(list(SECURE_BOOT_MODELS))
        qrow.addWidget(self.quick_sbm)
        qrow.addStretch()
        qv.addLayout(qrow)

        qsmb = QHBoxLayout()
        qsmb.addWidget(_val(page, tr.t("validate.quick_smbios")))
        self.quick_smbios = QLineEdit()
        self.quick_smbios.setPlaceholderText("MacPro7,1")
        qsmb.addWidget(self.quick_smbios, 1)
        qv.addLayout(qsmb)

        qsave = QPushButton(tr.t("validate.quick_save"))
        qsave.clicked.connect(self._save_quick)
        qv.addWidget(qsave, alignment=Qt.AlignRight)
        quick.setEnabled(False)
        v.addWidget(quick)

        # --- жёсткое предупреждение о железе (Wi-Fi/BT) ---
        self.val_hw_card = self._card(page)
        self.val_hw_card.setVisible(False)
        hv = QVBoxLayout(self.val_hw_card)
        self.val_hw_box = QVBoxLayout()
        hv.addLayout(self.val_hw_box)
        v.addWidget(self.val_hw_card)

        # --- беджи результата ---
        badge_row = QHBoxLayout()
        self.val_status = _h2(page, "—")
        badge_row.addWidget(self.val_status)
        badge_row.addStretch()
        v.addLayout(badge_row)
        self.val_meta = _muted(page, ""); self.val_meta.setWordWrap(True)
        v.addWidget(self.val_meta)

        self.val_progress = QProgressBar(); self.val_progress.setMaximum(0); self.val_progress.setVisible(False)
        v.addWidget(self.val_progress)

        # --- детальный свод ocvalidate по категориям ---
        splitter = QSplitter(Qt.Vertical)
        self.val_missing = QPlainTextEdit(); self.val_missing.setReadOnly(True)
        self.val_schema = QPlainTextEdit(); self.val_schema.setReadOnly(True)
        self.val_warn = QPlainTextEdit(); self.val_warn.setReadOnly(True)
        splitter.addWidget(self._labelled(self, tr.t("validate.missing_title"), self.val_missing))
        splitter.addWidget(self._labelled(self, tr.t("validate.schema_title"), self.val_schema))
        splitter.addWidget(self._labelled(self, tr.t("validate.warnings_title"), self.val_warn))
        self.val_audit = QPlainTextEdit(); self.val_audit.setReadOnly(True)
        splitter.addWidget(self._labelled(self, tr.t("validate.audit_title"), self.val_audit))
        splitter.setSizes([180, 140, 110, 150])
        v.addWidget(splitter, 1)
        return page

    def _labelled(self, parent, title, widget):
        w = QWidget(parent)
        ly = QVBoxLayout(w); ly.setContentsMargins(0, 0, 0, 0); ly.setSpacing(3)
        ly.addWidget(_h2(parent, title))
        ly.addWidget(widget, 1)
        return w

    def _pick_config(self):
        d, _ = QFileDialog.getOpenFileName(self, tr.t("validate.pick_config"), "",
                                           "config.plist (*.plist);;All files (*)")
        if d:
            self.val_config_path = Path(d)
            self.val_path_label.setText(d)
            self._load_quick()

    def _load_quick(self):
        """Загружает текущие значения config.plist в панель быстрых правок."""
        cfg_path = self._resolve_config()
        if not cfg_path or not cfg_path.exists():
            self.quick_card.setEnabled(False)
            return
        try:
            from ..builder import config_editor as ce
            cfg = ce.load_config(cfg_path)
        except Exception:
            self.quick_card.setEnabled(False)
            return
        self.quick_bootargs.setText(ce.get_boot_args(cfg))
        self.quick_sip.setChecked(ce.get_sip_enabled(cfg))
        self.quick_timeout.setValue(ce.get_timeout(cfg))
        self.quick_sbm.setCurrentText(ce.get_secure_boot_model(cfg))
        self.quick_smbios.setText(ce.get_smbios(cfg))
        self.quick_card.setEnabled(True)

    def _save_quick(self):
        """Сохраняет правки с резервной копией и предлагает перепроверку."""
        cfg_path = self._resolve_config()
        if not cfg_path or not cfg_path.exists():
            QMessageBox.information(self, tr.t("validate.title"),
                                    tr.t("validate.quick_need_config"))
            return
        try:
            from ..builder import config_editor as ce
            cfg = ce.load_config(cfg_path)
            ce.set_boot_args(cfg, self.quick_bootargs.text().strip())
            ce.set_sip(cfg, self.quick_sip.isChecked())
            ce.set_timeout(cfg, self.quick_timeout.value())
            ce.set_secure_boot_model(cfg, self.quick_sbm.currentText().strip())
            ce.set_smbios(cfg, self.quick_smbios.text().strip())
            backup = ce.save_config(cfg_path, cfg)
        except Exception as e:
            QMessageBox.critical(self, tr.t("validate.quick_title"), str(e))
            return
        self.val_config_path = cfg_path
        self.statusBar().showMessage(
            tr.t("validate.quick_saved").format(path=backup), 8000)
        if QMessageBox.question(self, tr.t("validate.quick_title"),
                                tr.t("validate.quick_revalidate")) == QMessageBox.Yes:
            self._do_validate()

    def _do_validate(self):
        """Запускает ocvalidate против config.plist."""
        if getattr(self, "_worker_val", None) and self._worker_val.isRunning():
            return
        cfg = self._resolve_config()
        if cfg is None:
            if self.profile is None:
                QMessageBox.information(self, tr.t("validate.title"), tr.t("validate.scan_first"))
            else:
                self.val_status.setText(tr.t("validate.no_result"))
            return
        self.val_config_path = cfg
        self._load_quick()
        self.val_progress.setVisible(True)
        self.val_status.setText("…")
        self._worker_val = ValidateWorker(cfg)
        self._worker_val.done.connect(self._validate_done)
        self._worker_val.failed.connect(self._validate_failed)
        self._worker_val.start()

    def _validate_done(self, res):
        self.val_progress.setVisible(False)
        if res["tool_missing"]:
            self.val_status.setText(tr.t("validate.no_ocvalidate"))
            return
        missing = res.get("missing_keys", [])
        schema = res.get("schema_errors", [])
        warns = res.get("warnings", [])
        self.val_missing.setPlainText("\n".join(missing) if missing else tr.t("validate.empty_results"))
        self.val_schema.setPlainText("\n".join(schema) if schema else tr.t("validate.empty_results"))
        self.val_warn.setPlainText("\n".join(warns) if warns else tr.t("validate.empty_results"))
        tv = res.get("tool_version", "")
        self.val_meta.setText(f"{tr.t('validate.tool_version')}: {tv or '—'}")
        if res.get("ok"):
            self.val_status.setText("✔ " + tr.t("validate.valid"))
            self.val_status.setStyleSheet("color:#a6e3a1;")
        elif not schema and missing:
            self.val_status.setText("⚠ " + tr.t("validate.badge_missing_only"))
            self.val_status.setStyleSheet("color:#f9e2af;")
        else:
            self.val_status.setText("✖ " + tr.t("validate.invalid"))
            self.val_status.setStyleSheet("color:#f38ba8;")
        self.statusBar().showMessage(f"ocvalidate: {len(schema)} err / {len(warns)} warn", 6000)

    def _validate_failed(self, err):
        self.val_progress.setVisible(False)
        self.val_status.setText(tr.t("validate.invalid"))
        QMessageBox.critical(self, tr.t("validate.title"), str(err))

    def _resolve_config(self) -> Path | None:
        """config.plist для проверки: ручной выбор или последняя сборка."""
        if self.val_config_path and self.val_config_path.is_file():
            return self.val_config_path
        if self.profile and getattr(self, "last_build_dir", None):
            cand = self.last_build_dir / "EFI" / "OC" / "config.plist"
            if cand.is_file():
                return cand
        return None

    def _do_audit(self):
        """Структурный аудит EFI: kexts, ACPI, драйверы, SIP, USB."""
        if getattr(self, "_worker_audit", None) and self._worker_audit.isRunning():
            return
        cfg = self._resolve_config()
        if cfg is None or not cfg.is_file():
            QMessageBox.information(self, tr.t("validate.audit_title"),
                                    tr.t("validate.audit_need_path"))
            return
        self.val_config_path = cfg
        efi_root = cfg.parent.parent if cfg.parent.name.upper() == "OC" else cfg.parent
        self.val_audit.setPlainText(tr.t("validate.audit_running"))
        self._worker_audit = AuditWorker(efi_root)
        self._worker_audit.done.connect(self._audit_done)
        self._worker_audit.failed.connect(self._audit_failed)
        self._worker_audit.start()

    def _audit_done(self, issues):
        err = sum(1 for i in issues if int(i.severity) == 2)
        warn = sum(1 for i in issues if int(i.severity) == 1)
        info = sum(1 for i in issues if int(i.severity) == 0)
        if not issues:
            self.val_audit.setPlainText(tr.t("validate.audit_no_findings"))
            self.statusBar().showMessage(tr.t("validate.audit_no_findings"), 6000)
            return
        marks = {2: "✖", 1: "⚠", 0: "ℹ"}
        lines = [tr.t("validate.audit_summary").format(e=err, w=warn, i=info), ""]
        for issue in sorted(issues, key=lambda x: -int(x.severity)):
            title = _issue_title(issue)
            fix = tr.issue(issue.code, "fix", issue.suggestion)
            lines.append(f"{marks.get(int(issue.severity), '•')} {title}")
            if issue.detail and (tr.current == "ru" or not _has_cyrillic(issue.detail)):
                lines.append(f"   {issue.detail}")
            if fix:
                lines.append(f"   → {fix}")
            lines.append("")
        self.val_audit.setPlainText("\n".join(lines).rstrip())
        self.statusBar().showMessage(
            f"EFI audit: {err} err / {warn} warn / {info} info", 6000)

    def _audit_failed(self, err):
        self.val_audit.setPlainText(str(err))

    def _refresh_validate_hw(self):
        """Показывает на вкладке валидации состояние Wi-Fi/Bluetooth железа."""
        if not self.profile:
            self.val_hw_card.setVisible(False)
            return
        p = self.profile
        # чистим
        while self.val_hw_box.count():
            it = self.val_hw_box.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        w = (p.net.wifi_chipset or "")
        if w == "mediatek":
            self.val_hw_card.setVisible(True)
            t = _h2(self.val_hw_card, "✖ " + tr.t("validate.wifi_mediatek_title"))
            t.setStyleSheet("color:#f38ba8;")
            self.val_hw_box.addWidget(t)
            d = _val(self.val_hw_card, tr.t("validate.wifi_mediatek_desc")); d.setWordWrap(True)
            self.val_hw_box.addWidget(d)
            b = _val(self.val_hw_card, "⚠ " + tr.t("validate.bt_unsupported"))
            b.setStyleSheet("color:#f9e2af;")
            self.val_hw_box.addWidget(b)
        elif w == "" :
            self.val_hw_card.setVisible(False)
        else:
            self.val_hw_card.setVisible(True)
            t = _h2(self.val_hw_card, "✔ " + tr.t("validate.wifi_ok"))
            t.setStyleSheet("color:#a6e3a1;")
            self.val_hw_box.addWidget(t)
            if w == "broadcom" and p.net.has_bt:
                self.val_hw_box.addWidget(_val(self.val_hw_card, tr.t("validate.bt_broadcom")))

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
        self.usb_refresh_btn = QPushButton(tr.t("usb.refresh")); self.usb_refresh_btn.setObjectName("ghost")
        self.usb_refresh_btn.clicked.connect(self._usb_refresh)
        row1.addWidget(self.usb_refresh_btn)
        row1.addStretch()
        uv.addLayout(row1)

        self.usb_combo = QComboBox()
        self.usb_combo.setMinimumHeight(40)
        self.usb_combo.currentIndexChanged.connect(self._usb_select)
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

        # --- 3.5. Карта USB-портов ---
        self.usb_make_map = QCheckBox(tr.t("usb.make_map"))
        self.usb_make_map.setChecked(True)
        v.addWidget(self.usb_make_map)
        map_desc = _muted(page, tr.t("usb.make_map_desc")); map_desc.setWordWrap(True)
        v.addWidget(map_desc)

        # --- 3.6. История сборок ---
        hist_card = self._card(page)
        hv = QVBoxLayout(hist_card)
        hrow = QHBoxLayout()
        hrow.addWidget(_h2(page, tr.t("history.title")))
        hrow.addStretch()
        hist_refresh = QPushButton(tr.t("history.refresh"))
        hist_refresh.setObjectName("ghost")
        hist_refresh.clicked.connect(self._history_refresh)
        hrow.addWidget(hist_refresh)
        hv.addLayout(hrow)
        self.history_list = QListWidget(); self.history_list.setMaximumHeight(110)
        hv.addWidget(self.history_list)
        hbtns = QHBoxLayout()
        self.history_open_btn = QPushButton(tr.t("history.open"))
        self.history_open_btn.setObjectName("ghost")
        self.history_open_btn.clicked.connect(self._history_open)
        self.history_restore_btn = QPushButton(tr.t("history.restore"))
        self.history_restore_btn.setObjectName("ghost")
        self.history_restore_btn.clicked.connect(self._history_restore)
        self.history_clear_btn = QPushButton(tr.t("history.clear"))
        self.history_clear_btn.setObjectName("ghost")
        self.history_clear_btn.clicked.connect(self._history_clear)
        self.history_save_btn = QPushButton(tr.t("history.save"))
        self.history_save_btn.setObjectName("ghost")
        self.history_save_btn.clicked.connect(self._history_save)
        hbtns.addWidget(self.history_open_btn)
        hbtns.addWidget(self.history_restore_btn)
        hbtns.addWidget(self.history_clear_btn)
        hbtns.addWidget(self.history_save_btn)
        hbtns.addStretch()
        hv.addLayout(hbtns)
        v.addWidget(hist_card)

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

        log_row = QHBoxLayout()
        log_row.addWidget(_h2(page, tr.t("usb.log")))
        log_row.addStretch()
        clear_btn = QPushButton(tr.t("usb.log_clear")); clear_btn.setObjectName("ghost")
        clear_btn.clicked.connect(self._usb_log_clear)
        save_btn = QPushButton(tr.t("usb.log_save")); save_btn.setObjectName("ghost")
        save_btn.clicked.connect(self._usb_log_save)
        log_row.addWidget(clear_btn)
        log_row.addWidget(save_btn)
        v.addLayout(log_row)
        self.usb_log = QPlainTextEdit(); self.usb_log.setReadOnly(True); self.usb_log.setMinimumHeight(180)
        v.addWidget(self.usb_log, 1)

        # сразу просканируем флешки и историю
        self._usb_refresh()
        self._history_refresh()
        return page

    def _usb_refresh(self):
        """Обновляет список USB-флешек в фоне (PowerShell не блокирует окно)."""
        if getattr(self, "usb_list_worker", None) and self.usb_list_worker.isRunning():
            return
        self.usb_refresh_btn.setEnabled(False)
        self.usb_empty.setText(tr.t("usb.refreshing"))
        self.usb_empty.setVisible(True)
        self.usb_list_worker = UsbListWorker(self)
        self.usb_list_worker.done.connect(self._usb_fill)
        self.usb_list_worker.failed.connect(self._usb_failed)
        self.usb_list_worker.finished.connect(
            lambda: self.usb_refresh_btn.setEnabled(True))
        self.usb_list_worker.start()

    def _usb_fill(self, devices: list):
        self.usb_devices = devices or []
        self.usb_combo.blockSignals(True)
        self.usb_combo.clear()
        if not self.usb_devices:
            self.usb_empty.setText(tr.t("usb.no_devices"))
            self.usb_empty.setVisible(True)
            self.usb_selected_desc.setText("")
            self.usb_combo.setEnabled(False)
            self.usb_combo.blockSignals(False)
            return
        self.usb_empty.setVisible(False)
        self.usb_combo.setEnabled(True)
        for d in self.usb_devices:
            if d.letter:
                label = f"{d.letter}   {d.model or d.label}   {d.size}"
            else:
                label = f"Disk {d.disk_number}   {d.model or d.label}   {d.size}   RAW"
            self.usb_combo.addItem(label, d.device)
        self.usb_combo.blockSignals(False)
        self._usb_select()
        self.statusBar().showMessage(
            f"{tr.t('usb.detected')}: {len(self.usb_devices)}", 3000)

    def _usb_log_clear(self):
        self.usb_log.clear()

    def _usb_log_save(self):
        text = self.usb_log.toPlainText()
        if not text.strip():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, tr.t("usb.log_save"), "HackicLab-usb-log.txt",
            "Text (*.txt);;All files (*)")
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, tr.t("usb.title"), str(e))
            return
        self.statusBar().showMessage(
            tr.t("usb.log_saved").format(path=path), 4000)

    def _usb_failed(self, err: str):
        self.usb_devices = []
        self.usb_combo.clear()
        self.usb_combo.setEnabled(False)
        self.usb_empty.setText(f"{tr.t('usb.no_devices')}: {err}")
        self.usb_empty.setVisible(True)
        self.usb_selected_desc.setText("")

    def _history_refresh(self):
        """Показывает последние сборки из истории."""
        from ..builder import history
        self.history_list.clear()
        try:
            entries = history.list_entries()
        except Exception:
            entries = []
        if not entries:
            it = QListWidgetItem(tr.t("history.empty"))
            it.setFlags(Qt.NoItemFlags)
            self.history_list.addItem(it)
            return
        for e in entries:
            ocv = "OK" if e.ocvalidate_ok else ("err" if e.ocvalidate_ok is False else "—")
            text = (f"{e.created_at} · {e.smbios or '—'} · "
                    f"{e.opencore or '—'} · ocvalidate: {ocv}")
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, e)
            if not e.exists:
                it.setForeground(QColor("#f38ba8"))
            self.history_list.addItem(it)

    def _history_selected(self):
        it = self.history_list.currentItem()
        return it.data(Qt.UserRole) if it else None

    def _history_open(self):
        entry = self._history_selected()
        if not entry:
            return
        path = Path(entry.efi_path)
        if not path.exists():
            QMessageBox.warning(self, tr.t("history.title"), tr.t("history.missing"))
            return
        import os
        try:
            os.startfile(str(path))
        except Exception as e:
            QMessageBox.critical(self, tr.t("history.title"), str(e))

    def _history_clear(self):
        if QMessageBox.question(
                self, tr.t("history.title"),
                tr.t("history.clear_ask")) != QMessageBox.Yes:
            return
        from ..builder import history
        n = history.clear_entries()
        self._history_refresh()
        self.statusBar().showMessage(
            tr.t("history.cleared").format(count=n), 4000)

    def _history_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr.t("history.save"), "HackicLab-history.json",
            "JSON (*.json);;All files (*)")
        if not path:
            return
        try:
            from ..builder import history
            out = history.export_entries(Path(path))
        except Exception as e:
            QMessageBox.critical(self, tr.t("history.title"), str(e))
            return
        self.statusBar().showMessage(
            tr.t("history.saved").format(path=out), 4000)

    def _history_restore(self):
        entry = self._history_selected()
        if not entry:
            return
        d = QFileDialog.getExistingDirectory(self, tr.t("history.pick_target"))
        if not d:
            return
        try:
            from ..builder import history
            out = history.restore(entry.id, Path(d))
        except Exception as e:
            QMessageBox.critical(self, tr.t("history.title"), str(e))
            return
        self.statusBar().showMessage(tr.t("history.restored").format(path=out), 8000)

    def _usb_select(self):
        idx = self.usb_combo.currentIndex()
        if idx < 0 or not getattr(self, "usb_devices", None):
            self.usb_selected_desc.setText("")
            return
        d = self.usb_devices[idx]
        bits = [f"Disk {d.disk_number}", d.model or d.label, d.size,
                d.letter if d.letter else "RAW"]
        self.usb_selected_desc.setText(
            f"{tr.t('usb.selected')}: " + " · ".join(x for x in bits if x))

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

    def _confirm_phrase(self, device: str, disk_number: str = "") -> str:
        """Фраза по тому, что видно в поле: WRITE F: или WRITE DISK 3."""
        dev = (device or "").strip().upper()
        if len(dev) == 2 and dev.endswith(":"):
            return f"WRITE {dev}"
        num = str(disk_number or "").strip()
        if not num and dev.startswith("DISK"):
            num = dev[4:]
        if not num and dev.startswith("RAWDISK"):
            num = dev[7:]
        if num:
            return f"WRITE DISK {num}"
        return f"WRITE {dev}"

    def _usb_confirm(self, device: str):
        """Экран/диалог подтверждения: ввод фразы WRITE <device>."""
        from PySide6.QtWidgets import QDialog, QLineEdit, QDialogButtonBox, QPushButton, QLabel
        if not self._ensure_admin():
            return
        mode = self.usb_mode.currentData() or "full"

        dlg = QDialog(self)
        dlg.setWindowTitle(tr.t("usb.confirm_title"))
        dlg.setMinimumWidth(460)
        dlgv = QVBoxLayout(dlg)

        dev = next((x for x in getattr(self, "usb_devices", []) if x.device == device), None)
        if dev:
            bits = [f"Disk {dev.disk_number}", dev.model or dev.label, dev.size]
            bits.append(dev.letter if dev.letter else "RAW")
            dev_txt = " · ".join(x for x in bits if x)
        else:
            dev_txt = device
        planned = ""
        if dev and dev.raw:
            try:
                from ..builder.usb_writer import _find_free_drive_letter
                planned = _find_free_drive_letter()
            except Exception:
                planned = ""

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

        phrase = self._confirm_phrase(device, getattr(dev, "disk_number", ""))
        dlgv.addWidget(_val(dlg, f"{tr.t('usb.confirm_phrase')}:  {phrase}"))
        if dev and dev.raw:
            note = _muted(dlg, tr.t("usb.raw_note").format(letter=planned or "—"))
            note.setWordWrap(True)
            dlgv.addWidget(note)
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
            if inp.text().strip().upper() == phrase.upper():
                dlg.accept()
            else:
                self._usb_mismatch.setText(f"{tr.t('usb.confirm_mismatch')} {phrase}")
                self._usb_mismatch.setStyleSheet("color:#f38ba8;")

        ok_btn.clicked.connect(_try_accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted:
            self._usb_run(device, mode, planned, self.usb_make_map.isChecked())

    def _ensure_admin(self) -> bool:
        """Проверяет права администратора без запуска второго окна."""
        try:
            from ..builder.usb_writer import is_admin
            if is_admin():
                return True
        except Exception:
            return True
        QMessageBox.warning(self, tr.t("usb.admin_title"),
                            tr.t("usb.admin_manual"))
        return False

    def _usb_run(self, device: str, mode: str, planned_letter: str = "",
                 make_usb_map: bool = True):
        """Запуск записи EFI на флешку в фоновом потоке."""
        if getattr(self, "_usb_worker", None) and self._usb_worker.isRunning():
            return
        self.usb_progress.setVisible(True)
        self.usb_log.clear()
        self.usb_log.appendPlainText(tr.t("usb.running"))
        source = Path(self.usb_source.text())
        from ..builder.usb_writer import write_efi_to_usb
        skip_format = (mode in ("formatted", "repair"))
        recovery_macos = ""
        if getattr(self, "usb_recovery_chk", None) and self.usb_recovery_chk.isChecked():
            recovery_macos = self.usb_recovery_ver.currentData() or ""
        self._usb_worker = USBWriteWorker(source, device, skip_format, recovery_macos,
                                          planned_letter, make_usb_map)
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

    def _build_ports(self):
        """Вкладка «Порты и диски»: карта USB-портов и карта дисков."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h1(page, tr.t("usbmap.title")))

        ports_card = self._card(page)
        pv = QVBoxLayout(ports_card)
        pv.addWidget(_h2(page, tr.t("usbmap.ports_title")))
        pdesc = _muted(page, tr.t("usbmap.ports_desc")); pdesc.setWordWrap(True)
        pv.addWidget(pdesc)
        prow = QHBoxLayout()
        self.ports_run_btn = QPushButton(tr.t("usbmap.run"))
        self.ports_run_btn.clicked.connect(self._do_usbmap)
        self.ports_save_btn = QPushButton(tr.t("usbmap.save"))
        self.ports_save_btn.setObjectName("ghost")
        self.ports_save_btn.setEnabled(False)
        self.ports_save_btn.clicked.connect(self._save_usbmap)
        prow.addWidget(self.ports_run_btn)
        prow.addWidget(self.ports_save_btn)
        prow.addStretch()
        pv.addLayout(prow)
        self.usbmap_status = _muted(page, tr.t("usbmap.dsdt_note"))
        self.usbmap_status.setWordWrap(True)
        pv.addWidget(self.usbmap_status)
        self.usbmap_log = QPlainTextEdit(); self.usbmap_log.setReadOnly(True)
        self.usbmap_log.setMaximumHeight(110)
        pv.addWidget(self.usbmap_log)
        v.addWidget(ports_card)

        disk_card = self._card(page)
        dv = QVBoxLayout(disk_card)
        dv.addWidget(_h2(page, tr.t("diskmap.title")))
        ddesc = _muted(page, tr.t("diskmap.desc")); ddesc.setWordWrap(True)
        dv.addWidget(ddesc)
        drow = QHBoxLayout()
        self.disk_scan_btn = QPushButton(tr.t("diskmap.scan"))
        self.disk_scan_btn.clicked.connect(self._do_diskmap)
        drow.addWidget(self.disk_scan_btn)
        drow.addStretch()
        dv.addLayout(drow)
        self.disk_warn = _muted(page, ""); self.disk_warn.setWordWrap(True)
        dv.addWidget(self.disk_warn)
        self.disk_tree = QPlainTextEdit(); self.disk_tree.setReadOnly(True)
        dv.addWidget(self.disk_tree, 1)
        v.addWidget(disk_card, 1)
        return page

    def _do_usbmap(self):
        if getattr(self, "ports_worker", None) and self.ports_worker.isRunning():
            return
        self.ports_run_btn.setEnabled(False)
        self.ports_save_btn.setEnabled(False)
        self.usbmap_status.setText(tr.t("usbmap.running"))
        self.usbmap_log.setPlainText("")
        self.ports_worker = UsbMapWorker(self)
        self.ports_worker.done.connect(self._usbmap_done)
        self.ports_worker.failed.connect(self._usbmap_failed)
        self.ports_worker.finished.connect(lambda: self.ports_run_btn.setEnabled(True))
        self.ports_worker.start()

    def _usbmap_done(self, plist, log_text: str):
        self._usbmap_plist = plist
        if log_text:
            self.usbmap_log.setPlainText(log_text)
        if not plist:
            self.usbmap_status.setText(tr.t("usbmap.none"))
            self.ports_save_btn.setEnabled(False)
            return
        from ..builder.usb_map import summarise
        s = summarise(plist)
        self.usbmap_status.setText(tr.t("usbmap.found").format(
            ports=s["ports"], controllers=s["controllers"]))
        self.ports_save_btn.setEnabled(True)

    def _usbmap_failed(self, err: str):
        self.usbmap_status.setText(str(err))

    def _save_usbmap(self):
        plist = getattr(self, "_usbmap_plist", None)
        if not plist:
            QMessageBox.information(self, tr.t("usbmap.ports_title"),
                                    tr.t("usbmap.need_map"))
            return
        d = QFileDialog.getExistingDirectory(self, tr.t("usbmap.save"))
        if not d:
            return
        try:
            from ..builder.usb_map import write_map_kext
            base = Path(d)
            if (base / "OC").is_dir():
                kexts = base / "OC" / "Kexts"
            elif base.name.lower() == "oc":
                kexts = base / "Kexts"
            else:
                kexts = base
            out = write_map_kext(plist, kexts)
        except Exception as e:
            QMessageBox.critical(self, tr.t("usbmap.ports_title"), str(e))
            return
        self.usbmap_status.setText(tr.t("usbmap.saved").format(path=out))

    def _do_diskmap(self):
        if getattr(self, "disk_worker", None) and self.disk_worker.isRunning():
            return
        self.disk_scan_btn.setEnabled(False)
        self.disk_warn.setText(tr.t("diskmap.running"))
        self.disk_worker = DiskMapWorker(self)
        self.disk_worker.done.connect(self._diskmap_done)
        self.disk_worker.failed.connect(self._diskmap_failed)
        self.disk_worker.finished.connect(lambda: self.disk_scan_btn.setEnabled(True))
        self.disk_worker.start()

    def _diskmap_done(self, tree: str, warnings: list):
        self.disk_tree.setPlainText(tree or tr.t("diskmap.empty"))
        if not warnings:
            self.disk_warn.setText(tr.t("diskmap.none_warn"))
            return
        lines = []
        for w in warnings:
            key = w.get("key", "")
            try:
                text = tr.t(key).format(**{k: val for k, val in w.items() if k != "key"})
            except Exception:
                text = key
            lines.append("⚠ " + text)
        self.disk_warn.setText("\n".join(lines))

    def _diskmap_failed(self, err: str):
        self.disk_warn.setText(str(err))

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

        # Проверка лога OpenCore
        gb_log = QGroupBox(tr.t("oclog.title"))
        lv = QVBoxLayout(gb_log)
        log_row = QHBoxLayout()
        self.oclog_btn = QPushButton(tr.t("oclog.check"))
        self.oclog_btn.setObjectName("ghost")
        self.oclog_btn.clicked.connect(self._do_oclog)
        self.oclog_enable_btn = QPushButton(tr.t("oclog.enable"))
        self.oclog_enable_btn.setObjectName("ghost")
        self.oclog_enable_btn.clicked.connect(self._enable_oclog)
        log_row.addWidget(self.oclog_btn)
        log_row.addWidget(self.oclog_enable_btn)
        log_row.addStretch()
        lv.addLayout(log_row)
        self.oclog_out = QPlainTextEdit(); self.oclog_out.setReadOnly(True)
        self.oclog_out.setMaximumHeight(130)
        lv.addWidget(self.oclog_out)
        v.addWidget(gb_log)

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

    def _do_oclog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr.t("oclog.check"), "",
            "OpenCore log (*.txt);;All files (*)")
        if not path:
            return
        self.oclog_btn.setEnabled(False)
        self.oclog_out.setPlainText(tr.t("oclog.running"))
        self.oclog_worker = OCLogWorker(Path(path))
        self.oclog_worker.done.connect(self._oclog_done)
        self.oclog_worker.failed.connect(self._oclog_failed)
        self.oclog_worker.finished.connect(lambda: self.oclog_btn.setEnabled(True))
        self.oclog_worker.start()

    def _oclog_done(self, findings: list):
        marks = {"error": "✖", "warn": "⚠", "info": "ℹ"}
        lines = []
        for f in findings:
            lines.append(f"{marks.get(f.severity, '•')} {tr.t(f.key)}")
            if f.detail:
                for raw in f.detail.splitlines()[:6]:
                    lines.append("    " + raw)
        self.oclog_out.setPlainText("\n".join(lines))

    def _oclog_failed(self, err: str):
        self.oclog_out.setPlainText(tr.t("oclog.read_error") + "\n" + str(err))

    def _enable_oclog(self):
        cfg = self._resolve_config()
        if cfg is None or not cfg.is_file():
            QMessageBox.information(self, tr.t("oclog.title"), tr.t("oclog.need_config"))
            return
        from ..analyzer.oc_log import enable_logging
        ok = enable_logging(cfg)
        QMessageBox.information(
            self, tr.t("oclog.title"),
            tr.t("oclog.enabled") if ok else tr.t("oclog.enable_failed"))

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
        sender = self.sender()
        code = ""
        if isinstance(sender, QComboBox):
            code = sender.currentData() or ""
        if not code:
            code = self.lang_combo.currentData() or "ru"
        if code == tr.current:
            return
        if self._workers_running():
            self._sync_lang_combos()
            QMessageBox.information(self, "HackicLab", tr.t("app.lang_busy"))
            return
        tr.set_lang(code)
        # пересобираем страницы после выхода из обработчика сигнала
        QTimer.singleShot(0, self._rebuild_pages)

    def _retranslate(self):
        """Совместимость: полная пересборка страниц под текущий язык."""
        self._rebuild_pages()

    _WORKER_ATTRS = ("_worker_scan", "_worker_build", "_usb_worker", "_worker_usb",
                     "_worker_val", "_worker_audit", "_worker_an")

    def _workers_running(self) -> bool:
        for name in self._WORKER_ATTRS:
            w = getattr(self, name, None)
            try:
                if w is not None and w.isRunning():
                    return True
            except Exception:
                continue
        return False

    def _sync_lang_combos(self):
        for combo in (getattr(self, "lang_combo", None),
                      getattr(self, "settings_lang", None)):
            if combo is None:
                continue
            i = combo.findData(tr.current)
            if i >= 0:
                combo.blockSignals(True)
                combo.setCurrentIndex(i)
                combo.blockSignals(False)

    def _rebuild_pages(self):
        """Пересоздаёт все страницы на текущем языке, сохраняя состояние."""
        if not hasattr(self, "stack"):
            return
        idx = self.stack.currentIndex()
        st = {
            "profile": getattr(self, "profile", None),
            "build_dest": self.build_dest.text(),
            "usb_source": self.usb_source.text(),
            "usb_mode": self.usb_mode.currentIndex(),
            "usb_rec": self.usb_recovery_chk.isChecked(),
            "usb_ver": self.usb_recovery_ver.currentData(),
            "build_log": self.build_log.toPlainText(),
            "rationale": self.build_rationale.toPlainText(),
            "last_build_dir": getattr(self, "last_build_dir", None),
            "val_config_path": getattr(self, "val_config_path", None),
            "val_status": self.val_status.text(),
            "opt_usb": self.opt_usb.isChecked(),
            "opt_sip": self.opt_sip.isChecked(),
            "macos": self.macos_combo.currentData(),
        }
        while self.stack.count():
            w = self.stack.widget(0)
            self.stack.removeWidget(w)
            w.deleteLater()
        self._create_pages()

        icons = ["🖥", "⚙", "✔", "💾", "🔌", "🔍", "⚙", "ℹ"]
        self.nav.blockSignals(True)
        for i, key in enumerate(self._nav_keys):
            item = self.nav.item(i)
            if item is not None:
                item.setText(f"{icons[i]}  {tr.t(key)}")
        self.nav.blockSignals(False)
        self._tagline_label.setText(tr.t("app.tagline"))

        self.last_build_dir = st["last_build_dir"]
        if st["val_config_path"]:
            self.val_config_path = st["val_config_path"]
        self.build_dest.setText(st["build_dest"])
        self.usb_source.setText(st["usb_source"])
        self.usb_mode.setCurrentIndex(st["usb_mode"])
        self.usb_recovery_chk.setChecked(st["usb_rec"])
        if st["usb_ver"]:
            i = self.usb_recovery_ver.findData(st["usb_ver"])
            if i >= 0:
                self.usb_recovery_ver.setCurrentIndex(i)
        self.opt_usb.setChecked(st["opt_usb"])
        self.opt_sip.setChecked(st["opt_sip"])
        if st["macos"]:
            i = self.macos_combo.findData(st["macos"])
            if i >= 0:
                self.macos_combo.setCurrentIndex(i)
        self.build_log.setPlainText(st["build_log"])
        self.build_rationale.setPlainText(st["rationale"])
        self.val_status.setText(st["val_status"])
        if st["last_build_dir"]:
            try:
                self.val_last_label.setText(str(st["last_build_dir"]))
            except Exception:
                pass
        if st["profile"]:
            self.profile = st["profile"]
            self._scan_done(st["profile"])
        if st["val_config_path"]:
            try:
                self.val_path_label.setText(str(st["val_config_path"]))
                self._load_quick()
            except Exception:
                pass
        try:
            self._on_macos_change()
        except Exception:
            pass

        self.stack.setCurrentIndex(max(0, min(idx, self.stack.count() - 1)))
        self.nav.setCurrentRow(self.stack.currentIndex())
        self._sync_lang_combos()
        self.statusBar().showMessage(tr.t("app.lang_changed"), 2500)

    # ---- scan ----
    def _do_scan(self):
        if getattr(self, "_worker_scan", None) and self._worker_scan.isRunning():
            return
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
        self._refresh_validate_hw()
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
        if getattr(self, "_worker_build", None) and self._worker_build.isRunning():
            return
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
        self._last_build_options = opts
        self._last_build_smbios = plan.smbios
        self._rationale_text = ""
        self.build_rationale.clear()
        self.rationale_save_btn.setEnabled(False)
        self.build_progress.setVisible(True)
        self.build_log.clear()
        self.build_log.appendPlainText(tr.t("build.building"))
        self._worker_build = BuildWorker(plan, target)
        self._worker_build.done.connect(self._build_done)
        self._worker_build.failed.connect(self._build_failed)
        self._worker_build.start()

    def _build_done(self, res):
        self.build_progress.setVisible(False)
        self.last_build_dir = Path(res.root) if res and res.root else None
        if self.last_build_dir:
            self.val_last_label.setText(str(self.last_build_dir))
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
        # --- объяснение решений ---
        self._render_rationale()
        # статус
        if res.stats and res.stats.get("ocvalidate_ok") is False:
            self.statusBar().showMessage(f"ocvalidate: {len(res.stats.get('ocvalidate_errors', []))} ошибок", 6000)
        else:
            self.statusBar().showMessage(tr.t("build.done"), 4000)

    def _render_rationale(self):
        """Блок «Почему так собрано» по реально сгенерированному config.plist."""
        text = ""
        if self.profile:
            try:
                from ..knowledge.rationale import explain, render
                decisions = explain(
                    self.profile,
                    getattr(self, "_last_build_options", None),
                    smbios=getattr(self, "_last_build_smbios", None),
                    lang=tr.current,
                )
                text = render(decisions)
            except Exception as e:
                text = f"rationale: {e}"
        self._rationale_text = text
        self.build_rationale.setPlainText(text)
        self.rationale_save_btn.setEnabled(bool(text.strip()))

    def _save_rationale(self):
        """Сохраняет объяснение рядом с собранным EFI (.md или .txt)."""
        text = getattr(self, "_rationale_text", "")
        if not text.strip():
            return
        default = ""
        if getattr(self, "last_build_dir", None):
            default = str(Path(self.last_build_dir) / "REASONING.md")
        path, _ = QFileDialog.getSaveFileName(
            self, tr.t("build.rationale_save"), default,
            "Markdown (*.md);;Text (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
            self.statusBar().showMessage(tr.t("build.rationale_saved"), 5000)
        except OSError as e:
            QMessageBox.critical(self, tr.t("build.rationale"), str(e))

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
        if getattr(self, "_worker_an", None) and self._worker_an.isRunning():
            return
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
            title = _issue_title(iss)
            it = QListWidgetItem(f"{icon} {title}")
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
        if not cur:
            self.issue_detail.clear()
            return
        iss = cur.data(Qt.UserRole)
        if not iss:
            self.issue_detail.clear()
            return
        title = _issue_title(iss)
        fix = tr.issue(iss.code, "fix", iss.suggestion)
        detail = iss.detail or ""
        if tr.current != "ru" and _has_cyrillic(detail):
            detail = ""
        parts = [title]
        if detail:
            parts.append(detail)
        if fix:
            parts.append("→ " + fix)
        self.issue_detail.setPlainText("\n\n".join(parts))


def run_app() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_QSS)
    win = MainWindow()
    win.show()
    return app.exec()