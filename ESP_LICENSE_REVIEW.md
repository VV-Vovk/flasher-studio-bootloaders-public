# ESP Recovery redistribution review — HOLD

This is a technical evidence-gathering stage, not approval to distribute. The public audit workflow builds ESP32-C3 4 MiB Wi-Fi, BLE and combined configurations but uploads only textual dependency inventories and SPDX data. No ESP binaries, SDK source archives, ELF, ZIP or build folders are released. Other ESP targets remain on hold.

## Preliminary upstream findings
- ESP-IDF v5.4.x original code: Apache-2.0; component/file-specific licenses take precedence.
- Espressif esp32-wifi-lib and esp32-bt-lib: upstream states Apache-2.0 applies to precompiled object libraries. Exact checked-out submodule revisions still require review.
- FreeRTOS, lwIP, NimBLE, mbedTLS, newlib and other linked components may require their own notices/license texts. Compiler runtime and separate second-stage bootloader must be accounted for as well.
- SPDX SBOM is not a legal opinion, and file tags do not establish completeness. NOASSERTION, missing notice files or unidentified archives must be resolved manually.

References:
https://docs.espressif.com/projects/esp-idf/en/release-v5.4/esp32/COPYRIGHT.html
https://github.com/espressif/esp32-wifi-lib
https://github.com/espressif/esp32-bt-lib
https://github.com/espressif/esp-idf-sbom
https://github.com/espressif/esp-idf/tree/v5.4.2

Before public binary release: pin reviewed SDK image and submodule revisions, account for every linked library and compiler runtime in application and bootloader, assemble required actual notices and corresponding source where applicable, review vulnerability/support status and non-copyright obligations (e.g. Bluetooth qualification if relevant), test on actual hardware and explicitly approve the exact profile. Repeat for other targets/radio combinations; do not infer approval for a different build from C3. Preserve the existing private repository. No automatic release job for ESP exists.
