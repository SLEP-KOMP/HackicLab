"""UsbPortPicker: интерактивный выбор USB-портов с подсветкой лимита macOS.

Один и тот же виджет используется в мастере автосборки, в ручной сборке и на
отдельной вкладке «USB и накопители»: строит карту из DSDT/usbdump, показывает
порты по контроллерам, разъёмы и счётчик «N/15», красным — превышение.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..builder.usb_map import MAX_PORTS_PER_CONTROLLER, filter_ports, port_rows
from ..i18n import tr
from ._workers import UsbMapWorker

_CONNECTORS = {0: "usbmap.conn_usb2", 3: "usbmap.conn_usb3", 255: "usbmap.conn_internal"}
_WARN = QColor("#e5484d")
_MUTED = QColor("#8b93a1")


class UsbPortPicker(QWidget):
    """Выбор портов: чекбоксы по контроллерам, типы разъёмов, лимит 15."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plist = None
        self._worker = None
        self._busy = False

        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(8)
        row = QHBoxLayout()
        self.run_btn = QPushButton(tr.t("usbmap.run"))
        self.run_btn.clicked.connect(self.run)
        row.addWidget(self.run_btn)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        row.addWidget(self.summary, 1)
        v.addLayout(row)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr.t("usbmap.col_port"), tr.t("usbmap.col_type")])
        self.tree.setUniformRowHeights(True)
        self.tree.setMinimumHeight(200)
        self.tree.itemChanged.connect(self._on_item_changed)
        v.addWidget(self.tree, 1)

        self.status = QLabel(tr.t("usbmap.dsdt_note"))
        self.status.setWordWrap(True)
        v.addWidget(self.status)
        self.hint = QLabel(tr.t("usbmap.hint_types"))
        self.hint.setWordWrap(True)
        v.addWidget(self.hint)
        self.log = QPlainTextEdit(); self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.setPlaceholderText(tr.t("usbmap.log_hint"))
        v.addWidget(self.log)

    # --- данные ---

    def plist(self):
        return self._plist

    def selection(self) -> set:
        """Выбранные порты как набор пар (контроллер, имя порта)."""
        out = set()
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                child = group.child(j)
                data = child.data(0, Qt.ItemDataRole.UserRole)
                if data and child.checkState(0) == Qt.CheckState.Checked:
                    out.add(tuple(data))
        return out

    def filtered(self):
        """Карта только с выбранными портами (None, если карты нет)."""
        return filter_ports(self._plist, self.selection())

    def counts(self) -> dict:
        counts: dict[str, int] = {}
        for controller, _name in self.selection():
            counts[controller] = counts.get(controller, 0) + 1
        return counts

    def set_plist(self, plist, selected=None):
        """Показывает карту; ``selected`` — ранее выбранные порты."""
        self._plist = plist
        self._build_tree(selected)
        self.changed.emit()

    # --- построение дерева ---

    def _connector_text(self, row: dict) -> str:
        if not row.get("type_known", True):
            return tr.t("usbmap.conn_unknown")
        connector = row["connector"]
        key = _CONNECTORS.get(connector)
        return tr.t(key) if key else tr.t("usbmap.conn_other").format(type=connector)

    def _build_tree(self, selected=None):
        keep = set(selected) if selected else None
        self.tree.blockSignals(True)
        self.tree.clear()
        group = None
        current = None
        used: dict[str, int] = {}
        for row in port_rows(self._plist):
            controller = row["controller"]
            if controller != current:
                current = controller
                group = QTreeWidgetItem(self.tree, [controller, ""])
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                group.setData(0, Qt.ItemDataRole.UserRole, ("controller", controller))
            child = QTreeWidgetItem(group, [
                tr.t("usbmap.port_no").format(index=row["index"]),
                self._connector_text(row),
            ])
            if not row.get("type_known", True):
                # Пустой порт: тип неизвестен, не выдаём его за USB 2.0.
                for column in range(2):
                    child.setForeground(column, QBrush(_MUTED))
            child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            child.setData(0, Qt.ItemDataRole.UserRole, (controller, row["name"]))
            if keep is not None:
                checked = (controller, row["name"]) in keep
            else:
                # по умолчанию — первые 15 портов контроллера, как видит macOS
                checked = used.get(controller, 0) < MAX_PORTS_PER_CONTROLLER
                if checked:
                    used[controller] = used.get(controller, 0) + 1
            child.setCheckState(0, Qt.CheckState.Checked if checked
                                else Qt.CheckState.Unchecked)
        self.tree.expandAll()
        self.tree.blockSignals(False)
        self._recount()

    # --- реакции ---

    def _on_item_changed(self, item: QTreeWidgetItem, _column: int):
        if item.parent() is None:
            return  # заголовок контроллера не переключаем
        self._recount()

    def _recount(self):
        counts = self.counts()
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            controller = (group.data(0, Qt.ItemDataRole.UserRole) or ("", ""))[-1]
            count = counts.get(controller, 0)
            over = count > MAX_PORTS_PER_CONTROLLER
            group.setText(0, tr.t("usbmap.count").format(
                controller=controller, count=count,
                limit=MAX_PORTS_PER_CONTROLLER))
            brush = QBrush(_WARN) if over else QBrush()
            for column in range(2):
                group.setForeground(column, brush)
        self.tree.blockSignals(False)

        over = sorted(name for name, count in counts.items()
                      if count > MAX_PORTS_PER_CONTROLLER)
        if over:
            self.summary.setText(tr.t("usbmap.over_limit").format(
                controllers=", ".join(over), limit=MAX_PORTS_PER_CONTROLLER))
            self.summary.setProperty("tone", "err")
        else:
            self.summary.setText(tr.t("usbmap.found").format(
                ports=sum(counts.values()), controllers=len(counts)))
            self.summary.setProperty("tone", "ok")
        self.summary.style().unpolish(self.summary)
        self.summary.style().polish(self.summary)
        self.changed.emit()

    # --- запуск определения ---

    def run(self):
        if self._busy:
            return
        self._busy = True
        self.run_btn.setEnabled(False)
        self.status.setText(tr.t("usbmap.running"))
        self.log.setPlainText("")
        self._worker = UsbMapWorker(self)
        self._worker.done.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_done(self, plist, log_text: str):
        if log_text:
            self.log.setPlainText(log_text)
        if not plist:
            self.status.setText(tr.t("usbmap.none"))
            return
        self.set_plist(plist)
        self.status.setText(tr.t("usbmap.found").format(
            ports=sum(self.counts().values()),
            controllers=len(self.counts())))

    def _on_failed(self, err: str):
        self.status.setText(str(err))

    def _on_finished(self):
        self._busy = False
        self.run_btn.setEnabled(True)
