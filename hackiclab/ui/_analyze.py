"""Миксин AnalyzeMixin: методы главного окна (analyze).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..themes import tone
from ._common import _h2, _has_cyrillic, _issue_title, _macos_newer, _muted, _val
from ._workers import AnalyzeWorker, OCLogWorker
from .hwview import hardware_rows


class AnalyzeMixin:
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
    def _on_macos_change(self):
        """Подсвечивает возможную несовместимость выбранной macOS-версии с железом."""
        target = self.macos_combo.currentData() or ""
        p = self.profile
        if not p:
            self.macos_incompat.setVisible(False)
            return
        from ..knowledge.oc_platforms import MAX_MACOS_BY_GEN
        max_ver = MAX_MACOS_BY_GEN.get(p.cpu.generation, "Sonoma")
        parts: list[str] = []
        if "unsupported" in max_ver.lower() or (target and target != max_ver and _macos_newer(target, max_ver)):
            parts.append(tr.t("build.macos_maybe_incompat"))
        if target and ("27" in str(target) or "golden gate" in str(target).lower()):
            parts.append(tr.t("build.macos27_warning"))
        dgpu = getattr(p, "dgpu", None)
        if dgpu is not None and str(getattr(dgpu, "vendor", "") or "").lower() == "nvidia":
            parts.append(tr.t("build.gpu_nvidia_warning"))
        txt = "\n".join(parts)
        self.macos_incompat.setText(txt)
        self.macos_incompat.setVisible(bool(txt))
    def _pick_build_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr.t("build.pick"))
        if d:
            self.build_dest.setText(d)
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
