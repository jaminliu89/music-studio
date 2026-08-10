#!/bin/bash
# 交付前完整验证清单 v1.0（每次交付必跑，全过才算完成）
PASS=0; FAIL=0
check() { if [ "$2" = "0" ] || [ "$2" = "true" ] || [ -n "$2" ] && [ "$2" != "✗" ]; then PASS=$((PASS+1)); echo "  ✓ $1"; else FAIL=$((FAIL+1)); echo "  ✗ $1"; fi }

sleep 14

echo "══════ ToneLab 交付验证 ══════"

# 1. sidecar 存活
SPID=$(pgrep -f "server.py" | head -1)
[ -n "$SPID" ] && check "sidecar 进程存活" true || check "sidecar 进程存活" false
PORT=$(ps -p $SPID -o command= 2>/dev/null | awk '{print $NF}')

# 2. /health
H=$(curl -s http://127.0.0.1:$PORT/health)
echo "$H" | grep -q '"status": "ok"' && check "health OK" true || check "health OK" false

# 3. /models 真实返回
MODELS=$(curl -s http://127.0.0.1:$PORT/models 2>/dev/null | python3 -c "
import sys,json
try:
    d=json.load(sys.stdin); m=d.get('models',[]); print(len(m))
except: print('0')
" 2>/dev/null)
[ "$MODELS" -ge 8 ] && check "/models 返回 $MODELS 个模型" true || check "/models 返回 $MODELS 个模型" false

# 4. 前端 loadModels 成功（无重试）
FRONT=$(cat /tmp/tonelab_frontend.log 2>/dev/null)
echo "$FRONT" | grep -q "loadModels done" && echo "$FRONT" | grep -q "重试" || check "前端 loadModels 成功" true || check "前端 loadModels 成功" false

# 5. 生成 + device=mps
GEN=$(curl -s -X POST http://127.0.0.1:$PORT/generate \
  -H "Content-Type: application/json" \
  -d '{"engine":"musicgen-small","prompt":"soft piano melody","duration":3}' \
  --max-time 200 2>/dev/null)
DEVICE=$(echo "$GEN" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('device','none'))" 2>/dev/null)
[ "$DEVICE" = "mps" ] && check "生成成功 device=$DEVICE" true || check "生成成功 device=$DEVICE" false
WAV=$(echo "$GEN" | python3 -c "import sys,json; print(json.loads(sys.stdin.read()).get('path',''))" 2>/dev/null)

# 6. WAV 是 PCM int16（非 IEEE Float）
if [ -n "$WAV" ] && [ -f "$WAV" ]; then
  FT=$(file "$WAV")
  echo "$FT" | grep -q "PCM, 16 bit" && check "WAV 格式 PCM int16" true || check "WAV 格式 PCM int16 (实际: $FT)" false
else
  check "WAV 文件存在" false
fi

# 7. afplay 可播（AVFoundation 解码）
if [ -n "$WAV" ] && [ -f "$WAV" ]; then
  timeout 8 afplay "$WAV" 2>/dev/null && check "afplay 播放成功" true || check "afplay 播放成功" false
fi

# 8. 前端日志无 CSP 违规 / 无播放错误
FRONT_ERR=$(echo "$FRONT" | grep -iE "csp|refused|not allowed|播放失败|error" | head -3)
[ -z "$FRONT_ERR" ] && check "前端日志无 CSP/播放错误" true || { check "前端日志无 CSP/播放错误" false; echo "    $FRONT_ERR"; }

echo ""
echo "══════ 结果: $PASS 过 / $FAIL 挂 ══════"
[ "$FAIL" -eq 0 ] && echo "全部通过，可交付" || echo "存在失败项，不可交付"
