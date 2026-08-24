#!/usr/bin/env bash
# ============================================================
# 信息接口层 · 测试信号灯
# 说明: 验证 api/ 接口层能正确导入、聚合引擎降熵逻辑正确、
#       FastAPI 路由可响应、阻塞/返工判断可溯源。
# 用法: bash game-studio-agents/api/test_api.sh
# 退出码: 0 全部通过 / 1 存在失败
# ============================================================
set -u
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
PASS=0
FAIL=0

report() {
  local name="$1" ok="$2"
  if [ "$ok" -eq 0 ]; then
    PASS=$((PASS+1)); echo "  ✅ $name"
  else
    FAIL=$((FAIL+1)); echo "  ❌ $name"
  fi
}

echo "== 1. 接口层可导入（模型/聚合引擎/路由）=="
out=$($PY - <<'PYEOF'
import app, aggregator, models, runtime
print('API_IMPORT_OK')
PYEOF
)
if echo "$out" | grep -q "API_IMPORT_OK"; then
  report "接口层模块全部可导入" 0
else
  report "接口层模块全部可导入" 1
fi

echo "== 2. 路由注册完整 =="
out=$($PY - <<'PYEOF'
import app
paths = [r.path for r in app.app.routes if getattr(r, 'methods', None)]
needed = ['/ai/overview','/ai/workpackages','/ai/workpackages/{wp_id}','/ai/risks',
          '/ai/tasks','/ai/events','/dashboard/overview','/dashboard/workpackages',
          '/dashboard/dependencies','/dashboard/risks','/dashboard/workpackages/{wp_id}',
          '/dashboard/events']
missing = [p for p in needed if p not in paths]
print('MISSING=' + ','.join(missing) if missing else 'ALL_ROUTES_OK')
PYEOF
)
if echo "$out" | grep -q "ALL_ROUTES_OK"; then
  report "全部 12 个关键路由已注册" 0
else
  report "全部 12 个关键路由已注册 ($out)" 1
fi

echo "== 3. 降熵聚合：阻塞/返工判断正确（决策支撑）=="
out=$($PY - <<'PYEOF'
from runtime import bootstrap, build_snapshot
from aggregator import Aggregator, build_judgment, assess_risk

rt = bootstrap(modules=['gameplay','client','server','testing','release'])
mgr = rt['manager']
# 完成 gameplay
for tid, t in mgr.scheduler.queue.tasks.items():
    if t.payload.get('work_package',{}).get('id') == 'wp_gameplay':
        mgr.scheduler.on_complete(tid, mgr.role_id)
# 打回 client
mgr._on_department_delivery({'work_package_id': 'wp_client', 'status': 'rejected', 'reason': '设计不完整'})
snap = build_snapshot(manager=mgr, bus=rt['bus'])
agg = Aggregator(snap)

ov = agg.overview()
print('HEALTH=' + ov.health)
# 状态聚类
wps = agg.work_packages_aggregate(group_by='status')
by_label = {g.label: g.count for g in wps.groups}
print('STATUS=' + str(by_label))
# client 判断
for wp in agg.work_packages:
    if wp['id'] == 'wp_client':
        r = assess_risk(wp, agg.tasks)
        j = build_judgment(wp, agg.tasks)
        print('CLIENT_LEVEL=' + r['level'])
        print('CLIENT_JUDGE=' + (j.conclusion if j else ''))
        print('CLIENT_ACTION=' + (j.suggested_action if j else ''))
PYEOF
)
if echo "$out" | grep -q "HEALTH=critical"; then
  report "含阻塞时健康度=critical（降熵判断）" 0
else
  report "含阻塞时健康度=critical ($out)" 1
fi
if echo "$out" | grep -q "CLIENT_LEVEL=high"; then
  report "阻塞工作包风险等级=high" 0
else
  report "阻塞工作包风险等级=high ($out)" 1
fi
if echo "$out" | grep -q "CLIENT_ACTION=派督导/返工"; then
  report "阻塞工作包给出建议动作（决策支撑）" 0
else
  report "阻塞工作包给出建议动作（$out）" 1
fi

echo "== 4. 安全鉴权：配置 API_TOKEN 后 /ai/* 与 /dashboard/* 需 Bearer token =="
out=$(API_TOKEN='test-secret' $PY - <<'PYEOF'
from fastapi.testclient import TestClient
import app
from runtime import bootstrap
rt = bootstrap(modules=['gameplay','client'])
mgr = rt['manager']
app.attach_runtime(manager=mgr, bus=rt['bus'])
c = TestClient(app.app)
# 无 token -> 401
no = c.get('/ai/overview').status_code
bad = c.get('/ai/overview', headers={'Authorization':'Bearer wrong'}).status_code
ok = c.get('/ai/overview', headers={'Authorization':'Bearer test-secret'}).status_code
dash = c.get('/dashboard/overview', headers={'Authorization':'Bearer test-secret'}).status_code
health = c.get('/health').status_code
print(f'NO_TOKEN={no} BAD_TOKEN={bad} OK_TOKEN={ok} DASH_OK={dash} HEALTH={health}')
PYEOF
)
if echo "$out" | grep -q "NO_TOKEN=401 BAD_TOKEN=401 OK_TOKEN=200 DASH_OK=200 HEALTH=200"; then
  report "鉴权生效：无/错 token 401，正确 token 200，健康检查放行" 0
else
  report "鉴权生效：无/错 token 401，正确 token 200，健康检查放行 ($out)" 1
fi


echo "== 5. FastAPI 接口可响应 =="
out=$($PY - <<'PYEOF'
from fastapi.testclient import TestClient
import app
from runtime import bootstrap
rt = bootstrap(modules=['gameplay','client'])
mgr = rt['manager']
app.attach_runtime(manager=mgr, bus=rt['bus'])
c = TestClient(app.app)
paths = ['/health','/ai/overview','/ai/workpackages','/ai/tasks',
         '/ai/events','/dashboard/overview','/dashboard/dependencies',
         '/dashboard/workpackages','/ai/risks']
bad = []
for p in paths:
    r = c.get(p)
    if r.status_code != 200:
        bad.append(f'{p}:{r.status_code}')
print('BAD=' + ','.join(bad) if bad else 'ALL_200')
PYEOF
)
if echo "$out" | grep -q "ALL_200"; then
  report "9 个接口全部返回 200" 0
else
  report "9 个接口全部返回 200 ($out)" 1
fi

echo ""
echo "API 接口层测试信号灯: $PASS 通过 / $FAIL 失败"
if [ "$FAIL" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
else
  echo "🟢 全部通过"
  exit 0
fi
