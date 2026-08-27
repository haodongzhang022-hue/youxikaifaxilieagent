# wp_numeric_model_impl · 数值/经济后端实现方案

- **工作包**：wp_numeric_model_impl 数值/经济后端实现
- **部门**：程序线
- **主责角色**：server_dev
- **模块**：numeric_model
- **产出物类型**：tech_doc（技术实现方案）

## 一、经济系统后端实现

**架构设计**：
- 虚拟货币系统：硬通货（星核）/ 软通货（金币）/ 付费货币（晶钻）
- 交易流水表 + 余额快照，保证财务一致性
- 资源产出/消耗规则引擎：配置驱动，热更新不重启

**核心模块**：
- 货币服务：充值/消费/赠送/每日任务奖励
- 交易服务：玩家间交易（防倒卖/防洗钱校验）
- 商店服务：限时/常驻/促销，价格策略配置化

## 二、成长曲线实现

**角色成长**：
- 等级：经验曲线 L1~L60，采用分段函数控制升级节奏
- 装备强化：强化成功概率 + 保底机制（防挫败）
- 技能解锁：等级+任务双条件驱动

**数值模型**：
- 成长公式引擎：支持配置驱动（JSON Schema 校验）
- 参数调优：通过数据埋点实时调整曲线系数
- 平衡性检查：DPS 差异校验（目标 ≤10%）

## 三、数据库设计

```sql
-- 玩家账户表
CREATE TABLE player_account (
  player_id BIGINT PRIMARY KEY,
  currency_hard BIGINT NOT NULL DEFAULT 0,
  currency_soft BIGINT NOT NULL DEFAULT 0,
  currency_premium BIGINT NOT NULL DEFAULT 0,
  level INT NOT NULL DEFAULT 1,
  exp BIGINT NOT NULL DEFAULT 0,
  updated_at TIMESTAMP DEFAULT NOW()
);

-- 交易流水表
CREATE TABLE transaction_log (
  txn_id BIGINT PRIMARY KEY,
  player_id BIGINT NOT NULL,
  txn_type VARCHAR(32) NOT NULL,
  amount BIGINT NOT NULL,
  balance_after BIGINT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  INDEX idx_player_time (player_id, created_at)
);
```

## 四、验证指标

- 交易流水 100% 可追溯
- 余额更新原子性（防并发覆盖）
- 数值热更新延迟 < 5s
- 经济系统可支撑 10000 活跃玩家同时在线
