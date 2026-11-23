# HackicLab — заметки для разработки

## Структура UI: только миксины

`hackiclab/ui/` разбит на модули, большой одиночный файл `main_window.py`
(был 240 методов) **не восстанавливать**:

- `_common.py` — константы и модульные хелперы (подписи, release-notes, перевод Qt);
- `_workers.py` — все QThread-воркеры;
- `_core.py` — остов окна: layout, навигация, темы, страницы;
- `_wizard.py`, `_manual.py`, `_validate.py`, `_build.py`, `_usb.py`,
  `_sources.py`, `_analyze.py`, `_donate.py`, `_settings.py` — миксины
  (`CoreMixin`, `WizardMixin`, …), методы распределены по доменам;
- `main_window.py` — тонкий: класс-атрибуты, `__init__`, темы, сборка
  `MainWindow` из миксинов + `i18n_report` + `run_app`.

Если добавляете метод и он не обязан жить именно в `main_window.py`, кладите
его в подходящий миксин по названию. Новые UI-функции — сразу с переводами
в `i18n.py` (RU и EN) и прогоном тестов.

## Тесты

Полный прогон — из корня, иначе не находится `_bootstrap`:

```
python -m unittest discover -s tests -t tests
```

Медленный (~20 минут, 421 тест). Быстрее — точечно:
`python -m unittest discover -s tests -t tests -p "test_<имя>.py"`.

Тесты `test_i18n.py` сканируют весь пакет `hackiclab/ui/`, а не один
`main_window.py`.

## Правки экшенов GitHub Actions

`.github/workflows/build-macos.yml` собирает macOS в CI при пуше в `master`.
Имена файлов релиза: `HackicLab_<версия>_windows_x64.exe`,
`HackicLab_<версия>_macos_apple_silicon.zip` (arm64) и
`HackicLab_<версия>_macos_intel.zip` (x86_64). Версия берётся из
`hackiclab/__init__.py`; macOS-архивы собирает workflow, Windows EXE
загружается в релиз вручную.