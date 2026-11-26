"""Миксин SettingsMixin: методы главного окна (settings).

Выделено из ``main_window.py``; поведение не менялось.
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import __version__, uistate
from ..i18n import LANGS, tr
from ..themes import BASE_THEMES, BUILTIN_THEMES
from ._common import _h2, _muted, _release_notes_text, _val
from ._workers import UpdateCheckWorker, UpdateDownloadWorker
from .theme_tiles import MonitorButton


class SettingsMixin:
    def _build_settings(self):
        root = QWidget()
        outer = QVBoxLayout(root); outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        page = inner
        v = QVBoxLayout(page); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(page, v, "settings.title", "settings.subtitle")

        # Язык
        gb_lang = QGroupBox(tr.t("settings.language"))
        lg = QHBoxLayout(gb_lang)
        self.settings_lang = QComboBox()
        for l in LANGS:
            self.settings_lang.addItem(l.native, l.code)
        idx = next((i for i in range(self.settings_lang.count()) if self.settings_lang.itemData(i) == tr.current), 0)
        self.settings_lang.setCurrentIndex(idx)
        self.settings_lang.currentIndexChanged.connect(self._on_lang)
        lg.addWidget(self.settings_lang, 1)
        v.addWidget(gb_lang)

        # Тема оформления — плитки-мониторы
        gb_theme = QGroupBox(tr.t("settings.theme"))
        tv = QVBoxLayout(gb_theme)
        theme_desc = _muted(page, tr.t("settings.theme_descr")); theme_desc.setWordWrap(True)
        tv.addWidget(theme_desc)

        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_tiles: dict[str, MonitorButton] = {}
        base_labels = {
            "system": "settings.theme_system",
            "light": "settings.theme_light",
            "dark": "settings.theme_dark",
            "custom": "settings.theme_custom",
        }
        base_row = QHBoxLayout(); base_row.setSpacing(10)
        for key in BASE_THEMES:
            btn = MonitorButton(key, tr.t(base_labels[key]), gb_theme)
            self._theme_group.addButton(btn)
            self._theme_tiles[key] = btn
            base_row.addWidget(btn)
        base_row.addStretch()
        tv.addLayout(base_row)

        tv.addWidget(_h2(page, tr.t("settings.theme_builtin")))
        preset_labels = {
            "aqua": "settings.theme_aqua",
            "graphite": "settings.theme_graphite",
            "sonoma": "settings.theme_sonoma",
            "bigsur": "settings.theme_bigsur",
        }
        preset_row = QHBoxLayout(); preset_row.setSpacing(10)
        for key in BUILTIN_THEMES:
            btn = MonitorButton(key, tr.t(preset_labels[key]), gb_theme)
            self._theme_group.addButton(btn)
            self._theme_tiles[key] = btn
            preset_row.addWidget(btn)
        preset_row.addStretch()
        tv.addLayout(preset_row)
        self._theme_group.buttonClicked.connect(self._on_theme_tile)

        # Свой фон для темы «Моя тема»
        bg_row = QHBoxLayout()
        bg_row.addWidget(_h2(page, tr.t("settings.theme_bg")))
        self.bg_label = _muted(
            page,
            self._theme_bg or tr.t("settings.theme_bg_none"),
        )
        self.bg_label.setWordWrap(True)
        bg_row.addWidget(self.bg_label, 1)
        pick_bg = QPushButton(tr.t("settings.theme_bg_pick"))
        pick_bg.setObjectName("ghost")
        pick_bg.clicked.connect(self._pick_theme_bg)
        bg_row.addWidget(pick_bg)
        reset_bg = QPushButton(tr.t("settings.theme_bg_reset"))
        reset_bg.setObjectName("ghost")
        reset_bg.clicked.connect(self._reset_theme_bg)
        bg_row.addWidget(reset_bg)
        tv.addLayout(bg_row)
        v.addWidget(gb_theme)
        self._sync_theme_tiles()

        # Всё бесплатно: вместо фейковой активации — честное объяснение модели.
        gb_free = QGroupBox(tr.t("settings.free_title"))
        fv = QVBoxLayout(gb_free)
        free_text = _muted(page, tr.t("settings.free_text"))
        free_text.setWordWrap(True)
        fv.addWidget(free_text)
        free_plan = _muted(page, tr.t("settings.free_plan"))
        free_plan.setWordWrap(True)
        fv.addWidget(free_plan)
        v.addWidget(gb_free)

        # Обновления
        gb_upd = QGroupBox(tr.t("settings.updates"))
        uv = QVBoxLayout(gb_upd)
        self.upd_version = _val(page, f"{tr.t('settings.updates_version')}: {__version__}")
        uv.addWidget(self.upd_version)
        self.upd_auto = QCheckBox(tr.t("settings.updates_auto"))
        self.upd_auto.setChecked(bool(uistate.get("check_updates", True)))
        self.upd_auto.toggled.connect(
            lambda on: uistate.save(check_updates=bool(on)))
        uv.addWidget(self.upd_auto)

        upd_row = QHBoxLayout()
        self.upd_check_btn = QPushButton(tr.t("settings.updates_check"))
        self.upd_check_btn.clicked.connect(self._check_updates)
        upd_row.addWidget(self.upd_check_btn)
        self.upd_status = _muted(page, tr.t("settings.updates_idle"))
        self.upd_status.setWordWrap(True)
        upd_row.addWidget(self.upd_status, 1)
        uv.addLayout(upd_row)

        self.upd_notes = QPlainTextEdit()
        self.upd_notes.setReadOnly(True)
        self.upd_notes.setMaximumHeight(150)
        self.upd_notes.setVisible(False)
        uv.addWidget(self.upd_notes)

        self.upd_actions = QWidget(page)
        av = QHBoxLayout(self.upd_actions); av.setContentsMargins(0, 0, 0, 0)
        self.upd_now_btn = QPushButton(tr.t("settings.updates_now"))
        self.upd_now_btn.clicked.connect(self._install_update)
        self.upd_later_btn = QPushButton(tr.t("settings.updates_later"))
        self.upd_later_btn.setObjectName("ghost")
        self.upd_later_btn.clicked.connect(self._postpone_update)
        av.addWidget(self.upd_now_btn)
        av.addWidget(self.upd_later_btn)
        av.addStretch()
        self.upd_actions.setVisible(False)
        uv.addWidget(self.upd_actions)

        # Запасной путь: при лимите GitHub открыть страницу релиза вручную
        self.upd_fallback = QWidget(page)
        fb = QHBoxLayout(self.upd_fallback); fb.setContentsMargins(0, 0, 0, 0)
        self.upd_page_btn = QPushButton(tr.t("settings.updates_open_page"))
        self.upd_page_btn.setObjectName("ghost")
        self.upd_page_btn.clicked.connect(self._open_release_page)
        fb.addWidget(self.upd_page_btn)
        fb.addStretch()
        self.upd_fallback.setVisible(False)
        uv.addWidget(self.upd_fallback)

        self.upd_warning = _muted(page, tr.t("settings.updates_warning"))
        self.upd_warning.setWordWrap(True)
        self.upd_warning.setVisible(False)
        uv.addWidget(self.upd_warning)
        v.addWidget(gb_upd)
        self._pending_update = None

        v.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)
        return root
    def _check_updates(self, silent: bool = False):
        """Запускает проверку релиза на GitHub в фоновом потоке."""
        if getattr(self, "_upd_worker", None) and self._upd_worker.isRunning():
            return
        if not hasattr(self, "upd_check_btn"):
            return
        self.upd_check_btn.setEnabled(False)
        self.upd_status.setText(tr.t("settings.updates_checking"))
        self.upd_warning.setVisible(False)
        self._upd_silent = bool(silent)
        worker = UpdateCheckWorker()
        self._upd_worker = worker
        worker.found.connect(self._updates_found)
        worker.up_to_date.connect(self._updates_up_to_date)
        worker.failed.connect(self._updates_failed)
        worker.finished.connect(lambda: self.upd_check_btn.setEnabled(True))
        worker.start()
    def _auto_check_updates(self):
        if os.environ.get("HACKICLAB_NO_UPDATES"):
            return
        if bool(uistate.get("check_updates", True)):
            self._check_updates(silent=True)
    def _updates_found(self, info):
        self._pending_update = info
        uistate.save(postponed_update="")
        key = ("settings.updates_rebuild" if getattr(info, "is_rebuild", False)
               else "settings.updates_available")
        text = tr.t(key).format(version=info.version)
        self.upd_status.setText(text)
        notes = _release_notes_text(info.notes)
        self.upd_notes.setPlainText(notes)
        self.upd_notes.setVisible(bool(notes))
        self.upd_now_btn.setText(
            tr.t("settings.updates_now") if info.has_asset
            else tr.t("settings.updates_open_page"))
        self.upd_actions.setVisible(True)
        self.statusBar().showMessage(text, 8000)
        # Пересборку той же версии не предлагаем модальным окном при старте:
        # пользователь только что мог собрать её сам. В «Настройках» она видна.
        if (getattr(self, "_upd_silent", False) and info.has_asset
                and not getattr(info, "is_rebuild", False)):
            # предложение при старте: обновиться сейчас или отложить с напоминанием
            if self._confirm(
                tr.t("settings.updates"),
                f"{text}\n\n{tr.t('settings.updates_warning')}",
                tr.t("settings.updates_now"), tr.t("settings.updates_later"),
            ):
                self._install_update()
            else:
                self._postpone_update()
        self._upd_silent = False
    def _updates_up_to_date(self):
        self._pending_update = None
        self.upd_status.setText(tr.t("settings.updates_latest"))
        self.upd_notes.setVisible(False)
        self.upd_actions.setVisible(False)
        self.upd_fallback.setVisible(False)
    def _updates_failed(self, err: str):
        """Понятное сообщение вместо HTTP-кода: лимит GitHub — не поломка."""
        self._pending_update = None
        message = str(err).strip() or tr.t("settings.updates_hint")
        self.upd_status.setText(tr.t("settings.updates_failed").format(error=message))
        self.upd_actions.setVisible(False)
        self.upd_notes.setVisible(False)
        self.upd_fallback.setVisible(True)
    def _open_release_page(self):
        from .. import updater

        url = getattr(self, "_release_page_url", "") or updater.RELEASES_PAGE
        updater.open_release_page(url)
        self.upd_status.setText(tr.t("settings.updates_browser"))
    def _install_update(self):
        """Скачивает новую сборку и запускает подмену EXE."""
        from .. import updater
        info = getattr(self, "_pending_update", None)
        if info is None:
            return
        if not (info.has_asset and updater.can_self_update()):
            updater.open_release_page(info.page_url)
            self.upd_status.setText(tr.t("settings.updates_browser"))
            return
        if getattr(self, "_upd_dl", None) and self._upd_dl.isRunning():
            return
        self.upd_now_btn.setEnabled(False)
        self.upd_status.setText(tr.t("settings.updates_downloading"))
        worker = UpdateDownloadWorker(info)
        self._upd_dl = worker
        worker.done.connect(self._update_downloaded)
        worker.failed.connect(self._update_download_failed)
        worker.start()
    def _update_downloaded(self, path):
        from .. import updater
        self.upd_now_btn.setEnabled(True)
        if not updater.apply_update(Path(path)):
            self.upd_status.setText(tr.t("settings.updates_manual"))
            return
        self.upd_status.setText(tr.t("settings.updates_restarting"))
        updater.relaunch_self()
        # Штатный выход: PyInstaller сам удаляет временную папку _MEI.
        # Принудительный os._exit оставлял её и давал предупреждение при старте.
        QTimer.singleShot(300, QApplication.quit)
    def _update_download_failed(self, err):
        self.upd_now_btn.setEnabled(True)
        if getattr(err, "already_installed", False):
            # Скачалась ровно та сборка, что уже запущена: обновляться некуда.
            self._pending_update = None
            self.upd_status.setText(tr.t("settings.updates_latest"))
            self.upd_notes.setVisible(False)
            self.upd_actions.setVisible(False)
            self.upd_fallback.setVisible(False)
            return
        self.upd_status.setText(tr.t("settings.updates_failed").format(error=str(err)))
        self.upd_fallback.setVisible(True)
    def _postpone_update(self):
        info = getattr(self, "_pending_update", None)
        version = info.version if info else ""
        uistate.save(postponed_update=version, skipped_version=version)
        self.upd_actions.setVisible(False)
        self.upd_warning.setText(tr.t("settings.updates_postponed"))
        self.upd_warning.setVisible(True)
    def _on_theme_tile(self, btn):
        key = getattr(btn, "key", "")
        if not key:
            return
        self.apply_theme(key)
        self._hook_system_theme()
        if key == "custom" and not self._theme_bg:
            self.statusBar().showMessage(tr.t("settings.theme_bg_hint"), 5000)
    def _pick_theme_bg(self):
        """Выбор фонового изображения для темы «Моя тема»."""
        path, _ = QFileDialog.getOpenFileName(
            self, tr.t("settings.theme_bg_pick"), "",
            f"{tr.t('file.images')};;{tr.t('file.all_files')}")
        if not path:
            return
        self._theme_bg = path
        self._theme = "custom"
        uistate.save(background=path, theme="custom")
        self.apply_theme()
        if hasattr(self, "bg_label"):
            self.bg_label.setText(path)
        self._hook_system_theme()
    def _reset_theme_bg(self):
        """Убирает пользовательский фон, оставляя фирменную тему."""
        self._theme_bg = ""
        uistate.save(background="")
        self.apply_theme()
        if hasattr(self, "bg_label"):
            self.bg_label.setText(tr.t("settings.theme_bg_none"))
    def _build_about(self):
        page = QWidget()
        outer = QVBoxLayout(page); outer.setContentsMargins(0, 0, 0, 0)
        area = QScrollArea(); area.setWidgetResizable(True)
        area.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        v = QVBoxLayout(body); v.setContentsMargins(28, 24, 28, 24)
        self._page_header(body, v, "about.title", "about.subtitle")

        # Витрина: версия, описание и ссылки (имя уже в заголовке страницы)
        hero = self._card(body)
        hv = QVBoxLayout(hero); hv.setSpacing(8)
        meta = _muted(body, f"{tr.t('about.version')} {__version__}  ·  {tr.t('about.license')}")
        hv.addWidget(meta)
        tagline = _muted(body, tr.t("about.tagline")); tagline.setWordWrap(True)
        hv.addWidget(tagline)
        links = QHBoxLayout(); links.setSpacing(8)
        for key, url in (
            ("about.link_github", "https://github.com/SLEP-KOMP/HackicLab"),
            ("about.link_releases", "https://github.com/SLEP-KOMP/HackicLab/releases"),
            ("about.link_issues", "https://github.com/SLEP-KOMP/HackicLab/issues"),
        ):
            btn = QPushButton(tr.t(key))
            btn.setObjectName("ghost")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda _checked=False, target=url: QDesktopServices.openUrl(QUrl(target)))
            links.addWidget(btn)
        links.addStretch()
        hv.addLayout(links)
        v.addWidget(hero)

        # Что это
        c_what = self._card(body)
        wv = QVBoxLayout(c_what)
        wv.addWidget(_h2(body, tr.t("about.whatis")))
        what = _muted(body, tr.t("about.whatis_text")); what.setWordWrap(True)
        wv.addWidget(what)
        v.addWidget(c_what)

        # Возможности
        c_feat = self._card(body)
        fv = QVBoxLayout(c_feat); fv.setSpacing(4)
        fv.addWidget(_h2(body, tr.t("about.features_title")))
        for key in ("about.feature1", "about.feature2", "about.feature3",
                    "about.feature4", "about.feature5", "about.feature6",
                    "about.feature7"):
            item = _muted(body, "▸  " + tr.t(key)); item.setWordWrap(True)
            fv.addWidget(item)
        v.addWidget(c_feat)

        # Технологии
        c_tech = self._card(body)
        tv = QVBoxLayout(c_tech)
        tv.addWidget(_h2(body, tr.t("about.tech_title")))
        tech = _muted(body, tr.t("about.tech_text")); tech.setWordWrap(True)
        tv.addWidget(tech)
        tv.addSpacing(6)
        import PySide6

        tv.addWidget(_muted(body, f"{tr.t('about.version')} {__version__}  ·  "
                                  f"PySide6 {PySide6.__version__}  ·  "
                                  f"{tr.t('about.license')}"))
        v.addWidget(c_tech)

        # Дисклеймер
        c_disc = self._card(body)
        dv = QVBoxLayout(c_disc)
        dv.addWidget(_h2(body, tr.t("about.disc")))
        disc = _muted(body, tr.t("about.disc_text")); disc.setWordWrap(True)
        dv.addWidget(disc)
        v.addWidget(c_disc)

        v.addStretch()
        area.setWidget(body)
        outer.addWidget(area)
        return page
