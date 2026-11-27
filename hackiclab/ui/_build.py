"""Миксин BuildPageMixin: методы главного окна (build).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .. import uistate
from ..builder import BuildOptions, BuildPlan
from ..i18n import tr
from ..knowledge import manual_hw
from ._common import _efi_root_for, _h2, _muted, _val
from ._workers import BuildWorker, KextUpdateWorker
from .apple_progress import AppleProgressBar
from .theme_cards import ThemeCards


class BuildPageMixin:
    def _build_build(self):
        page = QWidget()
        self._build_page = page
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "build.title")
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

        main = QVBoxLayout(); main.setSpacing(12)
        v.addLayout(main, 1)

        # options with description cards
        gb = QGroupBox(tr.t("build.options"))
        opts = QVBoxLayout(gb)
        self.opt_usb = QCheckBox(tr.t("build.usb_toolbox")); self.opt_usb.setChecked(True)
        usb_desc = _muted(page, tr.t("build.usb_toolbox_desc")); usb_desc.setWordWrap(True)
        opts.addWidget(self.opt_usb)
        opts.addWidget(usb_desc)
        # Накопитель и порты проверяются на вкладках диагностики и записи —
        # чтобы не было двух разных списков предупреждений.
        ports_note = _muted(page, tr.t("build.ports_hint"))
        ports_note.setWordWrap(True)
        opts.addWidget(ports_note)
        opts.addSpacing(8)
        self.opt_sip = QCheckBox(tr.t("build.disable_sip"))
        self.opt_sip.setChecked(True)
        sip_desc = _muted(page, tr.t("build.sip_desc")); sip_desc.setWordWrap(True)
        opts.addWidget(self.opt_sip)
        opts.addWidget(sip_desc)
        sbm_row = QHBoxLayout()
        sbm_row.addWidget(_val(page, tr.t("build.secure_boot_model")))
        self.build_sbm = QComboBox()
        self.build_sbm.addItem(tr.t("build.sbm_disabled"), "Disabled")
        self.build_sbm.addItem(tr.t("build.sbm_default"), "Default")
        sbm_row.addWidget(self.build_sbm, 1)
        opts.addLayout(sbm_row)
        sbm_desc = _muted(page, tr.t("build.sbm_desc")); sbm_desc.setWordWrap(True)
        opts.addWidget(sbm_desc)
        opts.addSpacing(8)

        # Свои boot-args: часть плат AMD без npci=0x2000 не стартует,
        # а AMD GPU теряет ускорение без unfairgva=1.
        ba_row = QHBoxLayout()
        ba_row.addWidget(_val(page, tr.t("build.boot_args")))
        self.build_boot_args = QLineEdit()
        self.build_boot_args.setPlaceholderText(tr.t("build.boot_args_hint"))
        self.build_boot_args.setText(str(uistate.get("build_boot_args", "") or ""))
        ba_row.addWidget(self.build_boot_args, 1)
        for label_key, flag in (
                ("build.boot_args_preset_npci", "npci=0x2000"),
                ("build.boot_args_preset_gva", "unfairgva=1"),
        ):
            preset = QPushButton(tr.t(label_key))
            preset.setObjectName("ghost")
            preset.clicked.connect(
                lambda _=False, f=flag: self._add_boot_arg(f))
            ba_row.addWidget(preset)
        opts.addLayout(ba_row)
        ba_desc = _muted(page, tr.t("build.boot_args_desc")); ba_desc.setWordWrap(True)
        opts.addWidget(ba_desc)
        opts.addSpacing(8)
        self.opt_gui = QCheckBox(tr.t("build.gui_picker"))
        gui_desc = _muted(page, tr.t("build.gui_picker_desc")); gui_desc.setWordWrap(True)
        opts.addWidget(self.opt_gui)
        opts.addWidget(gui_desc)
        theme_hint = _muted(page, tr.t("themes.hint")); theme_hint.setWordWrap(True)
        opts.addWidget(theme_hint)
        self.build_themes = ThemeCards(page)
        opts.addWidget(self.build_themes)
        opts.addSpacing(8)
        self.opt_audio = QCheckBox(tr.t("build.audio_dxe"))
        audio_desc = _muted(page, tr.t("build.audio_dxe_desc")); audio_desc.setWordWrap(True)
        opts.addWidget(self.opt_audio)
        opts.addWidget(audio_desc)
        opts.addSpacing(8)
        self.opt_netboot = QCheckBox(tr.t("build.network_boot"))
        net_desc = _muted(page, tr.t("build.network_boot_desc")); net_desc.setWordWrap(True)
        opts.addWidget(self.opt_netboot)
        opts.addWidget(net_desc)
        opts.addSpacing(8)
        self.opt_legacy = QCheckBox(tr.t("build.legacy_boot"))
        legacy_desc = _muted(page, tr.t("build.legacy_boot_desc")); legacy_desc.setWordWrap(True)
        opts.addWidget(self.opt_legacy)
        opts.addWidget(legacy_desc)
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

        # macOS version selection
        mb = QGroupBox(tr.t("build.macos"))
        mv = QVBoxLayout(mb)
        mrow = QHBoxLayout()
        self.macos_combo = QComboBox()
        from ..knowledge.oc_platforms import MACOS_VERSIONS
        self.macos_combo.addItem(tr.t("build.macos_auto"), "")
        for mver in MACOS_VERSIONS:
            # номер версии в подписи: по «15» ориентироваться проще, чем по имени
            self.macos_combo.addItem(
                f"{mver['name']} ({mver['version']})", mver["name"])
        # пометим подсказкой о возможной несовместимости (tooltip)
        mrow.addWidget(self.macos_combo, 1)
        mv.addLayout(mrow)
        mac_desc = _muted(page, tr.t("build.macos_desc")); mac_desc.setWordWrap(True)
        mv.addWidget(mac_desc)
        self.macos_incompat = _muted(page, ""); self.macos_incompat.setWordWrap(True)
        self.macos_incompat.setObjectName("warn")
        self.macos_incompat.setVisible(False)
        mv.addWidget(self.macos_incompat)
        # Диапазон macOS под железо: минимум, потолок и рекомендация с причинами в подсказке.
        self.macos_range = _muted(page, ""); self.macos_range.setWordWrap(True)
        mv.addWidget(self.macos_range)
        self.macos_combo.currentIndexChanged.connect(self._on_macos_change)
        self.macos_combo.currentIndexChanged.connect(
            lambda _i: self._refresh_patches())
        # обзор шага 1 считает совместимость по той же версии, что пойдёт в сборку
        self.macos_combo.currentIndexChanged.connect(
            lambda _i: self._manual_refresh())
        # macOS — до опций: от версии зависят SMBIOS, патчи и кексты,
        # поэтому её логично выбрать первой.
        main.addWidget(mb)
        main.addWidget(gb)

        # Патчи: что применить к EFI и что — уже на macOS (root-патчи)
        pb = QGroupBox(tr.t("patches.title"))
        pv = QVBoxLayout(pb)
        phint = _muted(page, tr.t("patches.hint")); phint.setWordWrap(True)
        pv.addWidget(phint)
        prow = QHBoxLayout()
        self.patch_auto = QRadioButton(tr.t("patches.auto"))
        self.patch_auto.setChecked(True)
        self.patch_manual = QRadioButton(tr.t("patches.manual"))
        prow.addWidget(self.patch_auto)
        prow.addWidget(self.patch_manual)
        prow.addStretch()
        self.patch_refresh_btn = QPushButton(tr.t("patches.refresh"))
        self.patch_refresh_btn.setObjectName("ghost")
        self.patch_refresh_btn.clicked.connect(self._refresh_patches)
        prow.addWidget(self.patch_refresh_btn)
        pv.addLayout(prow)
        self.patch_list = QVBoxLayout()
        pv.addLayout(self.patch_list)
        pv.addWidget(_h2(page, tr.t("patches.report")))
        self.patch_report = QPlainTextEdit()
        self.patch_report.setReadOnly(True)
        self.patch_report.setMinimumHeight(150)
        pv.addWidget(self.patch_report)
        self.patch_copy_btn = QPushButton(tr.t("patches.copy"))
        self.patch_copy_btn.setObjectName("ghost")
        self.patch_copy_btn.clicked.connect(self._copy_patch_report)
        pv.addWidget(self.patch_copy_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.patch_auto.toggled.connect(lambda _on: self._refresh_patches())
        main.addWidget(pb)
        self._refresh_patches()

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
        self.kext_upd_btn = QPushButton(tr.t("build.kext_updates"))
        self.kext_upd_btn.setObjectName("ghost")
        self.kext_upd_btn.setToolTip(tr.t("build.kext_updates_desc"))
        self.kext_upd_btn.clicked.connect(self._check_kext_updates)
        build_row.addWidget(self.kext_upd_btn)
        build_row.addStretch()
        main.addLayout(build_row)

        self.manual_result = _val(page, "")
        self.manual_result.setWordWrap(True)
        main.addWidget(self.manual_result)

        self.build_progress = AppleProgressBar(); self.build_progress.setMaximum(0)
        self.build_progress.setVisible(False)
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
    def _add_boot_arg(self, flag: str):
        """Добавляет флаг в поле boot-args без дублей."""
        current = self.build_boot_args.text().split()
        if flag not in current:
            current.append(flag)
        self.build_boot_args.setText(" ".join(current))

    def _resolved_profile(self):
        """Профиль сборки: ручной выбор + UEFI-пути из последнего сканирования."""
        from ..knowledge import patches as patch_kb
        profile = getattr(self, "manual_profile", None) or manual_hw.build_profile(
            self._manual_selection())
        return patch_kb.merge_scan_paths(profile, getattr(self, "profile", None))

    def _patch_items(self):
        """План патчей для текущего профиля и целевой macOS."""
        from ..knowledge import patches as patch_kb
        try:
            profile = self._resolved_profile()
        except Exception:
            profile = None
        target = self.macos_combo.currentData() or ""
        if profile is None:
            return patch_kb, [], None, target
        return patch_kb, patch_kb.plan(profile, target), profile, target

    def _patch_ids(self):
        """None — «Авто» (всё нужное), иначе набор отмеченных id."""
        if getattr(self, "patch_auto", None) is not None and self.patch_auto.isChecked():
            return None
        return {i for i, cb in getattr(self, "_patch_checks", {}).items() if cb.isChecked()}

    def _refresh_mac_range(self):
        """Подпись с диапазоном macOS под железо; причины — в подсказке."""
        if not hasattr(self, "macos_range") or not hasattr(self, "macos_combo"):
            return
        from ..knowledge.mac_range import label, mac_range
        try:
            profile = self._resolved_profile()
        except Exception:
            profile = None
        if profile is None:
            self.macos_range.setText("")
            self.macos_range.setToolTip("")
            return
        rng = mac_range(profile, self.macos_combo.currentData() or "")
        self.macos_range.setText(tr.t("build.range").format(
            recommended=label(rng.recommended),
            lowest=label(rng.lowest),
            highest=label(rng.highest)))
        pick = 0 if tr.current == "ru" else 1
        self.macos_range.setToolTip("\n".join(r[pick] for r in rng.reasons))

    def _refresh_patches(self):
        """Пересобирает список патчей и отчёт под железо/язык/режим."""
        # Сборка страницы идёт по шагам: ручная форма обновляется раньше, чем
        # появляются список macOS и сами виджеты патчей. Без этой проверки
        # первый вызов падал и список оставался пустым до «Обновить список».
        if not hasattr(self, "patch_list") or not hasattr(self, "macos_combo"):
            return
        kb, items, profile, target = self._patch_items()
        while self.patch_list.count():
            w = self.patch_list.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        self._patch_checks = {}
        manual = not self.patch_auto.isChecked()
        if not items:
            self.patch_list.addWidget(_muted(self._build_page, tr.t("patches.empty")))
        for p in items:
            cb = QCheckBox(p.title(tr.current))
            cb.setToolTip(p.detail(tr.current))
            cb.setChecked(p.auto)
            cb.setEnabled(manual)
            cb.toggled.connect(lambda _on: self._render_patch_report())
            self.patch_list.addWidget(cb)
            self._patch_checks[p.id] = cb
        self._render_patch_report()
        self._refresh_mac_range()

    def page_build_owner(self):
        """Родитель для виджетов патчей (первая найденная страница)."""
        return self.build_log if hasattr(self, "build_log") else self

    def _render_patch_report(self):
        kb, items, profile, target = self._patch_items()
        if profile is None:
            self.patch_report.setPlainText("")
            return
        self.patch_report.setPlainText(
            kb.report(profile, target, self._patch_ids(), tr.current))

    def _copy_patch_report(self):
        QApplication.clipboard().setText(self.patch_report.toPlainText())
        self.manual_result.setText(tr.t("patches.copied"))

    def _do_build(self):
        if getattr(self, "_worker_build", None) and self._worker_build.isRunning():
            return
        uistate.save(build_boot_args=self.build_boot_args.text().strip())
        dest = (self.build_dest.text() or "").strip()
        if dest in ("", "—"):
            self._pick_build_dir()
            dest = (self.build_dest.text() or "").strip()
            if dest in ("", "—"):
                QMessageBox.warning(self, "HackicLab", tr.t("build.pick"))
                return
        profile = self._resolved_profile()
        theme_sel = sorted(self.build_themes.selection()) if hasattr(
            self, "build_themes") else []
        opts = BuildOptions(
            usb_toolbox=self.opt_usb.isChecked(),
            themes=set(theme_sel) or None,
            picker_variant=theme_sel[0] if theme_sel else "",
            custom_themes=dict(getattr(self.build_themes, "custom_dirs", {}) or {}),
            menu_font=(self.build_themes.menu_font()
                       if hasattr(self, "build_themes") else ""),
            disable_sip=self.opt_sip.isChecked(),
            gui_picker=self.opt_gui.isChecked(),
            audio_dxe=self.opt_audio.isChecked(),
            network_boot=self.opt_netboot.isChecked(),
            legacy_boot=self.opt_legacy.isChecked(),
            wifi_kext_mode=self.wifi_mode.currentData() or "itlwm",
            target_macos=self.macos_combo.currentData() or "",
            smbios_model=getattr(getattr(self, "manual_smbios", None),
                                 "currentData", lambda: "")() or "",
            boot_args=self.build_boot_args.text().strip(),
            secure_boot_model=self.build_sbm.currentData() or "Disabled",
            patches=self._patch_ids(),
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
        self.statusBar().showMessage(message, 4000)
    def _build_done(self, res):
        self.build_progress.setValue(100)
        self.build_progress.setVisible(False)
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
    def _check_kext_updates(self):
        """Сверяет кексты собранного EFI с последними релизами GitHub."""
        worker = getattr(self, "_worker_kext_upd", None)
        if worker is not None and worker.isRunning():
            return
        root = getattr(self, "last_build_dir", None)
        if not root:
            self.statusBar().showMessage(tr.t("build.ku_need_efi"), 6000)
            return
        self.kext_upd_btn.setEnabled(False)
        self.statusBar().showMessage(tr.t("build.ku_running"), 0)
        self._worker_kext_upd = KextUpdateWorker(Path(root))
        self._worker_kext_upd.done.connect(self._kext_updates_done)
        self._worker_kext_upd.failed.connect(self._kext_updates_failed)
        self._worker_kext_upd.start()

    def _kext_updates_done(self, states):
        self.kext_upd_btn.setEnabled(True)
        updates = [s for s in states if s.status == "update"]
        message = (tr.t("build.ku_done").format(updates=len(updates),
                                               total=len(states))
                   if updates else tr.t("build.ku_none").format(total=len(states)))
        lines = [message]
        for state in states:
            if state.status == "update":
                lines.append("  ↑ " + tr.t("build.ku_line").format(
                    name=state.name, installed=state.installed,
                    latest=state.latest))
            elif state.status == "ok":
                lines.append("  ✓ " + tr.t("build.ku_ok").format(
                    name=state.name, version=state.installed))
            else:
                lines.append("  ? " + tr.t("build.ku_unknown").format(
                    name=state.name))
        self.build_log.appendPlainText("\n" + "\n".join(lines))
        self.statusBar().showMessage(message, 8000)

    def _kext_updates_failed(self, error):
        self.kext_upd_btn.setEnabled(True)
        self.statusBar().showMessage(
            tr.t("build.ku_failed").format(err=error), 8000)

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
        self.build_log.setPlainText(str(err))
        result = getattr(self, "manual_result", None)
        if result is not None:
            result.setText(str(err))
        QMessageBox.critical(self, tr.t("build.title"), str(err))
