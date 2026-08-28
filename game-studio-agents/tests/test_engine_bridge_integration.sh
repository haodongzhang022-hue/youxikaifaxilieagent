#!/usr/bin/env bash
# ============================================================
# 引擎桥接层集成测试信号灯（test_engine_bridge_integration）
# 说明: 验证引擎桥接层接入 Agent 流水线的正确性——
#       1. engine_integration 模块可导入；
#       2. 集成门面（EngineIntegrationFacade）Mock 模式初始化；
#       3. 引擎命令执行（load_scene / create_node / play）正常；
#       4. 引擎事件 → MessageBus 事件映射正常（EngineEvent → Message）；
#       5. 引擎能力查询（Cocos/UE5 能力集）正确；
#       6. 引擎能力检查（engine_capability_check）全部通过；
#       7. 状态报告含集成信息。
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

echo "== 1. engine_integration 模块可导入 =="
out=$($PY - <<'PYEOF'
import engine_integration
from engine_integration import EngineIntegrationFacade, EngineEventBridge, engine_capability_check
from engine_bridge import EngineCommand, EngineCapability, EngineEvent, EngineResult
print("IMPORT_OK")
PYEOF
)
if echo "$out" | grep -q "IMPORT_OK"; then
  report "engine_integration 模块可导入" 0
else
  report "engine_integration 模块可导入" 1
fi

echo "== 2. 集成门面 Mock 模式初始化 =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
ok = facade.init()
assert ok, "init failed"
assert "cocos" in facade.available_engines
assert "ue5" in facade.available_engines
print(f"INIT_OK engines={facade.available_engines}")
PYEOF
)
if echo "$out" | grep -q "INIT_OK"; then
  report "集成门面 Mock 模式初始化" 0
else
  report "集成门面 Mock 模式初始化" 1
fi

echo "== 3. 引擎命令执行（load_scene/create_node/play） =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
facade.init()
r1 = facade.load_scene("assets/scenes/Main.scene")
r2 = facade.create_node("Player", "Root")
r3 = facade.play()
assert r1.success and r2.success and r3.success, "命令执行失败"
print(f"COMMANDS_OK load={r1.success} create={r2.success} play={r3.success}")
PYEOF
)
if echo "$out" | grep -q "COMMANDS_OK"; then
  report "引擎命令执行" 0
else
  report "引擎命令执行" 1
fi

echo "== 4. 引擎事件 → MessageBus 事件映射 =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
from engine_bridge import EngineEvent
facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
facade.init()

def on_event(msg):
    pass

facade.bus.on("cto", on_event)
facade.subscribe_event("scene_changed", "cto")
ev = EngineEvent(event_type="scene_changed", data={"scene": "Main"}, engine="cocos")
delivered = facade.emit_engine_event(ev)
assert delivered, "事件未投递"
# 验证消息已在总线记录
found = False
for msg in facade.bus.delivered:
    if msg.type == "ENGINE_EVENT" and msg.content.get("event_type") == "scene_changed":
        found = True
        break
assert found, "消息未记录到总线"
print(f"EVENT_BRIDGE_OK delivered={delivered}")
PYEOF
)
if echo "$out" | grep -q "EVENT_BRIDGE_OK"; then
  report "引擎事件 → MessageBus 映射" 0
else
  report "引擎事件 → MessageBus 映射" 1
fi

echo "== 5. 引擎能力查询（Cocos/UE5 能力集） =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
from engine_bridge import EngineCapability
facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
facade.init()
cocos_caps = facade.capabilities("cocos")
ue5_caps = facade.capabilities("ue5")
assert len(cocos_caps) > 0, "Cocos 能力集为空"
assert len(ue5_caps) > 0, "UE5 能力集为空"
# Cocos 不支持 blueprint.create，UE5 支持
assert EngineCapability.BLUEPRINT_CREATE not in cocos_caps, "Cocos 不应支持 blueprint"
assert EngineCapability.BLUEPRINT_CREATE in ue5_caps, "UE5 应支持 blueprint"
# Cocos 应支持 scene.load
assert facade.has_capability(EngineCapability.SCENE_LOAD, "cocos")
print(f"CAPS_OK cocos={len(cocos_caps)} ue5={len(ue5_caps)}")
PYEOF
)
if echo "$out" | grep -q "CAPS_OK"; then
  report "引擎能力查询" 0
else
  report "引擎能力查询" 1
fi

echo "== 6. 引擎能力检查（engine_capability_check 全通过） =="
out=$($PY - <<'PYEOF'
from engine_integration import engine_capability_check
result = engine_capability_check(use_mock=True)
assert all(result.values()), f"检查未全通过: {result}"
print(f"CHECK_ALL_OK {result}")
PYEOF
)
if echo "$out" | grep -q "CHECK_ALL_OK"; then
  report "引擎能力检查全通过" 0
else
  report "引擎能力检查全通过" 1
fi

echo "== 7. 状态报告含集成信息 =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"])
facade.init()
report = facade.report()
assert "integration" in report, "报告缺少 integration 字段"
assert report["integration"]["initialized"] is True
print(f"REPORT_OK initialized={report['integration']['initialized']}")
PYEOF
)
if echo "$out" | grep -q "REPORT_OK"; then
  report "状态报告含集成信息" 0
else
  report "状态报告含集成信息" 1
fi

echo "== 8. emit 单次投递（防双重投递回归） =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
from engine_bridge import EngineEvent
from message_bus import MessageBus

bus = MessageBus()
call_counts = {"cto": 0, "qa": 0}
bus.register("cto"); bus.register("qa")
bus.on("cto", lambda m: call_counts.__setitem__("cto", call_counts["cto"] + 1))
bus.on("qa", lambda m: call_counts.__setitem__("qa", call_counts["qa"] + 1))

facade = EngineIntegrationFacade(use_mock=True, engines=["cocos", "ue5"], bus=bus)
facade.event_bridge.subscribe("scene_changed", "cto")
facade.event_bridge.subscribe("scene_changed", "qa")

ev = EngineEvent(event_type="scene_changed", data={"scene": "main"}, engine="cocos")
delivered = facade.event_bridge.emit(ev)
assert call_counts["cto"] == 1, f"cto expected 1 got {call_counts['cto']}"
assert call_counts["qa"] == 1, f"qa expected 1 got {call_counts['qa']}"
assert set(delivered) == {"cto", "qa"}, delivered
print(f"EMIT_ONCE_OK cto={call_counts['cto']} qa={call_counts['qa']}")
PYEOF
)
if echo "$out" | grep -q "EMIT_ONCE_OK"; then
  report "emit 单次投递（防双重投递）" 0
else
  report "emit 单次投递（防双重投递）" 1
fi

echo "== 9. execute 异常路径携带 command（防 TypeError 回归） =="
out=$($PY - <<'PYEOF'
from engine_integration import EngineIntegrationFacade
from engine_bridge import EngineCommand, EngineCapability, EngineBridgeError

facade = EngineIntegrationFacade(use_mock=True, engines=["cocos"])
cmd = EngineCommand(capability=EngineCapability.SCENE_LOAD, params={"path": "Main.scene"})

def boom(c, e=""):
    raise EngineBridgeError("engine connect failed")
facade._bridge.execute = boom
r = facade.execute(cmd, "cocos")
assert r.success is False, "should be failure"
assert r.command is cmd, "command should be preserved"
print(f"EXEC_ERR_OK success={r.success} error={r.error}")
PYEOF
)
if echo "$out" | grep -q "EXEC_ERR_OK"; then
  report "execute 异常路径携带 command" 0
else
  report "execute 异常路径携带 command" 1
fi

echo ""
echo "=== 汇总 ==="
echo "通过: $pass / $((pass+fail))"
if [ "$fail" -gt "0" ]; then
  echo "结果: 🔴 失败"
  exit 1
else
  echo "结果: 🟢 全部通过"
  exit 0
fi
