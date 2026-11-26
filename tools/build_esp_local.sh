#!/usr/bin/env bash
# Build on YOUR computer. No GitHub token, upload, publish or Firebase usage.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RADIO="${1:-wifi-ble}"
FLASH="${2:-4}"
GPIO="${3:-4}"
HOLD="${4:-3}"
DEST="${5:-$ROOT/out-local}"
# Only the tracked, reviewed source snapshot is used.
REF="$(git -C "$ROOT" rev-parse HEAD)"
git -C "$ROOT" diff --quiet HEAD -- recovery tools LICENSE || { echo "Commit or discard tracked source changes before building"; exit 1; }
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$WORK/source" "$DEST"
git -C "$ROOT" archive "$REF" recovery tools LICENSE | tar -xf - -C "$WORK/source"
python3 "$WORK/source/tools/esp_profiles.py" prepare esp32c3 "$RADIO" "$FLASH" "$GPIO" "$HOLD"
IMAGE='espressif/idf@sha256:4317595a911886e04cbc6d731315d5fc2918e510b6733fc7d03381ab2d270082'
docker pull "$IMAGE"
docker run --rm --user "$(id -u):$(id -g)" -v "$WORK/source:/project" -w /project/recovery -e HOME=/tmp -e RADIO="$RADIO" -e FLASH="$FLASH" -e GPIO="$GPIO" -e HOLD="$HOLD" -e SOURCE_REF="$REF" -e TARGET=esp32c3 "$IMAGE" bash -ec '
  idf.py -DIDF_TARGET=esp32c3 -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.transport" build
  python /project/tools/audit_esp.py
  python -m venv /tmp/fs-sbom
  /tmp/fs-sbom/bin/pip install --disable-pip-version-check esp-idf-sbom==1.3.1
  /tmp/fs-sbom/bin/esp-idf-sbom create --file-tags -o /project/audit/application.spdx build/project_description.json
  python /project/tools/collect_esp_notices.py
  python /project/tools/notice_bundle.py /project/audit "$IDF_PATH" /project/THIRD_PARTY_NOTICES.txt
  python /project/tools/local_esp_package.py /project/recovery/build "$RADIO" "$FLASH" "$GPIO" "$HOLD" /project/out /project/THIRD_PARTY_NOTICES.txt "$SOURCE_REF"
'
cp "$WORK/source/out/"*.zip "$WORK/source/out/catalog.json" "$DEST/"
echo "Local test candidate in $DEST. Not hardware-tested; do not redistribute."
