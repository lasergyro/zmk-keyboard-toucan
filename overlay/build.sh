#!/usr/bin/env bash
# Build ToucanOverlay and assemble a menu-bar .app bundle.
#
#   ./build.sh            # build release .app
#   ./build.sh --run      # build, then (re)launch it
#   ./build.sh --debug    # debug build

set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

CONFIG=release
RUN=0
for arg in "$@"; do
  case "$arg" in
    --run)   RUN=1 ;;
    --debug) CONFIG=debug ;;
    -h|--help) echo "usage: ./build.sh [--run] [--debug]"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 1 ;;
  esac
done

# Keep the bundled fallback SVG in sync with the repo's generated drawing.
if [[ -f ../draw/keymap.svg ]]; then
  cp ../draw/keymap.svg Sources/ToucanOverlay/Resources/keymap.svg
fi

echo "==> swift build -c $CONFIG"
swift build -c "$CONFIG"

BIN_DIR=$(swift build -c "$CONFIG" --show-bin-path)
APP="ToucanOverlay.app"
CONTENTS="$APP/Contents"

echo "==> assembling $APP"
rm -rf "$APP"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"
cp "$BIN_DIR/ToucanOverlay" "$CONTENTS/MacOS/ToucanOverlay"

# Bundle.module resolves relative to the executable — copy the resource bundle
# next to the binary inside the .app.
if [[ -d "$BIN_DIR/ToucanOverlay_ToucanOverlay.bundle" ]]; then
  cp -R "$BIN_DIR/ToucanOverlay_ToucanOverlay.bundle" "$CONTENTS/MacOS/"
fi

# App icon (left half of the keymap; regenerate with icon/build-icon.sh).
if [[ -f icon/ToucanOverlay.icns ]]; then
  cp icon/ToucanOverlay.icns "$CONTENTS/Resources/ToucanOverlay.icns"
fi

cat > "$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>              <string>Toucan Overlay</string>
  <key>CFBundleDisplayName</key>       <string>Toucan Overlay</string>
  <key>CFBundleIdentifier</key>        <string>dev.toucan.overlay</string>
  <key>CFBundleExecutable</key>        <string>ToucanOverlay</string>
  <key>CFBundleIconFile</key>          <string>ToucanOverlay</string>
  <key>CFBundlePackageType</key>       <string>APPL</string>
  <key>CFBundleVersion</key>           <string>1</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key>    <string>13.0</string>
  <key>LSUIElement</key>               <true/>
  <key>NSPrincipalClass</key>          <string>NSApplication</string>
  <key>NSHighResolutionCapable</key>   <true/>
</dict>
</plist>
PLIST

# Ad-hoc sign so WebKit's helper processes launch cleanly.
codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true

echo "==> built $(pwd)/$APP"

if [[ "$RUN" == "1" ]]; then
  pkill -f "$APP/Contents/MacOS/ToucanOverlay" 2>/dev/null || true
  sleep 0.3
  open "$APP"
  echo "==> launched"
fi
