# HackicLab

**Интеллектуальный сборщик Hackintosh EFI** — GUI-приложение (RU/EN), которое сканирует ваше железо на Windows, автоматически подбирает и **реально скачивает** kext и OpenCore, генерирует `config.plist` по **полной схеме OpenCore**, прогоняет его через **ocvalidate** начисто и даёт рекомендации. Включает запись EFI на USB и полноценный установщик macOS Recovery.

[![Release](https://img.shields.io/github/v/release/SLEP-KOMP/HackicLab?include_prereleases&style=flat-square&label=Release)](https://github.com/SLEP-KOMP/HackicLab/releases)
[![Downloads](https://img.shields.io/github/downloads/SLEP-KOMP/HackicLab/total?style=flat-square&label=Downloads)](https://github.com/SLEP-KOMP/HackicLab/releases)
[![Лицензия: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Платформа: Windows](https://img.shields.io/badge/platform-Windows-0078d6.svg)](https://github.com/SLEP-KOMP/HackicLab)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab.svg)](https://www.python.org/)
[![GUI: PySide6](https://img.shields.io/badge/GUI-PySide6-green.svg)](https://doc.qt.io/qtforpython/)

> **Статус:** опубликованная версия v1.0.2 — обычный (Latest) релиз. Функции активно развиваются; перед операциями записи EFI на USB обязательно сохраняйте резервные копии важных данных.

## Возможности

- **Автосканирование железа** на Windows (CPU/GPU/аудио/сеть/host-платформа) через WMI/CIM/PnP/PowerShell с аккуратной детекцией активных беспроводных адаптеров (Wi-Fi/BT по PnP device-id, включая нативные Apple-модули Broadcom BCM94360).
- **Реальная загрузка** OpenCore и kext (Lilu, VirtualSMC, AppleALC и др.) с GitHub с локальным кэшем и обходом лимитов API.
- **Генерация `config.plist` по полной схеме OpenCore 1.0.8/1.0.9** — проходит `ocvalidate` начисто, без ошибок «Missing key».
- **Автоподбор SMBIOS под выбранную macOS-версию** — модель (iMacPro1,1 / MacPro7,1 и т.д.) и Serial/MLB/UUID/ROM подбираются автоматически и реально записываются в `config.plist`.
- **«Почему так собрано»** — после сборки HackicLab объясняет каждое решение (SMBIOS, SecureBootModel, SSDT, kexts, квирки Booter/Kernel, SIP, iGPU) по реально сгенерированному `config.plist`; объяснение можно сохранить в `.md` рядом с EFI.
- **Отдельная вкладка «Валидация»** — детальный свод `ocvalidate` по категориям (пропущенные ключи / ошибки схемы / предупреждения), повторная и ручная валидация.
- **Аудит готового EFI** прямо на вкладке «Валидация»: структура `BOOT/OpenCore.efi`, UEFI-драйверы, kexts и порядок загрузки (Lilu), осиротевшие ACPI-ренеймы, USB-маппинг, PlatformInfo/SMBIOS, SIP и boot-args — с уровнями «ошибка / предупреждение / инфо». 
- **Выбор macOS-версии** перед сборкой (Tahoe…High Sierra) с защитой от несовместимости железа.
- **Анализ ваших файлов**: укажите папку с kext/EFI — HackicLab сопоставит с железом, найдёт недостающие kext, несовместимости и даст рекомендации.
- **Проверки совместимости по источникам** — RX 580 2048SP (device-id `6FDF`) помечается как неподдерживаемая, Intel I211 получает AppleIGB вместо IntelMausi, MediaTek Wi-Fi/BT и Broadcom на Sonoma+ получают явные предупреждения, на Ryzen проверяется наличие патчей AMD Vanilla в `config.plist`.
- **Вкладка «Источники»** — проверенные ссылки (Dortania OpenCore/AMD/GPU/Wireless, AppleIGB, itlwm, OCLP, примеры готовых EFI mikigal/subhead/Maxritz) плюс **каталог типовых конфигураций**: настольные Intel и AMD, ноутбуки, мини-ПК и рабочие станции с поиском, фильтром по категориям, статусом поддержки и списком нужных kext/SSDT/quirks.
- **Запись EFI на USB** (по образцу hackmate, современнее): выбор флешки, режимы Full/Formatted/Repair, подтверждение вводом фразы, BIOS-чеклист.
- **Карта USB-портов (UTBMap)** — порты читаются из DSDT прошивки (через `iasl`), при недоступности — через `usbdump.exe` из USBToolBox; готовая карта сохраняется как `UTBMap.kext` в выбранную EFI.
- **Карта дисков и загрузчиков** — только чтение: диски, разделы, ESP, Windows / OpenCore / Linux / rEFInd, предупреждения о дубликатах OpenCore и MBR-разметке.
- **Проверка лога OpenCore (Log Checker)** — разбор boot-лога по 17 типовым ошибкам с подсказкой на RU/EN и кнопкой включения логирования в `config.plist`.
- **Полноценный установщик macOS Recovery** — загрузка установочных файлов Apple (~600 МБ) в `com.apple.recovery.boot`.
- **Оформление** — по умолчанию следует теме Windows; переключатели в виде экранов монитора (системная, светлая, тёмная, своя), встроенные темы в духе macOS (Aqua, Графит, Sonoma, Big Sur) и свой фон. Современный интерфейс PySide6, **два языка** (русский/английский).
- **Проверка обновлений** — приложение спрашивает последний релиз на GitHub, показывает список изменений и умеет обновить EXE на месте («Обновить сейчас» / «Отложить»).
- **Модель «сначала бесплатно»**: скан, сборка и анализ бесплатны; задел под Premium-функции (`license.py`).

## Требования

- **Платформа:** Windows только.
- **Python 3.10+** (для запуска из исходников) либо готовый `HackicLab.exe`.

## Загрузка

Готовый портативный дистрибутив для Windows — в разделе [Releases](https://github.com/SLEP-KOMP/HackicLab/releases). Просто скачайте `HackicLab.exe` и запустите — установка не требуется.

[Скачать последнюю опубликованную сборку](https://github.com/SLEP-KOMP/HackicLab/releases/latest).

## Технологии

| Слой | Технология |
|------|-----------|
| Язык | Python 3.10+ |
| GUI | PySide6 (Qt), темы (системная по умолчанию), i18n |
| Сканер | WMI / CIM / PnP / PowerShell |
| Конфиг | plistlib (config.plist OpenCore) |
| Валидация | встроенный `ocvalidate` из пакета OpenCore |
| Сеть | GitHub Releases (redirect `latest` + `expanded_assets`) |
| Упаковка | PyInstaller → `HackicLab.exe` |
| Монетизация | `license.py` (Free → Premium) |

Архитектура ядра переиспользует проверенные подходы экосистемы OpenCore: [hackmate](https://github.com/CorpNewt/hackmate), [OpCore-Simplify](https://github.com/lzhoang2801/OpCore-Simplify), [SSDTTime](https://github.com/corpnewt/SSDTTime), [USBToolBox](https://github.com/USBToolBox/tool), [acidanthera/OpenCorePkg](https://github.com/acidanthera/OpenCorePkg).

## Установка (разработка)

```powershell
python -m pip install -r requirements.txt
python main.py
```

Приложение запускается без прав администратора: UAC-запрос появляется только в момент записи EFI на флешку, и HackicLab предлагает перезапуститься с повышенными правами сам.

## Тесты

```powershell
python -m unittest discover -s tests -v
```

Тесты проверяют чистую логику без обращения к реальным дискам и сети: разбор вывода diskpart-скриптов, генерацию `config.plist`, стабильность идентификатора устройства, полноту переводов RU/EN.

## Сборка EXE

```powershell
python -m pip install -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean HackicLab.spec
# результат: dist/HackicLab.exe
```

## Структура проекта

```
hackiclab/
  scanner/      # модели + сканер железа Windows, карта дисков (diskmap)
  knowledge/    # kextDB, OC-платформы, SSDT-логика, rationale, sources
  builder/      # загрузка, config.plist, SMBIOS, EFI, ocvalidate,
                # config_editor, history, usb_writer, usb_map (UTBMap)
  analyzer/     # модели, анализ файлов, аудит EFI (efi_health), лог OC (oc_log)
  ui/           # главное окно PySide6
  assets/acpi/  # встроенные SSDT (.aml)
  i18n.py       # RU/EN переводы
  themes.py     # темы оформления
  license.py    # Free/Premium
main.py         # точка входа
HackicLab.spec  # конфигурация PyInstaller
requirements.txt       # зависимости для запуска
requirements-dev.txt   # зависимости для сборки EXE
tests/          # unittest-тесты чистой логики
```

## Дорожная карта

1. **Сейчас**: скан железа (с точной детекцией Wi-Fi/BT), реальная загрузка OpenCore/kext, генерация `config.plist` по полной схеме OpenCore, выбор macOS-версии, валидация ocvalidate начисто, авто-подбор SMBIOS под версию, отдельная вкладка «Валидация», запись EFI на USB + установщик macOS Recovery, анализ своих EFI-файлов, аудит готового EFI, объяснение решений («Почему так собрано»), быстрые правки `config.plist`, безопасная перезапись с резервной копией, история сборок, карта USB-портов (UTBMap), карта дисков и загрузчиков, проверка лога OpenCore, каталог источников и проверки совместимости (RX 580 2048SP, Intel I211, Wi-Fi/BT, AMD-патчи).
2. **Скоро**: процентный прогресс скачивания, сборка баннеров/скриншотов для README.
3. **Premium (будущее)**: облачные профили, авто-обновления, расширенный анализ совместимости.

## Лицензия

MIT. Построено на открытых технологиях сообщества OpenCore.

> ⚠️ Проект создан для изучения и законного использования. Устанавливайте macOS только на оборудование, которое вы имеете право использовать, соблюдая лицензию Apple. Инструмент помогает автоматизировать рутинную работу; конечная ответственность за совместимость — на пользователе.