"""Миксин PortsMixin: вкладка «USB и накопители».

USB-карту строит общий виджет UsbPortPicker (тот же, что в мастере сборки):
порты по контроллерам, типы разъёмов, счётчик N/15 с подсветкой лимита.
Накопители: известные проблемы диска + карта дисков (только чтение).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ._common import _h2, _muted
from ._workers import DiskMapWorker
from .usb_picker import UsbPortPicker


class PortsMixin:
    def _build_ports(self):
        """Вкладка «USB и накопители»: отдельный инструмент карты USB и диски."""
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
        self.ports_picker = UsbPortPicker(page)
        pv.addWidget(self.ports_picker)
        prow = QHBoxLayout()
        self.ports_save_btn = QPushButton(tr.t("usbmap.save"))
        self.ports_save_btn.setObjectName("ghost")
        self.ports_save_btn.clicked.connect(self._save_usbmap)
        prow.addWidget(self.ports_save_btn)
        prow.addStretch()
        pv.addLayout(prow)
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

    def _save_usbmap(self):
        plist = self.ports_picker.filtered()
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
        self.ports_picker.status.setText(tr.t("usbmap.saved").format(path=out))

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
