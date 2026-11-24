# HackicLab 1.1.0 — Pentium/Celeron, Core 2 Duo, Clover и разбор совместимости

Файлы релиза:

- `HackicLab_1.1.0_windows_x64.exe` — Windows x64;
- `HackicLab_1.1.0_macos_apple_silicon.zip` — Mac с Apple Silicon (arm64);
- `HackicLab_1.1.0_macos_intel.zip` — Mac с Intel (x86_64).

К каждому файлу лежит `.sha256`.

## Новое железо

- **Pentium/Celeron 7–12 поколений**: подмена CPUID и DummyPowerManagement,
  iGPU отключается — нужна дискретная карта.
- **AMD Ryzen 5 5600G (Cezanne)**: графика через NootedRed.
- **Intel Core 2 Duo/Quad (Penryn)**: High Sierra, FakeSMC вместо VirtualSMC.
- Sandy Bridge теперь тоже получает FakeSMC.

## Аудит и предупреждения

- **Clover EFI**: аудит распознаёт `EFI/CLOVER` и показывает SMBIOS, boot-args,
  кексты, драйверы и ACPI-таблицы.
- **macOS 27**: предупреждение, что запуск только через Liberator/патчер.
- **NVIDIA**: предупреждение об отсутствии поддержки с macOS 11.
- **Wi-Fi/Bluetooth и GPU**: подсказки по чипсетам и видеокартам на вкладке
  «Валидация».

## Данные

- Аудиокодеков стало 110+ (добито 18 из вики AppleALC).
- Новые источники: Mist, WhateverGreen, OpenCore Configuration.pdf.

> Сборка без подписи: Defender иногда ругается на EXE. Сверяйте SHA-256
> с файлом `.sha256` из релиза.
