# ============================================================
# 评审-修复闭环：上下文路由机制测试信号灯
# 说明: 验证「评审发现 bug → CodeBuddy 修复」闭环的**上下文路由机制**：
#       1. 上下文路由（全局ID + sessionID）——提交 PR / 工作包时注册原对话上下文，
#          评审打回时按全局ID定位到原对话（sessionID），继承完整上下文与历史
#          评审-修复记录来修复，信息细节不丢失；
#       2. 降级显性化——上下文路由不可用时降级到哈希校验，但**必须显性输出
#          降级说明**（原因 + 丢失的信息），禁止静默降级（否则持续丢上下文
#          导致修复效果变弱且无人察觉）。
# 退出码: 0 = 🟢 通过，1 = 🔴 阻塞
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/../config"
PY=python3
pass=0
fail=0

report() {
  if [ "$2" = "0" ]; then
    echo "  ✅ $1"
    pass=$((pass+1))
  else
    echo "  ❌ $1"
    fail=$((fail+1))
  fi
}

echo "== 1. 评审-修复闭环上下文路由（全局ID + sessionID 定位原对话）=="
out=$($PY - <<'PY'
from review_fix_router import ReviewFixRouter, ROUTE_SESSION, ROUTE_HASH
logs = []
def _log(tag, msg): logs.append((tag, msg))

r = ReviewFixRouter()
r.set_logger(_log)

# 提交 PR 时注册原对话上下文（全局ID + sessionID）
r.register_context("PR-23", "session_abc123", {"module": "server", "role": "cto"})
ctx, mode, degraded = r.route_review("PR-23", {"issue": "负载均衡"})
print("route_mode_1=%s" % mode)
print("degraded_1=%s" % degraded)
print("has_ctx_1=%s" % (ctx is not None))
r.record_fix("PR-23", {"fix": "负载均衡修复"})
print("history_len=%d" % len(ctx.history))

# 无上下文 → 降级哈希校验，必须显性输出降级说明
ctx2, mode2, degraded2 = r.route_review("PR-99", {"issue": "无上下文"})
print("route_mode_2=%s" % mode2)
print("degraded_2=%s" % degraded2)
print("has_ctx_2=%s" % (ctx2 is not None))
print("explicit_fallback=%s" % any(tag == "route_fallback" for tag, _ in logs))
print("summary=%s" % r.summary())
PY
)

# 1. 上下文路由：PR-23 走 session_route（非降级）
if echo "$out" | grep -q "route_mode_1=session_route" \
   && echo "$out" | grep -q "degraded_1=False" \
   && echo "$out" | grep -q "has_ctx_1=True"; then
  report "上下文路由：评审打回按全局ID定位到原对话（session_route，非降级）" 0
else
  report "上下文路由：评审打回按全局ID定位到原对话（session_route，非降级）" 1
fi

# 2. 上下文继承：修复后历史沉淀（1 review + 1 fix）
if echo "$out" | grep -q "history_len=2"; then
  report "上下文继承：历史评审-修复记录沉淀（history=2，信息不丢失）" 0
else
  report "上下文继承：历史评审-修复记录沉淀（history=2，信息不丢失）" 1
fi

# 3. 路由不可用 → 降级哈希校验
if echo "$out" | grep -q "route_mode_2=hash_fallback" \
   && echo "$out" | grep -q "degraded_2=True" \
   && echo "$out" | grep -q "has_ctx_2=False"; then
  report "降级：无 sessionID 上下文时降级到哈希校验兜底" 0
else
  report "降级：无 sessionID 上下文时降级到哈希校验兜底" 1
fi

# 4. 降级必须显性说明（route_fallback 告警），禁止静默降级
if echo "$out" | grep -q "explicit_fallback=True"; then
  report "降级显性化：哈希校验降级时输出显性说明（原因+丢失信息），不静默" 0
else
  report "降级显性化：哈希校验降级时输出显性说明（原因+丢失信息），不静默" 1
fi

# 5. 汇总统计区分上下文路由与降级
if echo "$out" | grep -q "'hash_fallback_count': 1" \
   && echo "$out" | grep -q "'context_registered': 1"; then
  report "机制可观测：路由统计区分上下文路由 vs 降级哈希校验" 0
else
  report "机制可观测：路由统计区分上下文路由 vs 降级哈希校验" 1
fi

# ============================================================
# 6. 评审闭环健康判别：区分「正常待评审」与「真正闭环中断」（防误报）
# ============================================================
echo "== 6. 闭环健康判别（正常待评审 vs 真正中断，防误报）=="
out_loop=$($PY - <<'PY'
from review_fix_router import ReviewFixRouter
r = ReviewFixRouter()

# 场景A：修复已打标签成功、新评审在下一轮才产生（最新 head 暂无评审结论）→ 正常待评审，不中断
pending = r.classify_loop_state("PR-31", has_newest_review=False, label_applied=True,
                                review_timeout=False, rounds_over_limit=False)
print("pending=%s" % pending)

# 场景B：打标签失败（修复状态未正确标记）→ 真正中断（硬性信号①）
interrupt_label = r.classify_loop_state("PR-31", has_newest_review=False,
                                        label_applied=False, review_timeout=False,
                                        rounds_over_limit=False)
print("interrupt_label=%s" % interrupt_label)

# 场景C：标签已打但长时间无后续评审 run 跟进 → 真正中断（硬性信号②）
interrupt_timeout = r.classify_loop_state("PR-31", has_newest_review=False,
                                          label_applied=True, review_timeout=True,
                                          rounds_over_limit=False)
print("interrupt_timeout=%s" % interrupt_timeout)

# 场景D：标签已打且有最新评审结论 → 闭环正常（有结论）
ok = r.classify_loop_state("PR-31", has_newest_review=True, label_applied=True,
                           review_timeout=False, rounds_over_limit=False)
print("ok=%s" % ok)
PY
)

# 6.1 正常待评审：标签已打、仅"暂无最新评审结论" → 必须判 pending_review（不误报中断）
if echo "$out_loop" | grep -q "pending=pending_review"; then
  report "闭环判别：修复已打标签、新评审尚在下一轮（暂无最新评审结论）→ 正常待评审，不误报中断" 0
else
  report "闭环判别：修复已打标签、新评审尚在下一轮（暂无最新评审结论）→ 正常待评审，不误报中断" 1
fi

# 6.2 真正中断须有硬性信号：打标签失败 / 评审超时 → 判 interrupted
if echo "$out_loop" | grep -q "interrupt_label=interrupted" \
   && echo "$out_loop" | grep -q "interrupt_timeout=interrupted"; then
  report "闭环判别：真正中断须有硬性信号（打标签失败 / 评审超时）才判 interrupted" 0
else
  report "闭环判别：真正中断须有硬性信号（打标签失败 / 评审超时）才判 interrupted" 1
fi

# 6.3 有最新评审结论且无硬性信号 → 闭环正常
if echo "$out_loop" | grep -q "ok=ok"; then
  report "闭环判别：有最新评审结论且无硬性信号 → 闭环正常（ok）" 0
else
  report "闭环判别：有最新评审结论且无硬性信号 → 闭环正常（ok）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 评审-修复闭环上下文路由机制通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 评审-修复闭环上下文路由机制存在阻塞项"
  exit 1
fi
