#!/usr/bin/env bash
# Regenerate the ToucanOverlay app icon (left half of the keymap outlines).
#
# Requires: rsvg-convert (brew install librsvg) and iconutil (macOS).
#   ./build-icon.sh   # rewrites icon.svg and ToucanOverlay.icns

set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

python3 gen_icon.py icon.svg

ICONSET=$(mktemp -d)/ToucanOverlay.iconset
mkdir -p "$ICONSET"
gen() { rsvg-convert -w "$1" -h "$1" icon.svg -o "$ICONSET/$2"; }
gen 16   icon_16x16.png
gen 32   icon_16x16@2x.png
gen 32   icon_32x32.png
gen 64   icon_32x32@2x.png
gen 128  icon_128x128.png
gen 256  icon_128x128@2x.png
gen 256  icon_256x256.png
gen 512  icon_256x256@2x.png
gen 512  icon_512x512.png
gen 1024 icon_512x512@2x.png
iconutil -c icns "$ICONSET" -o ToucanOverlay.icns

# Menu-bar status item: a vector template (PDF) macOS tints for the status bar.
python3 gen_icon.py menubar.svg --menubar
rsvg-convert -f pdf menubar.svg -o ../Sources/ToucanOverlay/Resources/toucan-menubar.pdf

echo "==> wrote $(pwd)/ToucanOverlay.icns"
echo "==> wrote $(pwd)/../Sources/ToucanOverlay/Resources/toucan-menubar.pdf"
