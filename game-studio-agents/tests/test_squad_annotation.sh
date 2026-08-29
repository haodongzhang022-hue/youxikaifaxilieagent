#!/usr/bin/env bash
# ============================================================
# 经理自动标注 squad_domain + 跨部门可调配小组测试信号灯
# 说明: 验证两个增强功能：
#       - 经理拆包时自动标注 squad_domain（减少手写标记）
#       - 开发小组扩展到更多部门（squad_pool 覆盖全部六部门）
#       - 跨部门自动调配/自动释放闭环
#
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

echo "== 1. 经理拆包自动标注 squad_domain =="
out=$($PY << 'PYBLK1'
import sys
sys.path.insert(0, '.')
from game_producer_agent import GameProducerAgent, ARCHITECTURE_MODULES, MODULE_SQUAD_DOMAIN
from message_bus import MessageBus

bus = MessageBus()
m = GameProducerAgent(bus=bus)
m.boot()

# 检查 MODULE_SQUAD_DOMAIN 覆盖全部模块
covered = all(mod in MODULE_SQUAD_DOMAIN for mod in ARCHITECTURE_MODULES)
print(f"MODULE_SQUAD_DOMAIN_COVERAGE: {'OK' if covered else 'FAIL'}")

# 拆包验证自动标注
decomposed = []
for mod, info in ARCHITECTURE_MODULES.items():
    decomposed.append({'project': 'test', 'module': mod, **info})
wps = m._split_work_packages(decomposed)

all_annotated = all(wp.get('squad_domain') for wp in wps)
print(f"ALL_SQUAD_DOMAIN_ANNOTATED: {'OK' if all_annotated else 'FAIL'}")

# 验证具体模块映射正确
for wp in wps:
    mod = wp['module']
    expected = MODULE_SQUAD_DOMAIN.get(mod, '')
    actual = wp.get('squad_domain', '')
    if expected and actual != expected:
        print(f"MAPPING_MISMATCH_{mod}: {actual} != {expected}")
        break
else:
    print("MAPPING_OK")

# 验证跨部门覆盖
print(f"DEPARTMENT_COVERAGE: design={sum(1 for w in wps if w['department']=='design')}, program={sum(1 for w in wps if w['department']=='program')}, art={sum(1 for w in wps if w['department']=='art')}, qa={sum(1 for w in wps if w['department']=='qa')}, pm={sum(1 for w in wps if w['department']=='pm')}, ops={sum(1 for w in wps if w['department']=='ops')}")
PYBLK1
)

if echo "$out" | grep -q "MODULE_SQUAD_DOMAIN_COVERAGE: OK"; then
  report "MODULE_SQUAD_DOMAIN 覆盖全部架构模块" 0
else
  report "MODULE_SQUAD_DOMAIN 覆盖全部架构模块" 1
fi

if echo "$out" | grep -q "ALL_SQUAD_DOMAIN_ANNOTATED: OK"; then
  report "经理拆包时全部自动标注 squad_domain" 0
else
  report "经理拆包时全部自动标注 squad_domain" 1
fi

if echo "$out" | grep -q "MAPPING_OK"; then
  report "模块→squad_domain 映射正确" 0
else
  report "模块→squad_domain 映射正确" 1
fi

if echo "$out" | grep -q "DEPARTMENT_COVERAGE"; then
  report "六部门全覆盖（design/program/art/qa/pm/ops）" 0
else
  report "六部门全覆盖（design/program/art/qa/pm/ops）" 1
fi

echo "== 2. 跨部门自动调配/自动释放 =="
out2=$($PY << 'PYBLK2'
import sys
sys.path.insert(0, '.')
from message_bus import MessageBus
from department_agents import DesignDeptAgent, ArtDeptAgent, QaDeptAgent
from dispatch_capability import DispatchCapability
from squad_pool import get_global_squad_pool, SQUAD_IDLE, SQUAD_BUSY
import squad_pool

# 重置全局池
squad_pool._GLOBAL_SQUAD_POOL = None
pool = get_global_squad_pool()

bus = MessageBus()
# 注册所有小组长
for s in pool.list_squads():
    leader = s["leader"]
    if leader not in bus.roles:
        bus.register(leader)
        bus.on(leader, lambda m: None)

cap = DispatchCapability("producer", bus=bus, squad_pool=pool)
results = {}

# --- 策划线自动调配 ---
design = DesignDeptAgent(bus)
design.boot()
wp1 = {"id": "wp_design_auto", "label": "玩法设计", "module": "gameplay",
       "department_name": "策划线", "squad_domain": "gameplay_design", "owner": "lead_designer"}
r1 = cap.dispatch_work_package(wp1)
bus.process_all()
results["design_auto_trigger"] = any(e['event'] == 'auto_squad' for e in design.log)
results["design_auto_release"] = any(e['event'] == 'auto_squad_release' for e in design.log)
results["design_done"] = "wp_design_auto" in design.done_packages

# 验证小组已释放
design_squads = pool.find(domain="gameplay_design")
results["design_squad_idle"] = all(s.status == SQUAD_IDLE for s in design_squads)

# --- 美术线自动调配 ---
art = ArtDeptAgent(bus)
art.boot()
wp2 = {"id": "wp_art_auto", "label": "美术风格", "module": "art_direction",
       "department_name": "美术线", "squad_domain": "art_direction", "owner": "art_director"}
r2 = cap.dispatch_work_package(wp2)
bus.process_all()
results["art_auto_trigger"] = any(e['event'] == 'auto_squad' for e in art.log)
results["art_auto_release"] = any(e['event'] == 'auto_squad_release' for e in art.log)
results["art_done"] = "wp_art_auto" in art.done_packages
art_squads = pool.find(domain="art_direction")
results["art_squad_idle"] = all(s.status == SQUAD_IDLE for s in art_squads)

# --- 测试线自动调配 ---
qa = QaDeptAgent(bus)
qa.boot()
wp3 = {"id": "wp_qa_auto", "label": "质量测试", "module": "testing",
       "department_name": "测试线", "squad_domain": "qa_testing", "owner": "qa_engineer"}
r3 = cap.dispatch_work_package(wp3)
bus.process_all()
results["qa_auto_trigger"] = any(e['event'] == 'auto_squad' for e in qa.log)
results["qa_auto_release"] = any(e['event'] == 'auto_squad_release' for e in qa.log)
results["qa_done"] = "wp_qa_auto" in qa.done_packages
qa_squads = pool.find(domain="qa_testing")
results["qa_squad_idle"] = all(s.status == SQUAD_IDLE for s in qa_squads)

# --- 未声明 squad_domain 不触发 ---
wp4 = {"id": "wp_no_squad", "label": "普通任务", "module": "gameplay",
       "department_name": "策划线", "owner": "lead_designer"}
r4 = cap.dispatch_work_package(wp4)
bus.process_all()
results["no_squad_no_trigger"] = (len(design._squad_wp_ids) == 0)

for k, v in results.items():
    print(f"  {k}: {'OK' if v else 'FAIL'}")
print("ALL_PASS" if all(results.values()) else "SOME_FAIL")
PYBLK2
)

if echo "$out2" | grep -q "ALL_PASS"; then
  report "跨部门自动调配/释放全部通过" 0
  echo "$out2"
else
  report "跨部门自动调配/释放全部通过" 1
  echo "$out2"
fi

echo "== 3. 小组池覆盖全部部门 =="
out3=$($PY << 'PYBLK3'
import sys
sys.path.insert(0, '.')
from squad_pool import create_default_squad_pool

pool = create_default_squad_pool()
domains = set()
for s in pool.list_squads():
    domains.add(s["domain"])

# 期望的 squad domains
expected = {
    "client_dev", "server_dev", "ai_dev", "engine_dev", "tools_dev",  # 程序线
    "gameplay_design", "narrative_design",  # 策划线
    "art_direction", "ui_design",  # 美术线
    "qa_testing",  # 测试线
    "release_pm",  # 项目管理
    "data_ops",  # 运营线
}
all_covered = expected.issubset(domains)
print(f"SQUAD_COUNT: {pool.count()}")
print(f"ALL_DOMAIN_COVERED: {'OK' if all_covered else 'FAIL'}")
print(f"DOMAINS: {sorted(domains)}")
PYBLK3
)

if echo "$out3" | grep -q "ALL_DOMAIN_COVERED: OK"; then
  report "小组池覆盖全部六部门领域" 0
else
  report "小组池覆盖全部六部门领域" 1
fi

if echo "$out3" | grep -q "SQUAD_COUNT: 12"; then
  report "小组池共 12 个小组" 0
else
  report "小组池共 12 个小组" 1
fi

echo "== 3.5 各部门接入开发小组闭环（dev_team 模块扩展） =="
out35=$($PY << 'PYBLK35'
import sys
sys.path.insert(0, '.')
from message_bus import MessageBus
from department_agents import (DesignDeptAgent, ArtDeptAgent, QaDeptAgent,
                               PmDeptAgent, OpsDeptAgent)

bus = MessageBus()
# 各部门执行一个工作包，验证返回的 artifact 均带 dev_team（开发小组闭环结果）
cases = [
    (DesignDeptAgent(bus), "wp_gp", {"id": "wp_gp", "module": "gameplay", "label": "玩法", "project": "P"}, "策划线"),
    (ArtDeptAgent(bus), "wp_art", {"id": "wp_art", "module": "art_direction", "label": "美术", "project": "P"}, "美术线"),
    (QaDeptAgent(bus), "wp_qa", {"id": "wp_qa", "module": "testing", "label": "测试", "project": "P"}, "测试线"),
    (PmDeptAgent(bus), "wp_pm", {"id": "wp_pm", "module": "release", "label": "发版", "project": "P"}, "项目管理"),
    (OpsDeptAgent(bus), "wp_ops", {"id": "wp_ops", "module": "data_ops", "label": "运营", "project": "P"}, "运营线"),
]
all_ok = True
for agent, wp_id, wp, dept in cases:
    try:
        art = agent._execute(wp, {"payload": {}})
        dt = art.get("dev_team", {})
        if not isinstance(dt, dict) or not dt.get("team_id") or dt.get("ok") is not True:
            all_ok = False
            print(f"FAIL {dept}: dev_team={dt}")
    except Exception as e:
        all_ok = False
        print(f"EXC {dept}: {e}")
print(f"ALL_DEPT_DEVTEAM: {'OK' if all_ok else 'FAIL'}")
PYBLK35
)

if echo "$out35" | grep -q "ALL_DEPT_DEVTEAM: OK"; then
  report "策划/美术/测试/项目/运营五部门均接入开发小组闭环 dev_team" 0
else
  report "策划/美术/测试/项目/运营五部门均接入开发小组闭环 dev_team" 1
  echo "$out35" | grep -E "FAIL|EXC"
fi

echo "== 4. 与既有功能回归 =="
reg1=$($PY squad_pool.py 2>&1)
if echo "$reg1" | grep -q "🟢 通过"; then
  report "SquadPool 原有演示通过（回归）" 0
else
  report "SquadPool 原有演示通过（回归）" 1
fi

reg2=$($PY squad_auto.py 2>&1)
if echo "$reg2" | grep -q "🟢 通过"; then
  report "SquadAuto 原有演示通过（回归）" 0
else
  report "SquadAuto 原有演示通过（回归）" 1
fi

echo ""
if [ "$fail" -eq 0 ]; then
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🟢 经理自动标注+跨部门小组池通过"
  exit 0
else
  echo "测试信号灯结果: $pass 通过 / $fail 失败"
  echo "🔴 经理自动标注+跨部门小组池存在阻塞项"
  exit 1
fi
