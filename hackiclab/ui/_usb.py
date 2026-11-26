"""Миксин UsbMixin: методы главного окна (usb).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .. import uistate
from ..i18n import tr
from ._common import _h2, _muted, _val
from ._workers import UsbListWorker, USBWriteWorker
from .apple_progress import AppleProgressBar


class UsbMixin:
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
        saved_mode = self.usb_mode.findData(str(uistate.get("usb_mode", "full")))
        if saved_mode > 0:
            self.usb_mode.setCurrentIndex(saved_mode)
        mv.addWidget(self.usb_mode)
        self.usb_mode_desc = _muted(page, tr.t("usb.mode_full")); self.usb_mode_desc.setWordWrap(True)
        mv.addWidget(self.usb_mode_desc)
        self.usb_mode.currentIndexChanged.connect(self._usb_mode_change)
        self._usb_mode_change()

        # --- 3. Источник EFI ---
        src_card = self._card(page)
        sv = QVBoxLayout(src_card)
        srow = QHBoxLayout()
        srow.addWidget(_h2(page, tr.t("usb.source")))
        self.usb_source = QLabel("—"); self.usb_source.setObjectName("muted")
        self.usb_source.setWordWrap(True)
        # прошлый выбор источника переживает перезапуск, если папка на месте
        _src = str(uistate.get("usb_source", "") or "")
        if _src and ((Path(_src) / "EFI").is_dir() or (Path(_src) / "OC").is_dir()):
            self.usb_source.setText(_src)
        srow.addWidget(self.usb_source, 1)
        src_btn = QPushButton(tr.t("usb.browse_source"))
        src_btn.clicked.connect(self._pick_efi_source)
        srow.addWidget(src_btn)
        last_btn = QPushButton(tr.t("usb.source_last"))
        last_btn.setObjectName("ghost")
        last_btn.setToolTip(tr.t("usb.source_last_hint"))
        last_btn.clicked.connect(self._usb_source_last)
        srow.addWidget(last_btn)
        man_btn = QPushButton(tr.t("usb.make_manifest"))
        man_btn.setObjectName("ghost")
        man_btn.setToolTip(tr.t("usb.make_manifest_hint"))
        man_btn.clicked.connect(self._usb_make_manifest)
        srow.addWidget(man_btn)
        sv.addLayout(srow)
        src_hint = _muted(page, tr.t("usb.source_hint")); src_hint.setWordWrap(True)
        sv.addWidget(src_hint)
        self.usb_storage_warn = _muted(page, ""); self.usb_storage_warn.setWordWrap(True)
        sv.addWidget(self.usb_storage_warn)
        v.addWidget(src_card)
        v.addWidget(mode_card)

        # --- 3.5. macOS Recovery (полноценный установщик) ---
        rec_card = self._card(page)
        rcv = QVBoxLayout(rec_card)
        rec_row = QHBoxLayout()
        self.usb_recovery_chk = QCheckBox(tr.t("usb.include_recovery"))
        self.usb_recovery_chk.setChecked(bool(uistate.get("usb_recovery", True)))
        rec_row.addWidget(self.usb_recovery_chk)
        rec_row.addStretch()
        rcv.addLayout(rec_row)
        rec_desc = _muted(page, tr.t("usb.include_recovery_desc")); rec_desc.setWordWrap(True)
        rcv.addWidget(rec_desc)
        mist = QLabel('<a href="https://github.com/ninxsoft/Mist">Mist</a> — '
                      + tr.t("usb.mist_hint"))
        mist.setOpenExternalLinks(True)
        mist.setWordWrap(True)
        rcv.addWidget(mist)
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
        self.usb_recovery_ver.setEnabled(self.usb_recovery_chk.isChecked())
        v.addWidget(rec_card)

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

        # Что именно кладём в EFI на флешке: карту портов собираем здесь,
        # потому что она привязана к носителю и к моменту записи.
        map_row = QHBoxLayout()
        self.usb_map_chk = QCheckBox(tr.t("usb.map_chk"))
        self.usb_map_chk.setChecked(True)
        self.usb_map_chk.setToolTip(tr.t("usb.map_chk_hint"))
        map_row.addWidget(self.usb_map_chk)
        map_row.addStretch()
        v.addLayout(map_row)

        # --- Кнопки ---
        btn_row = QHBoxLayout()
        self.usb_write_btn = QPushButton(tr.t("usb.start"))
        self.usb_write_btn.clicked.connect(self._usb_start)
        btn_row.addWidget(self.usb_write_btn)
        self.usb_verify_btn = QPushButton(tr.t("usb.verify"))
        self.usb_verify_btn.setObjectName("ghost")
        self.usb_verify_btn.setToolTip(tr.t("usb.verify_hint"))
        self.usb_verify_btn.clicked.connect(self._usb_verify)
        btn_row.addWidget(self.usb_verify_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self.usb_verify_status = _muted(page, "")
        self.usb_verify_status.setWordWrap(True)
        v.addWidget(self.usb_verify_status)

        self.usb_progress = AppleProgressBar(); self.usb_progress.setMaximum(0); self.usb_progress.setVisible(False)
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
        self._usb_refresh_storage_warn()
    def _usb_mode_change(self):
        mode = self.usb_mode.currentData() or "full"
        key = {
            "full": "usb.mode_full",
            "formatted": "usb.mode_formatted",
            "repair": "usb.mode_repair",
        }.get(mode, "usb.mode_full")
        self.usb_mode_desc.setText(tr.t(key))
        uistate.save(usb_mode=mode)
    def _usb_recovery_toggle(self, on: bool):
        self.usb_recovery_ver.setEnabled(bool(on))
        uistate.save(usb_recovery=bool(on))
    def _pick_efi_source(self):
        d = QFileDialog.getExistingDirectory(self, tr.t("usb.source"))
        if d:
            self.usb_source.setText(d)
            uistate.save(usb_source=d)
    def _usb_start(self):
        """Проверка входных данных и запуск подтверждения."""
        # Сканирование для записи готовой EFI не нужно: источник — папка с EFI.
        src = self.usb_source.text().strip()
        if not src or src == "—" or not Path(src).is_dir():
            QMessageBox.warning(self, tr.t("usb.title"), tr.t("usb.need_source"))
            return
        idx = self.usb_combo.currentIndex()
        if idx < 0 or not getattr(self, "usb_devices", None):
            QMessageBox.warning(self, tr.t("usb.title"), tr.t("usb.no_devices"))
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

        # Проверки перед записью: объём флешки и версия установщика.
        notes = []
        try:
            import re as _re
            match = _re.search(r"([\d.,]+)", getattr(dev, "size", "") or "")
            gb = float(match.group(1).replace(",", ".")) if match else 0.0
        except (TypeError, ValueError):
            gb = 0.0
        recovery_on = bool(self.usb_recovery_chk.isChecked())
        if recovery_on and 0 < gb < 8:
            notes.append(tr.t("usb.warn_small_stick").format(
                size=getattr(dev, "size", "") or "?"))
        build_target = (self.macos_combo.currentData() or "") if hasattr(
            self, "macos_combo") else ""
        recovery_ver = (self.usb_recovery_ver.currentData() or "") if hasattr(
            self, "usb_recovery_ver") else ""
        if recovery_on and build_target and recovery_ver and \
                build_target not in recovery_ver and recovery_ver not in build_target:
            notes.append(tr.t("usb.warn_recovery_mismatch").format(
                build=build_target, recovery=recovery_ver))
        if notes:
            warn_box = _val(dlg, "\n".join("⚠  " + n for n in notes))
            warn_box.setObjectName("warn")
            warn_box.setWordWrap(True)
            dlgv.addWidget(warn_box)

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
            self._usb_run(device, mode, planned,
                          make_usb_map=self.usb_map_chk.isChecked())

    def _usb_source_last(self):
        """Берёт папку последней сборки как источник EFI."""
        last = getattr(self, "last_build_dir", None)
        if not last:
            self.usb_verify_status.setText(tr.t("usb.source_last_none"))
            return
        self.usb_source.setText(str(last))
        uistate.save(usb_source=str(last))
        self._usb_refresh_storage_warn()

    def _usb_make_manifest(self):
        """Пишет манифест целостности в чужой EFI, чтобы работала проверка."""
        from ..builder.integrity_manifest import write_manifest

        src = Path(self.usb_source.text())
        root = None
        if src.is_dir():
            if (src / "OC").is_dir():
                root = src
            elif (src / "EFI" / "OC").is_dir():
                root = src / "EFI"
        if root is None:
            self.usb_verify_status.setText(tr.t("usb.make_manifest_no_efi"))
            return
        path = write_manifest(root)
        self.usb_verify_status.setText(
            tr.t("usb.make_manifest_ok").format(path=path) if path
            else tr.t("usb.make_manifest_fail"))

    def _usb_refresh_storage_warn(self):
        """Предупреждения о накопителе — в одном месте, на записи."""
        label = getattr(self, "usb_storage_warn", None)
        if label is None:
            return
        profile = getattr(self, "profile", None) or getattr(self, "manual_profile", None)
        storage = getattr(profile, "storage", None) if profile is not None else None
        if storage is None:
            label.setText("")
            return
        from ..knowledge.storage_support import warnings as storage_warnings

        lines = storage_warnings(storage, tr.current)
        label.setText("\n".join(f"⚠ {line}" for line in lines))

    def _usb_selected_device(self):
        """Объект выбранной флешки из последнего списка устройств."""
        data = self.usb_combo.currentData() if hasattr(self, "usb_combo") else None
        if not data:
            return None
        return next((x for x in getattr(self, "usb_devices", [])
                     if x.device == data), None)

    def _usb_verify(self):
        """Сверяет записанную флешку с манифестом сборки."""
        from ..builder.integrity_manifest import verify_manifest

        dev = self._usb_selected_device()
        if dev is None:
            self.usb_verify_status.setText(tr.t("usb.verify_need_device"))
            return
        letter = (getattr(self, "_usb_last_letter", "")
                  or getattr(dev, "letter", "") or "")
        root = Path(f"{letter}:\\EFI") if letter and letter != "RAW" else None
        if root is None or not (root / "OC" / "config.plist").is_file():
            self.usb_verify_status.setText(tr.t("usb.verify_no_efi"))
            return
        report = verify_manifest(root)
        if report is None:
            self.usb_verify_status.setText(tr.t("usb.verify_no_manifest"))
        elif report.ok:
            self.usb_verify_status.setText(
                tr.t("usb.verify_ok").format(count=report.checked))
        else:
            self.usb_verify_status.setText(
                tr.t("usb.verify_bad").format(count=report.drift))

    def _usb_run(self, device: str, mode: str, planned_letter: str = "",
                 make_usb_map: bool = False):
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
        # буква после записи нужна «Проверить флешку»: у RAW-флешки её ещё нет
        self._usb_last_letter = (target_letter or "").rstrip(":")
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
