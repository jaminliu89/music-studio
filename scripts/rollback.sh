#!/bin/bash
# ToneLab 回滚: checkout 旧 tag 重出片
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

TAG="${1:?用法: rollback.sh vX.Y.Z}"
git tag -l | grep -qx "$TAG" || { echo "✗ tag $TAG 不存在"; exit 1; }

# 保护未提交改动
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "✗ 有未提交改动，先 stash/commit"; exit 1
fi

git checkout "$TAG"
bash scripts/build-release.sh
echo "已回滚到 $TAG。返回主线: git checkout main"
