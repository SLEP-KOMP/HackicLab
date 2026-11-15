# План переноса фич из hackmate в HackicLab

**Статус:** черновик плана · **Дата:** 2026-11-15
**Источник:** [hackmatelabs/hackmate](https://github.com/hackmatelabs/hackmate) v4.0.0 (MIT), локальная сборка `D:\HackMate-Flutter-GUI-Windows`, эталонный EFI `D:\OpCore-Simplify-main\...\Results\EFI`
**Приёмник:** HackicLab (этот репозиторий)

---

## 0. Принципы переноса

1. **Переносим идеи и алгоритмы, а не код целиком.** hackmate — MIT, но его стиль (TUI + Flutter-мост + POSIX-ветки) нам не подходит. Заимствуем логику и переписываем под нашу архитектуру (`scanner` / `knowledge` / `builder` / `analyzer` / `ui`).
2. **Ничего не дублируем.** Если функциональность у нас уже есть (запись на USB, macOS Recovery, генерация `config.plist`, проверка `ocvalidate`), мы расширяем её, а не делаем вторую.
3. **Каждая фича проходит через i18n (RU/EN) и вкладку.** Новые строки — только через `hackiclab/i18n.py` (`tr.t("...")`).
4. **Windows-only.** Не тащим linux/macos-ветки, `sudo`, `lspci`, `ioreg`.
5. **Обратная совместимость.** Новые поля `HardwareProfile` / `BuildPlan` — с дефолтами, чтобы старые `.hackiclab` профили читались.

---

## 1. Сводная таблица

| № | Фича hackmate | Приоритет | Объём | Куда в HackicLab |
|---|---|---|---|---|
| 1 | EFI Health Check (аудит любого EFI) | **P0** | M | новый `analyzer/efi_health.py` + вкладка «Валидация» |
| 2 | Rationale (объяснение решений) | **P0** | S–M | новый `knowledge/rationale.py` + вкладка «Сборка» |
| 3 | Config Editor (правка `config.plist`) | **P1** | M | новый `builder/config_editor.py` + вкладка «Валидация» |
| 4 | Build History + Restore EFI | **P1** | S–M | новый `builder/history.py` + вкладка «Запись на USB» |
| 5 | Repair EFI с бэкапом | **P1** | S | расширить `builder/usb_writer.py` |
| 6 | Автоматический USB-маппинг | **P2** | L | новый `builder/usb_map.py` |
| 7 | Dual Boot / Disk Map | **P2** | M | новый `scanner/diskmap.py` + вкладка «Запись на USB» |
| 8 | Log Checker (разбор логов OpenCore) | **P2** | M | новый `analyzer/oc_log.py` + вкладка «Анализ» |
| 9 | HWDB submit (анонимная телеметрия железа) | **P3** | S | опционально, только с согласия |
| 10 | HackMate Core (граф. пикер OpenCanopy) | **P3** | M | расширить `builder/efi_layout.py` |

Объём: S ≈ до 100 строк, M ≈ 100–400, L ≈ 400+.

---

## 2. Детально по фичам

### №1. EFI Health Check — аудит любого EFI · P0

**Что делает в hackmate:** модуль `efi_health.audit(efi_root)` разбирает *любой* OpenCore EFI (в т.ч. собранный руками) и возвращает список `(level, title, detail)`, где level ∈ `critical|warn|info|ok`. Проверки:
- **ACPI**: «осиротевшие» ренеймы — в `config.plist` есть `Find/Replace`, но целевого имени в SSDT нет (`_check_acpi`, `_acpi_names_defined`).
- **Kexts**: отсутствует исполняемый файл бандла; устаревшие kexts из `DEPRECATED_KEXTS`; нарушения порядка загрузки (`LILU_DEPENDENTS` — плагины без Lilu).
- **USB-маппинг**: бандл `USBMap.kext`/`UTBMap.kext` присутствует, но внутри нет портов; или маппинг не соответствует железу (`_check_usb_map`).
- **SIP**: побитовое декодирование `csr-active-config` в человекочитаемые флаги (`_decode_csr`).
- **PlatformInfo**: не задан SMBIOS / противоречивые поля (`_check_platform_info`).
- **boot-args**: отсутствует `-no_compat_check` там, где нужен (`_check_boot_args`).
- **Итог**: `summarise()` (счётчики) + `format_report()` (текстовый отчёт).

**Кому у нас:** `hackiclab/analyzer/efi_health.py`.

**Точки интеграции:**
- `analyzer/engine.py` уже имеет `Analyzer` + `AnalysisIssue(severity, code, title, detail, kext, suggestion)` и `Severity` (INFO/WARNING/ERROR). Переиспользуем структуру: level `critical→ERROR`, `warn→WARNING`, `info/ok→INFO`. Это позволит показывать результаты существующим механизмом.
- Вкладка «Валидация»: `main_window.py:402 _build_validate`, `:483 _do_validate`, `:506 _validate_done`, `:138 ValidateWorker`. Добавить вторую кнопку «Аудит EFI…» (выбор папки) и отдельный блок результатов под `ocvalidate`-сводом.
- `ocvalidate.py` (`OCVResult`) не трогаем — аудит идёт рядом.

**Шаги:**
1. `analyzer/efi_health.py`: `audit(efi_root: Path) -> list[AnalysisIssue]` + хелперы `_decode_csr`, `_acpi_names_defined` (парс `.aml`/`.dsl` на имена), `_kext_executable`, `_usb_bundle_info`, `DEPRECATED_KEXTS`.
2. `Analyzer.audit_efi(folder)` — обёртка, возвращающая issues.
3. UI: кнопка + вывод; группировка по severity, фильтр «только ошибки».
4. i18n: блок `efihealth.*` (RU/EN).
5. Тест на эталонном EFI с диска D (`Results\EFI`) — ожидаем «чисто» или минимальные предупреждения.

**Риски:** парсинг AML без сторонних зависимостей — ограничиться поиском ASCII-имён (как в hackmate), не полноценным дизассемблером.

---

### №2. Rationale — объяснение решений · P0

**Что делает в hackmate:** `rationale.explain(...)` собирает список `Decision(section, key, value, reason, doc_url)` по разделам: macOS-версия, SMBIOS, kexts, SSDT, Kernel, boot-args, DeviceProperties, Booter, UEFI. Затем `render()` — читаемый текст / `to_rows()` — таблица.

**Зачем нам:** это ключевая «прозрачность» — пользователь видит, **почему** выбран каждый kext/квирк. Хорошо дополняет вкладку «Валидация» и нашу модель «рекомендации».

**Кому у нас:** новый `hackiclab/knowledge/rationale.py`.

**Точки интеграции:**
- Данные берём из уже существующих `knowledge/kexts.py` (`select_kexts`, `KEXT_DB`, `smbios_model_for`), `builder/config_gen.py` (`_apply_macos_model`, quirk-набор), `builder/ssdt_factory.py`, `knowledge/oc_platforms.py`.
- Показ — вкладка «Сборка» (`_build_done`), блок «Почему так собрано». Плюс выгрузка в `.txt`/`.md` рядом с EFI.

**Шаги:**
1. `rationale.py`: `Decision` dataclass + `explain(profile, plan, macos_target) -> list[Decision]`.
2. Заполнить причинами: почему MacPro7,1 (AMD, без iGPU), почему `ProvideCurrentCpuInfo` (AMD), почему эти kexts (Wi-Fi BCM4360 → AirportBrcmFixup; Apple BT → без BrcmPatchRAM).
3. UI-блок + кнопка «Сохранить объяснение».
4. i18n.

**Риски:** причины не должны «врать» — текст только для решений, реально принятых генератором (без выдуманных пунктов).

---

### №3. Config Editor — правка `config.plist` · P1

**Что делает в hackmate:** `config_editor.py` — безопасные get/set по dot-пути, парс/сборка `boot-args`, SIP вкл/выкл (`set_sip`), `HideAuxiliary`, `Timeout`, OC-логирование, `SecureBootModel`, SMBIOS-модель, `ig-platform-id` для iGPU + `suggest_framebuffers()`.

**Зачем нам:** после `ocvalidate` и аудита пользователь хочет **исправить** найденное, не открывая ProperTree.

**Кому у нас:** новый `hackiclab/builder/config_editor.py` (+ простая форма в UI).

**Точки интеграции:**
- `builder/config_gen.py` умеет генерировать, но не править чужой файл. Editor — отдельный слой поверх `plistlib`.
- UI: на вкладке «Валидация» — панель «Быстрые правки» (boot-args, SIP, Timeout, SecureBootModel, SMBIOS-модель) с кнопкой «Сохранить» и авто-бэкапом.
- Совместимо с нашим `disable_sip`/`csr-active-config` (`config_gen.py:139–141`) — используем те же значения.

**Шаги:**
1. `config_editor.py`: `get_value/set_value`, `get/set_boot_args`, `get/set_sip`, `get/set_timeout`, `get/set_secure_boot_model`, `get/set_smbios`, `suggest_framebuffers`.
2. Бэкап `config.plist.bak` перед любой записью.
3. UI-форма + валидация значений (не дать сломать plist).
4. После сохранения — предложить перезапустить `ocvalidate`.

**Риски:** запись битых типов (data vs string) — строгая типизация по исходному значению.

---

### №4. Build History + Restore EFI · P1

**Что делает в hackmate:** `build_history.py` хранит записи о сборках; `restore` умеет откатиться к предыдущему EFI из бэкапа. Flutter-UI имеет экраны «Build History» и «Restore EFI».

**Кому у нас:** новый `hackiclab/builder/history.py`.

**Точки интеграции:**
- Хранилище — `.hackiclab/history/` (уже в `.gitignore`) или `%LOCALAPPDATA%\HackicLab\history`.
- Запись создаётся в конце `EFIBuilder.build()` (`builder.py`).
- UI: вкладка «Запись на USB» — список прошлых сборок с кнопкой «Восстановить»/«Открыть папку».

**Шаги:**
1. `history.py`: `HistoryEntry` (дата, профиль, macOS, путь EFI, версия OC, статус ocvalidate), `list()`, `add()`, `restore(id)`.
2. Хук в `builder.build()`.
3. UI-список + restore через `usb_writer.copy_efi`.
4. i18n `history.*`.

**Риски:** хранение больших EFI — храним только метаданные + путь, копию делаем при restore.

---

### №5. Repair EFI с резервной копией · P1

**Что делает в hackmate:** режим «Repair EFI» обновляет OpenCore/kexts/config на существующем EFI, **сначала делая бэкап**.

**У нас уже есть:** режимы Full / Already Formatted / Repair (`usb_writer.write_efi_to_usb(skip_format=...)`), но бэкапа перед ремонтом нет.

**Шаги:**
1. В `usb_writer.py`: перед `copy_efi` при `repair_mode` — скопировать существующий `EFI\` в `EFI_backup_<YYYYMMDD-HHMMSS>\`.
2. Сообщить путь бэкапа в логе и UI.
3. Связать с историей (№4), чтобы бэкап был восстановим из интерфейса.

**Риски:** мало места на флешке — проверять свободный объём перед бэкапом.

---

### №6. Автоматический USB-маппинг · P2

**Что делает в hackmate:** `auto_usb_map.py`:
- `generate_dsdt_map()` — из DSDT (через `iasl`) достаёт `_ADR`, типы коннекторов (`_UPC`) и индексы портов;
- `dump_controllers()` — запускает `usbdump.exe` (из USBToolBox) и снимает реальные порты;
- `build_map_plist()` — собирает итоговый `Info.plist` для USBMap/UTBMap.

**У нас уже есть:** `ssdt_factory.py` качает `iasl` (`open-acpica/acpica`) и умеет компилировать DSL — то есть половина инфраструктуры готова. В дорожной карте README это «расширенный маппинг USB-портов».

**Шаги:**
1. `builder/usb_map.py`: `dsdt_ports()`, `usbdump_ports()`, `build_utbmap()`.
2. Взять `usbdump.exe` из `D:\USBToolBox-1.2.0-RELEASE` (или качать из релиза USBToolBox, как это делает hackmate).
3. Кешировать результат в `.hackiclab/cache/usbmap/`.
4. UI: блок «USB-порты» на вкладке «Запись на USB» — «Определить порты» → предпросмотр → «Добавить USBMap.kext в EFI».
5. i18n `usbmap.*`.

**Риски:** `usbdump` требует прав администратора и живой загрузки Windows; без него — фолбэк только на DSDT. Не обещать полноценный маппинг, если данных мало.

---

### №7. Dual Boot / Disk Map · P2

**Что делает в hackmate:** `dualboot.py` — `scan_disks()`, `detect_bootloaders()` (Windows EFI, GRUB, OpenCore), `check_conflicts()` (несколько загрузчиков в одном ESP), `build_disk_tree()`, `fix_macos_boot()`.

**Кому у нас:** новый `hackiclab/scanner/diskmap.py` (или `builder/diskmap.py`).

**Шаги:**
1. Через PowerShell `Get-Disk`/`Get-Partition`/`Get-Volume` (стиль уже есть в `usb_writer.py:52`).
2. Определить ESP-разделы и загрузчики по структуре `EFI/Microsoft`, `EFI/BOOT`, `EFI/OC`, `EFI/systemd`.
3. Предупреждать о конфликтах при записи EFI на диск с существующим загрузчиком.
4. UI: вкладка «Запись на USB» — «Карта дисков» (только чтение, без записи).

**Риски:** **никаких операций записи** в чужой ESP на этом этапе — только просмотр и предупреждения.

---

### №8. Log Checker · P2

**Что делает в hackmate:** `log_checker.py` (55 КБ) разбирает логи OpenCore (`OC_LOG`), находит типовые ошибки загрузки (kext не инжектится, ACPI-ошибки, паники) и подсказывает причину.

**Кому у нас:** новый `analyzer/oc_log.py` (упрощённая версия — не тащим 55 КБ).

**Шаги:**
1. Парсер строк `OpenCore`-лога: уровни, `OC: ` префиксы, коды ошибок.
2. Маппинг «ошибка → причина → что делать» (10–15 самых частых кейсов).
3. UI: вкладка «Анализ» — «Проверить лог…» (файл или папка).
4. i18n `oclog.*`.

**Риски:** формат лога меняется между версиями OC — держать правила терпимыми (regex, а не жёсткая схема).

---

### №9. HWDB submit · P3 (опционально)

**Что делает:** отправляет анонимный профиль железа в общую базу для улучшения совместимости. У hackmate — с явным экраном согласия.

**Решение:** внедрять только по явному запросу и только с осознанным согласием пользователя (галочка, показ отправляемых полей, без серийников/UUID). По умолчанию — **выключено**. Сейчас не приоритет.

---

### №10. HackMate Core (графический пикер) · P3

**Что делает:** добавляет тему OpenCanopy (`Resources/Image/HackMate/…`) + ключи `config.plist`, чтобы вместо чёрно-белого меню был графический пикер с мышью.

**У нас:** `efi_layout.py` уже умеет класть `Resources` и `OpenCanopy` (исключается при Builtin-пикере).

**Шаги:** опциональная галочка «Графический пикер (OpenCanopy)» при сборке: копировать тему, включить `PickerMode=External`, `PickerVariant`. Свои ассеты делать не копируя чужие картинки — либо лицензионно чистые, либо генерировать свои.

**Риски:** размер EFI + лицензии на изображения. Отложено.

---

## 3. Порядок работ (рекомендуемый)

| Этап | Содержание | Результат |
|---|---|---|
| **Этап 1** | №1 EFI Health Check + №5 Repair с бэкапом | Вкладка «Валидация» реально находит проблемы в чужом EFI; запись стала безопаснее |
| **Этап 2** | №2 Rationale + №3 Config Editor | Пользователь понимает и может исправить сборку |
| **Этап 3** | №4 History/Restore + №7 Disk Map | Откат сборок и предупреждения о загрузчиках |
| **Этап 4** | №6 USB-маппинг + №8 Log Checker | Закрываем «Скоро» из дорожной карты |
| **Этап 5** | №9 HWDB (опц.) + №10 OpenCanopy (опц.) | Полировка |

Каждый этап завершается: RU/EN строки, `python -m compileall`/запуск, обновление README-дорожной карты, коммит.

---

## 4. Что НЕ переносим

- **TUI (textual) и Flutter-мост** — у нас PySide6-нативная архитектура.
- **Linux/macOS-ветки** (`sudo`, `lspci`, `ioreg`, `/Volumes`) — проект Windows-only.
- **Авто-обновление через GitHub** (у hackmate `updater.py`) — у нас отдельная стратегия релизов; при желании делается отдельной задачей.
- **Discord-инвайты и промо-экраны** — не наш продукт.
- **Копирование чужих ассетов/картинок** без лицензии.

---

## 5. Критерии готовности фичи

- [ ] Работает на реальном эталонном EFI с диска D и на пустой/битой папке (без падений).
- [ ] Все новые строки — в RU и EN.
- [ ] Не ломает существующие сценарии (сборка, запись на USB, Recovery, валидация).
- [ ] Логи/отчёт понятны пользователю без чтения кода.
- [ ] Обновлены README (возможности + дорожная карта).
