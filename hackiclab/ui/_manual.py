"""Миксин ManualBuildMixin: методы главного окна (manual).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..knowledge import manual_hw
from ._common import _h2, _val


class ManualBuildMixin:
    def _manual_from_scan(self) -> None:
        """Заполняет ручную форму железом из последнего сканирования."""
        profile = getattr(self, "profile", None)
        if profile is None:
            self.statusBar().showMessage(tr.t("manual.need_scan"), 6000)
            return
        cpu = getattr(profile, "cpu", None)
        vendor = (getattr(cpu, "vendor", "") or "").lower()
        generation = int(getattr(cpu, "generation", 0) or 0)
        laptop = profile.platform == "laptop"
        self.manual_laptop.setChecked(laptop)
        self.manual_cores.setValue(max(2, min(64, int(getattr(cpu, "core_count", 0) or getattr(cpu, "cores", 4) or 4))))
        if vendor == "amd":
            key = f"amd-zen{generation - 8 if generation > 8 else 1}d"
            if generation == 10:
                key = "amd-zen2d"
            elif generation == 11:
                key = "amd-zen3d"
            elif generation == 12:
                key = "amd-zen4d"
            key = key.replace("d", "m") if laptop else key
            if not self._select_data(self.manual_cpu, key):
                self._select_data(self.manual_cpu, "amd-zen2d")
        elif vendor == "intel":
            key = f"intel-{min(generation, 10)}{'m' if laptop else 'd'}"
            if generation >= 10 and not laptop:
                key = "intel-10d"
            if not self._select_data(self.manual_cpu, key):
                self._select_data(self.manual_cpu, "intel-8d")

        gpu = getattr(profile, "dgpu", None) or getattr(profile, "igpu", None)
        gpu_key = ""
        if gpu is not None:
            vendor_gpu = (getattr(gpu, "vendor", "") or "").lower()
            device = (getattr(gpu, "device_id", "") or "").lower().replace("0x", "")
            if vendor_gpu in ("amd", "nvidia"):
                # сначала точный device-id (RX 580 2048SP), потом общий вендор
                gpu_key = device if device and self.manual_gpu.findData(device) >= 0 \
                    else vendor_gpu
            elif device and self.manual_gpu.findData(device) >= 0:
                gpu_key = device
        if gpu_key:
            self._select_data(self.manual_gpu, gpu_key)

        audio = getattr(profile, "audio", None)
        if audio is not None and getattr(audio, "codec", ""):
            self.manual_audio.setText(str(audio.codec))

        eth = (getattr(getattr(profile, "net", None), "eth_chipset", "") or "").lower()
        if self.manual_eth.findData(eth) < 0:
            eth = ""
        self._select_data(self.manual_eth, eth)

        wifi = (getattr(getattr(profile, "net", None), "wifi_chipset", "") or "").lower()
        if self.manual_wifi.findData(wifi) < 0:
            wifi = ""
        self._select_data(self.manual_wifi, wifi)

        touch = str(getattr(profile, "touchpad_type", "") or "none")
        if self.manual_touchpad.findData(touch) < 0:
            touch = "ps2" if laptop else "none"
        self._select_data(self.manual_touchpad, touch)

        storage = getattr(profile, "storage", None)
        if storage is not None:
            self.manual_nvme.setChecked(bool(getattr(storage, "nvme_present", False)))
        self._manual_refresh()
    def _build_manual(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        v.setSpacing(10)
        v.addWidget(_h2(page, tr.t("manual.title")))
        from_scan = QPushButton(tr.t("manual.from_scan"))
        from_scan.clicked.connect(self._manual_from_scan)
        v.addWidget(from_scan, alignment=Qt.AlignmentFlag.AlignLeft)

        cols = QHBoxLayout()
        cols.setSpacing(18)
        form = QVBoxLayout()
        form.setSpacing(8)
        cols.addLayout(form, 3)

        self.manual_cpu = QComboBox()
        for option in manual_hw.CPU_OPTIONS:
            self.manual_cpu.addItem(option.title, option.key)
        default_index = self.manual_cpu.findData("intel-8d")
        if default_index >= 0:
            self.manual_cpu.setCurrentIndex(default_index)
        self._make_searchable(self.manual_cpu)
        self.manual_cpu.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.cpu", self.manual_cpu)

        row = QHBoxLayout()
        self.manual_laptop = QCheckBox(tr.t("manual.laptop"))
        self.manual_laptop.toggled.connect(self._manual_refresh)
        row.addWidget(self.manual_laptop)
        row.addSpacing(12)
        row.addWidget(QLabel(tr.t("manual.cores")))
        self.manual_cores = QSpinBox()
        self.manual_cores.setRange(2, 64)
        self.manual_cores.setValue(4)
        self.manual_cores.valueChanged.connect(self._manual_refresh)
        row.addWidget(self.manual_cores)
        row.addStretch()
        form.addLayout(row)

        self.manual_gpu = QComboBox()
        for option in manual_hw.GPU_OPTIONS:
            self.manual_gpu.addItem(option.title, option.key)
        self._make_searchable(self.manual_gpu)
        self.manual_gpu.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.gpu", self.manual_gpu)

        self.manual_audio = QLineEdit()
        self.manual_audio.setPlaceholderText(tr.t("manual.audio_ph"))
        self.manual_audio.textChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.audio", self.manual_audio)

        self.manual_eth = QComboBox()
        for value, title in manual_hw.ETHERNET_OPTIONS:
            self.manual_eth.addItem(title, value)
        self._make_searchable(self.manual_eth)
        self.manual_eth.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.eth", self.manual_eth)

        self.manual_wifi = QComboBox()
        for value, title in manual_hw.WIFI_OPTIONS:
            self.manual_wifi.addItem(title, value)
        self._make_searchable(self.manual_wifi)
        self.manual_wifi.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.wifi", self.manual_wifi)

        self.manual_touchpad = QComboBox()
        for value, title in manual_hw.TOUCHPAD_OPTIONS:
            self.manual_touchpad.addItem(title, value)
        self._make_searchable(self.manual_touchpad)
        self.manual_touchpad.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.touchpad", self.manual_touchpad)

        other = QHBoxLayout()
        self.manual_nvme = QCheckBox(tr.t("manual.nvme"))
        self.manual_nvme.setChecked(True)
        self.manual_nvme.toggled.connect(self._manual_refresh)
        other.addWidget(self.manual_nvme)
        self.manual_tb = QCheckBox(tr.t("manual.tb"))
        self.manual_tb.toggled.connect(self._manual_refresh)
        other.addWidget(self.manual_tb)
        other.addStretch()
        form.addLayout(other)

        self.manual_macos = QComboBox()
        self._make_searchable(self.manual_macos)
        self.manual_macos.currentIndexChanged.connect(self._manual_refresh)
        self._manual_field(page, form, "manual.macos", self.manual_macos)

        self.manual_result = _val(page, "")
        self.manual_result.setWordWrap(True)
        form.addWidget(self.manual_result)
        form.addStretch()

        review_card = self._card(page)
        rv = QVBoxLayout(review_card)
        rv.setContentsMargins(16, 12, 16, 12)
        rv.addWidget(_h2(page, tr.t("manual.review")))
        self.manual_review_box = QVBoxLayout()
        self.manual_review_box.setSpacing(6)
        rv.addLayout(self.manual_review_box)
        rv.addStretch()
        cols.addWidget(review_card, 2, Qt.AlignmentFlag.AlignTop)
        v.addLayout(cols, 1)

        self._manual_refresh()
        return page
    def _manual_field(self, page, layout, label_key: str, widget):
        row = QHBoxLayout()
        label = QLabel(tr.t(label_key), page)
        label.setObjectName("kv")
        label.setMinimumWidth(150)
        row.addWidget(label)
        row.addWidget(widget, 1)
        layout.addLayout(row)
    def _manual_selection(self):
        return manual_hw.ManualSelection(
            cpu=str(self.manual_cpu.currentData() or "intel-8d"),
            laptop=self.manual_laptop.isChecked(),
            cores=self.manual_cores.value(),
            gpu=str(self.manual_gpu.currentData() or ""),
            audio_codec=self.manual_audio.text().strip(),
            ethernet=str(self.manual_eth.currentData() or ""),
            wifi=str(self.manual_wifi.currentData() or ""),
            nvme=self.manual_nvme.isChecked(),
            thunderbolt=self.manual_tb.isChecked(),
            touchpad=str(self.manual_touchpad.currentData() or "ps2"),
        )
    def _manual_refresh(self, *_args):
        if not hasattr(self, "manual_review_box"):
            return
        profile = manual_hw.build_profile(self._manual_selection())
        self.manual_profile = profile
        self.manual_touchpad.setEnabled(profile.platform == "laptop")
        self._manual_fill_macos(profile)
        target = str(self.manual_macos.currentData() or "")
        self._manual_render(profile, manual_hw.review(profile, target, "itlwm"))
        # патчи зависят от железа и macOS — пересчитываем сразу после правки формы
        if hasattr(self, "_refresh_patches"):
            self._refresh_patches()
    def _manual_fill_macos(self, profile):
        from ..knowledge.oc_platforms import MACOS_VERSIONS, MAX_MACOS_BY_GEN
        ceiling = MAX_MACOS_BY_GEN.get(profile.cpu.generation, "Sonoma")
        order = ["High Sierra", "Mojave", "Catalina", "Big Sur", "Monterey",
                 "Ventura", "Sonoma", "Sequoia", "Tahoe", "Golden Gate"]

        def rank(name: str) -> int:
            low = (name or "").lower()
            return next((i for i, item in enumerate(order) if item.lower() in low), -1)

        current = str(self.manual_macos.currentData() or "")
        limit = rank(ceiling)
        self.manual_macos.blockSignals(True)
        self.manual_macos.clear()
        for entry in MACOS_VERSIONS:
            name = str(entry.get("name") or "")
            if limit >= 0 and rank(name) > limit:
                continue
            ver = str(entry.get("version") or "")
            self.manual_macos.addItem(f"{name} ({ver})" if ver else name, name)
        index = self.manual_macos.findData(current)
        if index < 0 and self.manual_macos.count():
            index = 0
        if index >= 0:
            self.manual_macos.setCurrentIndex(index)
        self.manual_macos.blockSignals(False)
    def _manual_render(self, profile, data):
        self._clear_layout(self.manual_review_box)
        platform_key = f"hw.platform.{data['platform']}"
        platform_text = tr.t(platform_key) if data["platform"] in (
            "laptop", "desktop", "mini", "workstation") else data["platform"]
        rows = [
            ("manual.r.gen", f"{data['generation']} · {data['codename']}"),
            ("manual.r.platform", platform_text),
            ("manual.r.max", data["max_macos"]),
            ("manual.r.smbios", data["smbios"] or "—"),
            ("manual.r.kexts", f"{data['kext_count']}: " + ", ".join(data["kexts"][:8])
             + ("…" if data["kext_count"] > 8 else "")),
            ("manual.r.ssdts", ", ".join(data["ssdts"]) or "—"),
        ]
        for key, value in rows:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            label = QLabel(tr.t(key), row)
            label.setObjectName("kv")
            label.setMinimumWidth(110)
            rl.addWidget(label)
            text = _val(row, value)
            text.setWordWrap(True)
            rl.addWidget(text, 1)
            self.manual_review_box.addWidget(row)
        for issue in data["issues"]:
            prefix = {"ok": "✔", "warn": "⚠", "err": "✖"}.get(issue["level"], "•")
            label = QLabel(f"{prefix} {issue['text']}", self.manual_review_box.parentWidget())
            label.setWordWrap(True)
            label.setObjectName(issue["level"] if issue["level"] in ("ok", "warn", "err") else "muted")
            self.manual_review_box.addWidget(label)
    def _manual_open(self):
        target = getattr(self, "_manual_last_target", None)
        if target:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
    def _manual_share(self):
        """Отчёт ручной сборки: страница новой задачи GitHub."""
        record = getattr(self, "_manual_record", "")
        if not record:
            self.statusBar().showMessage(tr.t("community.nothing"), 5000)
            return
        try:
            from ..knowledge import community
            payload = community.load(Path(record))
            if community.open_issue(payload):
                self.statusBar().showMessage(tr.t("community.share_opened"), 6000)
        except Exception as exc:
            self.statusBar().showMessage(f"[warn] {exc}", 6000)
    def _sync_recovery_version(self, target: str) -> None:
        """Ставит в «Записи на USB» ту же macOS, под которую собрана EFI.

        Иначе под Sonoma легко записать установщик Tahoe: EFI не загрузит
        чужой recovery.
        """
        combo = getattr(self, "usb_recovery_ver", None)
        name = (target or "").strip()
        if combo is None or not name:
            return
        for i in range(combo.count()):
            data = str(combo.itemData(i) or "")
            if name.lower() in data.lower() or data.lower() in name.lower():
                combo.setCurrentIndex(i)
                return
