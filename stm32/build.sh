#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
CC=${CC_ARM:-arm-none-eabi-gcc}
OBJCOPY=${OBJCOPY_ARM:-arm-none-eabi-objcopy}
"$CC" -mcpu=cortex-m3 -mthumb -Os -Wall -Wextra -Werror -Wno-misleading-indentation -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -nostdlib -Wl,--gc-sections,-Map=build/bootloader.map -T boot.ld start.S boot.c -o build/bootloader.elf
"$OBJCOPY" -O binary build/bootloader.elf build/bootloader.bin
