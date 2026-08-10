#!/bin/bash
# ToneLab 引擎 pyinstaller 打包脚本
# 用途：把 server.py + torch + transformers 全部打进 tonelab-engine 二进制
# 产物：dist/tonelab-engine → 拷贝进 src-tauri/resources/engines/musicgen/
# 注意：打包后约 2-3GB（torch 权重）；首次运行需解包到临时目录
set -e

PROJ_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENGINE_DIR="$PROJ_DIR/engines/musicgen"
VENV_PYTHON=...[truncated]