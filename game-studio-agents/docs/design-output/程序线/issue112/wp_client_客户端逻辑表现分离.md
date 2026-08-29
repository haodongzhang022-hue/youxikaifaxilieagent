# wp_client · 客户端逻辑/表现分离+纯逻辑类库下沉

- **工作包**：wp_client 客户端逻辑/表现分离+纯逻辑类库下沉
- **部门**：程序线
- **主责角色**：client_dev + cocos_dev
- **模块**：client
- **产出物类型**：tech_impl（技术实现文档 + 代码）
- **场景**：Issue #112「游戏向架构师的开发」——客户端需逻辑/表现分离

---

## 一、核心实现：纯逻辑类库（client_core/pure_logic.py）

### 1.1 GameState（纯数据结构）

```python
@dataclass
class GameState:
    player_id: str = ""
    hp: int = 100
    max_hp: int = 100
    mp: int = 50
    max_mp: int = 50
    level: int = 1
    exp: int = 0
    position_x: float = 0.0
    position_z: float = 0.0
    inventory: Dict[str, int] = ...
    buffs: List[str] = ...
```

**不依赖任何引擎 API**，可跨语言翻译为 TS/C#/C++。

### 1.2 PureLogicEngine（核心逻辑引擎）

| 操作 | 逻辑 | 表现层事件 |
|------|------|-----------|
| take_damage | 扣血 | damage（播放受击动画） |
| heal | 回血 | heal（播放治疗特效） |
| add_exp | 加经验/升级 | exp_gain + level_up |
| add_item | 添加道具 | item_gain（更新背包 UI） |
| use_item | 使用道具 | item_use（使用动画） |
| move | 移动 | move（更新节点位置） |

### 1.3 确定性计算（跨语言翻译基础）

```python
@staticmethod
def calculate_damage(base_atk, base_def, skill_multiplier, crit_chance, crit_multiplier):
    # 确定性 hash 判定暴击（而非随机数）
    # 同输入 → 同输出 → 跨语言测试可验证
```

---

## 二、核心实现：表现层分离（IPresentationAdapter）

### 2.1 接口定义

```python
class IPresentationAdapter:
    def init(self) -> bool: ...
    def destroy(self) -> None: ...
    def on_logic_event(self, event: LogicEvent) -> None: ...
    def poll_input(self) -> Dict: ...
    def render_state(self, state: GameState) -> None: ...
```

### 2.2 Cocos Presenter（CocosCreatorAdapter）

**事件 → Cocos 操作映射**：

| 逻辑事件 | Cocos 操作 |
|---------|-----------|
| damage | 播放受击动画 + 飘血数字 |
| heal | 播放治疗特效 + 绿色飘字 |
| level_up | 播放升级特效 + 全屏闪光 |
| exp_gain | 更新经验条 UI |
| item_gain | 更新背包 UI |
| item_use | 使用道具动画 |
| move | 更新角色节点位置 |

---

## 三、架构分层

```
┌──────────────────────────────────────────┐
│   表现层（Cocos/Unity/UE 各引擎实现）      │
│   · CocosPresenter（本产出）              │
│   · 渲染/动画/特效/音频/输入采集          │
├──────────────────────────────────────────┤
│   适配接口（IPresentationAdapter）         │
│   · 事件订阅 · 输入采集 · 状态渲染        │
├──────────────────────────────────────────┤
│   纯逻辑层（PureLogicEngine）             │
│   · 状态管理 · 战斗结算 · 道具管理        │
│   · 确定性计算 · 事件生成                 │
└──────────────────────────────────────────┘
```

**切换引擎时只替换表现层，逻辑层代码零改动或仅需语言翻译。**

---

## 四、组内分工记录（group_audit）

| 子任务 | 承接角色 | 产出说明 |
|--------|---------|---------|
| 客户端纯逻辑类库设计与逻辑/表现分离架构落地 | client_dev | pure_logic.py + cocos_presenter.py |
| Cocos Creator 接入纯逻辑类库 + 表现层分离验证 | cocos_dev | 事件→Cocos操作映射 + 渲染验证 |

> 分工经协作工作台（CollaborationWorkbench）`delegate` 记录，全程留痕可审计。

---

## 五、测试验证

```bash
bash game-studio-agents/tests/test_client_core.sh
# 12/12 通过 🟢
```

### 测试覆盖

| 验证项 | 结果 |
|--------|:---:|
| 伤害/治疗计算正确 | ✅ |
| 经验/升级逻辑正确 | ✅ |
| 道具管理正确 | ✅ |
| 确定性伤害计算（跨语言基础） | ✅ |
| 事件系统生成正确 | ✅ |
| 状态序列化（跨语言传输） | ✅ |
| Cocos 表现层初始化 | ✅ |
| 逻辑事件→表现层映射 | ✅ |
| 升级特效/道具渲染触发 | ✅ |
| 状态渲染触发 | ✅ |

---

## 六、验收通过后解锁下游

- **美术线 wp_art_direction**：表现层边界设计
- **测试线 wp_testing**：纯算法单元测试用例跨语言保留
