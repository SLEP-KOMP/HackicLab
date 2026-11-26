"""Миксин WizardMixin: методы главного окна (wizard).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QCompleter,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QScrollArea,
    QWidget,
)

from ..builder import BuildOptions, BuildPlan
from ..i18n import tr
from ._common import _efi_root_for, _h2, _muted, _val
from ._workers import BuildWorker, ScanWorker, UsbListWorker
from .apple_progress import AppleProgressBar
from .hwview import hardware_rows


class WizardMixin:
    def _wiz_state(self) -> dict:
        state = getattr(self, "_wiz", None)
        if state is None:
            state = {
                "step": 0, "profile": None, "macos": "", "kind": "usb",
                "device": "", "folder": "", "mode": "full", "wifi": "itlwm",
"usb_toolbox": True, "dual_boot": "", "disable_dgpu": False,
                "gui_picker": False,
                "audio_dxe": False, "network_boot": False, "legacy_boot": False,
                "share_log": False, "smbios_model": "",
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
        self.wiz_stack.addWidget(self._wiz_scroll(self._wiz_step_options(page)))
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
    def _wiz_scroll(self, widget) -> QScrollArea:
        """Длинные шаги (параметры и порты) прокручиваются, а не обрезаются."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setWidget(widget)
        return area

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

        self.wiz_usb_chk = QCheckBox(tr.t("wizard.options.usb"))
        self.wiz_usb_chk.setChecked(True)
        self.wiz_usb_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("usb_toolbox", bool(on)))
        lay.addWidget(self.wiz_usb_chk)
        usb_note = _muted(page, tr.t("build.usb_toolbox_desc"))
        usb_note.setWordWrap(True)
        lay.addWidget(usb_note)

        # Порты выбираются на вкладке записи на USB: там же, где карта
        # реально попадает в EFI. В мастере дублировать пикер незачем.
        ports_note = _muted(page, tr.t("wizard.options.ports_hint"))
        ports_note.setWordWrap(True)
        lay.addWidget(ports_note)

        # Тема графического меню: те же карточки, что в ручной сборке.
        from .theme_cards import ThemeCards
        thint = _muted(page, tr.t("themes.hint")); thint.setWordWrap(True)
        lay.addWidget(thint)
        self.wiz_themes = ThemeCards(widget)
        self.wiz_themes.changed.connect(self._wiz_themes_changed)
        lay.addWidget(self.wiz_themes)

        self.wiz_dgpu_chk = QCheckBox(tr.t("wizard.options.dgpu"))
        self.wiz_dgpu_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("disable_dgpu", bool(on)))
        lay.addWidget(self.wiz_dgpu_chk)
        dgpu_note = _muted(page, tr.t("wizard.options.dgpu_desc"))
        dgpu_note.setWordWrap(True)
        lay.addWidget(dgpu_note)

        srow = QHBoxLayout()
        self.wiz_smbios = QComboBox()
        self.wiz_smbios.currentIndexChanged.connect(
            lambda _i: self._wiz_state().__setitem__(
                "smbios_model", str(self.wiz_smbios.currentData() or "")))
        self._wiz_fill_smbios()
        smb_label = QLabel(tr.t("manual.smbios"), page)
        smb_label.setObjectName("kv")
        smb_label.setMinimumWidth(150)
        srow.addWidget(smb_label)
        srow.addWidget(self.wiz_smbios, 1)
        lay.addLayout(srow)
        smb_note = _muted(page, tr.t("manual.smbios_desc"))
        smb_note.setWordWrap(True)
        lay.addWidget(smb_note)

        self.wiz_gui_chk = QCheckBox(tr.t("build.gui_picker"))
        self.wiz_gui_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("gui_picker", bool(on)))
        lay.addWidget(self.wiz_gui_chk)
        gui_note = _muted(page, tr.t("build.gui_picker_desc"))
        gui_note.setWordWrap(True)
        lay.addWidget(gui_note)

        for key, state_key in (("build.audio_dxe", "audio_dxe"),
                               ("build.network_boot", "network_boot"),
                               ("build.legacy_boot", "legacy_boot")):
            chk = QCheckBox(tr.t(key))
            chk.toggled.connect(
                lambda on, k=state_key: self._wiz_state().__setitem__(k, bool(on)))
            lay.addWidget(chk)
            note = _muted(page, tr.t(f"{key}_desc"))
            note.setWordWrap(True)
            lay.addWidget(note)

        self.wiz_share_chk = QCheckBox(tr.t("wizard.options.share"))
        self.wiz_share_chk.toggled.connect(
            lambda on: self._wiz_state().__setitem__("share_log", bool(on)))
        lay.addWidget(self.wiz_share_chk)
        share_note = _muted(page, tr.t("wizard.options.share_desc"))
        share_note.setWordWrap(True)
        lay.addWidget(share_note)
        lay.addStretch()
        return widget
    def _wiz_themes_changed(self):
        """Выбранные темы меню → состояние мастера (первая — по умолчанию)."""
        state = self._wiz_state()
        cards = getattr(self, "wiz_themes", None)
        chosen = sorted(cards.selection()) if cards is not None else []
        state["themes"] = set(chosen) or None
        state["picker_variant"] = chosen[0] if chosen else ""

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
        self.wiz_usb_chk.setChecked(bool(state.get("usb_toolbox", True)))
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
    def _wiz_fill_smbios(self):
        """Модели SMBIOS в мастере — под платформу выбранного железа."""
        combo = getattr(self, "wiz_smbios", None)
        if combo is None:
            return
        from ..knowledge import manual_hw
        state = self._wiz_state()
        profile = state.get("profile")
        current = str(state.get("smbios_model") or "")
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr.t("manual.smbios_auto"), "")
        if profile is not None:
            for model in manual_hw.smbios_options(profile):
                combo.addItem(model, model)
        index = combo.findData(current)
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

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
                 "Ventura", "Sonoma", "Sequoia", "Tahoe", "Golden Gate"]

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
            ver = str(entry.get("version") or "")
            btn = self._wiz_option(None, layout, "macos", name,
                                   f"{name} ({ver})" if ver else name, desc)
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
            chosen = str(state.get("smbios_model") or "")
            smbios = chosen or smbios_model_for(profile, state.get("macos") or "")
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
        self._wiz_fill_smbios()
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
            themes=state.get("themes"),
            picker_variant=str(state.get("picker_variant") or ""),
            custom_themes=dict(getattr(getattr(self, "wiz_themes", None),
                                       "custom_dirs", {}) or {}),
            menu_font=(self.wiz_themes.menu_font()
                       if hasattr(self, "wiz_themes") else ""),
            disable_sip=True,
            wifi_kext_mode=str(state.get("wifi") or "itlwm"),
            target_macos=str(state.get("macos") or ""),
            disable_dgpu=bool(state.get("disable_dgpu")),
            dual_boot=str(state.get("dual_boot") or ""),
            gui_picker=bool(state.get("gui_picker")),
            audio_dxe=bool(state.get("audio_dxe")),
            network_boot=bool(state.get("network_boot")),
            legacy_boot=bool(state.get("legacy_boot")),
            smbios_model=str(state.get("smbios_model") or ""),
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
