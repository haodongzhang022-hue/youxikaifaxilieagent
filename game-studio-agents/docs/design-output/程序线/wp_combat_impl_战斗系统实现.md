# wp_combat_impl · 战斗系统实现

- **工作包**：wp_combat_impl 战斗机制/技能/NPC AI 实现
- **部门**：程序线
- **主责角色**：engine_dev（战斗框架）+ ai_programmer（NPC AI）+ client_dev（客户端手感）
- **模块**：combat_impl
- **产出物类型**：code（技术实现文档 + 代码骨架）

## 一、战斗框架实现（client_dev + engine_dev）

### 1.1 实时动作战斗框架
- **输入处理**：InputBuffer（前摇 ≤0.15s，后摇可取消），复用 `agent_core.BaseAgent` 的事件驱动消息路由
- **动作状态机**：Idle → Move → Attack(1/2/3连段) → HeavyAttack → Dodge(i-frames 0.3s) → Block(parry window 0.2s)
- **连段系统**：普攻 3 连 → 重击 → 派生技，通过 ComboQueue 管理

### 1.2 资源系统
- **体力**：行动消耗，自然恢复 + 战斗奖励
- **星核能量**：技能资源，随攻击命中/受击积累
- **怒气**：大招充能，60~90s 攒满（高风险场景加速）

### 1.3 战斗反馈
- 命中停顿、受击反馈、震屏、打击特效（对接客户端渲染管线）
- 反馈强度按 hitStop 时长 / shakeAmount / particleDensity 参数化

## 二、技能系统实现（server_dev + engine_dev）

| 职业 | 定位 | 核心机制实现 | 技能风格 |
|------|------|------------|---------|
| 守望者 | 均衡输出 | 星械变形（WeaponTransform）| 远近结合 |
| 星匠 | 坦克/承伤 | 护盾/嘲讽（ShieldSystem）| 大开大合 |
| 织雾者 | 治疗/辅助 | 治疗链/增益（HealChain）| 柔性支援 |
| 虚空猎手 | 刺客/爆发 | 隐身/背刺（StealthSystem）| 高速连击 |

### 技能数值锚点（对齐 wp_numeric_model）
- 单体技能 DPS ≈ 1.0 基准；范围技能降单体伤害换取覆盖
- 控制技能时长 ≤ 2s，目标减益存在递减机制
- 大招充能：普通战斗 60~90s 攒满

## 三、NPC AI 行为实现（ai_programmer）

### 3.1 行为树框架（BehaviorTree）
- **普通怪**：Patrol → Chase → Attack → Return
- **精英怪**：SkillPredict → Burst → WeakWindow（可反打）
- **BOSS**：Multi-phase AI（每阶段切换行为树 + 技能组）

### 3.2 难度自适应
- 根据玩家 DPS/生存时长动态微调攻击频率与技能释放
- 死亡重试后降低弹反难度（惩罚递减），避免挫败

## 四、实现验证

### 4.1 战斗框架测试
- 攻击前摇 ≤ 0.15s 验证
- 闪避无敌帧 0.3s 验证
- 连段系统正确性（3连 → 重击 → 派生）

### 4.2 数值平衡验证
- 各职业理论 DPS 差异 ≤ 10%
- 战斗时长锚定：普通战 30~60s，精英战 60~120s，BOSS 战 3~5 分钟

> 产出：程序线引擎/客户端/AI 程序员承接，经协作工作台 @分工 拆派战斗框架/技能/AI 子任务。
