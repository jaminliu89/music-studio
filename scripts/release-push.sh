#!/bin/bash
# ToneLab Stage 3: 推双端 Release（本地 tag → 用户验证后显式执行）
set -e
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJ"

TAG="${1:?用法: release-push.sh vX.Y.Z}"
VERSION="${TAG#v}"
DMG="dist-release/ToneLab-${VERSION}-macOS-AppleSilicon.dmg"

echo "════════ ToneLab $TAG 双端发布 ════════"

# 前置校验
[ -d .git ] || { echo "✗ 不是 git 仓库"; exit 1; }
git tag -l | grep -qx "$TAG" || { echo "✗ 本地 tag $TAG 不存在，先跑 build-release.sh"; exit 1; }
[ -f "$DMG" ] || { echo "✗ DMG 不存在: $DMG"; exit 1; }

# remote 检查（gitee / github 可缺其一，至少一个）
HAS_GITEE=$(git remote | grep -qx gitee && echo yes || echo no)
HAS_GITHUB=$(git remote | grep -qx github && echo yes || echo no)
if [ "$HAS_GITEE" = no ] && [ "$HAS_GITHUB" = no ]; then
  echo "✗ 无 gitee/github remote"; exit 1
fi

# 1. 推 tag + main
for remote in gitee github; do
  if git remote | grep -qx "$remote"; then
    echo "[push] $remote $TAG + main"
    git push "$remote" "$TAG" 2>&1 | tail -2 || true
    git push "$remote" main 2>&1 | tail -2 || true
  fi
done

# 2. GitHub Release（幂等）
if [ "$HAS_GITHUB" = yes ] && command -v gh >/dev/null 2>&1; then
  echo "[gh] release $TAG"
  if ! gh release view "$TAG" >/dev/null 2>&1; then
    NOTES=$(mktemp)
    cat > "$NOTES" <<EOF
# ToneLab $TAG

AI 音乐生成桌面应用。

## 安装

下载 DMG 后打开，将 ToneLab.app 拖入 Applications。

首次打开如提示无法验证开发者：系统设置 → 隐私与安全性 → 仍要打开

## 更新内容

- 情绪/场景三轴融合标签
- MPS 加速（含 stereo 模型）
- 高级生成参数（Guidance/温度/Top-K/Top-P）
- 日志监控模式
- 完整模型下载管理
EOF
    gh release create "$TAG" "$DMG" --notes-file "$NOTES" 2>&1 | tail -3
    rm -f "$NOTES"
  else
    echo "  release 已存在，跳过"
  fi
else
  echo "  ⚠️ 跳过 GitHub Release（无 gh CLI 或 remote）"
fi

# 3. Gitee Release（REST API）
if [ "$HAS_GITEE" = yes ] && [ -n "$GITEE_TOKEN" ]; then
  echo "[gitee] release $TAG"
  # 建 release
  REL_ID=$(curl -s -X POST "https://gitee.com/api/v5/repos/{owner}/{repo}/releases" \
    -H "Content-Type: application/json;charset=UTF-8" \
    -d "{\"access_token\":\"$GITEE_TOKEN\",\"tag_name\":\"$TAG\",\"name\":\"ToneLab $TAG\",\"body\":\"ToneLab $TAG 发布\"}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('id',''))" 2>/dev/null || echo "")
  if [ -n "$REL_ID" ]; then
    curl -s -X POST "https://gitee.com/api/v5/repos/{owner}/{repo}/releases/$REL_ID/attach_files" \
      -F "access_token=$GITEE_TOKEN" -F "file=@$DMG" >/dev/null 2>&1
    echo "  ✓ DMG 已上传"
  else
    echo "  ⚠️ Gitee release 创建失败（检查 GITEE_TOKEN / 仓库名）"
  fi
else
  echo "  ⚠️ 跳过 Gitee Release（无 GITEE_TOKEN）"
  echo "    手动上传: https://gitee.com/{owner}/{repo}/releases/new?tag=$TAG"
fi

echo ""
echo "════════ 发布完成 ════════"
echo "GitHub: https://github.com/{owner}/{repo}/releases/tag/$TAG"
echo "Gitee:  https://gitee.com/{owner}/{repo}/releases/tag/$TAG"
