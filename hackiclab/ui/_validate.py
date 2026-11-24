"""Миксин ValidateMixin: методы главного окна (validate).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ._common import _h2, _has_cyrillic, _issue_title, _muted, _val
from ._workers import AuditWorker, ValidateWorker


class ValidateMixin:
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
        from ..knowledge.gpu_support import gpu_note
        from ..knowledge.wifi_bt import note_for as wifi_note
        lang = "en" if tr.current == "en" else "ru"
        notes = [wifi_note(getattr(p.net, "wifi_name", "") or "").get(lang, "")]
        gpu = getattr(p, "dgpu", None) or getattr(p, "igpu", None)
        if gpu is not None:
            notes.append(gpu_note(getattr(gpu, "vendor", ""),
                                  getattr(gpu, "device_id", "")).get(lang, ""))
        extra = [n for n in notes if n]
        if extra:
            self.val_hw_card.setVisible(True)
            for note in extra:
                self.val_hw_box.addWidget(_val(self.val_hw_card, note))
