# Flasher Studio — public bootloader library

This repository publishes independently implemented bootloader candidates and links to upstream projects. No end-user firmware, credentials or private build history belongs here.

## Available package after CI publication
STM32F103C8T6 FS10 UART Recovery v0.2.2 — Apache-2.0, freestanding build, no external SDK or linked library, license included in ZIP. Experimental; not hardware-tested. Install explicitly over SWD only after backup, then update applications linked to 0x08004000 via UART. See stm32/README.md.

## Third-party sources
- AVR: [Arduino AVR core](https://github.com/arduino/ArduinoCore-avr), [MiniCore 3.0.2](https://github.com/MCUdude/MiniCore/tree/0bb50f6a6648e37cbe53012c61322345847c2a03), [Urboot](https://github.com/stefanrueger/urboot). Flasher Studio may retrieve exact original HEX directly from upstream and check known hashes; this repo does not redistribute AVR binaries.
- Nordic: [Adafruit nRF52 Bootloader](https://github.com/adafruit/Adafruit_nRF52_Bootloader/releases). Board-specific releases and separate SoftDevice terms; no mirroring.
- ESP: [ESP-IDF](https://github.com/espressif/esp-idf/tree/v5.4.2). Binary release deferred until linked-component license and notice review is complete.
- Factory ROM: consult the chip vendor's documentation; do not install a ROM bootloader.

No automatic installation. CI verification is not a hardware test. A new release must use a new version; never silently replace an existing package. License of local source: Apache-2.0 (see LICENSE); external projects retain their own licenses.
