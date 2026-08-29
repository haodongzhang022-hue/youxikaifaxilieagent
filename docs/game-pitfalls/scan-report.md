# 服务端坑点扫描报告（ISSUE #90 落点）

> 基于 `docs/game-pitfalls/` 经验库，对 `server/` 逐项扫描。
> 状态：🔴=必须修复  🟠=建议修复  ✅=合规

---

## 🔴 必须修复（3 项，C1/C2/C3）

| 编号 | 位置 | 问题 | 对应经验库 |
|------|------|------|-----------|
| C1 | `server/core/combat_service.py` `credit/debit/transfer` | 未校验 `amount<=0`，负数反向入账刷钱 | A1 |
| C2 | `server/core/combat_service.py` `process_attack` | 未校验 `session.player_id==caller`，越权攻击领奖 | B1 |
| C3 | `server/core/combat_service.py` `_roll_loot` | 自实现掉落未调 `cabi.roll_loot()`，跨端不一致 | C1 |

## 🟠 建议修复（扫描新增）

| 编号 | 位置 | 问题 | 对应经验库 |
|------|------|------|-----------|
| W1 | `server/core/gateway.py` `_handle_combat` attack | 信任客户端 `attack_power`，无上限 | E1/G1 |
| W2 | `server/core/world_state.py` `collect` | 资源类型/数量由客户端指定，无白名单无上限 | E2/G1 |
| W3 | `server/core/gateway.py` `_handle_quest` | 任务进度客户端上报，无单调校验，可刷完成 | D3/E4 |
| W4 | `server/core/combat_service.py` `transfer` | 无 `to==from` 校验、无单笔上限、无限流 | A3 |
| W5 | `server/core/combat_service.py` victory 发奖 | 无幂等键，可重复领奖 | A4/D2 |
| W6 | `server/core/world_state.py` move | 只查范围不查速度，可瞬移 | E3 |
| W7 | 全部服务 | 账本/进度仅内存态，重启即丢 | F1 |

## ✅ 合规项（作为良好范式保留）

- 货币用 `int` 记账，无浮点误差（A2）
- 全审计交易流水 `_transactions`（A5）
- 战斗结算用定点数 `cabi.fp_*`（C3）
- 四端 golden hash + `hash_json` 一致性校验（C6）
- 网关校验 session 与 player 绑定（B2）
- token 刷新轮换机制（B4）

---

## 修复优先级建议

1. **先堵刷钱/越权口子**：C1（负数校验）、C2（owner 校验）—— 这是最容易被黑/被刷的点。
2. **再统一一致性**：C3（掉落走 `cabi.roll_loot`）—— 违反核心架构约束。
3. **再收紧输入**：W1/W2/W3 信任客户端数值 → 改服务端权威计算。
4. **再加固健壮性**：W4-W7。

> 经验库会持续回填：每修复一项、每发现一个新坑，同步更新对应文档。
