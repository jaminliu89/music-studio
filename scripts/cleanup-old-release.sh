#!/bin/bash
# ToneLab 交付收尾：旧版残留清理到废纸篓 + 从新 DMG 装回 + 验证
# 铁律来源: tauri-python-sidecar skill · 旧版残留清理（2026-08-10 用户要求）
# 用法: bash scripts/cleanup-old-release.sh [新DMG路径]
# 默认从 dist-release/ 最新 DMG 安装
set -e

PROJ="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="ToneLab"
TRASH="$HOME/.Trash"
TS=$(date +%Y%m%d_%H%M%S)

NEW_DMG="${1:-$(ls -t "$PROJ"/dist-release/*.dmg 2>/dev/null | head -1)}"
# 规范化绝对路径（防止相对路径比较失败误移新 DMG）
NEW_DMG="$(cd "$(dirname "$NEW_DMG")" 2>/dev/null && pwd)/$(basename "$NEW_DMG")"
[ -f "$NEW_DMG" ] || { echo "✗ 无 DMG 可安装: $NEW_DMG"; exit 1; }

echo "════ 旧版残留清理 + 新版安装 ════"
echo "新 DMG: $NEW_DMG"

# 1. 杀全部旧进程（app + 引擎 + sidecar；排除脚本自身）
echo "[1/5] 杀旧进程..."
pkill -f "$APP_NAME.app/Contents/MacOS" 2>/dev/null || true
pkill -f "tonelab-engine" 2>/dev/null || true
# 只杀 ToneLab 的 server.py（engines/musicgen/ 路径），不误伤 ACE-Step 的 api_server.py
pkill -f "engines/musicgen/server.py" 2>/dev/null || true
sleep 3
LEFT=$(ps aux | grep -E "$APP_NAME|tonelab-engine|music-studio|server\.py" | grep -v grep | grep -v "cleanup-old-release" | head -5)
if [ -n "$LEFT" ]; then echo "  ⚠️ 残留进程:"; echo "$LEFT"; else echo "  ✓ 杀净"; fi

# 2. 旧 .app 进废纸篓
echo "[2/5] 旧 .app 进废纸篓..."
if [ -d "/Applications/$APP_NAME.app" ]; then
  OLD_VER=$(defaults read "/Applications/$APP_NAME.app/Contents/Info.plist" CFBundleShortVersionString 2>/dev/null || echo "unknown")
  mv "/Applications/$APP_NAME.app" "$TRASH/$APP_NAME-$OLD_VER.app"
  echo "  ✓ $APP_NAME-$OLD_VER.app → 废纸篓"
else
  echo "  ✓ 无旧 .app"
fi

# 3. 旧 DMG 进废纸篓（保留本次要装的新 DMG）
echo "[3/5] 旧 DMG 进废纸篓..."
for dmg in "$PROJ"/dist-release/*.dmg; do
  [ -f "$dmg" ] || continue
  [ "$dmg" = "$NEW_DMG" ] && continue
  mv "$dmg" "$TRASH/"
  echo "  ✓ $(basename "$dmg") → 废纸篓"
done

# 4. 从新 DMG 安装
echo "[4/5] 从新 DMG 安装..."
for m in /Volumes/$APP_NAME*; do [ -d "$m" ] && hdiutil detach "$m" -force >/dev/null 2>&1 || true; done
hdiutil attach "$NEW_DMG" -nobrowse >/dev/null 2>&1
sleep 2
VOL=$(ls /Volumes/ | grep -i "^$APP_NAME" | head -1)
[ -z "$VOL" ] && { echo "  ✗ 挂载失败"; exit 1; }
ditto "/Volumes/$VOL/$APP_NAME.app" "/Applications/$APP_NAME.app"
xattr -dr com.apple.quarantine "/Applications/$APP_NAME.app"
hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1
echo "  ✓ 安装完成: $(basename "$NEW_DMG")"

# 5. 验证三件套
echo "[5/5] 验证..."
INSTALLED_VER=$(defaults read "/Applications/$APP_NAME.app/Contents/Info.plist" CFBundleShortVersionString)
DMG_VER=$(echo "$(basename "$NEW_DMG")" | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
echo "  安装版本: $INSTALLED_VER (DMG: $DMG_VER)"
if [ "$INSTALLED_VER" != "$DMG_VER" ]; then
  echo "  ✗ 版本不匹配！"; exit 1
fi
ls "/Applications/$APP_NAME.app/Contents/Resources/resources/engines/musicgen/tonelab-engine" >/dev/null 2>&1 \
  && echo "  ✓ 独立引擎在位" || echo "  ⚠️ 无独立引擎（方案二模式）"
du -sh "/Applications/$APP_NAME.app" | awk '{print "  app 大小: "$1}'
echo ""
echo "════ 完成 · 废纸篓 ════"
ls "$TRASH" | grep -i "$APP_NAME" | sed 's/^/  /'
echo ""
echo "下一步: 启动应用验证 health（旧进程已杀净）"
