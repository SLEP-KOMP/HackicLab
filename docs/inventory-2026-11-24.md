# Инвентарь HackicLab и сверка с внешними источниками

Дата: 24.11.2026. Методика: подсчёт по коду проекта + сверка с публичными
доками AppleALC (wiki v1.9.8 от 30.09.2026), itlwm, WhateverGreen, Dortania
и темами сообщество. Цифры по чужим каталогам приблизительные: списки большие,
часть названий — алиасы одной и той же микросхемы.

## Что у нас есть

| Раздел | Количество |
|---|---|
| Кексты в базе (`KEXT_DB`) | 57 |
| Источники (`SOURCES`) | 30: hardware — 10, efi — 9, community — 6, guides — 5 |
| Пресеты каталога | 26: desktop Intel — 10, desktop AMD — 5, ноутбуки — 5, мини — 3, рабочие станции — 3 |
| Аудиокодеки (`LAYOUTS`) | 92 |
| PCI-патчи аудиоконтроллеров | 109 |
| Ethernet-чипсеты (распознавание) | 11 семейств: I217/I218/I219/I210/I211/I225/I226/I350, RTL8111, RTL8125, generic Intel/Realtek |
| Wi-Fi семейства | Broadcom, Intel (itlwm/AirportItlwm), Atheros (ATH9KFixup); MediaTek — «не поддерживается» |
| Bluetooth | Broadcom (BrcmPatchRAM), Intel (IntelBluetoothFirmware + BTPatcher) |
| GPU | Intel iGPU Sandy Bridge…Comet Lake, AMD Polaris/Navi 1x/Navi 2x/Vega, APU Raven/Cezanne (NootedRed); NVIDIA — предупреждение |
| Загрузчики | OpenCore (сборка и аудит), Clover (разбор EFI) |
| Legacy | Core 2 Duo (High Sierra), Sandy/Ivy (High Sierra/Catalina), Nehalem/Westmere |

## Сверка с AppleALC

В вики AppleALC v1.9.8 перечислено порядка 110–125 записей кодеков (Realtek,
Conexant, IDT, VIA, Cirrus, Creative, SigmaTel, Analog Devices), часть —
алиасы вроде ALC271X = ALC269. У нас 92 кодека.

Реально не хватает (встречаются в вики, у нас нет):

- Realtek: ALC284, ALC665, ALC882
- Cirrus: CS4206, CS4210
- Conexant: CX20583, CX20588, CX20722, CX20724, CX20755, CX20756
- VIA: VT2021
- Analog Devices: AD2000B
- IDT: 92HD71B7X, 92HD75B2X5, 92HD75B3X5, 92HD87B1, 92HD99BXX

Алиасы (ALC3234/3246/3253/3236/3241/867/899/1200, CX11880, CX20752/54)
считать отдельными кодеками не нужно — это те же микросхемы.

## Сверка с itlwm

itlwm поддерживает Intel-адаптеры серий 3160/3165/3168/7260/7265/8260/8265,
9260/9560, AX200/AX201/AX210/AX211 и часть BE200. У нас есть кексты itlwm и
AirportItlwm, но нет таблицы «чипсет → кекс → ограничения»: в UI видно только
семейство (Intel), а не конкретная модель.

## Сверка с WhateverGreen / Dortania

- Intel iGPU: поколения 2–10 (Sandy…Comet) — покрыты правилами ig-platform-id.
- AMD: Polaris, Navi 10/14/21/22/23, Vega — покрыты, NootRX для Navi 2x,
  NootedRed для APU Raven/Cezanne.
- NVIDIA: начиная с Big Sur не поддерживается; добавлено предупреждение.
- Нет видимой таблицы «device-id → поддерживается/нет»: логика есть, но
  пользователь не видит списка.

## Источники: что добавлено и чего не хватает

Добавлено в этот заход: Mist (загрузка установщиков macOS).

Не хватает ссылок в каталоге:

- документация WhateverGreen (таблица поддержки GPU);
- вики AppleALC «Supported codecs»;
- страница совместимости itlwm;
- документация OpenCore 1.0.9 (Configuration.pdf);
- OCLP docs (патчи для снятого с поддержки железа).

## Приоритеты

1. Добить ~13 аудиокодеков из списка выше (таблица `audio_layouts`).
2. Таблица Wi-Fi/BT: чипсет → кекс → что не работает (особенно Intel AX/BE).
3. Видимая матрица GPU по device-id (Intel/AMD/NVIDIA).
4. Добавить 5 ссылок из раздела «Источники».

## Ограничения подсчёта

Списки AppleALC и itlwm меняются с релизами; сравнение сделано по состоянию
на 30.09.2026. Точное число «поддерживаемых» кодеков зависит от того, считать
ли алиасы; поэтому цифры даны с оговоркой.
