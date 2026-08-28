#!/usr/bin/env bash
# ============================================================
# 引擎桥接层测试信号灯（test_engine_bridge）
# 说明: 验证引擎桥接层（EngineBridge）架构的正确性——
#       1. 统一引擎命令协议（EngineCommand）可用；
#       2. Windows 目标环境探测正确（模拟 Windows + Cocos + UE5）；
#       3. MCP 客户端 Mock 模式连接/调用正常；
#       4. 插件适配器发现/调用正常；
#       5. 引擎适配器工厂（cocos/ue5/mock）创建正确；
#       6. 引擎桥接门面（EngineBridgeFacade）统一入口可用；
#       7. 能力查询：Cocos 与 UE5 能力集差异正确。
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

echo "== 1. 引擎桥接层可导入 =="
out=$($PY - <<'PYEOF'
from engine_bridge import EngineBridgeFacade, BridgeConfig, EngineCommand, EngineCapability
from engine_bridge.environment import get_windows_environment
from engine_bridge.mcp_client import MCPClient
from engine_bridge.plugin_adapter import PluginAdapter
from engine_bridge.engine_adapter import create_engine_adapter
print("IMPORT_OK")
PYEOF
)
if echo "$out" | grep -q "IMPORT_OK"; then
  report "引擎桥接层模块可导入" 0
else
  report "引擎桥接层模块可导入" 1
fi

echo "== 2. Windows 目标环境探测 =="
out=$($PY - <<'PYEOF'
from engine_bridge.environment import get_windows_environment
env = get_windows_environment()
print('OS=' + env.os_name)
print('ENGINE_TYPE=' + env.engine_type)
print('COCOS_PATH=' + env.cocos_path)
print('COCOS_VERSION=' + env.cocos_version)
print('UE5_PATH=' + env.ue5_path)
print('UE5_VERSION=' + env.ue5_version)
print('MCP_COCOS=' + env.mcp_endpoints.get('cocos', ''))
print('MCP_UE5=' + env.mcp_endpoints.get('ue5', ''))
PYEOF
)
if echo "$out" | grep -q "OS=windows"; then
  report "Windows 环境探测正确" 0
else
  report "Windows 环境探测正确 ($out)" 1
fi
if echo "$out" | grep -q "ENGINE_TYPE=both"; then
  report "同时探测到 Cocos + UE5（both）" 0
else
  report "同时探测到 Cocos + UE5（both） ($out)" 1
fi
if echo "$out" | grep -q "COCOS_PATH=.*CocosCreator"; then
  report "Cocos Creator 路径探测正确" 0
else
  report "Cocos Creator 路径探测正确 ($out)" 1
fi
if echo "$out" | grep -q "UE5_PATH=.*Epic Games.*UE_5"; then
  report "UE5 路径探测正确" 0
else
  report "UE5 路径探测正确 ($out)" 1
fi
if echo "$out" | grep -q "MCP_COCOS=http"; then
  report "Cocos MCP 端点配置正确" 0
else
  report "Cocos MCP 端点配置正确 ($out)" 1
fi
if echo "$out" | grep -q "MCP_UE5=http"; then
  report "UE5 MCP 端点配置正确" 0
else
  report "UE5 MCP 端点配置正确 ($out)" 1
fi

echo "== 3. 引擎桥接门面 Mock 模式 =="
out=$($PY - <<'PYEOF'
from engine_bridge import EngineBridgeFacade, BridgeConfig
bridge = EngineBridgeFacade(BridgeConfig(use_mock=True, engines=['cocos','ue5']))
bridge.init()
print('ENGINES=' + ','.join(bridge.available_engines))
print('DEFAULT=' + bridge._default_engine)
# 加载场景
r = bridge.load_scene('assets/scenes/Main.scene')
print('LOAD_SCENE=' + str(r.success))
# 创建节点
r = bridge.create_node('Player', 'Root')
print('CREATE_NODE=' + str(r.success))
# Play
r = bridge.play()
print('PLAY=' + str(r.success))
# 查询状态
print('STATUS_COCOS=' + bridge.engine_status('cocos').value)
print('STATUS_UE5=' + bridge.engine_status('ue5').value)
PYEOF
)
if echo "$out" | grep -q "ENGINES=cocos,ue5"; then
  report "桥接初始化创建 cocos + ue5 适配器" 0
else
  report "桥接初始化创建 cocos + ue5 适配器 ($out)" 1
fi
if echo "$out" | grep -q "LOAD_SCENE=True"; then
  report "load_scene 命令执行成功" 0
else
  report "load_scene 命令执行成功 ($out)" 1
fi
if echo "$out" | grep -q "CREATE_NODE=True"; then
  report "create_node 命令执行成功" 0
else
  report "create_node 命令执行成功 ($out)" 1
fi
if echo "$out" | grep -q "PLAY=True"; then
  report "play 命令执行成功" 0
else
  report "play 命令执行成功 ($out)" 1
fi
if echo "$out" | grep -q "STATUS_COCOS=running" && echo "$out" | grep -q "STATUS_UE5=running"; then
  report "cocos + ue5 状态均为 running" 0
else
  report "cocos + ue5 状态均为 running ($out)" 1
fi

echo "== 4. 引擎适配器工厂 =="
out=$($PY - <<'PYEOF'
from engine_bridge.engine_adapter import create_engine_adapter
# Cocos
cocos = create_engine_adapter('cocos', use_mock=True)
print('COCOS_TYPE=' + cocos.engine_type)
print('COCOS_CAPS=' + str(len(cocos.capabilities())))
print('COCOS_CONNECT=' + str(cocos.connect()))
# UE5
ue5 = create_engine_adapter('ue5', use_mock=True)
print('UE5_TYPE=' + ue5.engine_type)
print('UE5_CAPS=' + str(len(ue5.capabilities())))
print('UE5_CONNECT=' + str(ue5.connect()))
# Mock
mock = create_engine_adapter('mock')
print('MOCK_TYPE=' + mock.engine_type)
# 不支持的引擎
try:
    create_engine_adapter('unity')
    print('UNITY_ERROR=False')
except Exception as e:
    print('UNITY_ERROR=True')
PYEOF
)
if echo "$out" | grep -q "COCOS_TYPE=cocos"; then
  report "Cocos 适配器类型正确" 0
else
  report "Cocos 适配器类型正确 ($out)" 1
fi
if echo "$out" | grep -q "COCOS_CONNECT=True"; then
  report "Cocos 适配器连接成功（Mock）" 0
else
  report "Cocos 适配器连接成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "UE5_TYPE=ue5"; then
  report "UE5 适配器类型正确" 0
else
  report "UE5 适配器类型正确 ($out)" 1
fi
if echo "$out" | grep -q "UE5_CONNECT=True"; then
  report "UE5 适配器连接成功（Mock）" 0
else
  report "UE5 适配器连接成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "UNITY_ERROR=True"; then
  report "不支持的引擎类型正确报错" 0
else
  report "不支持的引擎类型正确报错 ($out)" 1
fi

echo "== 5. 能力查询差异 =="
out=$($PY - <<'PYEOF'
from engine_bridge import EngineBridgeFacade, BridgeConfig, EngineCapability
bridge = EngineBridgeFacade(BridgeConfig(use_mock=True, engines=['cocos','ue5']))
bridge.init()
# UE5 有 Blueprint，Cocos 没有
print('UE5_BLUEPRINT=' + str(bridge.has_capability(EngineCapability.BLUEPRINT_CREATE, 'ue5')))
print('COCOS_BLUEPRINT=' + str(bridge.has_capability(EngineCapability.BLUEPRINT_CREATE, 'cocos')))
# 两者都有场景加载
print('UE5_SCENE=' + str(bridge.has_capability(EngineCapability.SCENE_LOAD, 'ue5')))
print('COCOS_SCENE=' + str(bridge.has_capability(EngineCapability.SCENE_LOAD, 'cocos')))
# 能力数量
print('COCOS_NUM=' + str(len(bridge.capabilities('cocos'))))
print('UE5_NUM=' + str(len(bridge.capabilities('ue5'))))
PYEOF
)
if echo "$out" | grep -q "UE5_BLUEPRINT=True"; then
  report "UE5 支持 Blueprint 创建" 0
else
  report "UE5 支持 Blueprint 创建 ($out)" 1
fi
if echo "$out" | grep -q "COCOS_BLUEPRINT=False"; then
  report "Cocos 不支持 Blueprint 创建（能力差异正确）" 0
else
  report "Cocos 不支持 Blueprint 创建（能力差异正确） ($out)" 1
fi
if echo "$out" | grep -q "COCOS_SCENE=True" && echo "$out" | grep -q "UE5_SCENE=True"; then
  report "Cocos + UE5 均支持场景加载" 0
else
  report "Cocos + UE5 均支持场景加载 ($out)" 1
fi
if echo "$out" | grep -q "COCOS_NUM=[0-9]" && echo "$out" | grep -q "UE5_NUM=[0-9]"; then
  report "能力数量非空" 0
else
  report "能力数量非空 ($out)" 1
fi

echo "== 6. MCP 客户端 Mock 模式 =="
out=$($PY - <<'PYEOF'
from engine_bridge.mcp_client import MCPClient
from engine_bridge.protocol import EngineCommand, EngineCapability
client = MCPClient('http://127.0.0.1:12345/mcp', engine='cocos', use_mock=True)
print('CONNECT=' + str(client.connect()))
print('CONNECTED=' + str(client.is_connected))
# 调用工具
result = client.call_tool('engine.scene.load', {'path': 'test.scene'})
print('CALL_OK=' + str(result.get('isError', False) == False))
# 执行命令
cmd = EngineCommand(EngineCapability.SCENE_LOAD, {'path': 'test.scene'})
r = client.execute_command(cmd)
print('EXECUTE=' + str(r.success))
print('CMD=' + r.command.capability.value)
# 工具列表
tools = client.list_tools()
print('TOOLS=' + str(len(tools)))
PYEOF
)
if echo "$out" | grep -q "CONNECT=True"; then
  report "MCP 客户端连接成功（Mock）" 0
else
  report "MCP 客户端连接成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "CALL_OK=True"; then
  report "MCP 工具调用成功（Mock）" 0
else
  report "MCP 工具调用成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "EXECUTE=True"; then
  report "MCP execute_command 成功" 0
else
  report "MCP execute_command 成功 ($out)" 1
fi
if echo "$out" | grep -q "CMD=scene.load"; then
  report "命令能力映射正确" 0
else
  report "命令能力映射正确 ($out)" 1
fi
if echo "$out" | grep -q "TOOLS=[0-9]"; then
  report "MCP 工具列表非空" 0
else
  report "MCP 工具列表非空 ($out)" 1
fi

echo "== 7. 插件适配器 Mock 模式 =="
out=$($PY - <<'PYEOF'
from engine_bridge.plugin_adapter import PluginAdapter
from engine_bridge.protocol import EngineCommand, EngineCapability

# Cocos 插件
plugins = PluginAdapter('cocos', use_mock=True)
plist = plugins.scan_plugins()
print('COCOS_PLUGINS=' + str(len(plist)))
# 调用插件
result = plugins.execute_plugin_call('cnb-scene-controller', 'scene.load', {'path': 'test.scene'})
print('PLUGIN_CALL=' + str(result.get('ok', False)))
# 执行命令
cmd = EngineCommand(EngineCapability.SCENE_LOAD, {'path': 'test.scene'})
r = plugins.execute_command(cmd)
print('PLUGIN_CMD=' + str(r.success))
# 不存在的插件
try:
    plugins.execute_plugin_call('nonexistent', 'test', {})
    print('MISSING_PLUGIN=False')
except Exception as e:
    print('MISSING_PLUGIN=True')

# UE5 插件
plugins_ue5 = PluginAdapter('ue5', use_mock=True)
plist_ue5 = plugins_ue5.scan_plugins()
print('UE5_PLUGINS=' + str(len(plist_ue5)))
PYEOF
)
if echo "$out" | grep -q "COCOS_PLUGINS=[0-9]"; then
  report "Cocos 插件发现成功（Mock）" 0
else
  report "Cocos 插件发现成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "PLUGIN_CALL=True"; then
  report "Cocos 插件调用成功（Mock）" 0
else
  report "Cocos 插件调用成功（Mock） ($out)" 1
fi
if echo "$out" | grep -q "PLUGIN_CMD=True"; then
  report "插件通道执行命令成功" 0
else
  report "插件通道执行命令成功 ($out)" 1
fi
if echo "$out" | grep -q "MISSING_PLUGIN=True"; then
  report "不存在的插件正确报错" 0
else
  report "不存在的插件正确报错 ($out)" 1
fi
if echo "$out" | grep -q "UE5_PLUGINS=[0-9]"; then
  report "UE5 插件发现成功（Mock）" 0
else
  report "UE5 插件发现成功（Mock） ($out)" 1
fi

echo "== 8. 命令集快捷方法 =="
out=$($PY - <<'PYEOF'
from engine_bridge.protocol import EngineCommandSet, EngineCapability

# load_scene
cmd = EngineCommandSet.load_scene('test.scene')
print('CMD1=' + cmd.capability.value)
print('CMD1_PARAM=' + str(cmd.params.get('path', '')))

# create_node
cmd = EngineCommandSet.create_node('Player', 'Root')
print('CMD2=' + cmd.capability.value)
print('CMD2_PARAM=' + cmd.params.get('name', ''))

# set_transform
cmd = EngineCommandSet.set_transform('/Root/Player', position=[0, 0, 0])
print('CMD3=' + cmd.capability.value)
print('CMD3_PARAM=' + str(cmd.params.get('position', [])))

# run_test
cmd = EngineCommandSet.run_test('combat')
print('CMD4=' + cmd.capability.value)
print('CMD4_PARAM=' + str(cmd.params.get('filter', '')))
PYEOF
)
if echo "$out" | grep -q "CMD1=scene.load" && echo "$out" | grep -q "CMD1_PARAM=test.scene"; then
  report "load_scene 命令构造正确" 0
else
  report "load_scene 命令构造正确 ($out)" 1
fi
if echo "$out" | grep -q "CMD2=node.create" && echo "$out" | grep -q "CMD2_PARAM=Player"; then
  report "create_node 命令构造正确" 0
else
  report "create_node 命令构造正确 ($out)" 1
fi
if echo "$out" | grep -q "CMD3=node.transform" && echo "$out" | grep -q "CMD3_PARAM=\[0, 0, 0\]"; then
  report "set_transform 命令构造正确" 0
else
  report "set_transform 命令构造正确 ($out)" 1
fi
if echo "$out" | grep -q "CMD4=test.run" && echo "$out" | grep -q "CMD4_PARAM=combat"; then
  report "run_test 命令构造正确" 0
else
  report "run_test 命令构造正确 ($out)" 1
fi

echo ""
echo "引擎桥接层测试信号灯结果: $pass 通过 / $fail 失败"
if [ "$fail" -gt 0 ]; then
  echo "🔴 阻塞：存在未通过断言"
  exit 1
fi
echo "🟢 全部通过"
exit 0
