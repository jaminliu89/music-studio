#!/bin/bash
# ToneLab DMG 打包（dmgbuild，弃用 Tauri 自带 bundle_dmg.sh）
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$SCRIPT_DIR/.." && pwd)"
VERSION=$(grep -m1 '"version"' "$PROJ/src-tauri/tauri.conf.json" | sed 's/.*"version": *"\([^"]*\)".*/\1/')
APP="$PROJ/src-tauri/target/release/bundle/macos/ToneLab.app"
OUT_DIR="$PROJ/dist-release"
OUT_DMG="$OUT_DIR/ToneLab-${VERSION}-macOS-AppleSilicon.dmg"
BG="$PROJ/dmg-assets/dmg-bg.png"
MANUAL="$PROJ/dmg-assets/使用说明.pdf"
ICON="$PROJ/src-tauri/icons/icon.icns"
SETTINGS="$SCRIPT_DIR/dmgbuild-settings.py"

for f in "$APP" "$BG" "$MANUAL" "$ICON" "$SETTINGS"; do
  [ -e "$f" ] || { echo "✗ 缺 $f"; exit 1; }
done

DMGBUILD="/Users/kimliu/Library/Python/3.12/bin/dmgbuild"
PY312="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"

mkdir -p "$OUT_DIR"
rm -f "$OUT_DMG"

# 清残留挂载卷 + rw 中间文件
for m in /Volumes/ToneLab* /Volumes/dmg.*; do
  [ -d "$m" ] && hdiutil detach "$m" -force >/dev/null 2>&1 || true
done
find "$OUT_DIR" -name "rw.*.dmg" -delete 2>/dev/null || true

# dmgbuild 打包
"$DMGBUILD" -s "$SETTINGS" \
  -D app="$APP" -D bg="$BG" -D pdf="$MANUAL" -D icon="$ICON" \
  "ToneLab ${VERSION}" "$OUT_DMG"

ls -lh "$OUT_DMG"
