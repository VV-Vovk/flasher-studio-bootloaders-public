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

## Build an ESP32-C3 Recovery candidate on your own PC (no publication)

Linux/WSL with Docker, Git, Bash and Python 3. Clone this repository, then run:

```bash
bash tools/build_esp_local.sh wifi-ble 4 4 3
# arguments: radio (wifi / ble / wifi-ble), Flash MiB, GPIO, hold seconds (0–5)
```

Defaults: Wi-Fi + BLE, 4 MiB, GPIO4, 3 seconds. Verify the actual board and Flash size first. Outputs: local ZIP and catalog.json in out-local. They are for own hardware experiments only, not public redistribution. The tool uses a pinned ESP-IDF image, a committed source snapshot, checks actual generated configuration and flash offsets, includes a conservative original notice inventory plus SPDX, and never uploads binaries. Local output is not hardware-tested. Browser import of local catalogs is a separate integration step.
