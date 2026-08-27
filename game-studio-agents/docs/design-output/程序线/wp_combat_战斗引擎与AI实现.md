# wp_combat_impl · 战斗引擎/AI 实现方案

- **工作包**：wp_combat_impl 战斗引擎/AI 实现
- **部门**：程序线
- **主责角色**：engine_dev + ai_programmer
- **模块**：combat
- **产出物类型**：tech_doc（技术实现方案）

## 一、战斗引擎实现（engine_dev）

**物理与碰撞**：
- 2.5D 空间定位 + 碰撞检测（AABB + 空间哈希）
- 命中判定：胶囊体扫描 + 精确受击盒检测
- 打击感：命中停顿（hitstop）、受击位移、屏幕震动

**战斗帧逻辑**：
- 固定 60Hz 战斗 tick，输入采样与逻辑帧分离
- 技能系统：技能配置驱动（CD/消耗/范围/判定帧）
- 状态机：角色状态（空闲/移动/攻击/受击/闪避/格挡）

**性能目标**：
- 同屏 30 敌人 + 10 玩家无掉帧
- 技能特效粒子数量可控（LOD 降级）
- 战斗场景内存 < 200MB

## 二、NPC AI 实现（ai_programmer）

**行为树框架**：
- 自定义行为树编辑器（可视化配置 + 代码扩展节点）
- 节点类型：选择/序列/并行/条件/动作/装饰器
- 运行时：AI tick 频率 10Hz（低频开销），战斗 AI 30Hz（高频响应）

**AI 行为模式**：

```python
# 战斗 AI 行为树示例（伪代码）
def build_combat_ai():
    return Selector([
        # 1. 优先：闪避/格挡
        Sequence([Condition("incoming_attack"), Action("dodge")]),
        # 2. 其次：技能释放
        Sequence([Condition("skill_ready"), Action("cast_skill")]),
        # 3. 默认：追击/攻击
        Sequence([Condition("in_range"), Action("attack")]),
        Action("approach")
    ])
```

**难度自适应**：
- DPS 监控器：实时统计玩家 DPS，调整 AI 攻击频率（±20% 范围内）
- 生存压力调节：玩家连续死亡 2 次 → AI 降低弹反难度窗口 15%
- BOSS 多阶段：每阶段切换行为树 + 技能组，阶段过渡有演出

## 三、战斗网络同步

- 客户端预测 + 服务端权威（Server Authority）
- 快照同步：每 tick 同步角色位置/状态，插值渲染
- 战斗重放：完整战斗记录可回放（调试/审计）

## 四、验证指标

- 战斗 tick 延迟 < 50ms（P99）
- AI 决策延迟 < 16ms
- 战斗同步带宽 < 20KB/s/玩家
- 同屏战斗 30 敌人不掉帧
