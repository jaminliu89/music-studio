#!/bin/bash
# ToneLab 环境引导安装脚本
# 检测缺失 → 建 venv → 装依赖 → 写 config.json → 输出 READY
# 用途：新用户首次启动时由应用调用；也支持手动 bash setup-backends.sh 执行
set -e

CONFIG_DIR="$HOME/.config/tonelab"
CONFIG_FILE="$CONFIG_DIR/config.json"
VENV_DIR="$HOME/.tonelab-env"
PYTHON_BIN=""
SERVER_SCRIPT=""

# ── 1. 定位 server.py（bundle resources 优先，开发目录 fallback）──
RESOURCE_SERVER="$(dirname "$0")/resources/engines/musicgen/server.py"
DEV_SERVER="$HOME/Projects/music-studio/engines/musicgen/server.py"
if [ -f "$RESOURCE_SERVER" ]; then
  SERVER_SCRIPT="$RESOURCE_SERVER"
elif [ -f "$DEV_SERVER" ]; then
  SERVER_SCRIPT="$DEV_SERVER"
else
  echo "✗ 找不到 server.py（bundle 内与开发目录都没有）"
  exit 1
fi

echo "════════ ToneLab 环境安装 ════════"
echo "目标: 安装 Python 推理环境到 $VENV_DIR"

# ── 2. 检测系统 Python ──
PYTHON_CANDIDATES=(
  "/opt/homebrew/bin/python3"
  "/usr/local/bin/python3"
  "/usr/bin/python3"
)
for py in "${PYTHON_CANDIDATES[@]}"; do
  if [ -x "$py" ] && "$py" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
    PYTHON_BIN="$py"
    echo "✓ 系统 Python: $py ($("$py" --version 2>&1))"
    break
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "✗ 未找到 Python 3.10+，请先安装：brew install python@3.11"
  echo "  或访问 https://www.python.org/downloads/"
  exit 1
fi

# ── 3. 已存在的 venv 验证（可复用则跳过重建）──
if [ -x "$VENV_DIR/bin/python3" ]; then
  if "$VENV_DIR/bin/python3" -c "import torch, transformers, scipy" 2>/dev/null; then
    echo "✓ 现有环境完整（$VENV_DIR），跳过安装"
  else
    echo "⚠️ 现有环境不完整，重建..."
    rm -rf "$VENV_DIR"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi
else
  echo "→ 创建虚拟环境: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# ── 4. 安装依赖（国内走镜像）──
PIP="$VENV_DIR/bin/pip"
echo "→ 安装依赖（torch / transformers / scipy / tiktoken / sentencepiece / protobuf）"
echo "  首次安装需 5-15 分钟，请耐心等待"

# 检测国内网络：尝试 pip 默认源，失败自动切清华镜像
if "$PIP" install --quiet --upgrade pip 2>&1 | tail -1; then
  PIP_INDEX=""
  echo "✓ pip 直连可用"
else
  PIP_INDEX="-i https://pypi.tuna.tsinghua.edu.cn/simple"
  echo "⚠️ 直连失败，使用清华镜像"
fi

"$PIP" install $PIP_INDEX \
  torch torchaudio \
  transformers \
  scipy \
  tiktoken \
  sentencepiece \
  protobuf \
  requests 2>&1 | tail -3

# aria2（下载加速，可选）
if ! command -v aria2c >/dev/null 2>&1; then
  echo "→ 安装 aria2（模型下载加速）"
  if command -v brew >/dev/null 2>&1; then
    brew install aria2 >/dev/null 2>&1 || echo "  ⚠️ aria2 安装失败（不影响核心功能）"
  fi
fi

# ── 5. 验证安装 ──
echo "→ 验证环境..."
"$VENV_DIR/bin/python3" -c "
import torch, transformers, scipy
print(f'✓ torch {torch.__version__} (MPS: {torch.backends.mps.is_available()})')
print(f'✓ transformers {transformers.__version__}')
print(f'✓ scipy {scipy.__version__}')
" 2>&1

# ── 6. 写 config.json ──
mkdir -p "$CONFIG_DIR"
cat > "$CONFIG_FILE" << EOF
{
  "python_path": "$VENV_DIR/bin/python3",
  "server_script": "$SERVER_SCRIPT",
  "installed_at": "$(date '+%Y-%m-%d %H:%M:%S')"
}
EOF

echo ""
echo "════════ 安装完成 ════════"
echo "✓ config: $CONFIG_FILE"
echo "✓ python: $VENV_DIR/bin/python3"
echo "READY"
