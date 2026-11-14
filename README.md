# HackicLab

**Интеллектуальный сборщик Hackintosh EFI** — GUI-приложение (RU/EN), которое сканирует ваше железо на Windows, автоматически подбирает и **реально скачивает** kext и OpenCore, генерирует `config.plist`, прогоняет его через **ocvalidate** и даёт рекомендации.

[![Лицензия: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Версия](https://img.shields.io/badge/version-v1.0.0-brightgreen.svg)](https://github.com/SLEP-KOMP/HackicLab/releases)
[![Платформа: Windows](https://img.shields.io/badge/platform-Windows-0078d6.svg)](https://github.com/SLEP-KOMP/HackicLab)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](https://www.python.org/)
[![GUI: PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

## Возможности

- **Автосканирование железа** на Windows (CPU/GPU/аудио/сеть/host-платформа) через WMI/CIM/PnP/PowerShell.
- **Реальная загрузка** OpenCore и kext (Lilu, VirtualSMC, AppleALC и др.) с GitHub с локальным кэшем и обходом лимитов API.
- **Генерация `config.plist`** под ваш профиль: kext, SSDT, SMBIOS, ig-platform-id.
- **Выбор macOS-версии** перед сборкой (Tahoe…High Sierra) с защитой от несовместимости железа.
- **Валидация ocvalidate** собранного конфига в процессе сборки, вывод ошибок/предупреждений в журнал.
- **Анализ ваших файлов**: укажите папку с kext/EFI — HackicLab сопоставит с железом, найдёт недостающие kext, несовместимости и даст рекомендации.
- **Тёмная тема** (dark/light/system/custom), современный интерфейс PySide6, **два языка** (русский/английский).
- **Модель «сначала бесплатно»**: скан, сборка и анализ бесплатны; задел под Premium-функции (`license.py`).

## Требования

- **Платформа:** Windows только.
- **Python 3.10+** (для запуска из исходников) либо готовый `HackicLab.exe`.

## Загрузка

Готовый портативный дистрибутив для Windows — в разделе [Releases](https://github.com/SLEP-KOMP/HackicLab/releases). Просто скачайте `HackicLab.exe` и запустите — установка не требуется.

## Технологии

| Слой | Технология |
|------|-----------|
| Язык | Python 3.10+ |
| GUI | PySide6 (Qt), тёмная тема, i18n |
| Сканер | WMI / CIM / PnP / PowerShell |
| Конфиг | plistlib (config.plist OpenCore) |
| Валидация | встроенный `ocvalidate` из пакета OpenCore |
| Сеть | GitHub Releases (redirect `latest` + `expanded_assets`) |
| Упаковка | PyInstaller → `HackicLab.exe` |
| Монетизация | `license.py` (Free → Premium) |

Архитектура ядра переиспользует проверенные подходы экосистемы OpenCore: [hackmate](https://github.com/CorpNewt/hackmate), [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify), [SSDTTime](https://github.com/corpnewt/SSDTTime), [USBToolBox](https://github.com/USBToolBox/tool), [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg).

## Установка (разработка)

```powershell
python -m pip install PySide6 psutil
python main.py
```

## Сборка EXE

```powershell
python -m PyInstaller --noconfirm --clean HackicLab.spec
# результат: dist/HackicLab.exe
```

## Структура проекта

```
hackiclab/
  scanner/      # модели + сканер железа Windows
  knowledge/    # kextDB, OC-платформы, SSDT-логика
  builder/      # загрузка, config.plist, SMBIOS, EFI, ocvalidate
  analyzer/     # анализ файлов и рекомендации
  ui/           # главное окно PySide6
  assets/acpi/  # встроенные SSDT (.aml)
  i18n.py       # RU/EN переводы
  themes.py     # темы оформления
  license.py    # Free/Premium
main.py         # точка входа
HackicLab.spec  # конфигурация PyInstaller
```

## Дорожная карта

1. **Сейчас**: скан железа, реальная загрузка OpenCore/kext, генерация `config.plist`, выбор macOS-версии, валидация ocvalidate, анализ своих EFI-файлов.
2. **Скоро**: полная приведённая к нулю валидация config.plist, авто-подбор SMBIOS под выбранную версию, отдельная вкладка результатов валидации.
3. **Premium (будущее)**: облачные профили, авто-обновления, расширенный анализ совместимости.

## Лицензия

MIT. Построено на открытых технологиях сообщества OpenCore.

> ⚠️ Проект создан для изучения и законного использования. Устанавливайте macOS только на оборудование, которое вы имеете право использовать, соблюдая лицензию Apple. Инструмент помогает автоматизировать рутинную работу; конечная ответственность за совместимость — на пользователе.