"""Миксин DonateMixin: методы главного окна (donate).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QDesktopServices,
    QGuiApplication,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ._common import _h2, _muted


class DonateMixin:
    def _asset(self, *parts) -> Path:
        """Путь к ассету пакета — работает и в собранном EXE.

        В onefile-сборке ``__file__`` модуля из PYZ бывает относительным,
        поэтому базой служит ``sys._MEIPASS``.
        """
        bundled = getattr(sys, "_MEIPASS", None)
        if bundled:
            base = Path(bundled) / "hackiclab" / "assets"
        else:
            base = Path(__file__).resolve().parents[2] / "hackiclab" / "assets"
        return base / Path(*parts)
    def _logo_pixmap(self, name: str, height: int) -> QPixmap:
        pix = QPixmap(str(self._asset("brands", name)))
        if pix.isNull():
            return pix
        scaled = pix.scaledToHeight(height * 2, Qt.TransformationMode.SmoothTransformation)
        scaled.setDevicePixelRatio(2.0)
        return scaled
    def _build_donate(self):
        """Вкладка поддержки: форма-калькулятор, способы оплаты и фото автора.

        Контент стоит центральной колонкой с одинаковыми отступами слева и
        справа, как в «Параметрах» Windows: на широком окне поля не растягиваются
        и не выглядят огромными.
        """
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "donate.title", "donate.subtitle")

        cols = QHBoxLayout(); cols.setSpacing(18)
        left = QVBoxLayout(); left.setSpacing(14)

        why = self._card(page)
        wv = QVBoxLayout(why)
        wv.addWidget(_h2(page, tr.t("donate.why_title")))
        why_text = _muted(page, tr.t("donate.why_text")); why_text.setWordWrap(True)
        wv.addWidget(why_text)
        left.addWidget(why)

        form = self._card(page)
        fv = QVBoxLayout(form)
        fv.addWidget(_h2(page, tr.t("donate.amount_title")))
        hint = _muted(page, tr.t("donate.amount_hint")); hint.setWordWrap(True)
        fv.addWidget(hint)

        chips = QHBoxLayout(); chips.setSpacing(8)
        self.donate_group = QButtonGroup(self)
        for amount in (300, 600, 1200, 3000, 5000):
            chip = QPushButton(f"{amount} ₽")
            chip.setObjectName("chip")
            chip.setCheckable(True)
            chip.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            chip.setProperty("amount", amount)
            chip.clicked.connect(lambda _=False, a=amount: self.donate_amount.setValue(a))
            self.donate_group.addButton(chip)
            chips.addWidget(chip)
        chips.addStretch()
        fv.addLayout(chips)

        amount_row = QHBoxLayout()
        amount_row.addWidget(_h2(page, tr.t("donate.amount_custom")))
        self.donate_amount = QSpinBox()
        self.donate_amount.setRange(100, 100000)
        self.donate_amount.setSingleStep(100)
        self.donate_amount.setSuffix(" ₽")
        self.donate_amount.setValue(1000)
        self.donate_amount.valueChanged.connect(self._donate_recalc)
        amount_row.addWidget(self.donate_amount, 1)
        fv.addLayout(amount_row)

        self.donate_fee = _muted(page, "")
        self.donate_fee.setWordWrap(True)
        fv.addWidget(self.donate_fee)
        self.donate_limit = _muted(page, "")
        self.donate_limit.setWordWrap(True)
        fv.addWidget(self.donate_limit)

        wallet_row = QHBoxLayout()
        wallet_row.addWidget(_h2(page, tr.t("donate.wallet")))
        self.donate_wallet = QLabel(self._DONATE_WALLET)
        self.donate_wallet.setObjectName("kv")
        self.donate_wallet.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        wallet_row.addWidget(self.donate_wallet, 1)
        fv.addLayout(wallet_row)

        btns = QHBoxLayout()
        pay = QPushButton(tr.t("donate.pay"))
        pay.clicked.connect(self._open_donate)
        copy = QPushButton(tr.t("donate.copy"))
        copy.setObjectName("ghost")
        copy.clicked.connect(self._copy_wallet)
        btns.addWidget(pay)
        btns.addWidget(copy)
        btns.addStretch()
        fv.addLayout(btns)
        left.addWidget(form)

        methods = self._card(page)
        mv = QVBoxLayout(methods)
        mv.addWidget(_h2(page, tr.t("donate.methods_title")))
        logo_row = QHBoxLayout(); logo_row.setSpacing(0)
        strip = QFrame(page)
        strip.setObjectName("logoStrip")
        strip.setFixedHeight(44)
        strip_fixed = strip.sizePolicy()
        strip_fixed.setHorizontalPolicy(strip_fixed.Policy.Maximum)
        strip.setSizePolicy(strip_fixed)
        sl = QHBoxLayout(strip); sl.setContentsMargins(16, 0, 16, 0); sl.setSpacing(22)
        for name, height in (("yoomoney.png", 20), ("mir.png", 18), ("sbp.png", 19)):
            lbl = QLabel()
            pix = self._logo_pixmap(name, height)
            if not pix.isNull():
                lbl.setPixmap(pix)
            sl.addWidget(lbl, 0, Qt.AlignmentFlag.AlignVCenter)
        logo_row.addWidget(strip, 0, Qt.AlignmentFlag.AlignLeft)
        logo_row.addStretch()
        mv.addLayout(logo_row)
        for key in ("donate.methods_text", "donate.limits_text",
                    "donate.methods_foreign", "donate.logos_note"):
            lbl = _muted(page, tr.t(key)); lbl.setWordWrap(True)
            mv.addWidget(lbl)
        left.addWidget(methods)

        use = self._card(page)
        uv = QVBoxLayout(use)
        uv.addWidget(_h2(page, tr.t("donate.use_title")))
        for key in ("donate.use1", "donate.use2", "donate.use3", "donate.use4"):
            item = _muted(page, "•  " + tr.t(key)); item.setWordWrap(True)
            uv.addWidget(item)
        left.addWidget(use)
        cols.addLayout(left, 3)

        support = self._card(page)
        support.setMaximumWidth(380)
        vv = QVBoxLayout(support)
        vv.addWidget(_h2(page, tr.t("donate.qr_title")))
        qr = QLabel()
        pix = QPixmap(str(self._asset("support", "donate-qr.png")))
        if not pix.isNull():
            qr.setPixmap(pix.scaled(240, 240,
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation))
        qr.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vv.addWidget(qr)
        hint = _muted(page, tr.t("donate.qr_hint")); hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        vv.addWidget(hint)
        note = _muted(page, tr.t("donate.qr_note")); note.setWordWrap(True)
        vv.addWidget(note)
        thanks = _muted(page, tr.t("donate.author_thanks")); thanks.setWordWrap(True)
        vv.addWidget(thanks)
        vv.addStretch(1)
        cols.addWidget(support, 2, Qt.AlignmentFlag.AlignTop)
        cols_box = QWidget(page)
        cols_box.setLayout(cols)
        v.addWidget(cols_box, 0, Qt.AlignmentFlag.AlignTop)

        legal = self._card(page)
        lv = QVBoxLayout(legal)
        legal_text = _muted(page, tr.t("donate.legal")); legal_text.setWordWrap(True)
        lv.addWidget(legal_text)
        v.addWidget(legal)
        v.addStretch(1)

        self._donate_recalc()
        return page
    def _donate_recalc(self, *_args):
        """Считает комиссию и подсказывает про лимит в один перевод."""
        amount = self.donate_amount.value()
        fee = 0 if amount >= 4000 else max(1, round(amount * 0.01))
        self.donate_fee.setText(
            tr.t("donate.fee_free") if fee == 0
            else tr.t("donate.fee_percent").format(fee=fee))
        over = amount > 15000
        self.donate_limit.setText(
            tr.t("donate.limit_over") if over else tr.t("donate.limit_ok"))
        wanted = "warn" if over else "muted"
        if self.donate_limit.objectName() != wanted:
            self.donate_limit.setObjectName(wanted)
            self.donate_limit.style().unpolish(self.donate_limit)
            self.donate_limit.style().polish(self.donate_limit)
        for btn in self.donate_group.buttons():
            value = btn.property("amount")
            if isinstance(value, int) and btn.isChecked() != (value == amount):
                btn.blockSignals(True)
                btn.setChecked(value == amount)
                btn.blockSignals(False)
    def _open_donate(self):
        QDesktopServices.openUrl(QUrl(self._DONATE_URL))
    def _copy_wallet(self):
        QGuiApplication.clipboard().setText(self._DONATE_WALLET)
        self.statusBar().showMessage(
            tr.t("donate.copied").format(wallet=self._DONATE_WALLET), 5000)
