"""Миксин BuildPageMixin: методы главного окна (build).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import uistate
from ..builder import BuildOptions, BuildPlan
from ..i18n import tr
from ..knowledge import manual_hw
from ._common import _efi_root_for, _h2, _muted, _val
from ._workers import BuildWorker
from .apple_progress import AppleProgressBar


class BuildPageMixin:
    def _build_build(self):
        page = QWidget()
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
            audio_dxe=self.opt_audio.isChecked(),
            network_boot=self.opt_netboot.isChecked(),
            legacy_boot=self.opt_legacy.isChecked(),
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
