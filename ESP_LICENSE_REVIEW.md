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


## ESP32-C3 evidence review, 2026-11-26 — still HOLD

All three 4 MiB profiles (Wi-Fi, BLE, combined) built successfully in [audit run 45803078716](https://github.com/VV-Vovk/flasher-studio-bootloaders-public/actions/runs/45803078716). Each SPDX inventory contains 133 package records and 26 NOASSERTION concluded-license entries; the SDK inventory includes unused components. Both application and second-stage bootloader archive maps were inspected. The first audit used SDK commit `f5c3654a1c2d2a01f7f67def7a0dc48e691f63c0` and image `espressif/idf@sha256:4317595a911886e04cbc6d731315d5fc2918e510b6733fc7d03381ab2d270082`; the next audit pins that image.

Exact radio-library LICENSE files independently inspected at the recorded submodule revisions:
- [Wi-Fi](https://github.com/espressif/esp32-wifi-lib/blob/206fe3e13e788b5fad8be6d39b5d9742e4bd9985/LICENSE)
- [C3/S3 Bluetooth controller](https://github.com/espressif/esp32c3-bt-lib/blob/72599d583c232ea78d6461b5b502426c6e5a1ec9/LICENSE)
- [PHY](https://github.com/espressif/esp-phy-lib/blob/fc76520d481fc3d08cbc001ef47804a4457fffd7/LICENSE)
- [Coexistence](https://github.com/espressif/esp-coex-lib/blob/cb6667841f63457246d56a9170f3409917e9d5a8/LICENSE)

All four texts are Apache-2.0 (identical Git blob d645695673349e3947e8e5ae42332d0ac3164cd7). This is only a component-level license check, not a distribution approval. Retain each applicable copyright and notice. Other unresolved records include lwIP, HTTP Parser, micro-ecc, SDK submodules, and SDK package metadata; distinguish actual linked code from unused/test components. The combined map additionally references newlib libc.a, libstdc++.a and libgcc.a from Espressif GCC 14.2.0 (20241119). Check actual toolchain copyright/license files and eligibility for the GCC Runtime Library Exception, not just a generic GCC license description. See https://www.gnu.org/licenses/gcc-exception-3.1-faq.html .

Second-stage audit collects original notice text, SHA-256, active-map archive/object references, compiler version, unresolved SPDX records. It intentionally does not output firmware. Review of actual notices, per-file obligations, security status, hardware and Bluetooth qualification remains outstanding. Do not treat successful CI as legal approval.
