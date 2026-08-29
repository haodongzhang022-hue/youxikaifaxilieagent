# wp_testing · 纯算法单元测试用例跨语言保留 + 回归基线

- **工作包**：wp_testing 纯算法单元测试用例跨语言保留+回归基线
- **部门**：测试线
- **主责角色**：qa_engineer（功能测试/回归测试）
- **协办角色**：auto_qa（自动化测试/CI集成）
- **模块**：testing
- **产出物类型**：test_doc + test_script（单元测试用例 + 回归基线）
- **依赖**：程序线 wp_client（纯逻辑类库）+ wp_engine（阶段感知引擎）+ wp_server（协议资产库）+ 美术线 wp_art_direction（表现层边界）
- **场景**：Issue #112「游戏向架构师的开发」——纯算法需跨语言保留 + 回归基线

---

## 〇、核心目标

Issue #112 核心思想之一是**"跨阶段资产复用"**——纯数学/算法资产是
跨越所有阶段的"不换零件"核心资产。而**算法单元测试用例（Unit Tests）**
是可以一直保留的：无论算法从 Python/TS 翻译到 C#/C++，只要跑一遍当年
的测试用例结果一致，就说明重构成功。

本工作包实现：
1. **确定性计算跨语言保留**：验证 pure_logic 核心算法为确定性（同输入→同输出），
   这是跨语言翻译可回归的前提；
2. **边界条件覆盖**：纯逻辑引擎的伤害/治疗/升级/道具等边界保护；
3. **阶段边界越界检测**：验证 stage_aware_engine "阶段不对=错"的护栏；
4. **协议多语言生成一致性**：验证 protocol_tools 四种语言生成的一致性和向后兼容；
5. **回归基线**：验证依赖的上游产出物（wp_client/wp_art_direction 等）可测且基线全绿。

---

## 一、跨语言保留单元测试矩阵

| 测试模块 | 核心算法 | 确定性 | 跨语言可翻译 | 回归基线 |
|---------|---------|--------|------------|---------|
| `PureLogicEngine.calculate_damage` | 伤害公式（max(1, atk×multiplier - def×0.5)）| ✅ MD5 确定性暴击 | ✅ 纯数学 | ✅ |
| `PureLogicEngine.exp_to_level` | 经验→等级（exp//100+1）| ✅ | ✅ | ✅ |
| `PureLogicEngine.state_hash` | 状态哈希（SHA256确定性）| ✅ | ✅ | ✅ |
| `GameState.to_dict/from_dict` | 状态序列化（JSON）| ✅ | ✅ | ✅ |
| `StageBoundaryGuard.check` | 阶段边界检查（阶段不对=错）| ✅ | ✅ | ✅ |
| `EngineStageSelector.select` | 阶段→引擎选型 | ✅ | ✅ | ✅ |
| `ProtocolParser.parse` | 协议解析 | ✅ | ✅ | ✅ |
| `ProtocolCodegen.generate_*` | 四语言代码生成 | ✅ | ✅ | ✅ |
| `ProtocolVersionManager.check_backward_compat` | 向后兼容 | ✅ | ✅ | ✅ |

---

## 二、确定性验证（跨语言保留的前提）

### 2.1 calculate_damage 确定性

```python
# 相同输入 → 相同输出（MD5 确定性暴击判定）
d1 = calculate_damage(100, 50)   # {damage: X, is_crit: Y}
d2 = calculate_damage(100, 50)   # {damage: X, is_crit: Y}  ← 必须相等
```

- 不依赖 `random`，暴击判定基于 `hashlib.md5(f"{atk}:{def}:{multiplier}")`
- 不同输入（atk/def/multiplier 任一变化）→ 结果确定性变化
- **跨语言保留**：MD5 算法在 Python/TS/C#/C++ 中实现一致，可交叉验证

### 2.2 exp_to_level 确定性

```python
exp_to_level(0)   → 1   # 0exp → Lv1
exp_to_level(50)  → 1   # 50exp → Lv1
exp_to_level(150) → 2   # 150exp → Lv2
exp_to_level(250) → 3   # 250exp → Lv3
exp_to_level(350) → 4   # 350exp → Lv4
```

- 纯整数运算 `exp // 100 + 1`，跨语言完全一致

### 2.3 state_hash 确定性

```python
# 相同状态 → 相同哈希（SHA256 排序键 JSON 序列化）
state_hash(s1) == state_hash(s2)  # 相同状态必须相等
state_hash(s1) != state_hash(s3)  # 不同状态必须不同
```

- `json.dumps(sort_keys=True)` + `hashlib.sha256`，跨语言可实现一致

---

## 三、纯逻辑引擎边界条件覆盖

| # | 场景 | 期望行为 | 测试结果 |
|---|------|---------|:-------:|
| 1 | 过量伤害（剩余HP < 伤害量）| HP 不低于 0 | ✅ |
| 2 | 负伤害 | HP 不变（不恢复）| ✅ |
| 3 | 过量治疗（HP + 治疗 > 上限）| HP 不超过 max_hp | ✅ |
| 4 | 负治疗 | HP 不变（不扣减）| ✅ |
| 5 | 多次升级链（350exp）| Lv1→Lv4，maxHP 100→160，升级后满血 | ✅ |
| 6 | 道具耗尽后使用 | 返回 `not_enough` 事件 | ✅ |
| 7 | 事件队列 | 正确生成 + 消费后清空 | ✅ |

---

## 四、阶段边界越界检测（阶段不对=错）

### 4.1 Cocos 阶段（MVP 验证期）

| 模块 | 适用阶段 | 当前阶段=Cocos | 结果 |
|------|---------|:-----------:|:---:|
| `combat_turn_based`（回合制）| 阶段1 | ✅ | ✅ 通过 |
| `render_2d`（2D渲染）| 阶段1 | ✅ | ✅ 通过 |
| `combat_frame_sync`（帧同步）| 阶段3 | ❌ | ✅ 越界拦截（过度设计）|
| `combat_real_time`（实时战斗）| 阶段2 | ❌ | ✅ 越界拦截（过度设计）|
| `render_3d_advanced`（3D高精）| 阶段3 | ❌ | ✅ 越界拦截（过度设计）|

### 4.2 Unity 阶段（商业化期）

| 模块 | 适用阶段 | 当前阶段=Unity | 结果 |
|------|---------|:-----------:|:---:|
| `combat_real_time`（实时战斗）| 阶段2 | ✅ | ✅ 通过 |
| `physics_advanced`（高级物理）| 阶段2 | ✅ | ✅ 通过 |
| `ai_behavior_tree`（AI行为树）| 阶段3 | ❌ | ✅ 越界拦截（过度设计）|
| `combat_frame_sync`（帧同步）| 阶段3 | ❌ | ✅ 越界拦截（过度设计）|

### 4.3 UE 阶段（3A/重度实时）

| 模块 | 适用阶段 | 当前阶段=UE | 结果 |
|------|---------|:-----------:|:---:|
| `combat_frame_sync`（帧同步）| 阶段3 | ✅ | ✅ 通过 |
| `ai_behavior_tree`（AI行为树）| 阶段3 | ✅ | ✅ 通过 |
| `render_3d_advanced`（3D高精）| 阶段3 | ✅ | ✅ 通过 |
| `network_low_freq`（低频网络）| 阶段1 | ❌ | ✅ 技术债标记 |

### 4.4 阶段切换规则

- 阶段1→阶段2：✅ 可以（只能前进）
- 阶段2→阶段3：✅ 可以（只能前进）
- 阶段3→阶段2：❌ 不可以（不能后退）

---

## 五、协议多语言生成一致性

### 5.1 解析完整性

- 13 个 message：PlayerData / GameRequest / GameResponse / LoginRequest / LoginResponse /
  GameplayActionRequest / GameplaySnapshotResponse / CombatRequest / CombatResponse /
  EconomyTransferRequest / EconomyTransferResponse / StageTransitionRequest / StageTransitionResponse
- 4 个 enum：Platform / ErrorCode / MsgType / GameStage

### 5.2 四语言生成

| 语言 | 生成方式 | LoginRequest 表示 |
|------|---------|------------------|
| Python | `@dataclass class LoginRequest` | ✅ |
| TypeScript | `interface LoginRequest` | ✅ |
| C# | `[Serializable] class LoginRequest` | ✅ |
| C++ | `struct LoginRequest` | ✅ |

### 5.3 向后兼容

- 自比较（old == new）：✅ 兼容
- 删除字段：✅ 检出 1 项违规
- 规则：字段只增不改，新增字段用 optional 标记

---

## 六、回归基线验证

### 6.1 上游产出物可测性

| 产出物 | 位置 | 状态 |
|--------|------|:---:|
| wp_client 纯逻辑类库 | `client_core/pure_logic.py` | ✅ 存在可测 |
| wp_client 表现层适配器 | `client_core/cocos_presenter.py` | ✅ 存在可测 |
| wp_engine 阶段感知引擎 | `game-studio-agents/config/stage_aware_engine.py` | ✅ 存在可测 |
| wp_server 协议工具链 | `game-studio-agents/config/protocol_tools.py` | ✅ 存在可测 |
| wp_server 协议定义 | `server/proto/protocol.proto` | ✅ 存在可测 |
| wp_server 无状态服务端 | `server/core/stateless_server.py` | ✅ 存在可测 |
| wp_art_direction 美术边界 | `docs/design-output/美术线/issue112/*.md` | ✅ 存在可测 |

### 6.2 既有回归基线

| 测试脚本 | 结果 |
|---------|:---:|
| `test_client_core.sh`（客户端纯逻辑类库）| 🟢 12/12 通过 |
| `test_stage_aware_engine.sh`（阶段感知引擎）| 🟢 14/14 通过 |
| `test_pure_algorithm_cross_lang.sh`（本工作包）| 🟢 30/30 通过 |

---

## 七、测试信号灯汇总

```
=== 汇总: 30 通过 / 0 失败 ===
🟢 wp_testing 纯算法跨语言单元测试 + 回归基线 全部通过
```

| 测试大类 | 通过 | 说明 |
|---------|:---:|------|
| 确定性计算跨语言保留 | 6 | 同输入同输出、不同输入有变化、边界保护 |
| pure_logic 边界条件 | 7 | 伤害/治疗/升级/道具/事件边界 |
| 阶段边界越界检测 | 7 | 三阶段越界检测 + 选型 + 切换规则 |
| 协议多语言生成 | 5 | 解析完整、四语言生成、兼容检查 |
| 回归基线 | 5 | 上游产出物可测 + 既有回归全绿 |
| **合计** | **30** | **全部通过** |

---

## 八、关键交付建议

1. **跨语言保留策略**：核心算法的单元测试用例应单独存放，作为"跨阶段资产"
   随纯算法资产库长期保留。当算法翻译为 TS/C#/C++ 后，用同一组测试用例回归。
2. **确定性是前提**：只有确定性计算才能跨语言回归。`calculate_damage` 用 MD5
   替代 random 暴击判定是正确做法，翻译到 TS/C#/C++ 时保持同样逻辑。
3. **阶段边界护栏**：`StageBoundaryGuard` 是"阶段不对=错"的执行者，新增模块
   时必须登记其适用阶段，防止 Cocos 阶段用 UE 架构（过度设计）。
4. **协议向后兼容**：协议字段只增不改，删字段必被检出。这是跨引擎/跨语言
   平滑迁移的底线。
5. **回归基线扩展**：后续每次算法重构或新增模块，应在 `test_pure_algorithm_cross_lang.sh`
   中追加对应测试用例，保持回归基线持续覆盖。

---

*全程机制驱动：task_scheduler 派发 → DepartmentAgent 承接 → CollaborationWorkbench 组内分工 → REVIEW_RESULT 上报。*
