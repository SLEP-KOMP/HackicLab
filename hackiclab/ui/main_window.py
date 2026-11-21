"""Главное окно HackicLab (PySide6): тёмная тема, RU/EN, 4 вкладки."""

from __future__ import annotations

import html
import os
import re
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSize, Qt, QThread, QTimer, QTranslator, QUrl, Signal
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, uistate
from ..analyzer import Analyzer
from ..builder import (
    BuildOptions,
    BuildPlan,
    EFIBuilder,
)
from ..i18n import LANG_CODES, LANGS, detect_system_language, tr
from ..knowledge import manual_hw
from ..knowledge.configs import (
    STATUS_LIMITED,
    STATUS_NATIVE,
    STATUS_PATCHED,
    by_category,
    categories_of,
    search_configs,
    similar_configs,
)
from ..knowledge.preflight import bios_requirements
from ..knowledge.sources import (
    GROUP_COMMUNITY,
    GROUP_EFI,
    GROUP_GUIDES,
    GROUP_HARDWARE,
    SOURCES,
    note_of,
    sources_by_group,
    title_of,
)
from ..scanner import HardwareProfile, Scanner
from ..themes import BASE_THEMES, BUILTIN_THEMES, detect_system_scheme, get_qss, tone
from .apple_progress import AppleProgressBar
from .hwview import hardware_rows
from .theme_tiles import MonitorButton

#: Имя локального сервера для проверки «программа уже запущена».
SINGLE_INSTANCE = "hackiclab-single-instance"

#: Ширина центральной колонки контента — как у «Параметров» Windows.
COLUMN_MAX_WIDTH = 1280

#: Перевод стандартных кнопок Qt (Yes/No, OK) — живёт весь запуск.
_QT_TRANSLATOR: QTranslator | None = None


def install_qt_translator(lang: str) -> None:
    """Подключает qtbase_<lang>.qm, чтобы кнопки диалогов были на языке UI.

    Файлы переводов лежат в PySide6/translations; в собранном EXE путь
    подсказывает ``sys._MEIPASS``. Если файла нет, диалоги останутся на
    английском, поэтому приложение дополнительно задаёт подписи само.
    """
    global _QT_TRANSLATOR
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        return
    if _QT_TRANSLATOR is not None:
        app.removeTranslator(_QT_TRANSLATOR)
        _QT_TRANSLATOR = None
    from PySide6.QtCore import QLibraryInfo

    folders = [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        folders.append(Path(bundled) / "PySide6" / "translations")
    for folder in folders:
        qm = folder / f"qtbase_{lang}.qm"
        if not qm.exists():
            continue
        translator = QTranslator()
        if translator.load(str(qm)):
            app.installTranslator(translator)
            _QT_TRANSLATOR = translator
            return

#: Ссылка на сервер живёт весь запуск — иначе Qt соберёт его как мусор.
_SINGLE_SERVER: object | None = None


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
            p = Scanner().scan()
            self.done.emit(p)
        except Exception as e:
            self.failed.emit(str(e))


class BuildWorker(QThread):
    """Сборка EFI в фоне: возвращает результат и шлёт шаги прогресса."""
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(int, str)

    def __init__(self, plan: BuildPlan, target: Path):
        super().__init__()
        self.plan = plan
        self.target = target

    def run(self):
        try:
            res = EFIBuilder(self.plan, on_progress=self._progress).build(self.target)
            self.done.emit(res)
        except Exception as e:
            self.failed.emit(str(e))

    def _progress(self, percent: int, message: str):
        self.progress.emit(int(percent), str(message))


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
            from ..builder.usb_backend import write_efi_to_usb
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
            from ..builder.ocvalidate import find_ocvalidate, run_ocvalidate
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
                build_disk_tree,
                check_conflicts,
                scan_all_bootloaders,
                scan_disks,
            )
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
            from ..builder.usb_backend import get_usb_devices
            self.done.emit(get_usb_devices())
        except Exception as e:
            self.failed.emit(str(e))


class UpdateCheckWorker(QThread):
    """Проверка последнего релиза на GitHub в фоне."""
    found = Signal(object)
    up_to_date = Signal()
    failed = Signal(str)

    def run(self):
        try:
            from .. import updater
            info = updater.check_for_update()
            if info is None:
                self.up_to_date.emit()
            else:
                self.found.emit(info)
        except Exception as e:
            self.failed.emit(str(e))


class UpdateDownloadWorker(QThread):
    """Скачивание EXE обновления в фоне."""
    done = Signal(object)
    failed = Signal(object)

    def __init__(self, info):
        super().__init__()
        self.info = info

    def run(self):
        try:
            from .. import updater
            self.done.emit(updater.download_update(self.info))
        except Exception as e:
            self.failed.emit(e)


def _release_notes_text(text: str, limit: int = 4000) -> str:
    """Превращает markdown релиза в читаемый текст для панели «Обновления».

    В релизе описание хранится разметкой, и в QPlainTextEdit она выглядела
    как мусор: «### Установка», «> ⚠️», обратные кавычки и звёздочки.
    """
    result: list[str] = []
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue
        stripped = re.sub(r"^#{1,6}\s*", "", stripped)
        stripped = re.sub(r"^[-*+]\s+", "• ", stripped)
        stripped = re.sub(r"^\d+[.)]\s+", lambda m: f"{m.group(0).strip()} ", stripped)
        stripped = re.sub(r"^>\s*", "", stripped)
        stripped = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", stripped)
        stripped = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", stripped)
        stripped = re.sub(r"\*\*(.+?)\*\*", r"\1", stripped)
        stripped = re.sub(r"__(.+?)__", r"\1", stripped)
        stripped = re.sub(r"`([^`]+)`", r"\1", stripped)
        stripped = re.sub(r"^\s*[—–-]{3,}\s*$", "", stripped)
        result.append(stripped.strip())
    cleaned = "\n".join(result)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned[:limit]


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


def _efi_root_for(folder) -> Path:
    """Корень сборки: выбранная папка, а если выбрана сама папка EFI — её родитель."""
    root = Path(str(folder))
    if root.name.upper() == "EFI":
        root = root.parent
    return root


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
    #: Профиль, отложенный перед перезапуском с правами администратора: память
    #: прежнего процесса повышенному экземпляру недоступна.
    _PENDING_PROFILE = "profile-pending.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("HackicLab")
        self.setMinimumSize(880, 560)
        self._fit_to_screen()
        self.profile: HardwareProfile | None = None
        self._restore_pending_profile()
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

    def _stash_profile_for_admin(self) -> None:
        """Кладёт профиль на диск перед перезапуском с UAC."""
        if not self.profile:
            return
        try:
            import json

            from ..builder.cache_manager import profiles_dir
            path = profiles_dir() / self._PENDING_PROFILE
            path.write_text(json.dumps(self.profile.to_dict(), ensure_ascii=False),
                            encoding="utf-8")
        except Exception:
            pass

    def _restore_pending_profile(self) -> None:
        """Подхватывает профиль, отложенный перед перезапуском с UAC."""
        try:
            import json

            from ..builder.cache_manager import profiles_dir
            path = profiles_dir() / self._PENDING_PROFILE
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            path.unlink(missing_ok=True)
            self.profile = HardwareProfile.from_dict(data)
        except Exception:
            return

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
        self.nav.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav.currentRowChanged.connect(self._on_nav)
        self._nav_rows: list[int] = []
        self._page_rows: dict[int, int] = {}
        self._nav_keys: list[str] = []
        self._nav_icons: list[str] = []
        self._rebuild_nav()
        side_layout.addWidget(self.nav, 1)
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
        self.page_auto = self._build_wizard()
        self.page_build = self._build_build()
        self.page_validate = self._build_validate()
        self.page_usb = self._build_usb()
        self.page_sources = self._build_sources()
        self.page_donate = self._build_donate()
        self.page_settings = self._build_settings()
        self.page_about = self._build_about()
        for page in (self.page_auto, self.page_build,
                     self.page_validate, self.page_usb, self.page_sources,
                     self.page_donate, self.page_settings, self.page_about):
            page.setObjectName("pageRoot")
            self.stack.addWidget(self._scroll_page(page))
        self._go_page(0)

    # ---- pages ----
    def _card(self, parent):
        w = QFrame(parent); w.setObjectName("card"); return w

    def _page_header(self, page, layout, title_key: str, subtitle_key: str):
        """Заголовок страницы: крупный заголовок и короткое пояснение в одну фразу."""
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(_h1(page, tr.t(title_key)))
        sub = _muted(page, tr.t(subtitle_key))
        sub.setWordWrap(True)
        head.addWidget(sub)
        layout.addLayout(head)

    def _stat_tiles(self, page, layout, items):
        """Ряд плиток-метрик: крупное значение и короткая подпись."""
        row = QHBoxLayout()
        row.setSpacing(12)
        for value, caption in items:
            tile = self._card(page)
            tv = QVBoxLayout(tile)
            tv.setContentsMargins(16, 14, 16, 14)
            tv.setSpacing(2)
            big = QLabel(str(value), tile)
            big.setObjectName("tileValue")
            cap = QLabel(caption, tile)
            cap.setObjectName("muted")
            cap.setWordWrap(True)
            tv.addWidget(big)
            tv.addWidget(cap)
            row.addWidget(tile, 1)
        layout.addLayout(row)

    def _metric_tile(self, page, row, caption: str) -> QLabel:
        """Плитка с крупным значением, которое можно обновлять после проверки."""
        tile = self._card(page)
        tv = QVBoxLayout(tile)
        tv.setContentsMargins(16, 14, 16, 14)
        tv.setSpacing(2)
        value = QLabel("—", tile)
        value.setObjectName("tileValue")
        cap = QLabel(caption, tile)
        cap.setObjectName("muted")
        cap.setWordWrap(True)
        tv.addWidget(value)
        tv.addWidget(cap)
        row.addWidget(tile, 1)
        return value

    def _scroll_page(self, page: QWidget) -> QScrollArea:
        """Прокрутка и центральная колонка: поля слева и справа одинаковые.

        Как в «Параметрах» Windows: на широком мониторе контент не растягивается
        на всю ширину, а стоит колонкой ``COLUMN_MAX_WIDTH`` по центру.
        """
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        area.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        area.viewport().setAutoFillBackground(False)
        page.setMaximumWidth(COLUMN_MAX_WIDTH)
        # Высота страницы — по содержимому: иначе последний блок (например,
        # «Анализ ваших файлов EFI») уезжает за пределы области прокрутки.
        page.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        shell = QWidget()
        shell.setObjectName("pageShell")
        shell.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        row = QHBoxLayout(shell)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        row.addStretch(1)
        row.addWidget(page, 1000)
        row.addStretch(1)
        area.setWidget(shell)
        return area

    # ---- wizard: быстрая сборка ----
    def _wiz_state(self) -> dict:
        state = getattr(self, "_wiz", None)
        if state is None:
            state = {
                "step": 0, "profile": None, "macos": "", "kind": "usb",
                "device": "", "folder": "", "mode": "full", "wifi": "itlwm",
                "usb_toolbox": True, "dual_boot": "", "disable_dgpu": False,
                "gui_picker": False,
                "share_log": False,
            }
            self._wiz = state
        return state

    def _build_wizard(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(10)
        self._page_header(page, v, "wizard.title", "wizard.subtitle")
        self._stat_tiles(page, v, [
            (tr.t("tile.scan_engine_v"), tr.t("tile.scan_engine")),
            (tr.t("tile.scan_offline_v"), tr.t("tile.scan_offline")),
            (tr.t("tile.scan_safe_v"), tr.t("tile.scan_safe")),
        ])

        steps = QHBoxLayout()
        steps.setSpacing(6)
        self.wiz_chips = []
        step_keys = ("wizard.step.hw", "wizard.step.macos", "wizard.step.target",
                     "wizard.step.mode", "wizard.step.wifi", "wizard.step.options",
                     "wizard.step.summary")
        for index, key in enumerate(step_keys):
            chip = QLabel(f"{index + 1}. {tr.t(key)}", page)
            chip.setObjectName("stepChip")
            chip.setProperty("active", "false")
            self.wiz_chips.append(chip)
            steps.addWidget(chip)
        steps.addStretch()
        v.addLayout(steps)

        self.wiz_stack = QStackedWidget()
        self.wiz_stack.addWidget(self._wiz_step_hw(page))
        self.wiz_stack.addWidget(self._wiz_step_macos(page))
        self.wiz_stack.addWidget(self._wiz_step_target(page))
        self.wiz_stack.addWidget(self._wiz_step_mode(page))
        self.wiz_stack.addWidget(self._wiz_step_wifi(page))
        self.wiz_stack.addWidget(self._wiz_step_options(page))
        self.wiz_stack.addWidget(self._wiz_step_summary(page))
        v.addWidget(self.wiz_stack, 1)

        foot = QHBoxLayout()
        self.wiz_back = QPushButton(tr.t("wizard.back"))
        self.wiz_back.setObjectName("ghost")
        self.wiz_back.clicked.connect(self._wiz_back)
        foot.addWidget(self.wiz_back)
        self.wiz_hint = _muted(page, "")
        self.wiz_hint.setWordWrap(True)
        foot.addWidget(self.wiz_hint, 1)
        self.wiz_next = QPushButton(tr.t("wizard.next"))
        self.wiz_next.clicked.connect(self._wiz_next)
        foot.addWidget(self.wiz_next)
        v.addLayout(foot)

        self._wiz_show(int(self._wiz_state().get("step", 0)))
        return page

    def _wiz_option(self, parent, layout, key: str, value: str,
                    title: str, desc: str = "") -> QPushButton:
        """Карточка-переключатель для шага мастера."""
        text = title if not desc else f"{title}\n{desc}"
        btn = QPushButton(text, parent)
        btn.setObjectName("optionCard")
        btn.setCheckable(True)
        btn.setProperty("value", value)
        # Имя для скринридеров: без него карточка читается как «кнопка».
        btn.setAccessibleName(title)
        if desc:
            btn.setAccessibleDescription(desc)
            btn.setToolTip(desc)
        btn.clicked.connect(lambda: self._wiz_select(key, value, layout))
        layout.addWidget(btn)
        return btn

    def _wiz_select(self, key: str, value: str, layout):
        state = self._wiz_state()
        state[key] = value
        for i in range(layout.count()):
            widget = layout.itemAt(i).widget()
            if isinstance(widget, QPushButton) and widget.property("value") is not None:
                widget.setChecked(str(widget.property("value")) == value)
        self._wiz_update_hint()

    def _wiz_step_hw(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        card = self._card(page)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(16, 12, 16, 12)
        cv.setSpacing(6)
        self.wiz_hw_rows = QVBoxLayout()
        self.wiz_hw_rows.setSpacing(6)
        cv.addLayout(self.wiz_hw_rows)
        self.wiz_hw_empty = _muted(page, tr.t("wizard.hw.empty"))
        self.wiz_hw_empty.setWordWrap(True)
        cv.addWidget(self.wiz_hw_empty)
        lay.addWidget(card)
        row = QHBoxLayout()
        self.wiz_scan_btn = QPushButton(tr.t("wizard.hw.scan"))
        self.wiz_scan_btn.clicked.connect(self._wiz_scan)
        row.addWidget(self.wiz_scan_btn)
        self.wiz_scan_bar = QProgressBar()
        self.wiz_scan_bar.setMaximum(0)
        self.wiz_scan_bar.setVisible(False)
        row.addWidget(self.wiz_scan_bar, 1)
        lay.addLayout(row)

        # Скан живёт здесь: отдельной страницы «Сканирование» больше нет,
        # а эти имена используют общие обработчики _do_scan/_scan_done.
        self.hw_grid = self.wiz_hw_rows
        self.scan_progress = self.wiz_scan_bar
        self.scan_empty_card = self.wiz_hw_empty
        self.scan_save_btn = QPushButton(tr.t("scan.save"))
        self.scan_save_btn.setObjectName("ghost")
        self.scan_save_btn.setVisible(False)
        self.scan_save_btn.clicked.connect(self._save_profile)
        lay.addWidget(self.scan_save_btn)
        lay.addStretch()
        return widget

    def _wiz_step_macos(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.wiz_macos_hint = _muted(page, "")
        self.wiz_macos_hint.setWordWrap(True)
        lay.addWidget(self.wiz_macos_hint)
        self.wiz_macos_box = QVBoxLayout()
        self.wiz_macos_box.setSpacing(6)
        lay.addLayout(self.wiz_macos_box)
        lay.addStretch()
        return widget

    def _wiz_step_target(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        hint = _muted(page, tr.t("wizard.target.hint"))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.wiz_target_box = QVBoxLayout()
        self.wiz_target_box.setSpacing(6)
        lay.addLayout(self.wiz_target_box)
        row = QHBoxLayout()
        self.wiz_usb_refresh_btn = QPushButton(tr.t("usb.refresh"))
        self.wiz_usb_refresh_btn.setObjectName("ghost")
        self.wiz_usb_refresh_btn.clicked.connect(self._wiz_refresh_usb)
        row.addWidget(self.wiz_usb_refresh_btn)
        self.wiz_folder_btn = QPushButton(tr.t("wizard.target.folder"))
        self.wiz_folder_btn.setObjectName("ghost")
        self.wiz_folder_btn.clicked.connect(self._wiz_pick_folder)
        row.addWidget(self.wiz_folder_btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        return widget

    def _wiz_step_mode(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.wiz_mode_box = QVBoxLayout()
        self.wiz_mode_box.setSpacing(6)
        for value, title, desc in (
            ("full", "wizard.mode.full", "wizard.mode.full_desc"),
            ("formatted", "wizard.mode.formatted", "wizard.mode.formatted_desc"),
            ("repair", "wizard.mode.repair", "wizard.mode.repair_desc"),
        ):
            btn = self._wiz_option(page, self.wiz_mode_box, "mode", value,
                                   tr.t(title), tr.t(desc))
            btn.setChecked(value == "full")
        lay.addLayout(self.wiz_mode_box)
        lay.addStretch()
        return widget

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

    def _wiz_step_wifi(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.wiz_wifi_box = QVBoxLayout()
        self.wiz_wifi_box.setSpacing(6)
        lay.addLayout(self.wiz_wifi_box)
        lay.addStretch()
        self._wiz_build_wifi_options()
        return widget

    def _wiz_build_wifi_options(self) -> None:
        """Показывает только те режимы Wi-Fi, что подходят к найденному чипу.

        Intel — itlwm/AirportItlwm, Broadcom — без Intel-кекстов (нативный
        AirPort или AirportBrcmFixup). Раньше шаг всегда предлагал Intel.
        """
        layout = getattr(self, "wiz_wifi_box", None)
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        state = self._wiz_state()
        profile = state.get("profile")
        net = getattr(profile, "net", None) if profile is not None else None
        chipset = (getattr(net, "wifi_chipset", "") or "").lower()
        native = bool(getattr(net, "bt_native_apple", False))
        if profile is None or chipset == "intel":
            options = self._WIFI_INTEL
            if state.get("wifi") not in {value for value, _, _ in options}:
                state["wifi"] = "itlwm"
        elif chipset == "broadcom":
            options = self._WIFI_NATIVE if native else self._WIFI_BRCM
            state["wifi"] = "none"
        else:
            options = (("none", "wizard.wifi.none", "wizard.wifi.none_desc"),)
            state["wifi"] = "none"
        for value, title, desc in options:
            button = self._wiz_option(self, layout, "wifi", value,
                                      tr.t(title), tr.t(desc))
            button.setChecked(value == state.get("wifi"))

    def _wiz_step_options(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        lay.addWidget(_h2(page, tr.t("wizard.options.dual")))
        self.wiz_dual_box = QVBoxLayout()
        self.wiz_dual_box.setSpacing(6)
        for value, key in (
            ("", "wizard.options.dual.none"),
            ("windows", "wizard.options.dual.windows"),
            ("linux", "wizard.options.dual.linux"),
            ("both", "wizard.options.dual.both"),
        ):
            btn = self._wiz_option(page, self.wiz_dual_box, "dual_boot", value, tr.t(key))
            btn.setChecked(value == "")
        lay.addLayout(self.wiz_dual_box)

        self.wiz_dgpu_chk = QCheckBox(tr.t("wizard.options.dgpu"))
        self.wiz_dgpu_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("disable_dgpu", bool(on)))
        lay.addWidget(self.wiz_dgpu_chk)
        dgpu_note = _muted(page, tr.t("wizard.options.dgpu_desc"))
        dgpu_note.setWordWrap(True)
        lay.addWidget(dgpu_note)

        self.wiz_gui_chk = QCheckBox(tr.t("build.gui_picker"))
        self.wiz_gui_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("gui_picker", bool(on)))
        lay.addWidget(self.wiz_gui_chk)
        gui_note = _muted(page, tr.t("build.gui_picker_desc"))
        gui_note.setWordWrap(True)
        lay.addWidget(gui_note)

        self.wiz_share_chk = QCheckBox(tr.t("wizard.options.share"))
        self.wiz_share_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("share_log", bool(on)))
        lay.addWidget(self.wiz_share_chk)
        share_note = _muted(page, tr.t("wizard.options.share_desc"))
        share_note.setWordWrap(True)
        lay.addWidget(share_note)
        lay.addStretch()
        return widget

    def _wiz_fill_options(self):
        state = self._wiz_state()
        profile = state.get("profile")
        dgpu = getattr(profile, "dgpu", None) if profile is not None else None
        has_dgpu = bool(dgpu)
        self.wiz_dgpu_chk.setVisible(has_dgpu)
        if not has_dgpu:
            state["disable_dgpu"] = False
            self.wiz_dgpu_chk.setChecked(False)
        elif dgpu is not None and dgpu.vendor == "nvidia":
            # Nvidia в macOS не работает: предлагаем отключить сразу
            self.wiz_dgpu_chk.setChecked(True)
            state["disable_dgpu"] = True
        self.wiz_share_chk.setChecked(bool(state.get("share_log", False)))
        for index in range(self.wiz_dual_box.count()):
            item = self.wiz_dual_box.itemAt(index)
            widget = item.widget() if item is not None else None
            if isinstance(widget, QPushButton):
                widget.setChecked(str(widget.property("value") or "") ==
                                  str(state.get("dual_boot") or ""))

    def _wiz_step_summary(self, page) -> QWidget:
        widget = QWidget()
        lay = QVBoxLayout(widget)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        card = self._card(page)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(16, 12, 16, 12)
        cv.setSpacing(6)
        self.wiz_sum_rows = QVBoxLayout()
        self.wiz_sum_rows.setSpacing(4)
        cv.addLayout(self.wiz_sum_rows)
        lay.addWidget(card)
        self.wiz_badges = QHBoxLayout()
        self.wiz_badges.setSpacing(8)
        lay.addLayout(self.wiz_badges)
        self.wiz_build_btn = QPushButton(tr.t("wizard.build.start"))
        self.wiz_build_btn.clicked.connect(self._wiz_build)
        lay.addWidget(self.wiz_build_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.wiz_progress = AppleProgressBar()
        self.wiz_progress.setRange(0, 100)
        self.wiz_progress.setVisible(False)
        lay.addWidget(self.wiz_progress)
        self.wiz_log = QPlainTextEdit()
        self.wiz_log.setReadOnly(True)
        self.wiz_log.setPlaceholderText(tr.t("wizard.build.log_placeholder"))
        self.wiz_log.setMaximumHeight(210)
        lay.addWidget(self.wiz_log)
        self.wiz_result = _val(page, "")
        self.wiz_result.setWordWrap(True)
        lay.addWidget(self.wiz_result)
        row = QHBoxLayout()
        self.wiz_open_btn = QPushButton(tr.t("wizard.build.open"))
        self.wiz_open_btn.setObjectName("ghost")
        self.wiz_open_btn.setVisible(False)
        self.wiz_open_btn.clicked.connect(self._wiz_open_folder)
        row.addWidget(self.wiz_open_btn)
        self.wiz_usb_btn = QPushButton(tr.t("wizard.build.to_usb"))
        self.wiz_usb_btn.setObjectName("ghost")
        self.wiz_usb_btn.setVisible(False)
        self.wiz_usb_btn.clicked.connect(self._wiz_to_usb)
        row.addWidget(self.wiz_usb_btn)
        self.wiz_share_btn = QPushButton(tr.t("community.share"))
        self.wiz_share_btn.setObjectName("ghost")
        self.wiz_share_btn.setToolTip(tr.t("community.share_hint"))
        self.wiz_share_btn.setVisible(False)
        self.wiz_share_btn.clicked.connect(self._wiz_share)
        row.addWidget(self.wiz_share_btn)
        row.addStretch()
        lay.addLayout(row)
        lay.addStretch()
        return widget

    # ---- wizard: данные и переходы ----
    def _wiz_show(self, step: int):
        state = self._wiz_state()
        step = max(0, min(step, self.wiz_stack.count() - 1))
        state["step"] = step
        self.wiz_stack.setCurrentIndex(step)
        for index, chip in enumerate(self.wiz_chips):
            chip.setProperty("active", "true" if index == step else "false")
            chip.style().unpolish(chip)
            chip.style().polish(chip)
        self.wiz_back.setVisible(step > 0)
        self.wiz_next.setVisible(step < self.wiz_stack.count() - 1)
        if step == 1:
            self._wiz_fill_macos()
        elif step == 2:
            self._wiz_fill_target()
        elif step == 4:
            self._wiz_build_wifi_options()
        elif step == 5:
            self._wiz_fill_options()
        elif step == 6:
            self._wiz_fill_summary()
        self._wiz_update_hint()

    def _wiz_back(self):
        self._wiz_show(self._wiz_state()["step"] - 1)

    def _wiz_next(self):
        state = self._wiz_state()
        step = state["step"]
        if step == 0 and not state.get("profile"):
            self.wiz_hint.setText(tr.t("wizard.hw.need_scan"))
            return
        if step == 1 and not state.get("macos"):
            self.wiz_hint.setText(tr.t("wizard.macos.need"))
            return
        if step == 2 and not (state.get("device") or state.get("folder")):
            self.wiz_hint.setText(tr.t("wizard.target.need"))
            return
        self._wiz_show(step + 1)

    def _wiz_update_hint(self):
        label = getattr(self, "wiz_hint", None)
        if label is None:
            return
        state = self._wiz_state()
        step = state["step"]
        text = ""
        if step == 0:
            text = tr.t("wizard.hint.hw") if state.get("profile") else tr.t("wizard.hint.scan")
        elif step == 1:
            text = tr.t("wizard.hint.macos")
        elif step == 2:
            text = tr.t("wizard.hint.target")
        elif step == 3:
            text = tr.t("wizard.mode." + str(state.get("mode") or "full") + "_hint")
        elif step == 4:
            text = tr.t("wizard.wifi.hint")
        elif step == 5:
            text = tr.t("wizard.hint.options")
        label.setText(text)

    def _wiz_fill_hw(self):
        layout = getattr(self, "wiz_hw_rows", None)
        if layout is None:
            return
        self._clear_layout(layout)
        state = self._wiz_state()
        rows = hardware_rows(state.get("profile"), state.get("macos") or "")
        self.wiz_hw_empty.setVisible(not rows)
        for item in rows:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(10)
            name = QLabel(tr.t(item["key"]), row)
            name.setObjectName("kv")
            name.setMinimumWidth(130)
            rl.addWidget(name)
            value = _val(row, item["value"])
            value.setWordWrap(True)
            rl.addWidget(value, 1)
            note = item.get("note") or ""
            if note:
                hint = tr.t(note) if note.startswith("hw.") else note
                note_label = _muted(row, hint)
                note_label.setWordWrap(True)
                rl.addWidget(note_label)
            layout.addWidget(row)

    def _wiz_fill_macos(self):
        layout = getattr(self, "wiz_macos_box", None)
        if layout is None:
            return
        self._clear_layout(layout)
        state = self._wiz_state()
        profile = state.get("profile")
        if profile is None:
            self.wiz_macos_hint.setText(tr.t("wizard.macos.no_profile"))
            return
        from ..knowledge.oc_platforms import MACOS_VERSIONS, MAX_MACOS_BY_GEN
        ceiling = MAX_MACOS_BY_GEN.get(profile.cpu.generation, "Sonoma")
        order = ["High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
                 "Ventura", "Sonoma", "Sequoia", "Tahoe"]

        def rank(name: str) -> int:
            low = (name or "").lower()
            return next((i for i, item in enumerate(order) if item.lower() in low), -1)

        limit = rank(ceiling)
        self.wiz_macos_hint.setText(tr.t("wizard.macos.hint").format(max=ceiling))
        for entry in MACOS_VERSIONS:
            name = entry.get("name", "")
            if limit >= 0 and rank(name) > limit:
                continue
            desc = f"{entry.get('version', '')} · {entry.get('release', '')}"
            if rank(name) == limit:
                desc += " · " + tr.t("wizard.macos.max")
            btn = self._wiz_option(None, layout, "macos", name, name, desc)
            btn.setChecked(state.get("macos") == name)

    def _wiz_fill_target(self):
        layout = getattr(self, "wiz_target_box", None)
        if layout is None:
            return
        self._clear_layout(layout)
        state = self._wiz_state()
        devices = list(getattr(self, "usb_devices", []) or [])
        for device in devices:
            letter = getattr(device, "letter", "") or ""
            size = getattr(device, "size", "") or ""
            model = getattr(device, "model", "") or getattr(device, "label", "") or "USB"
            title = f"{letter or 'RAW'} · {model}"
            btn = self._wiz_option(None, layout, "device", str(getattr(device, "device", "")),
                                   title, size)
            btn.setChecked(state.get("device") == str(getattr(device, "device", "")))
        if state.get("folder"):
            btn = self._wiz_option(None, layout, "folder", state["folder"],
                                   tr.t("wizard.target.folder_ready"), state["folder"])
            btn.setChecked(True)
        if not devices and not state.get("folder"):
            empty = _muted(None, tr.t("wizard.target.empty"))
            empty.setWordWrap(True)
            layout.addWidget(empty)
        elif state.get("folder"):
            state["kind"] = "folder"

    _VENDOR_TONES = {
        "intel": "#2f6fb3",
        "amd": "#b3352f",
        "nvidia": "#3f8f4f",
        "audio": "#7a5cd6",
        "other": "#56606e",
    }

    def _badge(self, parent, text: str, tone: str) -> QLabel:
        badge = QLabel(text, parent)
        color = self._VENDOR_TONES.get(tone, self._VENDOR_TONES["other"])
        badge.setStyleSheet(
            f"background:{color}; color:#ffffff; border-radius:9px;"
            "padding:3px 10px; font-weight:600;")
        badge.setWordWrap(False)
        return badge

    def _badge_texts(self, profile) -> list[tuple[str, str]]:
        """Короткие подписи железа: CPU, GPU, аудиокодек."""
        items: list[tuple[str, str]] = []
        cpu = getattr(profile, "cpu", None)
        if cpu is not None and getattr(cpu, "name", ""):
            tone = "amd" if (getattr(cpu, "vendor", "") or "").lower() == "amd" else "intel"
            items.append((str(cpu.name), tone))
        for gpu in (getattr(profile, "dgpu", None), getattr(profile, "igpu", None)):
            name = getattr(gpu, "name", "") if gpu is not None else ""
            if not name:
                continue
            vendor = (getattr(gpu, "vendor", "") or "").lower()
            items.append((str(name), vendor if vendor in ("intel", "amd", "nvidia") else "other"))
        audio = getattr(profile, "audio", None)
        codec = getattr(audio, "codec", "") if audio is not None else ""
        if codec:
            items.append((str(codec), "audio"))
        return items

    def _fill_badges(self, layout, profile) -> None:
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        if profile is None:
            return
        for text, tone_name in self._badge_texts(profile):
            layout.addWidget(self._badge(self, text, tone_name))
        layout.addStretch()

    def _wiz_fill_summary(self):
        layout = getattr(self, "wiz_sum_rows", None)
        if layout is None:
            return
        self._clear_layout(layout)
        state = self._wiz_state()
        profile = state.get("profile")
        self._fill_badges(getattr(self, "wiz_badges", None), profile)
        if profile is None:
            return
        smbios = ""
        try:
            from ..knowledge.kexts import smbios_model_for
            smbios = smbios_model_for(profile, state.get("macos") or "")
        except Exception:
            smbios = ""
        rows = [
            ("wizard.sum.macos", state.get("macos") or "—"),
            ("wizard.sum.target", self._wiz_target_label()),
            ("wizard.sum.mode", tr.t("wizard.mode." + str(state.get("mode") or "full"))),
            ("wizard.sum.wifi", tr.t("wizard.wifi." + str(state.get("wifi") or "itlwm"))),
            ("hw.smbios", smbios or "—"),
        ]
        dual = str(state.get("dual_boot") or "")
        if dual:
            rows.append(("wizard.sum.dual", tr.t("wizard.options.dual." + dual)))
        if state.get("disable_dgpu"):
            rows.append(("wizard.sum.dgpu", tr.t("wizard.sum.dgpu_off")))
        if state.get("share_log"):
            rows.append(("wizard.sum.share", tr.t("wizard.sum.share_on")))
        for key, value in rows:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            name = QLabel(tr.t(key), row)
            name.setObjectName("kv")
            name.setMinimumWidth(130)
            rl.addWidget(name)
            text = _val(row, value)
            text.setWordWrap(True)
            rl.addWidget(text, 1)
            layout.addWidget(row)

    def _wiz_target_label(self) -> str:
        state = self._wiz_state()
        if state.get("kind") == "folder" and state.get("folder"):
            return str(state["folder"])
        for device in getattr(self, "usb_devices", []) or []:
            if str(getattr(device, "device", "")) == str(state.get("device")):
                letter = getattr(device, "letter", "") or "RAW"
                model = getattr(device, "model", "") or getattr(device, "label", "") or "USB"
                return f"{letter} · {model}"
        return "—"

    # ---- wizard: действия ----
    def _wiz_scan(self):
        if getattr(self, "_worker_scan", None) and self._worker_scan.isRunning():
            return
        self.wiz_scan_btn.setEnabled(False)
        self.wiz_scan_bar.setVisible(True)
        self._worker_scan = ScanWorker()
        self._worker_scan.done.connect(self._wiz_scan_done)
        self._worker_scan.failed.connect(self._wiz_scan_failed)
        self._worker_scan.start()

    def _wiz_scan_done(self, profile):
        self.wiz_scan_btn.setEnabled(True)
        self.wiz_scan_bar.setVisible(False)
        self._wiz_state()["profile"] = profile
        self._scan_done(profile)
        self._wiz_fill_hw()
        self._wiz_update_hint()

    def _wiz_scan_failed(self, err):
        self.wiz_scan_btn.setEnabled(True)
        self.wiz_scan_bar.setVisible(False)
        QMessageBox.critical(self, tr.t("wizard.title"), str(err))

    def _wiz_refresh_usb(self):
        if getattr(self, "usb_list_worker", None) and self.usb_list_worker.isRunning():
            return
        self.wiz_usb_refresh_btn.setEnabled(False)
        self.usb_list_worker = UsbListWorker(self)
        self.usb_list_worker.done.connect(self._wiz_usb_devices)
        self.usb_list_worker.failed.connect(
            lambda err: self.wiz_hint.setText(str(err)))
        self.usb_list_worker.finished.connect(
            lambda: self.wiz_usb_refresh_btn.setEnabled(True))
        self.usb_list_worker.start()

    def _wiz_usb_devices(self, devices: list):
        self.usb_devices = devices or []
        self._wiz_fill_target()

    def _wiz_pick_folder(self):
        # Повторный клик открывал второй диалог: путь вводился в одном окне,
        # а подтверждался пустой в другом, и выбор «терялся».
        if getattr(self, "_wiz_folder_busy", False):
            return
        self._wiz_folder_busy = True
        try:
            folder = QFileDialog.getExistingDirectory(
                self, tr.t("wizard.target.folder"))
        finally:
            self._wiz_folder_busy = False
        folder = (folder or "").strip()
        if not folder or not Path(folder).is_dir():
            return
        state = self._wiz_state()
        if state.get("folder") == folder and state.get("kind") == "folder":
            return
        state["folder"] = folder
        state["kind"] = "folder"
        state["device"] = ""
        self._wiz_fill_target()
        self._wiz_update_hint()

    def _wiz_target_dir(self) -> Path:
        state = self._wiz_state()
        if state.get("kind") == "folder" and state.get("folder"):
            return _efi_root_for(state["folder"])
        import time
        stamp = time.strftime("%Y%m%d-%H%M")
        return Path.home() / "Documents" / f"HackicLab-EFI-{stamp}"

    def _wiz_build(self):
        if getattr(self, "_worker_wiz", None) and self._worker_wiz.isRunning():
            return
        state = self._wiz_state()
        profile = state.get("profile")
        if profile is None:
            QMessageBox.information(self, tr.t("wizard.title"), tr.t("wizard.hw.need_scan"))
            return
        opts = BuildOptions(
            usb_toolbox=bool(state.get("usb_toolbox", True)),
            disable_sip=True,
            wifi_kext_mode=str(state.get("wifi") or "itlwm"),
            target_macos=str(state.get("macos") or ""),
            disable_dgpu=bool(state.get("disable_dgpu")),
            dual_boot=str(state.get("dual_boot") or ""),
            gui_picker=bool(state.get("gui_picker")),
        )
        target = self._wiz_target_dir()
        self._wiz_last_target = target
        plan = BuildPlan(profile=profile, options=opts)
        self._last_build_options = opts
        self._last_build_smbios = plan.smbios
        self.wiz_log.clear()
        self.wiz_progress.setVisible(True)
        self.wiz_progress.setValue(0)
        self.wiz_result.setText("")
        self.wiz_open_btn.setVisible(False)
        self.wiz_usb_btn.setVisible(False)
        self.wiz_build_btn.setEnabled(False)
        self._worker_wiz = BuildWorker(plan, target)
        self._worker_wiz.progress.connect(self._wiz_progress)
        self._worker_wiz.done.connect(self._wiz_done)
        self._worker_wiz.failed.connect(self._wiz_failed)
        self._worker_wiz.start()

    def _wiz_progress(self, percent: int, message: str):
        self.wiz_log.appendPlainText(f"[{percent:3d}%] {message}")
        self.wiz_log.verticalScrollBar().setValue(
            self.wiz_log.verticalScrollBar().maximum())
        self.wiz_progress.setValue(percent)

    def _wiz_done(self, res):
        self.wiz_build_btn.setEnabled(True)
        self.wiz_progress.setValue(100)
        ok = bool(getattr(res, "ok", False))
        root = getattr(res, "root", None) or getattr(self, "_wiz_last_target", None)
        if root:
            self.last_build_dir = Path(root)
            self._wiz_last_target = Path(root)
            try:
                self.val_last_label.setText(str(root))
            except Exception:
                pass
        self.wiz_result.setText(
            tr.t("wizard.build.ok") if ok else tr.t("wizard.build.fail"))
        self.wiz_result.setProperty("tone", "ok" if ok else "err")
        self.wiz_result.style().unpolish(self.wiz_result)
        self.wiz_result.style().polish(self.wiz_result)
        self.wiz_open_btn.setVisible(bool(root))
        if self._wiz_state().get("kind") == "usb":
            self.wiz_usb_btn.setVisible(bool(root))
        record = getattr(res, "stats", {}).get("community_record", "") if res else ""
        self._wiz_record = record
        self.wiz_share_btn.setVisible(bool(record))
        errors = list(getattr(res, "errors", []) or [])
        for error in errors[:10]:
            self.wiz_log.appendPlainText(f"[err] {error}")
        if root:
            self.wiz_log.appendPlainText(tr.t("wizard.build.saved").format(path=root))
            if self._wiz_state().get("share_log"):
                try:
                    from ..knowledge.build_report import build_report
                    text = build_report(self._wiz_state().get("profile"),
                                        getattr(self, "_last_build_options", None),
                                        res)
                    report_path = Path(root) / "HackicLab-build-report.log"
                    report_path.write_text(text, encoding="utf-8")
                    self.wiz_log.appendPlainText(
                        tr.t("wizard.build.report_saved").format(path=report_path))
                except Exception as exc:
                    self.wiz_log.appendPlainText(f"[warn] {exc}")
        for line in (getattr(res, "log", []) or [])[-40:]:
            self.wiz_log.appendPlainText(line)
        if self._wiz_state().get("share_log") and record:
            self._maybe_auto_share(record)

    def _maybe_auto_share(self, record: str) -> None:
        """После сборки открывает готовый отчёт на GitHub, если это включено.

        Ничего не отправляется само: GitHub показывает форму с текстом,
        отправить её может только пользователь кнопкой «Submit new issue».
        """
        try:
            from ..knowledge import community
            payload = community.load(Path(record))
            if community.open_issue(payload):
                self.statusBar().showMessage(tr.t("community.share_opened"), 6000)
        except Exception:
            pass

    def _wiz_failed(self, err):
        self.wiz_build_btn.setEnabled(True)
        self.wiz_progress.setVisible(False)
        self.wiz_result.setText(str(err))
        self.wiz_result.setProperty("tone", "err")
        self.wiz_result.style().unpolish(self.wiz_result)
        self.wiz_result.style().polish(self.wiz_result)

    def _wiz_open_folder(self):
        target = getattr(self, "_wiz_last_target", None)
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _wiz_share(self):
        """Отправка отчёта в общую базу: страница новой задачи GitHub."""
        record = getattr(self, "_wiz_record", "")
        if not record:
            return
        try:
            from ..knowledge import community
            payload = community.load(Path(record))
            self.wiz_log.appendPlainText(tr.t("community.share_hint"))
            if community.open_issue(payload):
                self.wiz_log.appendPlainText(tr.t("community.share_opened"))
        except Exception as exc:
            self.wiz_log.appendPlainText(f"[warn] {exc}")

    def _manual_share(self):
        """Отчёт ручной сборки: страница новой задачи GitHub."""
        record = getattr(self, "_manual_record", "")
        if not record:
            self.statusBar().showMessage(tr.t("community.nothing"), 5000)
            return
        try:
            from ..knowledge import community
            payload = community.load(Path(record))
            if community.open_issue(payload):
                self.statusBar().showMessage(tr.t("community.share_opened"), 6000)
        except Exception as exc:
            self.statusBar().showMessage(f"[warn] {exc}", 6000)

    def _sync_recovery_version(self, target: str) -> None:
        """Ставит в «Записи на USB» ту же macOS, под которую собрана EFI.

        Иначе под Sonoma легко записать установщик Tahoe: EFI не загрузит
        чужой recovery.
        """
        combo = getattr(self, "usb_recovery_ver", None)
        name = (target or "").strip()
        if combo is None or not name:
            return
        for i in range(combo.count()):
            data = str(combo.itemData(i) or "")
            if name.lower() in data.lower() or data.lower() in name.lower():
                combo.setCurrentIndex(i)
                return

    def _wiz_to_usb(self):
        state = self._wiz_state()
        target = getattr(self, "_wiz_last_target", None)
        if target:
            self.usb_source.setText(str(target))
        device = str(state.get("device") or "")
        index = self.usb_combo.findData(device) if device else -1
        if index >= 0:
            self.usb_combo.setCurrentIndex(index)
        self._sync_recovery_version(str(state.get("macos") or ""))
        self._go_page(self.page_usb)

    # ---- manual hardware setup ----
    def _make_searchable(self, combo) -> None:
        """Включает поиск по списку: набрал «Ryzen 5 3600» — выбрал строку.

        Обычный QComboBox прокручивается к текущему элементу, и мышью легко
        попасть в соседнее поколение. С completer выбор становится точным.
        """
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = combo.completer()
        if completer is None:
            return
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

    def _select_data(self, combo, value: str) -> bool:
        index = combo.findData(value)
        if index < 0:
            return False
        combo.setCurrentIndex(index)
        return True

    def _manual_from_scan(self) -> None:
        """Заполняет ручную форму железом из последнего сканирования."""
        profile = getattr(self, "profile", None)
        if profile is None:
            self.statusBar().showMessage(tr.t("manual.need_scan"), 6000)
            return
        cpu = getattr(profile, "cpu", None)
        vendor = (getattr(cpu, "vendor", "") or "").lower()
        generation = int(getattr(cpu, "generation", 0) or 0)
        laptop = profile.platform == "laptop"
        self.manual_laptop.setChecked(laptop)
        self.manual_cores.setValue(max(2, min(64, int(getattr(cpu, "core_count", 0) or getattr(cpu, "cores", 4) or 4))))
        if vendor == "amd":
            key = f"amd-zen{generation - 8 if generation > 8 else 1}d"
            if generation == 10:
                key = "amd-zen2d"
            elif generation == 11:
                key = "amd-zen3d"
            elif generation == 12:
                key = "amd-zen4d"
            key = key.replace("d", "m") if laptop else key
            if not self._select_data(self.manual_cpu, key):
                self._select_data(self.manual_cpu, "amd-zen2d")
        elif vendor == "intel":
            key = f"intel-{min(generation, 10)}{'m' if laptop else 'd'}"
            if generation >= 10 and not laptop:
                key = "intel-10d"
            if not self._select_data(self.manual_cpu, key):
                self._select_data(self.manual_cpu, "intel-8d")

        gpu = getattr(profile, "dgpu", None) or getattr(profile, "igpu", None)
        gpu_key = ""
        if gpu is not None:
            vendor_gpu = (getattr(gpu, "vendor", "") or "").lower()
            device = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "")
            if vendor_gpu in ("amd", "nvidia"):
                gpu_key = vendor_gpu
            elif device and self.manual_gpu.findData(device) >= 0:
                gpu_key = device
        if gpu_key:
            self._select_data(self.manual_gpu, gpu_key)

        audio = getattr(profile, "audio", None)
        if audio is not None and getattr(audio, "codec", ""):
            self.manual_audio.setText(str(audio.codec))

        eth = (getattr(getattr(profile, "net", None), "eth_chipset", "") or "").lower()
        if self.manual_eth.findData(eth) < 0:
            eth = ""
        self._select_data(self.manual_eth, eth)

        wifi = (getattr(getattr(profile, "net", None), "wifi_chipset", "") or "").lower()
        if self.manual_wifi.findData(wifi) < 0:
            wifi = ""
        self._select_data(self.manual_wifi, wifi)

        touch = str(getattr(profile, "touchpad_type", "") or "none")
        if self.manual_touchpad.findData(touch) < 0:
            touch = "ps2" if laptop else "none"
        self._select_data(self.manual_touchpad, touch)

        storage = getattr(profile, "storage", None)
        if storage is not None:
            self.manual_nvme.setChecked(bool(getattr(storage, "nvme_present", False)))
        self._manual_refresh()

    def _build_manual(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(10)
        v.addWidget(_h2(page, tr.t("manual.title")))
        from_scan = QPushButton(tr.t("manual.from_scan"))
        from_scan.clicked.connect(self._manual_from_scan)
        v.addWidget(from_scan, alignment=Qt.AlignmentFlag.AlignLeft)

        cols = QHBoxLayout()
        cols.setSpacing(18)
        form = QVBoxLayout()
        form.setSpacing(8)
        cols.addLayout(form, 3)

        self.manual_cpu = QComboBox()
        for option in manual_hw.CPU_OPTIONS:
            self.manual_cpu.addItem(option.title, option.key)
        default_index = self.manual_cpu.findData("intel-8d")
        if default_index >= 0:
            self.manual_cpu.setCurrentIndex(default_index)
        self._make_searchable(self.manual_cpu)
        self.manual_cpu.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.cpu", self.manual_cpu)

        row = QHBoxLayout()
        self.manual_laptop = QCheckBox(tr.t("manual.laptop"))
        self.manual_laptop.toggled.connect(self._manual_refresh)
        row.addWidget(self.manual_laptop)
        row.addSpacing(12)
        row.addWidget(QLabel(tr.t("manual.cores")))
        self.manual_cores = QSpinBox()
        self.manual_cores.setRange(2, 64)
        self.manual_cores.setValue(4)
        self.manual_cores.valueChanged.connect(self._manual_refresh)
        row.addWidget(self.manual_cores)
        row.addStretch()
        form.addLayout(row)

        self.manual_gpu = QComboBox()
        for option in manual_hw.GPU_OPTIONS:
            self.manual_gpu.addItem(option.title, option.key)
        self._make_searchable(self.manual_gpu)
        self.manual_gpu.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.gpu", self.manual_gpu)

        self.manual_audio = QLineEdit()
        self.manual_audio.setPlaceholderText(tr.t("manual.audio_ph"))
        self.manual_audio.textChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.audio", self.manual_audio)

        self.manual_eth = QComboBox()
        for value, title in manual_hw.ETHERNET_OPTIONS:
            self.manual_eth.addItem(title, value)
        self._make_searchable(self.manual_eth)
        self.manual_eth.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.eth", self.manual_eth)

        self.manual_wifi = QComboBox()
        for value, title in manual_hw.WIFI_OPTIONS:
            self.manual_wifi.addItem(title, value)
        self._make_searchable(self.manual_wifi)
        self.manual_wifi.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.wifi", self.manual_wifi)

        self.manual_touchpad = QComboBox()
        for value, title in manual_hw.TOUCHPAD_OPTIONS:
            self.manual_touchpad.addItem(title, value)
        self._make_searchable(self.manual_touchpad)
        self.manual_touchpad.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.touchpad", self.manual_touchpad)

        other = QHBoxLayout()
        self.manual_nvme = QCheckBox(tr.t("manual.nvme"))
        self.manual_nvme.setChecked(True)
        self.manual_nvme.toggled.connect(self._manual_refresh)
        other.addWidget(self.manual_nvme)
        self.manual_tb = QCheckBox(tr.t("manual.tb"))
        self.manual_tb.toggled.connect(self._manual_refresh)
        other.addWidget(self.manual_tb)
        other.addStretch()
        form.addLayout(other)

        self.manual_macos = QComboBox()
        self._make_searchable(self.manual_macos)
        self.manual_macos.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.macos", self.manual_macos)

        self.manual_result = _val(page, "")
        self.manual_result.setWordWrap(True)
        form.addWidget(self.manual_result)
        form.addStretch()

        review_card = self._card(page)
        rv = QVBoxLayout(review_card)
        rv.setContentsMargins(16, 12, 16, 12)
        rv.addWidget(_h2(page, tr.t("manual.review")))
        self.manual_review_box = QVBoxLayout()
        self.manual_review_box.setSpacing(6)
        rv.addLayout(self.manual_review_box)
        rv.addStretch()
        cols.addWidget(review_card, 2, Qt.AlignmentFlag.AlignTop)
        v.addLayout(cols, 1)

        self._manual_refresh()
        return page

    def _manual_field(self, page, layout, label_key: str, widget):
        row = QHBoxLayout()
        label = QLabel(tr.t(label_key), page)
        label.setObjectName("kv")
        label.setMinimumWidth(150)
        row.addWidget(label)
        row.addWidget(widget, 1)
        layout.addLayout(row)

    def _manual_selection(self):
        return manual_hw.ManualSelection(
            cpu=str(self.manual_cpu.currentData() or "intel-8d"),
            laptop=self.manual_laptop.isChecked(),
            cores=self.manual_cores.value(),
            gpu=str(self.manual_gpu.currentData() or ""),
            audio_codec=self.manual_audio.text().strip(),
            ethernet=str(self.manual_eth.currentData() or ""),
            wifi=str(self.manual_wifi.currentData() or ""),
            nvme=self.manual_nvme.isChecked(),
            thunderbolt=self.manual_tb.isChecked(),
            touchpad=str(self.manual_touchpad.currentData() or "ps2"),
        )

    def _manual_refresh(self, *_args):
        if not hasattr(self, "manual_review_box"):
            return
        profile = manual_hw.build_profile(self._manual_selection())
        self.manual_profile = profile
        self.manual_touchpad.setEnabled(profile.platform == "laptop")
        self._manual_fill_macos(profile)
        target = str(self.manual_macos.currentData() or "")
        self._manual_render(profile, manual_hw.review(profile, target, "itlwm"))

    def _manual_fill_macos(self, profile):
        from ..knowledge.oc_platforms import MACOS_VERSIONS, MAX_MACOS_BY_GEN
        ceiling = MAX_MACOS_BY_GEN.get(profile.cpu.generation, "Sonoma")
        order = ["High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
                 "Ventura", "Sonoma", "Sequoia", "Tahoe"]

        def rank(name: str) -> int:
            low = (name or "").lower()
            return next((i for i, item in enumerate(order) if item.lower() in low), -1)

        current = str(self.manual_macos.currentData() or "")
        limit = rank(ceiling)
        self.manual_macos.blockSignals(True)
        self.manual_macos.clear()
        for entry in MACOS_VERSIONS:
            name = str(entry.get("name") or "")
            if limit >= 0 and rank(name) > limit:
                continue
            self.manual_macos.addItem(name, name)
        index = self.manual_macos.findData(current)
        if index < 0 and self.manual_macos.count():
            index = 0
        if index >= 0:
            self.manual_macos.setCurrentIndex(index)
        self.manual_macos.blockSignals(False)

    def _manual_render(self, profile, data):
        self._clear_layout(self.manual_review_box)
        platform_key = f"hw.platform.{data['platform']}"
        platform_text = tr.t(platform_key) if data["platform"] in (
            "laptop", "desktop", "mini", "workstation") else data["platform"]
        rows = [
            ("manual.r.gen", f"{data['generation']} · {data['codename']}"),
            ("manual.r.platform", platform_text),
            ("manual.r.max", data["max_macos"]),
            ("manual.r.smbios", data["smbios"] or "—"),
            ("manual.r.kexts", f"{data['kext_count']}: " + ", ".join(data["kexts"][:8])
             + ("…" if data["kext_count"] > 8 else "")),
            ("manual.r.ssdts", ", ".join(data["ssdts"]) or "—"),
        ]
        for key, value in rows:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            label = QLabel(tr.t(key), row)
            label.setObjectName("kv")
            label.setMinimumWidth(110)
            rl.addWidget(label)
            text = _val(row, value)
            text.setWordWrap(True)
            rl.addWidget(text, 1)
            self.manual_review_box.addWidget(row)
        for issue in data["issues"]:
            prefix = {"ok": "✔", "warn": "⚠", "err": "✖"}.get(issue["level"], "•")
            label = QLabel(f"{prefix} {issue['text']}", self.manual_review_box.parentWidget())
            label.setWordWrap(True)
            label.setObjectName(issue["level"] if issue["level"] in ("ok", "warn", "err") else "muted")
            self.manual_review_box.addWidget(label)

    def _manual_open(self):
        target = getattr(self, "_manual_last_target", None)
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def _build_build(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "build.title", "build.subtitle")
        self._stat_tiles(page, v, [
            (tr.t("tile.build_kexts_v"), tr.t("tile.build_kexts")),
            (tr.t("tile.build_oc_v"), tr.t("tile.build_oc")),
            (tr.t("tile.build_check_v"), tr.t("tile.build_check")),
        ])

        # Шаг 1: железо вручную. Форма переехала сюда со страницы сканирования.
        v.addWidget(_h2(page, tr.t("manual.step_hw")))
        v.addWidget(self._build_manual())

        # Шаг 2: параметры сборки и журнал.
        v.addWidget(_h2(page, tr.t("manual.step_build")))
        bios = self._card(page)
        bv = QVBoxLayout(bios)
        bv.addWidget(_h2(page, tr.t("bios.title")))
        bios_hint = _muted(page, tr.t("bios.subtitle"))
        bios_hint.setWordWrap(True)
        bv.addWidget(bios_hint)
        profile = getattr(self, "profile", None)
        from ..scanner.models import HardwareProfile as _HP
        report = bios_requirements(profile or _HP())
        for key in report.requirements:
            item = QLabel("✓  " + tr.t(key), bios)
            item.setObjectName("muted")
            item.setWordWrap(True)
            bv.addWidget(item)
        self.bios_box = bv
        v.addWidget(bios)

        # Слева настройки и журнал, справа карточка с яблоком и прогрессом —
        # как фото автора в «Поддержке».
        cols = QHBoxLayout(); cols.setSpacing(18)
        main = QVBoxLayout(); main.setSpacing(12)
        cols.addLayout(main, 3)
        cols.addWidget(self._apple_card(page), 1, Qt.AlignmentFlag.AlignTop)
        v.addLayout(cols, 1)

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
        self.opt_gui = QCheckBox(tr.t("build.gui_picker"))
        gui_desc = _muted(page, tr.t("build.gui_picker_desc")); gui_desc.setWordWrap(True)
        opts.addWidget(self.opt_gui)
        opts.addWidget(gui_desc)
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
        main.addWidget(gb)

        # macOS version selection
        mb = QGroupBox(tr.t("build.macos"))
        mv = QVBoxLayout(mb)
        mrow = QHBoxLayout()
        self.macos_combo = QComboBox()
        from ..knowledge.oc_platforms import MACOS_VERSIONS
        self.macos_combo.addItem(tr.t("build.macos_auto"), "")
        for mver in MACOS_VERSIONS:
            self.macos_combo.addItem(mver["name"], mver["name"])
        # пометим подсказкой о возможной несовместимости (tooltip)
        mrow.addWidget(self.macos_combo, 1)
        mv.addLayout(mrow)
        mac_desc = _muted(page, tr.t("build.macos_desc")); mac_desc.setWordWrap(True)
        mv.addWidget(mac_desc)
        self.macos_incompat = _muted(page, ""); self.macos_incompat.setWordWrap(True)
        self.macos_incompat.setObjectName("warn")
        self.macos_incompat.setVisible(False)
        mv.addWidget(self.macos_incompat)
        self.macos_combo.currentIndexChanged.connect(self._on_macos_change)
        main.addWidget(mb)

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
        note.setObjectName("ok")
        dv.addWidget(note)
        main.addWidget(dest_card)

        build_row = QHBoxLayout()
        build_btn = QPushButton(tr.t("build.button"))
        build_btn.clicked.connect(self._do_build)
        build_row.addWidget(build_btn)
        self.manual_open_btn = QPushButton(tr.t("manual.open"))
        self.manual_open_btn.setObjectName("ghost")
        self.manual_open_btn.setVisible(False)
        self.manual_open_btn.clicked.connect(self._manual_open)
        build_row.addWidget(self.manual_open_btn)
        build_row.addStretch()
        main.addLayout(build_row)

        self.manual_result = _val(page, "")
        self.manual_result.setWordWrap(True)
        main.addWidget(self.manual_result)

        self.build_progress = QProgressBar(); self.build_progress.setMaximum(0); self.build_progress.setVisible(False)
        main.addWidget(self.build_progress)

        lbl = _h2(page, tr.t("build.log"))
        main.addWidget(lbl)
        self.build_log = QPlainTextEdit(); self.build_log.setReadOnly(True); self.build_log.setMinimumHeight(160)
        self.build_log.setPlaceholderText(tr.t("common.log_placeholder"))
        main.addWidget(self.build_log, 1)

        # --- Почему так собрано (объяснение решений) ---
        rrow = QHBoxLayout()
        rrow.addWidget(_h2(page, tr.t("build.rationale")))
        rrow.addStretch()
        self.rationale_save_btn = QPushButton(tr.t("build.rationale_save"))
        self.rationale_save_btn.setObjectName("ghost")
        self.rationale_save_btn.setEnabled(False)
        self.rationale_save_btn.clicked.connect(self._save_rationale)
        rrow.addWidget(self.rationale_save_btn)
        main.addLayout(rrow)
        self.build_rationale = QPlainTextEdit(); self.build_rationale.setReadOnly(True)
        self.build_rationale.setMinimumHeight(140)
        self.build_rationale.setPlaceholderText(tr.t("build.rationale_empty"))
        main.addWidget(self.build_rationale, 1)

        # --- помощь проекту: отчёт о сборке ---
        share = self._card(page)
        sv = QVBoxLayout(share)
        sv.setContentsMargins(16, 12, 16, 12)
        sv.addWidget(_h2(page, tr.t("community.title")))
        share_hint = _muted(page, tr.t("community.manual_hint"))
        share_hint.setWordWrap(True)
        sv.addWidget(share_hint)
        self.manual_share_chk = QCheckBox(tr.t("community.manual_auto"))
        self.manual_share_chk.setChecked(bool(uistate.get("share_reports", False)))
        self.manual_share_chk.toggled.connect(
            lambda on: uistate.save(share_reports=bool(on)))
        sv.addWidget(self.manual_share_chk)
        self.manual_share_btn = QPushButton(tr.t("community.share"))
        self.manual_share_btn.setObjectName("ghost")
        self.manual_share_btn.setToolTip(tr.t("community.share_hint"))
        self.manual_share_btn.clicked.connect(self._manual_share)
        sv.addWidget(self.manual_share_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        v.addWidget(share)
        return page

    def _build_validate(self):
        """Вкладка «Валидация»: детальный свод ocvalidate + состояние Wi-Fi/BT."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "validate.title", "validate.subtitle")

        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.val_tile_state = self._metric_tile(page, tiles, tr.t("validate.tile_state"))
        self.val_tile_err = self._metric_tile(page, tiles, tr.t("validate.tile_errors"))
        self.val_tile_warn = self._metric_tile(page, tiles, tr.t("validate.tile_warnings"))
        v.addLayout(tiles)

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
        self.val_config_path: Path | None = None
        self.val_path_label = QLabel(tr.t("validate.none")); self.val_path_label.setObjectName("muted")
        self.val_path_label.setWordWrap(True)
        self.val_path_label.setVisible(False)
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
        qv.addWidget(qsave, alignment=Qt.AlignmentFlag.AlignRight)
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
        self.val_status = QLabel(tr.t("validate.not_checked"))
        self.val_status.setObjectName("muted")
        badge_row.addWidget(self.val_status)
        badge_row.addStretch()
        v.addLayout(badge_row)
        self.val_meta = _muted(page, ""); self.val_meta.setWordWrap(True)
        v.addWidget(self.val_meta)

        self.val_progress = QProgressBar(); self.val_progress.setMaximum(0); self.val_progress.setVisible(False)
        v.addWidget(self.val_progress)

        # --- детали проверки: вкладки, а не четыре пустые панели ---
        details = self._card(page)
        dv = QVBoxLayout(details)
        dv.addWidget(_h2(page, tr.t("validate.details_title")))
        self.val_tabs = QTabWidget()
        self.val_missing = QPlainTextEdit(); self.val_missing.setReadOnly(True)
        self.val_schema = QPlainTextEdit(); self.val_schema.setReadOnly(True)
        self.val_warn = QPlainTextEdit(); self.val_warn.setReadOnly(True)
        self.val_audit = QPlainTextEdit(); self.val_audit.setReadOnly(True)
        for wdg, hint in (
            (self.val_missing, "validate.empty_results"),
            (self.val_schema, "validate.empty_results"),
            (self.val_warn, "validate.empty_results"),
            (self.val_audit, "validate.audit_hint"),
        ):
            wdg.setPlaceholderText(tr.t(hint))
            wdg.setMinimumHeight(220)
            wdg.textChanged.connect(self._refresh_val_tabs)
        self.val_tabs.addTab(self.val_missing, tr.t("validate.missing_title"))
        self.val_tabs.addTab(self.val_schema, tr.t("validate.schema_title"))
        self.val_tabs.addTab(self.val_warn, tr.t("validate.warnings_title"))
        self.val_tabs.addTab(self.val_audit, tr.t("validate.audit_title"))
        dv.addWidget(self.val_tabs)
        v.addWidget(details)
        v.addWidget(self._build_analyze())
        v.addStretch(1)
        return page

    def _refresh_val_tabs(self):
        """Показывает число замечаний прямо в заголовках вкладок."""
        tabs = getattr(self, "val_tabs", None)
        if tabs is None:
            return
        skip = {tr.t("validate.empty_results"), tr.t("validate.audit_no_findings"), ""}
        for idx, wdg, key in (
            (0, self.val_missing, "validate.missing_title"),
            (1, self.val_schema, "validate.schema_title"),
            (2, self.val_warn, "validate.warnings_title"),
            (3, self.val_audit, "validate.audit_title"),
        ):
            lines = [ln for ln in wdg.toPlainText().splitlines() if ln.strip() and ln.strip() not in skip]
            if key == "validate.audit_title":
                # В аудите считаем только строки-замечания, а не пояснения к ним.
                lines = [ln for ln in lines if ln.lstrip().startswith(("✖", "⚠", "ℹ"))]
            tabs.setTabText(idx, tr.t(key) + (f" ({len(lines)})" if lines else ""))

    def _labelled(self, parent, title, widget):
        w = QWidget(parent)
        ly = QVBoxLayout(w); ly.setContentsMargins(0, 0, 0, 0); ly.setSpacing(3)
        ly.addWidget(_h2(parent, title))
        ly.addWidget(widget, 1)
        return w

    def _pick_config(self):
        d, _ = QFileDialog.getOpenFileName(self, tr.t("validate.pick_config"), "",
                                           f"{tr.t('file.plist')};;{tr.t('file.all_files')}")
        if d:
            self.val_config_path = Path(d)
            self.val_path_label.setText(d)
            self.val_path_label.setVisible(True)
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
        if self._ask_yes_no(tr.t("validate.quick_title"),
                             tr.t("validate.quick_revalidate")):
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
            self.val_status.setObjectName("ok")
            self._set_val_tiles("ok", len(schema), len(warns))
        elif not schema and missing:
            self.val_status.setText("⚠ " + tr.t("validate.badge_missing_only"))
            self.val_status.setObjectName("warn")
        else:
            self.val_status.setText("✖ " + tr.t("validate.invalid"))
            self.val_status.setObjectName("err")
            self._set_val_tiles("err", len(schema), len(warns))
        self.statusBar().showMessage(f"ocvalidate: {len(schema)} err / {len(warns)} warn", 6000)

    def _set_val_tiles(self, tone: str, errors: int, warnings: int) -> None:
        """Крупная сводка валидации: статус, ошибки, предупреждения."""
        state_labels = {
            "ok": tr.t("validate.tile_ok"),
            "warn": tr.t("validate.tile_warn"),
            "err": tr.t("validate.tile_err"),
        }
        for tile, label in (
            (getattr(self, "val_tile_state", None), state_labels.get(tone, "—")),
            (getattr(self, "val_tile_err", None), str(errors)),
            (getattr(self, "val_tile_warn", None), str(warnings)),
        ):
            if tile is None:
                continue
            tile.setText(label)
            tile.setProperty("tone", tone)

    def _validate_failed(self, err):
        self.val_progress.setVisible(False)
        self.val_status.setText(tr.t("validate.invalid"))
        QMessageBox.critical(self, tr.t("validate.title"), str(err))

    def _resolve_config(self) -> Path | None:
        """config.plist для проверки: ручной выбор или последняя сборка."""
        if self.val_config_path:
            cfg = Path(str(self.val_config_path))
            if cfg.is_file():
                return cfg
        build_dir = getattr(self, "last_build_dir", None)
        if build_dir:
            cand = Path(build_dir) / "EFI" / "OC" / "config.plist"
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
        while (it := self.val_hw_box.takeAt(0)) is not None:
            w = it.widget()
            if w is not None:
                w.deleteLater()
        w = (p.net.wifi_chipset or "")
        if w == "mediatek":
            self.val_hw_card.setVisible(True)
            t = _h2(self.val_hw_card, "✖ " + tr.t("validate.wifi_mediatek_title"))
            t.setObjectName("err")
            self.val_hw_box.addWidget(t)
            d = _val(self.val_hw_card, tr.t("validate.wifi_mediatek_desc")); d.setWordWrap(True)
            self.val_hw_box.addWidget(d)
            b = _val(self.val_hw_card, "⚠ " + tr.t("validate.bt_unsupported"))
            b.setObjectName("warn")
            self.val_hw_box.addWidget(b)
        elif w == "" :
            self.val_hw_card.setVisible(False)
        else:
            self.val_hw_card.setVisible(True)
            t = _h2(self.val_hw_card, "✔ " + tr.t("validate.wifi_ok"))
            t.setObjectName("ok")
            self.val_hw_box.addWidget(t)
            if w == "broadcom" and p.net.has_bt:
                self.val_hw_box.addWidget(_val(self.val_hw_card, tr.t("validate.bt_broadcom")))

    def _build_usb(self):
        """Мастер записи EFI на флешку: выбор носителя, разметка, проверка."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "usb.title", "usb.subtitle")

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

        # --- 3.7. Резервные копии EFI ---
        bk_card = self._card(page)
        bv = QVBoxLayout(bk_card)
        brow = QHBoxLayout()
        brow.addWidget(_h2(page, tr.t("usb.backups.title")))
        brow.addStretch()
        self.backup_refresh_btn = QPushButton(tr.t("usb.backups.refresh"))
        self.backup_refresh_btn.setObjectName("ghost")
        self.backup_refresh_btn.clicked.connect(self._backup_refresh)
        brow.addWidget(self.backup_refresh_btn)
        bv.addLayout(brow)
        bk_hint = _muted(page, tr.t("usb.backups.hint")); bk_hint.setWordWrap(True)
        bv.addWidget(bk_hint)
        self.backup_combo = QComboBox()
        bv.addWidget(self.backup_combo)
        self.backup_empty = _muted(page, tr.t("usb.backups.empty")); self.backup_empty.setWordWrap(True)
        bv.addWidget(self.backup_empty)
        self.backup_restore_btn = QPushButton(tr.t("usb.backups.restore"))
        self.backup_restore_btn.setObjectName("ghost")
        self.backup_restore_btn.clicked.connect(self._backup_restore)
        bv.addWidget(self.backup_restore_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        v.addWidget(bk_card)

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
        self.usb_log.setPlaceholderText(tr.t("common.log_placeholder"))
        v.addWidget(self.usb_log, 1)

        # сразу просканируем флешки, историю и резервные копии
        self._usb_refresh()
        self._backup_refresh()
        self._history_refresh()
        v.addWidget(self._build_ports())
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
        self.usb_list_worker.failed.connect(self._usb_list_failed)
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
        if hasattr(self, "wiz_target_box"):
            self._wiz_fill_target()
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
            f"{tr.t('file.text')};;{tr.t('file.all_files')}")
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
        except Exception as e:
            QMessageBox.critical(self, tr.t("usb.title"), str(e))
            return
        self.statusBar().showMessage(
            tr.t("usb.log_saved").format(path=path), 4000)

    def _usb_list_failed(self, err: str):
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
            it.setFlags(Qt.ItemFlag.NoItemFlags)
            self.history_list.addItem(it)
            return
        for e in entries:
            ocv = "OK" if e.ocvalidate_ok else ("err" if e.ocvalidate_ok is False else "—")
            text = (f"{e.created_at} · {e.smbios or '—'} · "
                    f"{e.opencore or '—'} · ocvalidate: {ocv}")
            it = QListWidgetItem(text)
            it.setData(Qt.ItemDataRole.UserRole, e)
            if not e.exists:
                it.setForeground(QColor("#f38ba8"))
            self.history_list.addItem(it)

    def _history_selected(self):
        it = self.history_list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _history_open(self):
        entry = self._history_selected()
        if not entry:
            return
        path = Path(entry.efi_path)
        if not path.exists():
            QMessageBox.warning(self, tr.t("history.title"), tr.t("history.missing"))
            return
        try:
            os.startfile(str(path))
        except Exception as e:
            QMessageBox.critical(self, tr.t("history.title"), str(e))

    def _confirm(self, title: str, text: str, yes_text: str, no_text: str) -> bool:
        """Диалог подтверждения с явными подписями кнопок на языке интерфейса.

        Стандартные Yes/No из QMessageBox берут перевод из qtbase_*.qm, а его
        может не быть в сборке — поэтому подписи задаём сами.
        """
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(text)
        yes = box.addButton(yes_text, QMessageBox.ButtonRole.YesRole)
        box.addButton(no_text, QMessageBox.ButtonRole.NoRole)
        box.setDefaultButton(yes)
        box.exec()
        return box.clickedButton() is yes

    def _ask_yes_no(self, title: str, text: str) -> bool:
        """Локализованный диалог Да/Нет вместо стандартных Yes/No."""
        return self._confirm(title, text, tr.t("common.yes"), tr.t("common.no"))

    def _history_clear(self):
        if not self._ask_yes_no(
                tr.t("history.title"), tr.t("history.clear_ask")):
            return
        from ..builder import history
        n = history.clear_entries()
        self._history_refresh()
        self.statusBar().showMessage(
            tr.t("history.cleared").format(count=n), 4000)

    def _history_save(self):
        path, _ = QFileDialog.getSaveFileName(
            self, tr.t("history.save"), "HackicLab-history.json",
            f"{tr.t('file.json')};;{tr.t('file.all_files')}")
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

    def _backup_refresh(self):
        """Список резервных копий EFI, которые создаются перед перезаписью."""
        combo = getattr(self, "backup_combo", None)
        if combo is None:
            return
        try:
            from ..builder.usb_backend import list_backups
            backups = list_backups()
        except Exception:
            backups = []
        combo.blockSignals(True)
        combo.clear()
        for path in backups:
            combo.addItem(path.name, str(path))
        combo.blockSignals(False)
        combo.setEnabled(bool(backups))
        self.backup_restore_btn.setEnabled(bool(backups))
        self.backup_empty.setVisible(not backups)

    def _backup_restore(self):
        """Возвращает выбранную резервную копию на флешку после подтверждения."""
        from PySide6.QtWidgets import QInputDialog

        from ..builder import usb_writer

        worker = getattr(self, "_worker_usb", None)
        if worker is not None and worker.isRunning():
            return
        path = self.backup_combo.currentData() if hasattr(self, "backup_combo") else None
        if not path:
            return
        device = self.usb_combo.currentData() if hasattr(self, "usb_combo") else ""
        if not device:
            QMessageBox.information(self, tr.t("usb.backups.title"), tr.t("usb.choose"))
            return
        if not self._ensure_admin():
            return
        dev = next((x for x in getattr(self, "usb_devices", []) if x.device == device), None)
        disk_number = getattr(dev, "disk_number", "") if dev else ""
        try:
            letter = usb_writer.resolve_drive_letter(device, disk_number)
        except Exception as exc:
            QMessageBox.critical(self, tr.t("usb.backups.title"), str(exc))
            return
        phrase = self._confirm_phrase(device, disk_number)
        text, ok = QInputDialog.getText(
            self, tr.t("usb.backups.restore"),
            tr.t("usb.backups.type").format(phrase=phrase))
        if not ok or text.strip().upper() != phrase:
            return
        self.usb_log.appendPlainText(
            f"→ {tr.t('usb.backups.restored_from')}: {path}")
        try:
            usb_writer.restore_backup(Path(str(path)), letter,
                                      log=self.usb_log.appendPlainText)
        except Exception as exc:
            QMessageBox.critical(self, tr.t("usb.backups.title"), str(exc))
            return
        self.usb_log.appendPlainText(tr.t("usb.backups.restored"))
        self.statusBar().showMessage(tr.t("usb.backups.restored"), 6000)
        self._backup_refresh()
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
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLineEdit, QPushButton
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
                from ..builder.usb_backend import _find_free_drive_letter
                planned = _find_free_drive_letter()
            except Exception:
                planned = ""

        dlgv.addWidget(_h2(dlg, f"{tr.t('usb.confirm_target')}: {dev_txt}"))

        action = {"full": tr.t("usb.mode_full"),
                  "formatted": tr.t("usb.mode_formatted"),
                  "repair": tr.t("usb.mode_repair")}.get(mode, "")
        dlgv.addWidget(_h2(dlg, f"{tr.t('usb.confirm_action')}: {action}"))

        if mode == "full":
            warn = _val(dlg, "⚠  " + tr.t("usb.warn_erase")); warn.setObjectName("err")
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
        btns.addButton(ok_btn, QDialogButtonBox.ButtonRole.AcceptRole)
        btns.addButton(cancel_btn, QDialogButtonBox.ButtonRole.RejectRole)
        dlgv.addWidget(btns)

        def _try_accept():
            if inp.text().strip().upper() == phrase.upper():
                dlg.accept()
            else:
                self._usb_mismatch.setText(f"{tr.t('usb.confirm_mismatch')} {phrase}")
                self._usb_mismatch.setObjectName("err")

        ok_btn.clicked.connect(_try_accept)
        cancel_btn.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._usb_run(device, mode, planned, self.usb_make_map.isChecked())

    def _ensure_admin(self) -> bool:
        """Проверяет права: EXE запускается от администратора через манифест.

        Перезапуска с UAC здесь больше нет — он терял профиль и требовал
        подтверждения посреди работы. Если прав всё-таки нет (запуск из
        исходников), просто предупреждаем.
        """
        try:
            from ..builder.usb_backend import is_admin
        except Exception as e:
            QMessageBox.warning(self, tr.t("usb.admin_title"), str(e))
            return False
        if is_admin():
            return True
        QMessageBox.warning(self, tr.t("usb.admin_title"), tr.t("usb.admin_manual"))
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
        self._usb_bios_dialog()

    def _usb_bios_dialog(self):
        from PySide6.QtWidgets import (
            QDialog,
            QListWidget,
            QListWidgetItem,
            QPushButton,
            QVBoxLayout,
        )
        dlg = QDialog(self)
        dlg.setWindowTitle(tr.t("usb.bios_title"))
        dlg.setMinimumWidth(520)
        dlgv = QVBoxLayout(dlg)
        dlgv.addWidget(_h2(dlg, tr.t("usb.bios_desc")))
        lst = QListWidget(dlg)
        for key in ("usb.bios1", "usb.bios2", "usb.bios3", "usb.bios4", "usb.bios5"):
            it = QListWidgetItem("→  " + tr.t(key))
            lst.addItem(it)
        lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        dlgv.addWidget(lst)
        btn = QPushButton(tr.t("usb.bios_finish"))
        btn.clicked.connect(dlg.accept)
        dlgv.addWidget(btn, alignment=Qt.AlignmentFlag.AlignRight)
        dlg.exec()

    def _build_ports(self):
        """Вкладка «Порты и диски»: карта USB-портов и карта дисков."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h2(page, tr.t("usbmap.title")))

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
        self.usbmap_log.setPlaceholderText(tr.t("usbmap.log_hint"))
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
        self.disk_tree.setPlaceholderText(tr.t("diskmap.hint"))
        self.disk_tree.setMinimumHeight(220)
        self.disk_tree.setMaximumHeight(340)
        dv.addWidget(self.disk_tree, 1)
        v.addWidget(disk_card)
        v.addStretch(1)
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

    # ---- sources ----
    def _link_label(self, parent, src) -> QWidget:
        """Строка-ссылка: заголовок открывается в браузере, ниже пояснение."""
        w = QWidget(parent)
        lv = QVBoxLayout(w); lv.setContentsMargins(0, 2, 0, 2); lv.setSpacing(1)
        a = QLabel(w)
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setText(
            f'<a href="{src.url}" style="color:#89b4fa; text-decoration:none;">'
            f'{html.escape(title_of(src, tr.current))}</a>'
        )
        a.setOpenExternalLinks(True)
        a.setWordWrap(True)
        a.setToolTip(src.url)
        lv.addWidget(a)
        note = note_of(src, tr.current)
        if note:
            n = _muted(w, note); n.setWordWrap(True)
            lv.addWidget(n)
        return w

    def _build_sources(self):
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner); v.setContentsMargins(28, 24, 28, 24); v.setSpacing(10)
        self._page_header(inner, v, "sources.title", "sources.subtitle")

        # --- под ваше железо ---
        self._src_ctx_page = inner
        ctx_card = self._card(inner)
        cv = QVBoxLayout(ctx_card); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(4)
        self._src_ctx = QVBoxLayout(); self._src_ctx.setSpacing(4)
        cv.addLayout(self._src_ctx)
        v.addWidget(ctx_card)

        # --- поиск и фильтр ---
        row = QHBoxLayout()
        self.src_query = QLineEdit()
        self.src_query.setPlaceholderText(tr.t("sources.search"))
        self.src_query.setClearButtonEnabled(True)
        self.src_query.textChanged.connect(self._refresh_sources)
        row.addWidget(self.src_query, 2)
        self.src_cat = QComboBox()
        self.src_cat.currentIndexChanged.connect(self._refresh_sources)
        row.addWidget(self.src_cat, 1)
        v.addLayout(row)

        self.src_count = _muted(inner, "")
        v.addWidget(self.src_count)

        self._src_results = QVBoxLayout(); self._src_results.setSpacing(8)
        v.addLayout(self._src_results)

        v.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._refill_source_categories()
        self._fill_sources_ctx()
        self._refresh_sources()
        return page

    def _refill_source_categories(self):
        combo = getattr(self, "src_cat", None)
        if combo is None:
            return
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr.t("sources.all"), "")
        for cat in categories_of():
            combo.addItem(f"{tr.t('sources.cat.' + cat)} ({len(by_category(cat))})", cat)
        idx = combo.findData(current) if current else 0
        combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)

    def _status_badge(self, parent, status: str) -> QLabel:
        levels = {
            STATUS_NATIVE: "ok",
            STATUS_PATCHED: "warn",
            STATUS_LIMITED: "err",
        }
        badge = QLabel(tr.t("sources.status." + status), parent)
        badge.setObjectName("badge")
        badge.setProperty("tone", levels.get(status, "muted"))
        return badge

    def _support_report(self, cfg):
        """Кэшированный вердикт «соберётся ли EFI» для записи каталога."""
        cache = getattr(self, "_sup_cache", None)
        if cache is None:
            cache = {}
            self._sup_cache = cache
        if cfg.key not in cache:
            from ..knowledge.support import support_report
            cache[cfg.key] = support_report(cfg)
        return cache[cfg.key]

    def _support_badge(self, parent, cfg) -> QLabel:
        rep = self._support_report(cfg)
        levels = {"full": "ok", "partial": "warn", "none": "err"}
        badge = QLabel(tr.t("support.level." + rep.level), parent)
        badge.setObjectName("badge")
        badge.setProperty("tone", levels.get(rep.level, "warn"))
        reasons = [tr.t(key) for key in rep.failed]
        tip = tr.t("support.tooltip")
        if reasons:
            tip += "\n- " + "\n- ".join(reasons)
        badge.setToolTip(tip)
        return badge

    def _suggest_config(self):
        """Открывает issue с обезличенным описанием просканированного железа."""
        from ..knowledge import registry as hw_registry
        prof = getattr(self, "profile", None)
        if not prof:
            return
        try:
            record = hw_registry.find(prof) or hw_registry.register(prof)
        except Exception:
            record = None
        if record and hw_registry.open_issue(record):
            self.statusBar().showMessage(tr.t("sources.unknown_opened"), 6000)
            return
        QMessageBox.information(self, tr.t("sources.title"),
                                tr.t("sources.unknown_failed"))

    def _mini_link(self, parent, text: str, url: str) -> QLabel:
        a = QLabel(parent)
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setText(
            f'<a href="{html.escape(url)}" style="color:#89b4fa; text-decoration:none;">'
            f'{html.escape(text)} ↗</a>'
        )
        a.setOpenExternalLinks(True)
        a.setToolTip(url)
        return a

    def _config_card(self, parent, cfg) -> QWidget:
        card = self._card(parent)
        cv = QVBoxLayout(card); cv.setContentsMargins(14, 12, 14, 12); cv.setSpacing(4)
        head = QHBoxLayout()
        title = _h2(card, cfg.heading(tr.current)); title.setWordWrap(True)
        head.addWidget(title, 1)
        head.addWidget(self._support_badge(card, cfg))
        head.addWidget(self._status_badge(card, cfg.status))
        cv.addLayout(head)

        meta = _muted(
            card,
            f"{tr.t('sources.cat.' + cfg.category)} · {cfg.cpu} · {cfg.gpu} · "
            f"macOS: {cfg.macos}",
        )
        meta.setWordWrap(True)
        cv.addWidget(meta)

        for prefix, values in (("kexts", cfg.kexts), ("SSDT", cfg.ssdts), ("quirks", cfg.quirks)):
            if values:
                line = _muted(card, f"{prefix}: " + ", ".join(values))
                line.setWordWrap(True)
                cv.addWidget(line)

        note = _val(card, cfg.text(tr.current)); note.setWordWrap(True)
        cv.addWidget(note)

        links = QHBoxLayout(); links.setSpacing(14)
        for key in cfg.sources:
            src = SOURCES.get(key)
            if src is not None:
                links.addWidget(self._mini_link(card, title_of(src, tr.current), src.url))
        if cfg.url:
            links.addWidget(self._mini_link(card, tr.t("sources.details"), cfg.url))
        links.addStretch()
        cv.addLayout(links)
        return card

    def _clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _refresh_sources(self):
        """Перестраивает выдачу по строке поиска и выбранной категории."""
        lay = getattr(self, "_src_results", None)
        page = getattr(self, "_src_ctx_page", None)
        if lay is None or page is None:
            return
        query = self.src_query.text() if hasattr(self, "src_query") else ""
        cat = self.src_cat.currentData() if hasattr(self, "src_cat") else ""
        self._clear_layout(lay)

        found = search_configs(query, cat or "")
        if found:
            lay.addWidget(_h2(page, tr.t("sources.configs")))
            for cfg in found:
                lay.addWidget(self._config_card(page, cfg))

        q = (query or "").strip().lower()
        groups = ((GROUP_HARDWARE, "sources.hardware"),
                  (GROUP_GUIDES, "sources.guides"),
                  (GROUP_EFI, "sources.efi"),
                  (GROUP_COMMUNITY, "sources.community"))
        shown_links = 0
        for group, key in groups:
            items = sources_by_group(group, tr.current)
            if q:
                items = [
                    s for s in items
                    if q in f"{s.title} {s.title_en} {s.note} {s.note_en}".lower()
                ]
            if not items:
                continue
            card = self._card(page)
            cv = QVBoxLayout(card); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(2)
            cv.addWidget(_h2(page, tr.t(key)))
            for src in items:
                cv.addWidget(self._link_label(page, src))
                shown_links += 1
            lay.addWidget(card)

        if hasattr(self, "src_count"):
            self.src_count.setText(
                tr.t("sources.found").format(configs=len(found), links=shown_links)
            )

    def _fill_sources_ctx(self):
        """Ссылки и ближайшие конфигурации под текущий профиль."""
        lay = getattr(self, "_src_ctx", None)
        page = getattr(self, "_src_ctx_page", None)
        if lay is None or page is None:
            return
        self._clear_layout(lay)
        prof = getattr(self, "profile", None)
        if not prof:
            lbl = _muted(page, tr.t("sources.no_profile")); lbl.setWordWrap(True)
            lay.addWidget(lbl)
            return
        lay.addWidget(_h2(page, tr.t("sources.for_hw")))
        # ближайшие записи каталога
        sim = similar_configs(prof, limit=2)
        for cfg in sim:
            row = QHBoxLayout()
            title = _val(page, cfg.heading(tr.current)); title.setWordWrap(True)
            row.addWidget(title, 1)
            row.addWidget(self._status_badge(page, cfg.status))
            lay.addLayout(row)
            meta = _muted(page, f"{cfg.cpu} · {cfg.gpu} · macOS: {cfg.macos}")
            meta.setWordWrap(True)
            lay.addWidget(meta)
        if not sim:
            warn = _val(page, tr.t("sources.unknown_title")); warn.setWordWrap(True)
            lay.addWidget(warn)
            hint = _muted(page, tr.t("sources.unknown_hint")); hint.setWordWrap(True)
            lay.addWidget(hint)
            btn = QPushButton(tr.t("sources.unknown_suggest"))
            btn.setObjectName("ghost")
            btn.clicked.connect(self._suggest_config)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
    def _build_analyze(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        v.addWidget(_h2(page, tr.t("analyze.title")))

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
        v.addWidget(run, alignment=Qt.AlignmentFlag.AlignLeft)

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
        self.oclog_out.setMaximumHeight(150)
        self.oclog_out.setPlaceholderText(tr.t("oclog.hint"))
        lv.addWidget(self.oclog_out)
        v.addWidget(gb_log)

        self.an_progress = QProgressBar(); self.an_progress.setMaximum(0); self.an_progress.setVisible(False)
        v.addWidget(self.an_progress)

        findings = self._card(page)
        fv = QVBoxLayout(findings)
        fv.addWidget(_h2(page, tr.t("analyze.results_title")))
        self.an_empty_hint = _muted(page, tr.t("analyze.list_empty"))
        self.an_empty_hint.setWordWrap(True)
        fv.addWidget(self.an_empty_hint)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.issue_list = QListWidget(); self.issue_list.setObjectName("issueList")
        self.issue_list.setMinimumHeight(240)
        self.issue_detail = QTextEdit(); self.issue_detail.setReadOnly(True)
        self.issue_detail.setMinimumHeight(240)
        self.issue_detail.setPlaceholderText(tr.t("analyze.detail_empty"))
        splitter.addWidget(self.issue_list)
        splitter.addWidget(self.issue_detail)
        splitter.setSizes([540, 380])
        self.issue_list.currentItemChanged.connect(self._on_issue)
        fv.addWidget(splitter, 1)
        v.addWidget(findings)
        v.addStretch(1)
        return page

    def _do_oclog(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr.t("oclog.check"), "",
            f"{tr.t('file.opencore_log')};;{tr.t('file.all_files')}")
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

    _DONATE_URL = "https://yoomoney.ru/to/4100115796556073"
    _DONATE_WALLET = "4100115796556073"

    def _asset(self, *parts) -> Path:
        """Путь к ассету пакета — работает и в собранном EXE.

        В onefile-сборке ``__file__`` модуля из PYZ бывает относительным,
        поэтому базой служит ``sys._MEIPASS``.
        """
        bundled = getattr(sys, "_MEIPASS", None)
        if bundled:
            base = Path(bundled) / "hackiclab" / "assets"
        else:
            base = Path(__file__).resolve().parents[2] / "hackiclab" / "assets"
        return base / Path(*parts)

    def _rounded_photo(self, path: Path, width: int, height: int, radius: int) -> QPixmap:
        """Кадрирует фото под пропорции карточки и скругляет углы."""
        source = QPixmap(str(path))
        if source.isNull():
            return source
        scaled = source.scaled(
            width, height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        canvas = QPixmap(width, height)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, width, height, radius, radius)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, scaled.copy(x, y, width, height))
        painter.end()
        return canvas

    def _apple_pixmap(self, size: int) -> QPixmap:
        """Яблоко из SVG (иконка simple-icons, CC0) в цвете текущей темы."""
        from PySide6.QtSvg import QSvgRenderer

        path = self._asset("brands", "apple.svg")
        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return QPixmap()
        source = QPixmap(size, size)
        source.fill(Qt.GlobalColor.transparent)
        painter = QPainter(source)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
        painter.end()
        # иконка чёрная: перекрашиваем в цвет текста текущей темы
        tint = self.palette().color(QPalette.ColorRole.WindowText)
        pix = QPixmap(source.size())
        pix.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pix)
        painter.drawPixmap(0, 0, source)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pix.rect(), tint)
        painter.end()
        return pix

    def _apple_card(self, parent):
        """Карточка справа: яблоко и тонкий прогресс с процентами, как при загрузке macOS."""
        card = self._card(parent)
        card.setObjectName("appleCard")
        card.setMinimumWidth(200)
        card.setMaximumWidth(280)
        av = QVBoxLayout(card)
        av.setContentsMargins(20, 24, 20, 24)
        av.setSpacing(14)

        logo = QLabel(card)
        logo.setObjectName("appleLogo")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setPixmap(self._apple_pixmap(92))
        av.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)

        self.apple_percent = QLabel("0 %", card)
        self.apple_percent.setObjectName("applePercent")
        self.apple_percent.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(self.apple_percent)

        self.apple_bar = QProgressBar(card)
        self.apple_bar.setObjectName("appleProgress")
        self.apple_bar.setRange(0, 100)
        self.apple_bar.setValue(0)
        self.apple_bar.setTextVisible(False)
        self.apple_bar.setFixedHeight(6)
        av.addWidget(self.apple_bar)

        self.apple_caption = _muted(card, tr.t("build.apple_caption"))
        self.apple_caption.setWordWrap(True)
        self.apple_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        av.addWidget(self.apple_caption)
        av.addStretch(1)
        return card

    def _set_apple_progress(self, percent: int):
        """Обновляет яблоко-прогресс; при 100 % показывает готовность."""
        percent = max(0, min(100, int(percent)))
        bar = getattr(self, "apple_bar", None)
        if bar is not None:
            bar.setValue(percent)
        label = getattr(self, "apple_percent", None)
        if label is not None:
            label.setText(f"{percent} %")
        caption = getattr(self, "apple_caption", None)
        if caption is not None:
            if percent >= 100:
                caption.setText(tr.t("build.apple_done"))
            elif percent > 0:
                caption.setText(tr.t("build.apple_working"))
            else:
                caption.setText(tr.t("build.apple_caption"))

    def _logo_pixmap(self, name: str, height: int) -> QPixmap:
        pix = QPixmap(str(self._asset("brands", name)))
        if pix.isNull():
            return pix
        scaled = pix.scaledToHeight(height * 2, Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(2.0)
        return scaled

    def _build_donate(self):
        """Вкладка поддержки: форма-калькулятор, способы оплаты и фото автора.

        Контент стоит центральной колонкой с одинаковыми отступами слева и
        справа, как в «Параметрах» Windows: на широком окне поля не растягиваются
        и не выглядят огромными.
        """
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "donate.title", "donate.subtitle")

        cols = QHBoxLayout(); cols.setSpacing(18)
        left = QVBoxLayout(); left.setSpacing(14)

        why = self._card(page)
        wv = QVBoxLayout(why)
        wv.addWidget(_h2(page, tr.t("donate.why_title")))
        why_text = _muted(page, tr.t("donate.why_text")); why_text.setWordWrap(True)
        wv.addWidget(why_text)
        left.addWidget(why)

        form = self._card(page)
        fv = QVBoxLayout(form)
        fv.addWidget(_h2(page, tr.t("donate.amount_title")))
        hint = _muted(page, tr.t("donate.amount_hint")); hint.setWordWrap(True)
        fv.addWidget(hint)

        chips = QHBoxLayout(); chips.setSpacing(8)
        self.donate_group = QButtonGroup(self)
        for amount in (300, 600, 1200, 3000, 5000):
            chip = QPushButton(f"{amount} ₽")
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            chip.setProperty("amount", amount)
            chip.clicked.connect(lambda _=False, a=amount: self.donate_amount.setValue(a))
            self.donate_group.addButton(chip)
            chips.addWidget(chip)
        chips.addStretch()
        fv.addLayout(chips)

        amount_row = QHBoxLayout()
        amount_row.addWidget(_h2(page, tr.t("donate.amount_custom")))
        self.donate_amount = QSpinBox()
        self.donate_amount.setRange(100, 100000)
        self.donate_amount.setSingleStep(100)
        self.donate_amount.setSuffix(" ₽")
        self.donate_amount.setValue(1000)
        self.donate_amount.valueChanged.connect(self._donate_recalc)
        amount_row.addWidget(self.donate_amount, 1)
        fv.addLayout(amount_row)

        self.donate_fee = _muted(page, "")
        self.donate_fee.setWordWrap(True)
        fv.addWidget(self.donate_fee)
        self.donate_limit = _muted(page, "")
        self.donate_limit.setWordWrap(True)
        fv.addWidget(self.donate_limit)

        wallet_row = QHBoxLayout()
        wallet_row.addWidget(_h2(page, tr.t("donate.wallet")))
        self.donate_wallet = QLabel(self._DONATE_WALLET)
        self.donate_wallet.setObjectName("kv")
        self.donate_wallet.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        wallet_row.addWidget(self.donate_wallet, 1)
        fv.addLayout(wallet_row)

        btns = QHBoxLayout()
        pay = QPushButton(tr.t("donate.pay"))
        pay.clicked.connect(self._open_donate)
        copy = QPushButton(tr.t("donate.copy"))
        copy.setObjectName("ghost")
        copy.clicked.connect(self._copy_wallet)
        btns.addWidget(pay)
        btns.addWidget(copy)
        btns.addStretch()
        fv.addLayout(btns)
        left.addWidget(form)

        methods = self._card(page)
        mv = QVBoxLayout(methods)
        mv.addWidget(_h2(page, tr.t("donate.methods_title")))
        logo_row = QHBoxLayout(); logo_row.setSpacing(0)
        strip = QFrame(page)
        strip.setObjectName("logoStrip")
        strip.setFixedHeight(44)
        strip_fixed = strip.sizePolicy()
        strip_fixed.setHorizontalPolicy(strip_fixed.Policy.Maximum)
        strip.setSizePolicy(strip_fixed)
        sl = QHBoxLayout(strip); sl.setContentsMargins(16, 0, 16, 0); sl.setSpacing(22)
        for name, height in (("yoomoney.png", 20), ("mir.png", 18), ("sbp.png", 19)):
            lbl = QLabel()
            pix = self._logo_pixmap(name, height)
            if not pix.isNull():
                lbl.setPixmap(pix)
            sl.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row.addWidget(strip, 0, Qt.AlignmentFlag.AlignLeft)
        logo_row.addStretch()
        mv.addLayout(logo_row)
        for key in ("donate.methods_text", "donate.limits_text",
                    "donate.methods_foreign", "donate.logos_note"):
            lbl = _muted(page, tr.t(key)); lbl.setWordWrap(True)
            mv.addWidget(lbl)
        left.addWidget(methods)

        use = self._card(page)
        uv = QVBoxLayout(use)
        uv.addWidget(_h2(page, tr.t("donate.use_title")))
        for key in ("donate.use1", "donate.use2", "donate.use3", "donate.use4"):
            item = _muted(page, "•  " + tr.t(key)); item.setWordWrap(True)
            uv.addWidget(item)
        left.addWidget(use)
        cols.addLayout(left, 3)

        author = self._card(page)
        author.setMaximumWidth(380)
        av = QVBoxLayout(author)
        photo = QLabel()
        pix = self._rounded_photo(self._asset("support", "author.png"), 300, 384, 18)
        if not pix.isNull():
            photo.setPixmap(pix)
        photo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        av.addWidget(photo)
        role = _muted(page, tr.t("donate.author_role"))
        av.addWidget(role)
        quote = QLabel(tr.t("donate.author_quote"))
        quote.setWordWrap(True)
        quote.setObjectName("h2")
        av.addWidget(quote)
        thanks = _muted(page, tr.t("donate.author_thanks")); thanks.setWordWrap(True)
        av.addWidget(thanks)
        av.addStretch(1)
        cols.addWidget(author, 2, Qt.AlignmentFlag.AlignTop)
        cols_box = QWidget(page)
        cols_box.setLayout(cols)
        v.addWidget(cols_box, 0, Qt.AlignmentFlag.AlignTop)

        legal = self._card(page)
        lv = QVBoxLayout(legal)
        legal_text = _muted(page, tr.t("donate.legal")); legal_text.setWordWrap(True)
        lv.addWidget(legal_text)
        v.addWidget(legal)
        v.addStretch(1)

        self._donate_recalc()
        return page

    def _donate_recalc(self, *_args):
        """Считает комиссию и подсказывает про лимит в один перевод."""
        amount = self.donate_amount.value()
        fee = 0 if amount >= 4000 else max(1, round(amount * 0.01))
        self.donate_fee.setText(
            tr.t("donate.fee_free") if fee == 0
            else tr.t("donate.fee_percent").format(fee=fee))
        over = amount > 15000
        self.donate_limit.setText(
            tr.t("donate.limit_over") if over else tr.t("donate.limit_ok"))
        wanted = "warn" if over else "muted"
        if self.donate_limit.objectName() != wanted:
            self.donate_limit.setObjectName(wanted)
            self.donate_limit.style().unpolish(self.donate_limit)
            self.donate_limit.style().polish(self.donate_limit)
        for btn in self.donate_group.buttons():
            value = btn.property("amount")
            if isinstance(value, int) and btn.isChecked() != (value == amount):
                btn.blockSignals(True)
                btn.setChecked(value == amount)
                btn.blockSignals(False)

    def _open_donate(self):
        QDesktopServices.openUrl(QUrl(self._DONATE_URL))

    def _copy_wallet(self):
        QGuiApplication.clipboard().setText(self._DONATE_WALLET)
        self.statusBar().showMessage(
            tr.t("donate.copied").format(wallet=self._DONATE_WALLET), 5000)

    def _build_settings(self):
        root = QWidget()
        outer = QVBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        page = inner
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "settings.title", "settings.subtitle")

        # Язык
        gb_lang = QGroupBox(tr.t("settings.language"))
        lg = QHBoxLayout(gb_lang)
        self.settings_lang = QComboBox()
        for l in LANGS:
            self.settings_lang.addItem(l.native, l.code)
        idx = next((i for i in range(self.settings_lang.count()) if self.settings_lang.itemData(i) == tr.current), 0)
        self.settings_lang.setCurrentIndex(idx)
        self.settings_lang.currentIndexChanged.connect(self._on_lang)
        lg.addWidget(self.settings_lang, 1)
        v.addWidget(gb_lang)

        # Тема оформления — плитки-мониторы
        gb_theme = QGroupBox(tr.t("settings.theme"))
        tv = QVBoxLayout(gb_theme)
        theme_desc = _muted(page, tr.t("settings.theme_descr")); theme_desc.setWordWrap(True)
        tv.addWidget(theme_desc)

        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_tiles: dict[str, MonitorButton] = {}
        base_labels = {
            "system": "settings.theme_system",
            "light": "settings.theme_light",
            "dark": "settings.theme_dark",
            "custom": "settings.theme_custom",
        }
        base_row = QHBoxLayout(); base_row.setSpacing(10)
        for key in BASE_THEMES:
            btn = MonitorButton(key, tr.t(base_labels[key]), gb_theme)
            self._theme_group.addButton(btn)
            self._theme_tiles[key] = btn
            base_row.addWidget(btn)
        base_row.addStretch()
        tv.addLayout(base_row)

        tv.addWidget(_h2(page, tr.t("settings.theme_builtin")))
        preset_labels = {
            "aqua": "settings.theme_aqua",
            "graphite": "settings.theme_graphite",
            "sonoma": "settings.theme_sonoma",
            "bigsur": "settings.theme_bigsur",
        }
        preset_row = QHBoxLayout(); preset_row.setSpacing(10)
        for key in BUILTIN_THEMES:
            btn = MonitorButton(key, tr.t(preset_labels[key]), gb_theme)
            self._theme_group.addButton(btn)
            self._theme_tiles[key] = btn
            preset_row.addWidget(btn)
        preset_row.addStretch()
        tv.addLayout(preset_row)
        self._theme_group.buttonClicked.connect(self._on_theme_tile)

        # Свой фон для темы «Моя тема»
        bg_row = QHBoxLayout()
        bg_row.addWidget(_h2(page, tr.t("settings.theme_bg")))
        self.bg_label = _muted(
            page,
            self._theme_bg or tr.t("settings.theme_bg_none"),
        )
        self.bg_label.setWordWrap(True)
        bg_row.addWidget(self.bg_label, 1)
        pick_bg = QPushButton(tr.t("settings.theme_bg_pick"))
        pick_bg.setObjectName("ghost")
        pick_bg.clicked.connect(self._pick_theme_bg)
        bg_row.addWidget(pick_bg)
        reset_bg = QPushButton(tr.t("settings.theme_bg_reset"))
        reset_bg.setObjectName("ghost")
        reset_bg.clicked.connect(self._reset_theme_bg)
        bg_row.addWidget(reset_bg)
        tv.addLayout(bg_row)
        v.addWidget(gb_theme)
        self._sync_theme_tiles()

        # Всё бесплатно: вместо фейковой активации — честное объяснение модели.
        gb_free = QGroupBox(tr.t("settings.free_title"))
        fv = QVBoxLayout(gb_free)
        free_text = _muted(page, tr.t("settings.free_text"))
        free_text.setWordWrap(True)
        fv.addWidget(free_text)
        free_plan = _muted(page, tr.t("settings.free_plan"))
        free_plan.setWordWrap(True)
        fv.addWidget(free_plan)
        v.addWidget(gb_free)

        # Обновления
        gb_upd = QGroupBox(tr.t("settings.updates"))
        uv = QVBoxLayout(gb_upd)
        self.upd_version = _val(page, f"{tr.t('settings.updates_version')}: {__version__}")
        uv.addWidget(self.upd_version)
        self.upd_auto = QCheckBox(tr.t("settings.updates_auto"))
        self.upd_auto.setChecked(bool(uistate.get("check_updates", True)))
        self.upd_auto.toggled.connect(
            lambda on: uistate.save(check_updates=bool(on)))
        uv.addWidget(self.upd_auto)

        upd_row = QHBoxLayout()
        self.upd_check_btn = QPushButton(tr.t("settings.updates_check"))
        self.upd_check_btn.clicked.connect(self._check_updates)
        upd_row.addWidget(self.upd_check_btn)
        self.upd_status = _muted(page, tr.t("settings.updates_idle"))
        self.upd_status.setWordWrap(True)
        upd_row.addWidget(self.upd_status, 1)
        uv.addLayout(upd_row)

        self.upd_notes = QPlainTextEdit()
        self.upd_notes.setReadOnly(True)
        self.upd_notes.setMaximumHeight(150)
        self.upd_notes.setVisible(False)
        uv.addWidget(self.upd_notes)

        self.upd_actions = QWidget(page)
        av = QHBoxLayout(self.upd_actions); av.setContentsMargins(0, 0, 0, 0)
        self.upd_now_btn = QPushButton(tr.t("settings.updates_now"))
        self.upd_now_btn.clicked.connect(self._install_update)
        self.upd_later_btn = QPushButton(tr.t("settings.updates_later"))
        self.upd_later_btn.setObjectName("ghost")
        self.upd_later_btn.clicked.connect(self._postpone_update)
        av.addWidget(self.upd_now_btn)
        av.addWidget(self.upd_later_btn)
        av.addStretch()
        self.upd_actions.setVisible(False)
        uv.addWidget(self.upd_actions)

        # Запасной путь: при лимите GitHub открыть страницу релиза вручную
        self.upd_fallback = QWidget(page)
        fb = QHBoxLayout(self.upd_fallback); fb.setContentsMargins(0, 0, 0, 0)
        self.upd_page_btn = QPushButton(tr.t("settings.updates_open_page"))
        self.upd_page_btn.setObjectName("ghost")
        self.upd_page_btn.clicked.connect(self._open_release_page)
        fb.addWidget(self.upd_page_btn)
        fb.addStretch()
        self.upd_fallback.setVisible(False)
        uv.addWidget(self.upd_fallback)

        self.upd_warning = _muted(page, tr.t("settings.updates_warning"))
        self.upd_warning.setWordWrap(True)
        self.upd_warning.setVisible(False)
        uv.addWidget(self.upd_warning)
        v.addWidget(gb_upd)
        self._pending_update = None

        v.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return root

    # ---- обновления ----
    def _check_updates(self, silent: bool = False):
        """Запускает проверку релиза на GitHub в фоновом потоке."""
        if getattr(self, "_upd_worker", None) and self._upd_worker.isRunning():
            return
        if not hasattr(self, "upd_check_btn"):
            return
        self.upd_check_btn.setEnabled(False)
        self.upd_status.setText(tr.t("settings.updates_checking"))
        self.upd_warning.setVisible(False)
        self._upd_silent = bool(silent)
        worker = UpdateCheckWorker()
        self._upd_worker = worker
        worker.found.connect(self._updates_found)
        worker.up_to_date.connect(self._updates_up_to_date)
        worker.failed.connect(self._updates_failed)
        worker.finished.connect(lambda: self.upd_check_btn.setEnabled(True))
        worker.start()

    def _auto_check_updates(self):
        if os.environ.get("HACKICLAB_NO_UPDATES"):
            return
        if bool(uistate.get("check_updates", True)):
            self._check_updates(silent=True)

    def _updates_found(self, info):
        self._pending_update = info
        uistate.save(postponed_update="")
        key = ("settings.updates_rebuild" if getattr(info, "is_rebuild", False)
               else "settings.updates_available")
        text = tr.t(key).format(version=info.version)
        self.upd_status.setText(text)
        notes = _release_notes_text(info.notes)
        self.upd_notes.setPlainText(notes)
        self.upd_notes.setVisible(bool(notes))
        self.upd_now_btn.setText(
            tr.t("settings.updates_now") if info.has_asset
            else tr.t("settings.updates_open_page"))
        self.upd_actions.setVisible(True)
        self.statusBar().showMessage(text, 8000)
        # Пересборку той же версии не предлагаем модальным окном при старте:
        # пользователь только что мог собрать её сам. В «Настройках» она видна.
        if (getattr(self, "_upd_silent", False) and info.has_asset
                and not getattr(info, "is_rebuild", False)):
            # предложение при старте: обновиться сейчас или отложить с напоминанием
            if self._confirm(
                tr.t("settings.updates"),
                f"{text}\n\n{tr.t('settings.updates_warning')}",
                tr.t("settings.updates_now"), tr.t("settings.updates_later"),
            ):
                self._install_update()
            else:
                self._postpone_update()
        self._upd_silent = False

    def _updates_up_to_date(self):
        self._pending_update = None
        self.upd_status.setText(tr.t("settings.updates_latest"))
        self.upd_notes.setVisible(False)
        self.upd_actions.setVisible(False)
        self.upd_fallback.setVisible(False)

    def _updates_failed(self, err: str):
        """Понятное сообщение вместо HTTP-кода: лимит GitHub — не поломка."""
        self._pending_update = None
        message = str(err).strip() or tr.t("settings.updates_hint")
        self.upd_status.setText(tr.t("settings.updates_failed").format(error=message))
        self.upd_actions.setVisible(False)
        self.upd_notes.setVisible(False)
        self.upd_fallback.setVisible(True)

    def _open_release_page(self):
        from .. import updater

        url = getattr(self, "_release_page_url", "") or updater.RELEASES_PAGE
        updater.open_release_page(url)
        self.upd_status.setText(tr.t("settings.updates_browser"))

    def _install_update(self):
        """Скачивает новую сборку и запускает подмену EXE."""
        from .. import updater
        info = getattr(self, "_pending_update", None)
        if info is None:
            return
        if not (info.has_asset and updater.can_self_update()):
            updater.open_release_page(info.page_url)
            self.upd_status.setText(tr.t("settings.updates_browser"))
            return
        if getattr(self, "_upd_dl", None) and self._upd_dl.isRunning():
            return
        self.upd_now_btn.setEnabled(False)
        self.upd_status.setText(tr.t("settings.updates_downloading"))
        worker = UpdateDownloadWorker(info)
        self._upd_dl = worker
        worker.done.connect(self._update_downloaded)
        worker.failed.connect(self._update_download_failed)
        worker.start()

    def _update_downloaded(self, path):
        from .. import updater
        self.upd_now_btn.setEnabled(True)
        if not updater.apply_update(Path(path)):
            self.upd_status.setText(tr.t("settings.updates_manual"))
            return
        self.upd_status.setText(tr.t("settings.updates_restarting"))
        updater.relaunch_self()
        # Штатный выход: PyInstaller сам удаляет временную папку _MEI.
        # Принудительный os._exit оставлял её и давал предупреждение при старте.
        QTimer.singleShot(300, QApplication.quit)

    def _update_download_failed(self, err):
        self.upd_now_btn.setEnabled(True)
        if getattr(err, "already_installed", False):
            # Скачалась ровно та сборка, что уже запущена: обновляться некуда.
            self._pending_update = None
            self.upd_status.setText(tr.t("settings.updates_latest"))
            self.upd_notes.setVisible(False)
            self.upd_actions.setVisible(False)
            self.upd_fallback.setVisible(False)
            return
        self.upd_status.setText(tr.t("settings.updates_failed").format(error=str(err)))
        self.upd_fallback.setVisible(True)

    def _postpone_update(self):
        info = getattr(self, "_pending_update", None)
        version = info.version if info else ""
        uistate.save(postponed_update=version, skipped_version=version)
        self.upd_actions.setVisible(False)
        self.upd_warning.setText(tr.t("settings.updates_postponed"))
        self.upd_warning.setVisible(True)

    def _on_theme_tile(self, btn):
        key = getattr(btn, "key", "")
        if not key:
            return
        self.apply_theme(key)
        self._hook_system_theme()
        if key == "custom" and not self._theme_bg:
            self.statusBar().showMessage(tr.t("settings.theme_bg_hint"), 5000)

    def _pick_theme_bg(self):
        """Выбор фонового изображения для темы «Моя тема»."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr.t("settings.theme_bg_pick"), "",
            f"{tr.t('file.images')};;{tr.t('file.all_files')}")
        if not path:
            return
        self._theme_bg = path
        self._theme = "custom"
        uistate.save(background=path, theme="custom")
        self.apply_theme()
        if hasattr(self, "bg_label"):
            self.bg_label.setText(path)
        self._hook_system_theme()

    def _reset_theme_bg(self):
        """Убирает пользовательский фон, оставляя фирменную тему."""
        self._theme_bg = ""
        uistate.save(background="")
        self.apply_theme()
        if hasattr(self, "bg_label"):
            self.bg_label.setText(tr.t("settings.theme_bg_none"))

    def _build_about(self):
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "about.title", "about.subtitle")

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
        tv.addWidget(_muted(page, f"{tr.t('about.version')} {__version__} · {tr.t('about.license')}"))
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
    NAV_GROUPS = (
        ("nav.group.start", (
            ("nav.auto", "✨", "nav.auto.sub"),
        )),
        ("nav.group.build", (
            ("nav.build", "⚙", "nav.build.sub"),
            ("nav.validate", "✅", "nav.validate.sub"),
            ("usb.nav", "💾", "usb.nav.sub"),
        )),
        ("nav.group.more", (
            ("nav.sources", "📚", "nav.sources.sub"),
            ("donate.nav", "💛", "donate.nav.sub"),
            ("nav.settings", "⚙", "nav.settings.sub"),
            ("nav.about", "ℹ", "nav.about.sub"),
        )),
    )

    def _rebuild_nav(self, current: int | None = None):
        """Меню с группами и подписью у каждого пункта.

        Порядок пунктов совпадает с порядком страниц в стеке, но в списке
        между группами стоят разделители, поэтому номер строки и номер
        страницы различаются — пересчёт идёт через ``_page_rows``.
        """
        if current is None:
            current = self.stack.currentIndex() if hasattr(self, "stack") else 0
        self.nav.blockSignals(True)
        self.nav.clear()
        self._nav_rows = []
        self._page_rows = {}
        self._nav_keys = []
        self._nav_icons = []
        page = 0
        first_group = True
        for _group_key, items in self.NAV_GROUPS:
            if not first_group:
                # разделитель между группами: без текста, чтобы скринридер
                # не читал служебные слова вроде «Начало» и «Сборка»
                spacer = QListWidgetItem()
                spacer.setFlags(Qt.ItemFlag.NoItemFlags)
                spacer.setSizeHint(QSize(0, 12))
                self.nav.addItem(spacer)
                self._nav_rows.append(-1)
            first_group = False
            for title_key, icon, _sub_key in items:
                label = tr.t(title_key)
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, title_key)
                item.setData(Qt.ItemDataRole.AccessibleTextRole, label)
                item.setSizeHint(QSize(0, 40))
                self.nav.addItem(item)
                widget = QWidget()
                widget.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                widget.setAccessibleName(label)
                lay = QHBoxLayout(widget)
                lay.setContentsMargins(12, 0, 10, 0)
                lay.setSpacing(10)
                title = QLabel(f"{icon}  {label}", widget)
                title.setObjectName("navTitle")
                title.setAccessibleName(label)
                lay.addWidget(title)
                lay.addStretch(1)
                self.nav.setItemWidget(item, widget)
                self._nav_keys.append(title_key)
                self._nav_icons.append(icon)
                self._nav_rows.append(page)
                self._page_rows[page] = self.nav.count() - 1
                page += 1
        self.nav.blockSignals(False)
        self._select_nav(current)

    def _select_nav(self, page: int) -> None:
        """Выделяет пункт меню, соответствующий странице, без перехода по сигналу."""
        row = self._page_rows.get(page, 0)
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(row)
        self.nav.blockSignals(False)

    def _nav_titles(self) -> list[str]:
        """Подписи пунктов меню без групп — для самопроверки локализации."""
        return [tr.t(key) for key in getattr(self, "_nav_keys", [])]

    def _page_index(self, page) -> int:
        """Номер страницы в стеке по самому виджету.

        В стеке лежат обёртки QScrollArea, поэтому stack.indexOf(page) не
        находит исходный виджет — сравниваем содержимое обёрток.
        """
        widget = page
        while widget is not None:
            idx = self.stack.indexOf(widget)
            if idx >= 0:
                return idx
            widget = widget.parentWidget()
        return -1

    def _go_page(self, index):
        """Переходит на страницу по номеру или по самому виджету страницы.

        Номер страницы зависит от состава меню, поэтому вызовы по виджету
        надёжнее: порядок вкладок уже менялся.
        """
        if not isinstance(index, int):
            index = self._page_index(index)
        if index < 0:
            return
        row = getattr(self, "_page_rows", {}).get(index, 0)
        self.nav.setCurrentRow(row)

    def _on_nav(self, row):
        stack = getattr(self, "stack", None)
        if stack is None:
            return
        rows = getattr(self, "_nav_rows", [])
        if row < 0 or row >= len(rows):
            return
        page = rows[row]
        if 0 <= page < stack.count():
            stack.setCurrentIndex(page)

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
        uistate.save(language=code)
        install_qt_translator(code)
        # пересобираем страницы после выхода из обработчика сигнала
        QTimer.singleShot(0, self._rebuild_pages)

    def _retranslate(self):
        """Совместимость: полная пересборка страниц под текущий язык."""
        self._rebuild_pages()

    _WORKER_ATTRS = ("_worker_scan", "_worker_build", "_usb_worker", "_worker_usb",
                     "_worker_val", "_worker_audit", "_worker_an",
                     "_upd_worker", "_upd_dl")

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
            "opt_gui": self.opt_gui.isChecked(),
            "macos": self.macos_combo.currentData(),
            # Автоматическая сборка: без этого смена языка теряла журнал,
            # готовый отчёт и кнопки «Открыть папку»/«Отправить в базу».
            "wiz_log": self.wiz_log.toPlainText() if hasattr(self, "wiz_log") else "",
            "wiz_result": self.wiz_result.text() if hasattr(self, "wiz_result") else "",
            "wiz_record": getattr(self, "_wiz_record", ""),
            "wiz_target": getattr(self, "_wiz_last_target", None),
        }
        while self.stack.count():
            w = self.stack.widget(0)
            if w is None:
                break
            self.stack.removeWidget(w)
            w.deleteLater()
        self._create_pages()
        self._rebuild_nav(idx)
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
        self.opt_gui.setChecked(bool(st.get("opt_gui")))
        if st["macos"]:
            i = self.macos_combo.findData(st["macos"])
            if i >= 0:
                self.macos_combo.setCurrentIndex(i)
        self.build_log.setPlainText(st["build_log"])
        self.build_rationale.setPlainText(st["rationale"])
        if st["rationale"].strip():
            self._rationale_text = st["rationale"]
        self.rationale_save_btn.setEnabled(
            bool(st["rationale"].strip()) or bool(getattr(self, "profile", None)))
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
                self.val_path_label.setVisible(True)
                self._load_quick()
            except Exception:
                pass
        try:
            self._on_macos_change()
        except Exception:
            pass

        if st["wiz_log"]:
            self.wiz_log.setPlainText(st["wiz_log"])
        if st["wiz_result"]:
            self.wiz_result.setText(st["wiz_result"])
        self._wiz_record = st["wiz_record"]
        self._wiz_last_target = st["wiz_target"]
        self.wiz_share_btn.setVisible(bool(st["wiz_record"]))
        self.wiz_open_btn.setVisible(bool(st["wiz_target"]))

        self.stack.setCurrentIndex(max(0, min(idx, self.stack.count() - 1)))
        self._select_nav(self.stack.currentIndex())
        self._sync_lang_combos()
        self._sync_theme_tiles()
        self.statusBar().showMessage(tr.t("app.lang_changed"), 2500)

    # ---- scan ----
    def _wizard_macos(self) -> str:
        """Целевая macOS для подсказки SMBIOS: мастер, затем вкладка сборки."""
        state = getattr(self, "_wiz", None) or {}
        if state.get("macos"):
            return str(state["macos"])
        combo = getattr(self, "macos_combo", None)
        if combo is not None:
            return str(combo.currentData() or "")
        return ""

    def _scan_done(self, profile):
        self.scan_progress.setVisible(False)
        card = getattr(self, "scan_empty_card", None)
        if card is not None:
            card.setVisible(False)
        self.profile = profile
        try:
            from ..knowledge import registry as hw_registry
            self._last_hw_record = hw_registry.register(profile)
        except Exception:
            self._last_hw_record = None
        self._refresh_validate_hw()
        while (it := self.hw_grid.takeAt(0)) is not None:
            w = it.widget()
            if w is not None:
                w.deleteLater()
        rows = [
            (item["key"], item["value"], item["note"])
            for item in hardware_rows(profile, self._wizard_macos())
        ]
        for key, val, note in rows:
            c = self._card(self.page_auto)
            cv = QVBoxLayout(c); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(2)
            cv.addWidget(_h2(self.page_auto, tr.t(key)))
            vv = _val(self.page_auto, val); vv.setWordWrap(True)
            if note:
                hint = tr.t(note) if note.startswith("hw.") else note
                vv.setToolTip(hint)
                row = QHBoxLayout()
                row.addWidget(vv, 1)
                note_lbl = QLabel(hint, self)
                note_lbl.setObjectName("muted")
                row.addWidget(note_lbl)
                cv.addLayout(row)
            else:
                cv.addWidget(vv)
            self.hw_grid.addWidget(c)
        self.scan_save_btn.setVisible(True)
        self._fill_sources_ctx()
        self._wiz_state()["profile"] = profile
        self._wiz_update_hint()
        self.statusBar().showMessage(tr.t("scan.done"), 3000)

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
        if "unsupported" in max_ver.lower() or (target and target != max_ver and _macos_newer(target, max_ver)):
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
        dest = (self.build_dest.text() or "").strip()
        if dest in ("", "—"):
            self._pick_build_dir()
            dest = (self.build_dest.text() or "").strip()
            if dest in ("", "—"):
                QMessageBox.warning(self, "HackicLab", tr.t("build.pick"))
                return
        profile = getattr(self, "manual_profile", None) or manual_hw.build_profile(
            self._manual_selection())
        opts = BuildOptions(
            usb_toolbox=self.opt_usb.isChecked(),
            disable_sip=self.opt_sip.isChecked(),
            gui_picker=self.opt_gui.isChecked(),
            wifi_kext_mode=self.wifi_mode.currentData() or "itlwm",
            target_macos=self.macos_combo.currentData() or "",
        )
        plan = BuildPlan(profile=profile, options=opts)
        target = _efi_root_for(dest)
        self._manual_last_target = target
        self._last_build_profile = profile
        self.manual_result.setText("")
        self.manual_open_btn.setVisible(False)
        self._last_build_options = opts
        self._last_build_smbios = plan.smbios
        self._rationale_text = ""
        self.build_rationale.clear()
        self.rationale_save_btn.setEnabled(False)
        self.build_progress.setVisible(True)
        self.build_progress.setRange(0, 100)
        self.build_progress.setValue(0)
        self._set_apple_progress(0)
        self.build_log.clear()
        self.build_log.appendPlainText(tr.t("build.building"))
        self._worker_build = BuildWorker(plan, target)
        self._worker_build.progress.connect(self._build_progress)
        self._worker_build.done.connect(self._build_done)
        self._worker_build.failed.connect(self._build_failed)
        self._worker_build.start()

    def _build_progress(self, percent: int, message: str):
        """Живой журнал сборки: каждая строка появляется сразу, с процентом."""
        self.build_log.appendPlainText(f"[{percent:3d}%] {message}")
        self.build_log.verticalScrollBar().setValue(
            self.build_log.verticalScrollBar().maximum())
        self.build_progress.setValue(percent)
        self._set_apple_progress(percent)
        self.statusBar().showMessage(message, 4000)

    def _build_done(self, res):
        self.build_progress.setValue(100)
        self.build_progress.setVisible(False)
        self._set_apple_progress(100)
        self.last_build_dir = Path(res.root) if res and res.root else None
        if self.last_build_dir:
            self.val_last_label.setText(str(self.last_build_dir))
        ok = bool(getattr(res, "ok", False))
        result = getattr(self, "manual_result", None)
        if result is not None:
            result.setText(tr.t("manual.build.ok") if ok else tr.t("manual.build.fail"))
            result.setProperty("tone", "ok" if ok else "err")
            result.style().unpolish(result)
            result.style().polish(result)
        open_btn = getattr(self, "manual_open_btn", None)
        if open_btn is not None:
            open_btn.setVisible(bool(self.last_build_dir))
        log = f"target: {res.root}\n" + "\n".join(getattr(res, "log", []) or [])
        if res.stats:
            log += f"\n\n--- {tr.t('build.log_summary')} ---"
            log += f"\nOpenCore: {res.stats.get('opencore', '—')}"
            kexts_done = res.stats.get("kexts_downloaded", []) or []
            log += "\n" + tr.t("build.log_kexts").format(
                count=len(kexts_done), list=", ".join(kexts_done))
            kexts_missing = res.stats.get("kexts_missing", []) or []
            if kexts_missing:
                log += "\n" + tr.t("build.log_kexts_missing").format(
                    list=", ".join(kexts_missing))
            log += f"\nSSDT: {', '.join(res.stats.get('ssdt_placed', []) or [])}"
            log += f"\nSMBIOS: {res.stats.get('smbios', '')}"
            # ocvalidate
            ocv_ok = res.stats.get("ocvalidate_ok")
            ocv_err = res.stats.get("ocvalidate_errors", [])
            ocv_warn = res.stats.get("ocvalidate_warnings", [])
            log += "\n\n--- ocvalidate ---"
            if ocv_ok is None:
                log += "\n" + tr.t("build.log_ocv_skipped")
            elif ocv_ok:
                log += "\n" + tr.t("build.log_ocv_ok")
            else:
                log += "\n" + tr.t("build.log_ocv_problems").format(
                    errors=len(ocv_err), warnings=len(ocv_warn))
                for e in ocv_err[:25]:
                    log += f"\n  [err] {e}"
                for w in ocv_warn[:15]:
                    log += f"\n  [warn] {w}"
        self.build_log.setPlainText(log)
        self._manual_record = getattr(res, "stats", {}).get("community_record", "")
        if getattr(self, "manual_share_chk", None) is not None and self._manual_record:
            self._maybe_auto_share(self._manual_record)
        # --- объяснение решений ---
        self._render_rationale()
        self._sync_recovery_version(
            getattr(getattr(self, "_last_build_options", None), "target_macos", "") or "")
        # статус
        missing = (res.stats or {}).get("kexts_missing", []) or []
        if missing:
            self.statusBar().showMessage(
                tr.t("build.done_missing").format(list=", ".join(missing)), 8000)
        elif res.stats and res.stats.get("ocvalidate_ok") is False:
            self.statusBar().showMessage(
                tr.t("build.ocv_status_errors").format(
                    count=len(res.stats.get("ocvalidate_errors", []))), 6000)
        else:
            self.statusBar().showMessage(tr.t("build.done"), 4000)

    def _render_rationale(self):
        """Блок «Почему так собрано» по реально сгенерированному config.plist."""
        text = ""
        profile = getattr(self, "_last_build_profile", None) or self.profile
        if profile:
            try:
                from ..knowledge.rationale import explain, render
                decisions = explain(
                    profile,
                    getattr(self, "_last_build_options", None),
                    smbios=getattr(self, "_last_build_smbios", None),
                    lang=tr.current,
                )
                text = render(decisions)
            except Exception as e:
                text = f"rationale: {e}"
        self._rationale_text = text
        self.build_rationale.setPlainText(text)
        # Кнопка живая всегда, когда есть профиль: текст досчитается по клику,
        # иначе после перезапуска с сохранённым состоянием она оставалась серой.
        self.rationale_save_btn.setEnabled(bool(text.strip()) or bool(self.profile))

    def _save_rationale(self):
        """Сохраняет объяснение решений в выбранное пользователем место."""
        text = getattr(self, "_rationale_text", "") or ""
        if not text.strip():
            self._render_rationale()
            text = getattr(self, "_rationale_text", "") or ""
        if not text.strip():
            self.statusBar().showMessage(tr.t("build.rationale_empty"), 6000)
            return
        default = ""
        build_dir = getattr(self, "last_build_dir", None)
        if build_dir:
            default = str(Path(build_dir) / "REASONING.md")
        else:
            base = Path.home() / "Documents"
            default = str((base if base.is_dir() else Path.home()) / "HackicLab-reasoning.md")
        path, _ = QFileDialog.getSaveFileName(
            self, tr.t("build.rationale_save"), default,
            f"{tr.t('file.markdown')};;{tr.t('file.text')}")
        if not path:
            return
        try:
            Path(path).write_text(text, encoding="utf-8")
            self.statusBar().showMessage(tr.t("build.rationale_saved"), 5000)
        except OSError as e:
            QMessageBox.critical(self, tr.t("build.rationale"), str(e))

    def _build_failed(self, err):
        self.build_progress.setVisible(False)
        self._set_apple_progress(0)
        self.build_log.setPlainText(str(err))
        result = getattr(self, "manual_result", None)
        if result is not None:
            result.setText(str(err))
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
        self.an_empty_hint.setVisible(False)
        self._worker_an = AnalyzeWorker(self.profile, folder)
        self._worker_an.done.connect(self._analyze_done)
        self._worker_an.failed.connect(self._analyze_failed)
        self._worker_an.start()

    _SEV = {0: "ℹ", 1: "⚠", 2: "✖"}

    def _sev_color(self, severity: int) -> str:
        """Цвет серьёзности берётся из текущей темы, поэтому меняется вместе с ней."""
        level = {0: "muted", 1: "warn", 2: "err"}.get(int(severity), "muted")
        return tone(getattr(self, "_theme", "system"), level)[0]

    def _analyze_done(self, issues):
        self.an_progress.setVisible(False)
        self._issues = issues
        self.issue_list.clear()
        for iss in issues:
            icon = self._SEV.get(int(iss.severity), "ℹ")
            title = _issue_title(iss)
            it = QListWidgetItem(f"{icon} {title}")
            it.setData(Qt.ItemDataRole.UserRole, iss)
            it.setForeground(QColor(self._sev_color(int(iss.severity))))
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
        iss = cur.data(Qt.ItemDataRole.UserRole)
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
