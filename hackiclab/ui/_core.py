"""Миксин CoreMixin: методы главного окна (core).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import uistate
from ..i18n import LANGS, tr
from ._common import COLUMN_MAX_WIDTH, _h1, _muted, install_qt_translator


class CoreMixin:
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
        self.page_ports = self._build_ports()
        self.page_usb = self._build_usb()
        self.page_sources = self._build_sources()
        self.page_donate = self._build_donate()
        self.page_settings = self._build_settings()
        self.page_about = self._build_about()
        for page in (self.page_auto, self.page_build,
                     self.page_validate, self.page_ports, self.page_usb, self.page_sources,
                     self.page_donate, self.page_settings, self.page_about):
            page.setObjectName("pageRoot")
            self.stack.addWidget(self._scroll_page(page))
        self._go_page(0)
    def _card(self, parent):
        w = QFrame(parent); w.setObjectName("card"); return w
    def _page_header(self, page, layout, title_key: str, subtitle_key: str | None = None):
        """Заголовок страницы: крупный заголовок и, если нужен, короткое пояснение."""
        head = QVBoxLayout()
        head.setSpacing(4)
        head.addWidget(_h1(page, tr.t(title_key)))
        if subtitle_key:
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
            "opt_gui": self.opt_gui.isChecked(),
            "macos": self.macos_combo.currentData(),
            "smbios_model": (str(self.manual_smbios.currentData() or "")
                             if hasattr(self, "manual_smbios") else ""),
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
        self.opt_gui.setChecked(bool(st.get("opt_gui")))
        if st["macos"]:
            i = self.macos_combo.findData(st["macos"])
            if i >= 0:
                self.macos_combo.setCurrentIndex(i)
        saved_smbios = str(st.get("smbios_model") or "")
        if saved_smbios and hasattr(self, "manual_smbios"):
            i = self.manual_smbios.findData(saved_smbios)
            if i >= 0:
                self.manual_smbios.setCurrentIndex(i)
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
