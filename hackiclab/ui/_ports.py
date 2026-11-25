"""Миксин PortsMixin: карта USB-портов с выбором и карта дисков.

Отдельная вкладка: карта портов нужна при настройке EFI, а не при записи
флешки, поэтому из «Записи на USB» она убрана.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..builder.usb_map import MAX_PORTS_PER_CONTROLLER, port_rows
from ..i18n import tr
from ._common import _h2, _muted
from ._workers import DiskMapWorker, UsbMapWorker

_CONNECTOR_KEYS = {0: "usbmap.conn_usb2", 3: "usbmap.conn_usb3", 255: "usbmap.conn_internal"}


class PortsMixin:
    def _build_ports(self):
        """Вкладка «Порты и диски»: карта USB с выбором портов и карта дисков."""
        page = QWidget()
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "usbmap.title", "usbmap.subtitle")

        limit_card = self._card(page)
        lv = QVBoxLayout(limit_card)
        lv.addWidget(_h2(page, tr.t("usbmap.limit_title")))
        limit_text = _muted(page, tr.t("usbmap.limit_text")); limit_text.setWordWrap(True)
        lv.addWidget(limit_text)
        v.addWidget(limit_card)

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

        self.ports_list = QListWidget()
        self.ports_list.setMinimumHeight(180)
        self.ports_list.setMaximumHeight(320)
        self.ports_list.itemChanged.connect(self._ports_recount)
        pv.addWidget(self.ports_list)
        self.ports_count = _muted(page, "")
        self.ports_count.setWordWrap(True)
        pv.addWidget(self.ports_count)

        self.usbmap_log = QPlainTextEdit(); self.usbmap_log.setReadOnly(True)
        self.usbmap_log.setPlaceholderText(tr.t("usbmap.log_hint"))
        self.usbmap_log.setMaximumHeight(110)
        pv.addWidget(self.usbmap_log)
        v.addWidget(ports_card)

        disk_card = self._card(page)
        dv = QVBoxLayout(disk_card)
        dv.addWidget(_h2(page, tr.t("storage.title")))
        sdesc = _muted(page, tr.t("storage.desc")); sdesc.setWordWrap(True)
        dv.addWidget(sdesc)
        # Известные проблемы накопителя: те же правила, что в предупреждениях сборки.
        self.storage_warn = _muted(page, ""); self.storage_warn.setWordWrap(True)
        dv.addWidget(self.storage_warn)
        drow = QHBoxLayout()
        self.disk_scan_btn = QPushButton(tr.t("storage.scan"))
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
        self._refresh_storage_notes()
        return page

    def _refresh_storage_notes(self, *_args):
        """Предупреждения о накопителе для вкладки «USB и накопители»."""
        if not hasattr(self, "storage_warn"):
            return
        from ..knowledge.storage_support import warnings as storage_warnings
        profile = getattr(self, "profile", None)
        storage = getattr(profile, "storage", None) if profile is not None else None
        lines = storage_warnings(storage, tr.current) if storage is not None else []
        self.storage_warn.setText("\n".join(f"⚠ {line}" for line in lines)
                                  or tr.t("storage.none"))

    # --- карта USB-портов ---

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
            self.ports_list.clear()
            self.ports_count.setText("")
            self.usbmap_status.setText(tr.t("usbmap.none"))
            self.ports_save_btn.setEnabled(False)
            return
        rows = port_rows(plist)
        self._ports_render(rows)
        self.usbmap_status.setText(tr.t("usbmap.found").format(
            ports=len(rows), controllers=len({r["controller"] for r in rows})))

    def _ports_render(self, rows: list):
        """Строки портов с флажками; сверх лимита выключены заранее."""
        enabled: dict[str, int] = {}
        self.ports_list.blockSignals(True)
        self.ports_list.clear()
        current = None
        for row in rows:
            controller = row["controller"]
            if controller != current:
                current = controller
                head = QListWidgetItem(tr.t("usbmap.controller").format(name=controller))
                head.setFlags(Qt.ItemFlag.NoItemFlags)
                self.ports_list.addItem(head)
            item = QListWidgetItem(self._ports_label(row))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            used = enabled.get(controller, 0)
            item.setCheckState(
                Qt.CheckState.Checked if used < MAX_PORTS_PER_CONTROLLER
                else Qt.CheckState.Unchecked)
            if item.checkState() == Qt.CheckState.Checked:
                enabled[controller] = used + 1
            item.setData(Qt.ItemDataRole.UserRole, (controller, row["name"]))
            self.ports_list.addItem(item)
        self.ports_list.blockSignals(False)
        self._ports_recount()

    def _ports_label(self, row: dict) -> str:
        key = _CONNECTOR_KEYS.get(row["connector"])
        connector = tr.t(key) if key else tr.t("usbmap.conn_other").format(
            type=row["connector"])
        return f"{row['name']} · {tr.t('usbmap.port_no').format(index=row['index'])} · {connector}"

    def _ports_selection(self) -> set:
        selected = set()
        for i in range(self.ports_list.count()):
            item = self.ports_list.item(i)
            data = item.data(Qt.ItemDataRole.UserRole)
            if data and item.checkState() == Qt.CheckState.Checked:
                selected.add(tuple(data))
        return selected

    def _ports_counts(self) -> dict:
        counts: dict[str, int] = {}
        for controller, _name in self._ports_selection():
            counts[controller] = counts.get(controller, 0) + 1
        return counts

    def _ports_recount(self, *_args):
        counts = self._ports_counts()
        lines = [tr.t("usbmap.count").format(
            controller=name, count=count, limit=MAX_PORTS_PER_CONTROLLER)
            for name, count in sorted(counts.items())]
        over = [name for name, count in counts.items()
                if count > MAX_PORTS_PER_CONTROLLER]
        if over:
            lines.append(tr.t("usbmap.over_limit").format(
                controllers=", ".join(sorted(over)), limit=MAX_PORTS_PER_CONTROLLER))
        self.ports_count.setText("\n".join(lines))
        self.ports_count.setObjectName("warn" if over else "muted")
        self.ports_count.style().unpolish(self.ports_count)
        self.ports_count.style().polish(self.ports_count)
        self.ports_save_btn.setEnabled(
            bool(getattr(self, "_usbmap_plist", None)) and not over and bool(counts))

    def _usbmap_failed(self, err: str):
        self.usbmap_status.setText(str(err))

    def _save_usbmap(self):
        plist = getattr(self, "_usbmap_plist", None)
        if not plist:
            QMessageBox.information(self, tr.t("usbmap.ports_title"),
                                    tr.t("usbmap.need_map"))
            return
        from ..builder.usb_map import filter_ports

        selected = filter_ports(plist, self._ports_selection())
        if selected is None:
            QMessageBox.information(self, tr.t("usbmap.ports_title"),
                                    tr.t("usbmap.no_selection"))
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
            out = write_map_kext(selected, kexts)
        except Exception as e:
            QMessageBox.critical(self, tr.t("usbmap.ports_title"), str(e))
            return
        self.usbmap_status.setText(tr.t("usbmap.saved").format(path=out))

    # --- карта дисков (только чтение) ---

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
