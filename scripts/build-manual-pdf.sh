#!/bin/bash
# ToneLab 使用说明 PDF（markdown → HTML → Chrome headless 单页矢量 PDF）
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$SCRIPT_DIR/.." && pwd)"
SRC="$PROJ/dmg-assets/使用说明.md"
OUT="$PROJ/dmg-assets/使用说明.pdf"

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

cat > "$TMPDIR/render.html" <<'HEAD'
<!DOCTYPE html><html lang="zh-CN"><head>
<meta charset="UTF-8"><style>
  body { margin: 0; background: #fff; font-family: -apple-system, "PingFang SC", sans-serif; }
  .page { max-width: 800px; margin: 0 auto; padding: 56px 64px; color: #1a1a1a; }
  h1 { font-size: 28px; font-weight: 700; margin: 0 0 8px; }
  h2 { font-size: 20px; font-weight: 700; margin: 32px 0 8px; }
  h3 { font-size: 16px; font-weight: 700; margin: 20px 0 6px; }
  p { font-size: 14px; line-height: 1.8; margin: 6px 0; }
  li { font-size: 14px; line-height: 1.8; margin: 4px 0; list-style: none; }
  li::before { content: "·"; margin-right: 8px; color: #999; }
  hr { border: none; border-top: 1px solid #e5e0d5; margin: 24px 0; }
  strong { font-weight: 700; }
</style></head>
<body><div class="page"><div id="preview"></div></div>
<script src="https://cdn.jsdelivr.net/npm/marked@12/marked.min.js"></script>
<script id="src" type="text/markdown">
HEAD
cat "$SRC" >> "$TMPDIR/render.html"
cat >> "$TMPDIR/render.html" <<'TAIL'
</script><script>
  document.getElementById('preview').innerHTML = marked.parse(
    document.getElementById('src').textContent
  );
  requestAnimationFrame(() => setTimeout(() => {
    document.body.setAttribute('data-page-height', String(document.body.scrollHeight));
  }, 300));
</script></body></html>
TAIL

CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -x "$CHROME" ]; then
  # Chrome 缺失时用 Safari 无法 headless，退回简单 PDF（用 pandoc 或直接提示）
  if command -v pandoc >/dev/null 2>&1; then
    pandoc "$SRC" -o "$OUT"
    echo "✓ $OUT (pandoc 兜底) ($(du -h "$OUT" | awk '{print $1}'))"
    exit 0
  fi
  echo "✗ 缺 Chrome 和 pandoc，无法生成 PDF"; exit 1
fi

DUMP=$("$CHROME" --headless --disable-gpu --no-sandbox --virtual-time-budget=3000 \
  --dump-dom "file://$TMPDIR/render.html" 2>/dev/null | tr -d '\n')
H=$(echo "$DUMP" | grep -oE 'data-page-height="[0-9]+"' | head -1 | grep -oE '[0-9]+')
[ -z "$H" ] && H=2000
WPT=$(awk "BEGIN{print 800*72/96}")
HPT=$(awk "BEGIN{print $H*72/96}")

sed -i.bak "s|</style>|@page { size: ${WPT}pt ${HPT}pt; margin: 0; }\\n</style>|" "$TMPDIR/render.html"

"$CHROME" --headless --disable-gpu --no-sandbox --no-pdf-header-footer \
  --virtual-time-budget=3000 --print-to-pdf="$OUT" \
  --print-to-pdf-no-header "file://$TMPDIR/render.html" 2>/dev/null

echo "✓ $OUT ($(du -h "$OUT" | awk '{print $1}'))"
