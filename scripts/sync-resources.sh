#!/bin/bash
# 同步 sidecar 引擎脚本 + 引导脚本进 src-tauri/resources
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJ="$(cd "$SCRIPT_DIR/.." && pwd)"

mkdir -p "$PROJ/src-tauri/resources/engines/musicgen"
cp "$PROJ/engines/musicgen/server.py" "$PROJ/src-tauri/resources/engines/musicgen/server.py"
chmod +x "$PROJ/src-tauri/resources/setup-backends.sh"
echo "✓ server.py + setup-backends.sh 已同步"
