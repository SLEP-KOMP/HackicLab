"""Миксин SourcesMixin: методы главного окна (sources).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ..i18n import tr
from ..knowledge.configs import (
    STATUS_LIMITED,
    STATUS_NATIVE,
    STATUS_PATCHED,
    by_category,
    categories_of,
    search_configs,
    similar_configs,
)
from ..knowledge.sources import (
    GROUP_COMMUNITY,
    GROUP_EFI,
    GROUP_GUIDES,
    GROUP_HARDWARE,
    SOURCES,
    note_of,
    sources_by_group,
    title_of,
)
from ._common import _h2, _muted, _val


class SourcesMixin:
    def _link_label(self, parent, src) -> QWidget:
        """Строка-ссылка: заголовок открывается в браузере, ниже пояснение."""
        w = QWidget(parent)
        lv = QVBoxLayout(w); lv.setContentsMargins(0, 2, 0, 2); lv.setSpacing(1)
        a = QLabel(w)
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setText(
            f'<a href="{src.url}" style="color:#89b4fa; text-decoration:none;">'
            f'{html.escape(title_of(src, tr.current))}</a>'
        )
        a.setOpenExternalLinks(True)
        a.setWordWrap(True)
        a.setToolTip(src.url)
        lv.addWidget(a)
        note = note_of(src, tr.current)
        if note:
            n = _muted(w, note); n.setWordWrap(True)
            lv.addWidget(n)
        return w
    def _build_sources(self):
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        v = QVBoxLayout(inner); v.setContentsMargins(28, 24, 28, 24); v.setSpacing(10)
        self._page_header(inner, v, "sources.title", "sources.subtitle")

        # --- под ваше железо ---
        self._src_ctx_page = inner
        ctx_card = self._card(inner)
        cv = QVBoxLayout(ctx_card); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(4)
        self._src_ctx = QVBoxLayout(); self._src_ctx.setSpacing(4)
        cv.addLayout(self._src_ctx)
        v.addWidget(ctx_card)

        # --- поиск и фильтр ---
        row = QHBoxLayout()
        self.src_query = QLineEdit()
        self.src_query.setPlaceholderText(tr.t("sources.search"))
        self.src_query.setClearButtonEnabled(True)
        self.src_query.textChanged.connect(self._refresh_sources)
        row.addWidget(self.src_query, 2)
        self.src_cat = QComboBox()
        self.src_cat.currentIndexChanged.connect(self._refresh_sources)
        row.addWidget(self.src_cat, 1)
        v.addLayout(row)

        self.src_count = _muted(inner, "")
        v.addWidget(self.src_count)

        self._src_results = QVBoxLayout(); self._src_results.setSpacing(8)
        v.addLayout(self._src_results)

        v.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        self._refill_source_categories()
        self._fill_sources_ctx()
        self._refresh_sources()
        return page
    def _refill_source_categories(self):
        combo = getattr(self, "src_cat", None)
        if combo is None:
            return
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(tr.t("sources.all"), "")
        for cat in categories_of():
            combo.addItem(f"{tr.t('sources.cat.' + cat)} ({len(by_category(cat))})", cat)
        idx = combo.findData(current) if current else 0
        combo.setCurrentIndex(max(0, idx))
        combo.blockSignals(False)
    def _status_badge(self, parent, status: str) -> QLabel:
        levels = {
            STATUS_NATIVE: "ok",
            STATUS_PATCHED: "warn",
            STATUS_LIMITED: "err",
        }
        badge = QLabel(tr.t("sources.status." + status), parent)
        badge.setObjectName("badge")
        badge.setProperty("tone", levels.get(status, "muted"))
        return badge
    def _support_report(self, cfg):
        """Кэшированный вердикт «соберётся ли EFI» для записи каталога."""
        cache = getattr(self, "_sup_cache", None)
        if cache is None:
            cache = {}
            self._sup_cache = cache
        if cfg.key not in cache:
            from ..knowledge.support import support_report
            cache[cfg.key] = support_report(cfg)
        return cache[cfg.key]
    def _support_badge(self, parent, cfg) -> QLabel:
        rep = self._support_report(cfg)
        levels = {"full": "ok", "partial": "warn", "none": "err"}
        badge = QLabel(tr.t("support.level." + rep.level), parent)
        badge.setObjectName("badge")
        badge.setProperty("tone", levels.get(rep.level, "warn"))
        reasons = [tr.t(key) for key in rep.failed]
        tip = tr.t("support.tooltip")
        if reasons:
            tip += "\n- " + "\n- ".join(reasons)
        badge.setToolTip(tip)
        return badge
    def _suggest_config(self):
        """Открывает issue с обезличенным описанием просканированного железа."""
        from ..knowledge import registry as hw_registry
        prof = getattr(self, "profile", None)
        if not prof:
            return
        try:
            record = hw_registry.find(prof) or hw_registry.register(prof)
        except Exception:
            record = None
        if record and hw_registry.open_issue(record):
            self.statusBar().showMessage(tr.t("sources.unknown_opened"), 6000)
            return
        QMessageBox.information(self, tr.t("sources.title"),
                                tr.t("sources.unknown_failed"))
    def _mini_link(self, parent, text: str, url: str) -> QLabel:
        a = QLabel(parent)
        a.setTextFormat(Qt.TextFormat.RichText)
        a.setText(
            f'<a href="{html.escape(url)}" style="color:#89b4fa; text-decoration:none;">'
            f'{html.escape(text)} ↗</a>'
        )
        a.setOpenExternalLinks(True)
        a.setToolTip(url)
        return a
    def _config_card(self, parent, cfg) -> QWidget:
        card = self._card(parent)
        cv = QVBoxLayout(card); cv.setContentsMargins(14, 12, 14, 12); cv.setSpacing(4)
        head = QHBoxLayout()
        title = _h2(card, cfg.heading(tr.current)); title.setWordWrap(True)
        head.addWidget(title, 1)
        head.addWidget(self._support_badge(card, cfg))
        head.addWidget(self._status_badge(card, cfg.status))
        cv.addLayout(head)

        meta = _muted(
            card,
            f"{tr.t('sources.cat.' + cfg.category)} · {cfg.cpu} · {cfg.gpu} · "
            f"macOS: {cfg.macos}",
        )
        meta.setWordWrap(True)
        cv.addWidget(meta)

        for prefix, values in ((tr.t("sources.kexts"), cfg.kexts),
                               (tr.t("sources.ssdt"), cfg.ssdts),
                               (tr.t("sources.quirks"), cfg.quirks)):
            if values:
                line = _muted(card, f"{prefix}: " + ", ".join(values))
                line.setWordWrap(True)
                cv.addWidget(line)

        note = _val(card, cfg.text(tr.current)); note.setWordWrap(True)
        cv.addWidget(note)

        links = QHBoxLayout(); links.setSpacing(14)
        for key in cfg.sources:
            src = SOURCES.get(key)
            if src is not None:
                links.addWidget(self._mini_link(card, title_of(src, tr.current), src.url))
        if cfg.url:
            links.addWidget(self._mini_link(card, tr.t("sources.details"), cfg.url))
        links.addStretch()
        cv.addLayout(links)
        return card
    def _clear_layout(self, lay):
        while lay.count():
            it = lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()
    def _refresh_sources(self):
        """Перестраивает выдачу по строке поиска и выбранной категории."""
        lay = getattr(self, "_src_results", None)
        page = getattr(self, "_src_ctx_page", None)
        if lay is None or page is None:
            return
        query = self.src_query.text() if hasattr(self, "src_query") else ""
        cat = self.src_cat.currentData() if hasattr(self, "src_cat") else ""
        self._clear_layout(lay)

        found = search_configs(query, cat or "")
        if found:
            lay.addWidget(_h2(page, tr.t("sources.configs")))
            for cfg in found:
                lay.addWidget(self._config_card(page, cfg))

        q = (query or "").strip().lower()
        groups = ((GROUP_HARDWARE, "sources.hardware"),
                  (GROUP_GUIDES, "sources.guides"),
                  (GROUP_EFI, "sources.efi"),
                  (GROUP_COMMUNITY, "sources.community"))
        shown_links = 0
        for group, key in groups:
            items = sources_by_group(group, tr.current)
            if q:
                items = [
                    s for s in items
                    if q in f"{s.title} {s.title_en} {s.note} {s.note_en}".lower()
                ]
            if not items:
                continue
            card = self._card(page)
            cv = QVBoxLayout(card); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(2)
            cv.addWidget(_h2(page, tr.t(key)))
            for src in items:
                cv.addWidget(self._link_label(page, src))
                shown_links += 1
            lay.addWidget(card)

        if hasattr(self, "src_count"):
            self.src_count.setText(
                tr.t("sources.found").format(configs=len(found), links=shown_links)
            )
    def _fill_sources_ctx(self):
        """Ссылки и ближайшие конфигурации под текущий профиль."""
        lay = getattr(self, "_src_ctx", None)
        page = getattr(self, "_src_ctx_page", None)
        if lay is None or page is None:
            return
        self._clear_layout(lay)
        prof = getattr(self, "profile", None)
        if not prof:
            lbl = _muted(page, tr.t("sources.no_profile")); lbl.setWordWrap(True)
            lay.addWidget(lbl)
            return
        lay.addWidget(_h2(page, tr.t("sources.for_hw")))
        # ближайшие записи каталога
        sim = similar_configs(prof, limit=2)
        for cfg in sim:
            row = QHBoxLayout()
            title = _val(page, cfg.heading(tr.current)); title.setWordWrap(True)
            row.addWidget(title, 1)
            row.addWidget(self._status_badge(page, cfg.status))
            lay.addLayout(row)
            meta = _muted(page, f"{cfg.cpu} · {cfg.gpu} · macOS: {cfg.macos}")
            meta.setWordWrap(True)
            lay.addWidget(meta)
        if not sim:
            warn = _val(page, tr.t("sources.unknown_title")); warn.setWordWrap(True)
            lay.addWidget(warn)
            hint = _muted(page, tr.t("sources.unknown_hint")); hint.setWordWrap(True)
            lay.addWidget(hint)
            btn = QPushButton(tr.t("sources.unknown_suggest"))
            btn.setObjectName("ghost")
            btn.clicked.connect(self._suggest_config)
            lay.addWidget(btn, alignment=Qt.AlignmentFlag.AlignLeft)
