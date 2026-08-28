# wp_ai_logic · 程序化生成 / 引擎无关 AI 实现（Issue #90）

- **工作包**：wp_ai_logic 程序化生成/引擎无关 AI
- **部门**：程序线
- **主责角色**：ai_programmer
- **模块**：ai / procgen / behavior-tree
- **产出物类型**：ai_impl（AI 与程序化生成实现文档）
- **场景**：Issue #90「跨平台架构增强」——需实现程序化生成核心 + 引擎无关 NPC AI 行为系统

---

## 一、程序化生成核心设计

### 1.1 生成器架构（引擎无关）

```
┌──────────────────────────────────────────────────────────────┐
│             程序化生成核心（Procgen Core）                    │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 生成器注册表（Generator Registry）                     │  │
│  │  · TerrainGenerator（地形）                            │  │
│  │  · LevelGenerator（关卡）                              │  │
│  │  · PropGenerator（装饰物）                             │  │
│  │  · BuildingGenerator（建筑）                           │  │
│  │  · NarrativeGenerator（叙事）                          │  │
│  │  · ResourceGenerator（资源分布）                       │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │ 统一接口调用                           │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │ 生成管线（Pipeline）                                   │  │
│  │  seed → 地形 → 资源 → 敌兵 → 建筑 → 装饰 → 中立数据    │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │ 中立 JSON 输出                        │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │ 中立数据格式（Neutral Data Format）                     │  │
│  │  · 纯数据结构（JSON）                                  │  │
│  │  · 无引擎依赖                                          │  │
│  │  · 可序列化/可复现                                     │  │
│  └────────────────────┬───────────────────────────────────┘  │
│                       │ 各引擎适配器                          │
│  ┌────────────────────▼───────────────────────────────────┐  │
│  │ 引擎适配器（Web/Cocos/Unity/UE）                       │  │
│  │  · 将中立数据转为引擎原生对象                           │  │
│  │  · Prefab / Scene / Actor 实例化                       │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 1.2 生成器抽象接口

```python
# procgen/core/generator.py
from abc import ABC, abstractmethod
import random
import hashlib
from dataclasses import dataclass, field

@dataclass
class GenerationParams:
    """生成参数"""
    seed: str
    params: dict = field(default_factory=dict)
    
    def get_seed_int(self) -> int:
        """将 seed 字符串转为确定性整数"""
        return int(hashlib.sha256(self.seed.encode()).hexdigest()[:16], 16)

class BaseGenerator(ABC):
    """程序化生成器基类（引擎无关）"""
    
    def __init__(self, seed: str = ""):
        self.seed = seed
        self.rng = random.Random(GenerationParams(seed).get_seed_int())
        self.generator_version = "1.0.0"
    
    @abstractmethod
    def generate(self, params: dict) -> dict:
        """生成中立数据"""
        pass
    
    @abstractmethod
    def validate(self, data: dict) -> bool:
        """校验生成结果"""
        pass
    
    def export(self, data: dict) -> dict:
        """导出中立数据（含元信息）"""
        return {
            "generator": self.__class__.__name__,
            "version": self.generator_version,
            "seed": self.seed,
            "data": data,
        }

class TerrainGenerator(BaseGenerator):
    """地形生成器（Perlin/Simplex 噪声）"""
    
    def generate(self, params: dict) -> dict:
        width = params.get("width", 128)
        height = params.get("height", 128)
        octaves = params.get("octaves", 5)
        persistence = params.get("persistence", 0.5)
        
        heightmap = self._generate_noise(width, height, octaves, persistence)
        
        return {
            "type": "terrain",
            "width": width,
            "height": height,
            "heightmap": heightmap,
            "biome_map": self._classify_biomes(heightmap),
        }
    
    def _generate_noise(self, w: int, h: int, octaves: int, pers: float):
        """Perlin/Simplex 噪声生成"""
        # 实现：使用纯 Python 实现（无第三方依赖）
        # 多倍频叠加产生自然地形
        result = [[0.0] * w for _ in range(h)]
        amplitude = 1.0
        frequency = 1.0
        max_value = 0.0
        
        for _ in range(octaves):
            max_value += amplitude
            for y in range(h):
                for x in range(w):
                    result[y][x] += amplitude * self._noise_2d(
                        x * frequency / w, y * frequency / h)
            amplitude *= pers
            frequency *= 2.0
        
        # 归一化
        for y in range(h):
            for x in range(w):
                result[y][x] /= max_value
        return result
    
    def _noise_2d(self, x: float, y: float) -> float:
        """确定性 2D 噪声（基于 seed 的哈希噪声）"""
        # 实现简单确定性噪声（保证跨引擎一致）
        n = int(x * 10000) + int(y * 10000) * 73856093
        n = (n << 13) ^ n
        return (1.0 - ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7fffffff) / 1073741824.0)

class LevelGenerator(BaseGenerator):
    """关卡生成器"""
    
    def generate(self, params: dict) -> dict:
        level_type = params.get("type", "adventure")
        
        if level_type == "adventure":
            return self._generate_adventure(params)
        elif level_type == "dungeon":
            return self._generate_dungeon(params)
        else:
            return self._generate_open_world(params)
    
    def _generate_adventure(self, params):
        """生成冒险关卡（线性 → 分支）"""
        return {
            "type": "adventure",
            "nodes": self._generate_node_graph(params),
            "enemies": self._generate_enemies(params),
            "rewards": self._generate_rewards(params),
        }
    
    def _generate_dungeon(self, params):
        """生成地牢关卡（房间+连接）"""
        return {
            "type": "dungeon",
            "rooms": self._generate_rooms(params),
            "corridors": self._generate_corridors(params),
            "traps": self._generate_traps(params),
        }

class PropGenerator(BaseGenerator):
    """装饰物生成器"""
    
    def generate(self, params: dict) -> dict:
        # 基于地形数据放置装饰物
        props = []
        for y in range(params.get("height", 128)):
            for x in range(params.get("width", 128)):
                if self._should_place(x, y, params):
                    props.append({
                        "x": x, "y": y,
                        "prop_id": self._pick_prop(params.get("biome", "forest")),
                        "scale": self._random_scale(),
                        "rotation": self._random_rotation(),
                    })
        return {"props": props}
    
    def _should_place(self, x: int, y: int, params: dict) -> bool:
        """确定性放置判断"""
        return self.rng.random() < params.get("density", 0.3)
```

### 1.3 确定性保证

```python
# 同一种子 → 相同输出（跨引擎一致）
# 使用 PCG/XorShift 确定性 RNG，不用系统随机

class DeterministicRNG:
    """确定性随机数生成器（PCG 风格）"""
    
    def __init__(self, seed: int):
        self.state = seed
        self.inc = (seed ^ 0xDA3E39CB94B95BDB) | 1
    
    def next_u32(self) -> int:
        """生成下一个 32bit 随机数"""
        oldstate = self.state
        self.state = oldstate * 6364136223846793005 + self.inc
        xorshifted = ((oldstate >> 18) ^ oldstate) >> 27
        rot = oldstate >> 59
        return ((xorshifted >> rot) | (xorshifted << ((-rot) & 31))) & 0xFFFFFFFF
    
    def random(self) -> float:
        """返回 [0, 1) 随机数"""
        return self.next_u32() / 0xFFFFFFFF
    
    def randint(self, lo: int, hi: int) -> int:
        """返回 [lo, hi] 整数"""
        return lo + (self.next_u32() % (hi - lo + 1))
```

---

## 二、引擎无关 NPC AI 行为系统

### 2.1 行为树架构

```
┌──────────────────────────────────────────────────────────────┐
│          NPC AI 行为系统（引擎无关）                          │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ 行为树定义（JSON 驱动）                               │  │
│  │  · 树节点：selector/sequence/condition/action/        │  │
│  │  · 数据驱动：配置 JSON 定义 AI 行为                   │  │
│  │  · 引擎无关：纯逻辑执行                               │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │ 行为树执行引擎（Behavior Tree Executor）              │  │
│  │  · 节点状态机（IDLE/RUNNING/SUCCESS/FAILED）           │  │
│  │  · 黑板（Blackboard）共享数据                         │  │
│  │  · 感知系统（视野/听觉/触觉）                         │  │
│  └───────────────────────┬───────────────────────────────┘  │
│                          │                                   │
│  ┌───────────────────────▼───────────────────────────────┐  │
│  │ 引擎适配器（AI Adapter）                              │  │
│  │  · 寻路抽象（A*/NavMesh）                             │  │
│  │  · 动画触发（引擎表现）                               │  │
│  │  · 声音播放（引擎表现）                               │  │
│  │  · 特效触发（引擎表现）                               │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 行为树 JSON 格式

```json
{
  "npc_type": "elite_void_wisp",
  "version": "1.0.0",
  "root": {
    "type": "selector",
    "children": [
      {
        "type": "sequence",
        "name": "狂暴攻击（血量低时）",
        "children": [
          {"type": "condition", "condition": "health_ratio < 0.3"},
          {"type": "action", "action": "frenzy_attack", "params": {"duration_ms": 3000}}
        ]
      },
      {
        "type": "sequence",
        "name": "追击攻击",
        "children": [
          {"type": "condition", "condition": "player_visible && distance < 15"},
          {"type": "action", "action": "chase_and_attack", "params": {"attack_range": 3}}
        ]
      },
      {
        "type": "sequence",
        "name": "警戒巡逻",
        "children": [
          {"type": "condition", "condition": "player_detected"},
          {"type": "action", "action": "alert_patrol", "params": {"radius": 20}}
        ]
      },
      {
        "type": "action",
        "name": "正常巡逻",
        "action": "patrol",
        "params": {"waypoints": 4, "speed": 2.0}
      }
    ]
  },
  "blackboard": {
    "initial": {
      "health_ratio": 1.0,
      "player_visible": false,
      "distance": 100,
      "player_detected": false
    }
  }
}
```

### 2.3 行为树执行引擎（C++ 实现）

```cpp
// ai/behavior_tree/BehaviorTree.h
#pragma once
#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <unordered_map>

namespace game_ai {

enum class NodeStatus {
    IDLE, RUNNING, SUCCESS, FAILED
};

struct BTNode {
    virtual ~BTNode() = default;
    virtual NodeStatus Tick(Blackboard& bb, float dt) = 0;
    
    std::string name;
    std::string type;
};

class SelectorNode : public BTNode {
public:
    NodeStatus Tick(Blackboard& bb, float dt) override {
        for (auto& child : children) {
            auto status = child->Tick(bb, dt);
            if (status == NodeStatus::SUCCESS) {
                return NodeStatus::SUCCESS;
            }
            if (status == NodeStatus::RUNNING) {
                return NodeStatus::RUNNING;
            }
        }
        return NodeStatus::FAILED;
    }
    std::vector<std::shared_ptr<BTNode>> children;
};

class SequenceNode : public BTNode {
public:
    NodeStatus Tick(Blackboard& bb, float dt) override {
        for (auto& child : children) {
            auto status = child->Tick(bb, dt);
            if (status == NodeStatus::FAILED) {
                return NodeStatus::FAILED;
            }
            if (status == NodeStatus::RUNNING) {
                return NodeStatus::RUNNING;
            }
        }
        return NodeStatus::SUCCESS;
    }
    std::vector<std::shared_ptr<BTNode>> children;
};

class ConditionNode : public BTNode {
public:
    std::function<bool(Blackboard&)> predicate;
    
    NodeStatus Tick(Blackboard& bb, float dt) override {
        return predicate(bb) ? NodeStatus::SUCCESS : NodeStatus::FAILED;
    }
};

class ActionNode : public BTNode {
public:
    std::function<NodeStatus(Blackboard&, float)> action;
    
    NodeStatus Tick(Blackboard& bb, float dt) override {
        return action(bb, dt);
    }
};

class BehaviorTree {
public:
    void LoadFromJson(const std::string& json);
    NodeStatus Tick(Blackboard& bb, float dt) {
        if (!root_) return NodeStatus::FAILED;
        return root_->Tick(bb, dt);
    }
    
private:
    std::shared_ptr<BTNode> root_;
    std::unordered_map<std::string, std::string> blackboard_;
};

} // namespace game_ai
```

### 2.4 黑板（Blackboard）设计

```python
# ai/blackboard.py
"""黑板（Blackboard）：NPC AI 共享数据存储"""
from typing import Any, Dict

class Blackboard:
    """AI 行为共享数据容器（引擎无关）"""
    
    def __init__(self):
        self._data: Dict[str, Any] = {}
        self._listeners: Dict[str, list] = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        # 通知监听者（用于引擎表现层联动）
        if key in self._listeners:
            for cb in self._listeners[key]:
                cb(key, value)
    
    def watch(self, key: str, callback) -> None:
        """监听指定键值变化"""
        self._listeners.setdefault(key, []).append(callback)
    
    def to_dict(self) -> dict:
        return dict(self._data)
    
    def from_dict(self, data: dict) -> None:
        self._data = dict(data)
```

### 2.5 感知系统（引擎无关）

```python
# ai/perception.py
"""NPC 感知系统（引擎无关）"""
from dataclasses import dataclass, field
import math

@dataclass
class Perception:
    """NPC 感知数据"""
    visible_players: list = field(default_factory=list)  # [(player_id, distance)]
    heard_events: list = field(default_factory=list)      # [(event_type, position)]
    last_seen_position: tuple = None
    last_heard_position: tuple = None
    
    def is_player_visible(self, player_id: str) -> bool:
        return any(pid == player_id for pid, _ in self.visible_players)
    
    def nearest_player(self) -> tuple:
        if not self.visible_players:
            return None
        return min(self.visible_players, key=lambda x: x[1])

class PerceptionSystem:
    """感知系统：计算 NPC 对周围环境的感知"""
    
    def __init__(self, view_angle=60.0, view_distance=20.0,
                 hearing_radius=10.0):
        self.view_angle = view_angle      # 视野角度（度）
        self.view_distance = view_distance  # 视野距离（米）
        self.hearing_radius = hearing_radius  # 听觉半径（米）
    
    def update(self, npc_pos: tuple, npc_angle: float,
               players: list, events: list) -> Perception:
        """更新感知状态"""
        perception = Perception()
        
        # 视野检测
        for player in players:
            pos, dist = player.position, self._distance(npc_pos, player.position)
            if dist <= self.view_distance:
                angle = self._angle_to(npc_pos, pos, npc_angle)
                if abs(angle) <= self.view_angle / 2:
                    perception.visible_players.append((player.id, dist))
        
        # 听觉检测
        for evt in events:
            dist = self._distance(npc_pos, evt.position)
            if dist <= self.hearing_radius:
                perception.heard_events.append((evt.type, evt.position))
        
        # 记录最后感知
        if perception.visible_players:
            _, dist = perception.nearest_player()
            player = next(p for p in players if p.id == perception.nearest_player()[0])
            perception.last_seen_position = player.position
        
        return perception
    
    def _distance(self, a: tuple, b: tuple) -> float:
        return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2)
    
    def _angle_to(self, from_pos: tuple, to_pos: tuple, facing: float) -> float:
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        target_angle = math.degrees(math.atan2(dy, dx))
        # 规范化到 [-180, 180]
        diff = (target_angle - facing + 180) % 360 - 180
        return diff
```

---

## 三、寻路抽象层

### 3.1 寻路接口定义

```python
# ai/pathfinding.py
"""引擎无关寻路抽象接口"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class PathNode:
    """路径节点"""
    x: float
    y: float
    z: float = 0.0

class IPathfinding(ABC):
    """寻路抽象接口（各引擎实现）"""
    
    @abstractmethod
    def find_path(self, start: PathNode, end: PathNode) -> list:
        """查找路径，返回 PathNode 列表"""
        pass
    
    @abstractmethod
    def is_reachable(self, start: PathNode, end: PathNode) -> bool:
        """检查是否可达"""
        pass

class AStarPathfinding(IPathfinding):
    """A* 寻路实现（引擎无关，纯网格）"""
    
    def __init__(self, grid_width: int = 128, grid_height: int = 128,
                 walkable: callable = None):
        self.grid_width = grid_width
        self.grid_height = grid_height
        self.walkable = walkable or (lambda x, y: True)
    
    def find_path(self, start: PathNode, end: PathNode) -> list:
        """A* 寻路核心实现"""
        # 标准 A* 算法（使用堆优化）
        # 确定性实现：不依赖引擎导航网格
        return self._astar(start, end)
```

### 3.2 各引擎寻路适配

| 引擎 | 寻路方案 | 适配策略 |
|------|---------|---------|
| Web/React | 纯 JS 网格寻路 | 使用 A* 纯逻辑实现 |
| Cocos | Cocos 导航 | 调用引擎寻路 + 中间件校验 |
| Unity | NavMesh | 使用 Unity NavMesh + 中间件统一参数 |
| UE5 | NavMesh | 使用 UE NavMesh + 中间件统一参数 |

---

## 四、难度自适应系统（跨端统一）

### 4.1 动态难度调节

```python
# ai/difficulty.py
"""跨端统一难度自适应系统"""

class DifficultyAdaptor:
    """基于玩家表现的动态难度调节"""
    
    def __init__(self, base_difficulty: float = 1.0):
        self.base_difficulty = base_difficulty
        self.current_difficulty = base_difficulty
        self.performance_history = []
    
    def update(self, player_stats: dict) -> float:
        """根据玩家表现动态调节难度"""
        # 收集性能指标
        dps = player_stats.get("dps", 0)
        survival_time = player_stats.get("survival_time", 0)
        
        # 计算表现评分
        performance_score = self._calc_performance(dps, survival_time)
        self.performance_history.append(performance_score)
        
        # 动态调节难度
        avg = sum(self.performance_history[-10:]) / max(len(self.performance_history[-10:]), 1)
        if avg > 0.7:   # 玩家表现强 → 提高难度
            self.current_difficulty = min(2.0, self.current_difficulty * 1.05)
        elif avg < 0.3:  # 玩家表现弱 → 降低难度
            self.current_difficulty = max(0.5, self.current_difficulty * 0.95)
        
        return self.current_difficulty
    
    def get_ai_config(self) -> dict:
        """生成当前难度的 AI 配置"""
        return {
            "difficulty": self.current_difficulty,
            "attack_delay_ms": int(500 / self.current_difficulty),  # 攻击前摇
            "attack_damage_mult": self.current_difficulty,
            "ai_reaction_speed": 1.0 / self.current_difficulty,
        }

# 平台差异化配置
PLATFORM_DIFFICULTY = {
    "web":    {"attack_delay_factor": 1.2},  # 轻量端 AI 反应稍慢
    "cocos":  {"attack_delay_factor": 1.2},  # 轻量端 AI 反应稍慢
    "unity":  {"attack_delay_factor": 1.0},  # 完整端标准难度
    "ue5":    {"attack_delay_factor": 0.9},  # 高保真端 AI 更激进
}
```

### 4.2 NPC AI 状态机

```
┌────────────────────────────────────────────────────────────┐
│  NPC AI 状态机（引擎无关）                                  │
│                                                            │
│  [巡逻 Patrol] ──检测到玩家──→ [警觉 Alert]                 │
│       ↑                            │                       │
│       │                            ▼                       │
│       │                         [追击 Chase]               │
│       │                            │                       │
│       │              ┌─────────────┴─────────────┐        │
│       │              ▼                           ▼        │
│       │         [攻击 Attack]              [召唤 Summon]    │
│       │              │                           │        │
│       │              └─────────────┬─────────────┘        │
│       │                            ▼                       │
│       │                    [战斗 Combat]                   │
│       │                            │                       │
│       │             ┌──────────────┼──────────────┐       │
│       │             ▼              ▼              ▼       │
│       │        [狂暴 Frenzy]  [撤退 Retreat]  [治疗 Heal]   │
│       │             │              │              │       │
│       │             └──────────────┼──────────────┘       │
│       │                            ▼                       │
│       └──────玩家离开/战斗结束←──[返回 Return]              │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 五、程序化内容生成集成

### 5.1 生成→AI 联动管线

```
[seed] → [TerrainGen] → [LevelGen] → [EnemyGen] → [AI配置] → [各引擎场景]
   │          │             │            │            │           │
   │          ▼             ▼            ▼            ▼           ▼
   └──→ 地形数据 → 关卡布局 → 敌人布点 → 行为树JSON → 引擎适配器 → 场景实例
```

### 5.2 敌人生成器（含 AI 配置）

```python
# procgen/enemy_generator.py
"""敌人生成器：生成敌人 + 关联 AI 配置"""

class EnemyGenerator(BaseGenerator):
    """基于难度曲线生成敌人"""
    
    def generate(self, params: dict) -> dict:
        """生成敌人布点 + AI 配置"""
        level = params.get("level", 1)
        difficulty = params.get("difficulty", 1.0)
        
        # 基于难度曲线确定敌人类型和数量
        enemy_configs = self._calc_enemy_composition(level, difficulty)
        
        # 为每个敌人生成 AI 行为树
        enemies = []
        for config in enemy_configs:
            ai_behavior = self._generate_ai_behavior(config)
            enemies.append({
                "enemy_type": config["type"],
                "level": level,
                "position": config["position"],
                "ai_behavior": ai_behavior,
            })
        
        return {"enemies": enemies}
    
    def _generate_ai_behavior(self, config: dict) -> dict:
        """生成 NPC AI 行为树配置"""
        enemy_type = config["type"]
        
        # 不同类型敌人 → 不同行为模式
        ai_templates = {
            "void_wisp": {
                "root": {
                    "type": "selector",
                    "children": [
                        {"type": "sequence", "conditions": ["health<0.3"],
                         "action": "frenzy_attack"},
                        {"type": "sequence", "conditions": ["player_visible"],
                         "action": "chase_and_attack"},
                        {"type": "action", "action": "patrol"}
                    ]
                }
            },
            "elite_void_wisp": {
                "root": {
                    "type": "selector",
                    "children": [
                        {"type": "sequence", "conditions": ["health<0.2"],
                         "action": "summon_minions"},
                        {"type": "sequence", "conditions": ["player_visible", "distance>5"],
                         "action": "ranged_attack"},
                        {"type": "action", "action": "patrol"}
                    ]
                }
            }
        }
        
        return ai_templates.get(enemy_type, ai_templates["void_wisp"])
```

---

## 六、交付物与验收标准

| 交付物 | 路径 | 验收标准 |
|--------|------|---------|
| 生成器核心 | `procgen/core/` | 5 类生成器可运行 + 确定性验证 |
| 行为树引擎 | `ai/behavior_tree/` | 解析 JSON + 执行 + 引擎无关 |
| 黑板系统 | `ai/blackboard.py` | 数据共享 + 监听通知 |
| 感知系统 | `ai/perception.py` | 视野/听觉检测 + 引擎无关 |
| 寻路抽象 | `ai/pathfinding.py` | A* 实现 + 接口抽象 |
| 难度自适应 | `ai/difficulty.py` | 动态调节 + 平台差异化 |
| 敌人生成器 | `procgen/enemy_generator.py` | 含 AI 行为树配置 |

**验收指标**：
- 同一 seed 在 4 引擎生成完全一致的地图/敌人/AI 配置（hash 一致）
- 行为树 JSON 可被 4 引擎解析执行
- NPC AI 状态机在 4 引擎上行为一致
- 难度自适应跨端效果统一（同玩家表现 → 同难度调整）
- 生成性能：128×128 地图生成 ≤ 50ms

---

> 产出：ai_programmer 承接，基于策划线 wp_gameplay 程序化生成标准 + wp_combat NPC AI 行为设计 + 架构师中间件设计文档。
