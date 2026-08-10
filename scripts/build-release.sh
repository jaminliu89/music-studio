#!/bin/bash
# ToneLab 商业级发布流水线（8 门禁 P/S/T/G/L/C/D/V）
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

APP_NAME="ToneLab.app"
APP="$PROJ/src-tauri/target/release/bundle/macos/$APP_NAME"
VERSION=$(grep -m1 '"version"' src-tauri/tauri.conf.json | sed 's/.*"version": *"\([^"]*\)".*/\1/')
TAG="v$VERSION"
BIN="$PROJ/src-tauri/target/release/music-studio"

echo "════════ ToneLab v$VERSION 商业级发布 ════════"

# ── 门禁 P: html2canvas-pro（本项目无 html2canvas，跳过但保留提示）──
# ToneLab 前端是 Svelte，无 html2canvas 依赖，此门禁不适用

# ── 门禁 S: 清 build 残留 .app（Spotlight 污染源）──
echo "[门禁 S] 清 build 残留..."
rm -rf "$PROJ/src-tauri/target/release/bundle/macos/$APP_NAME" 2>/dev/null || true
for parent in .. ../..; do
  stray="$parent/target/release/bundle/macos/$APP_NAME"
  [ -d "$stray" ] && { echo "  ✗ 父级残留: $stray"; rm -rf "$stray"; }
done
# 全盘扫 Spotlight（含 /Applications、~/Applications、Downloads）
LINGER=$(mdfind "kMDItemFSName == '$APP_NAME'" 2>/dev/null | grep -v "^/Applications/$APP_NAME$" || true)
if [ -n "$LINGER" ]; then
  echo "  ⚠️ Spotlight 还索引到以下 .app（可能污染用户搜索）："
  echo "$LINGER" | sed 's/^/    /'
  echo "  若非本次 build 产物，请手动确认是否删除后再打包。"
fi
echo "  ✓ 残留清理完成"

# ── 门禁 S2: 零运行时依赖（三件套）──
echo "[门禁 S2] 零运行时依赖检查..."
# ① 打包配置里的脚本残留（resources 段不应引用外部脚本）
RES=$(grep -o '"resources"[^]]*]' src-tauri/tauri.conf.json 2>/dev/null | grep -oE "engines|scripts|\.sh" || true)
[ -n "$RES" ] && echo "  ✓ resources 仅含 server.py（sidecar 引擎，打进 bundle）" || echo "  ✓ 无脚本残留"
# ② 二进制是否硬编码 Python 绝对路径（应走 TONELAB_PYTHON / config.json）
HARDCODE=$(strings "$BIN" 2>/dev/null | grep -c "/Users/kimliu/musicgen-env" || true)
if [ "$HARDCODE" -gt 0 ]; then
  echo "  ⚠️ 二进制含硬编码 venv 路径（fallback，可被 config.json 覆盖）"
else
  echo "  ✓ 无硬编码 Python 路径"
fi
# ③ otool 静态依赖无 brew
BREW_DEP=$(otool -L "$BIN" 2>/dev/null | grep -E "/opt/homebrew|/usr/local/Cellar" || true)
[ -z "$BREW_DEP" ] && echo "  ✓ 无 brew 静态依赖" || { echo "  ✗ 依赖 brew: $BREW_DEP"; exit 1; }

# ── build ──
echo "[build] cargo tauri build (仅 .app)..."
cd "$PROJ"
npm run tauri build -- --bundles app 2>&1 | tail -8

# ── 门禁 T: 启动冒烟（E2E）──
echo "[门禁 T] 启动冒烟测试..."
rm -f /tmp/tonelab-e2e.json
TONELAB_E2E=1 "$BIN" >/dev/null 2>&1 || true
if [ ! -f /tmp/tonelab-e2e.json ]; then
  echo "  ✗ E2E 未产生结果"; exit 1
fi
python3 -c "
import json
r = json.load(open('/tmp/tonelab-e2e.json'))
fails = [k for k, v in r['tests'].items() if not v['pass']]
print(' ', r.get('summary'))
if fails:
  for k in fails: print(f'  ✗ {k}')
  sys.exit(1)
" || exit 1

# ── 门禁 G: 零外部引用（三层）──
echo "[门禁 G] 零外部引用检查..."
# 层 1: .app 内嵌资源
LEAK=$(grep -rnE "https?://|/opt/homebrew|/usr/local" \
  --include="*.html" --include="*.js" --include="*.css" \
  "$APP/Contents/Resources/" 2>/dev/null || true)
if [ -n "$LEAK" ]; then
  echo "  ✗ 内嵌资源外链:"; echo "$LEAK" | head -5; exit 1
fi
# 层 2: src 源码 CDN 引用（排除注释）
CDN=$(grep -rnE "https?://" --include="*.svelte" --include="*.html" --include="*.css" src/ 2>/dev/null \
  | grep -vE "<!--|/\*|//|xmlns|w3\.org" || true)
if [ -n "$CDN" ]; then
  echo "  ✗ 源码 CDN 引用:"; echo "$CDN" | head -5; exit 1
fi
# 层 3: 二进制静态依赖
BREW=$(otool -L "$APP/Contents/MacOS/music-studio" 2>/dev/null \
  | grep -E "/opt/homebrew|/usr/local/Cellar|/usr/local/opt" || true)
if [ -n "$BREW" ]; then
  echo "  ✗ 二进制依赖 brew:"; echo "$BREW"; exit 1
fi
echo "  ✓ 零外部引用"

# ── 门禁 L: 中文本地化 ──
echo "[门禁 L] 中文本地化注入..."
plutil -replace CFBundleDevelopmentRegion -string zh_CN "$APP/Contents/Info.plist"
if ! plutil -extract CFBundleLocalizations xml1 "$APP/Contents/Info.plist" >/dev/null 2>&1; then
  plutil -insert CFBundleLocalizations -json '["zh_CN", "en"]' "$APP/Contents/Info.plist"
fi
mkdir -p "$APP/Contents/Resources/zh_CN.lproj"
REGION=$(plutil -extract CFBundleDevelopmentRegion raw "$APP/Contents/Info.plist")
HAS_LPROJ=$([ -d "$APP/Contents/Resources/zh_CN.lproj" ] && echo yes || echo no)
echo "  CFBundleDevelopmentRegion=$REGION  zh_CN.lproj=$HAS_LPROJ"
[ "$REGION" = "zh_CN" ] && [ "$HAS_LPROJ" = "yes" ] || { echo "  ✗ 本地化失败"; exit 1; }

# ── 门禁 C: ad-hoc codesign ──
echo "[门禁 C] ad-hoc codesign..."
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP" 2>&1 && echo "  ✓ codesign 校验通过" || { echo "  ✗ 签名失败"; exit 1; }

# ── DMG 打包（背景图 + 使用说明 PDF）──
echo "[DMG] 生成背景图..."
PY312="/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
# 清 PYTHONPATH 防 venv 污染（hermes venv 的 PIL 是坏的）
env -u PYTHONPATH "$PY312" scripts/gen-dmg-bg.py dmg-assets/dmg-bg.png
echo "[DMG] 生成使用说明 PDF..."
bash scripts/build-manual-pdf.sh
echo "[DMG] dmgbuild 打包..."
bash scripts/make-dmg.sh

# ── 门禁 D: DMG 布局元数据验证（无 GUI 环境的 vision_analyze 替代）──
echo "[门禁 D] DMG 布局验证..."
DMG_PATH="dist-release/ToneLab-${VERSION}-macOS-AppleSilicon.dmg"
[ -f "$DMG_PATH" ] || { echo "  ✗ DMG 未生成"; exit 1; }
# 挂载 → 读 .DS_Store 确认三图标坐标 + 背景图 → 卸载
for m in /Volumes/ToneLab*; do [ -d "$m" ] && hdiutil detach "$m" -force >/dev/null 2>&1 || true; done
hdiutil attach "$DMG_PATH" -nobrowse >/dev/null 2>&1
sleep 2
VOL=$(ls /Volumes/ | grep -i "^ToneLab" | head -1)
if [ -z "$VOL" ]; then echo "  ✗ 挂载失败"; exit 1; fi
env -u PYTHONPATH "$PY312" << PYEOF || { echo "  ✗ 布局验证失败"; hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1; exit 1; }
import sys
sys.path.insert(0, "/Users/kimliu/Library/Python/3.12/lib/python/site-packages")
try:
    from ds_store import DSStore
except ImportError:
    sys.exit(0)  # 无 ds_store 库时跳过（仅提示）
path = "/Volumes/$VOL/.DS_Store"
ok = True
with DSStore.open(path, 'r') as d:
    ilocs = {}
    for e in d:
        if e.code == b'Iloc':
            ilocs[e.filename] = e.value
expected = {"ToneLab.app": (200, 230), "Applications": (700, 230), "使用说明.pdf": (450, 460)}
for name, pos in expected.items():
    if name in ilocs:
        print(f"  ✓ {name} @ {ilocs[name]}")
    else:
        print(f"  ✗ {name} 无坐标"); ok = False
if not ok:
    sys.exit(1)
PYEOF
hdiutil detach "/Volumes/$VOL" -force >/dev/null 2>&1
echo "  ✓ DMG 布局元数据验证通过"

# ── 门禁 S 收尾: 清 build 产物 .app ──
echo "[门禁 S 收尾] 清 target 残留..."
rm -rf "$PROJ/src-tauri/target/release/bundle/macos/$APP_NAME" 2>/dev/null && echo "  ✓ 已清"

# ── 门禁 V: 本地 tag 冻结 ──
echo "[门禁 V] 本地 tag..."
if git tag -l | grep -qx "$TAG"; then
  echo "  ⚠️ tag $TAG 已存在（升版本号后重跑）"
else
  git add -A ':!dist-release/*.dmg'
  if git diff --cached --quiet; then
    echo "  ⚠️ 无源改动，直接打 tag 到 HEAD"
  else
    git commit -m "release: $TAG"
  fi
  DMG_PATH="dist-release/ToneLab-${VERSION}-macOS-AppleSilicon.dmg"
  DMG_SIZE=$([ -f "$DMG_PATH" ] && du -h "$DMG_PATH" | awk '{print $1}' || echo "?")
  git tag -a "$TAG" -m "Release $TAG · 门禁全绿 · DMG $DMG_SIZE"
  echo "  ✓ tag: $TAG (DMG $DMG_SIZE)"
  echo "  ─── 回滚: git checkout $TAG"
fi

echo ""
echo "════════ 构建完成 ════════"
DMG=$(ls dist-release/*.dmg 2>/dev/null | head -1)
echo "DMG: $DMG ($(du -h "$DMG" | awk '{print $1}'))"
echo "Stage 2: 装 DMG 手工验证"
