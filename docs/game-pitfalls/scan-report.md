# 服务端坑点扫描报告（ISSUE #90 落点）

> 基于 `docs/game-pitfalls/` 经验库，对 `server/` 逐项扫描。
> 状态：🔴=必须修复  🟠=建议修复  ✅=合规
> 更新：✅ **C1/C2/C3 + W1-W7 已全部修复落地**（对应 PR 服务端安全修复）

---

## ✅ 已修复（3 项，C1/C2/C3）

| 编号 | 位置 | 问题 | 修复状态 |
|------|------|------|:----:|
| C1 | `server/core/combat_service.py` `credit/debit/transfer` | 负数/零/字符串金额反向入账刷钱 | ✅ 已校验 amount>0 + 类型校验 |
| C2 | `server/core/combat_service.py` `process_attack` | 未校验 `session.player_id==caller`，越权攻击领奖 | ✅ 已增加 caller 身份校验 |
| C3 | `server/core/combat_service.py` `_roll_loot` | 自实现掉落未调 `cabi.roll_loot()`，跨端不一致 | ✅ 已走 `cabi.roll_loot()` 对齐 |

## ✅ 已修复（扫描新增，W1-W7）

| 编号 | 位置 | 问题 | 修复状态 |
|------|------|------|:----:|
| W1 | `gateway.py`/`combat_service.py` | 信任客户端 `attack_power` 无上限 | ✅ 服务端归一 + MAX_ATTACK_POWER 约束 |
| W2 | `world_state.py` `collect` | 资源类型/数量无白名单无上限 | ✅ 白名单 + MAX_COLLECT_AMOUNT 上限 |
| W3 | `gateway.py` `_handle_quest` | 任务进度客户端上报，可刷完成 | ✅ 单调校验 + 范围校验 |
| W4 | `combat_service.py` `transfer` | 无 `to==from` 校验、无单笔上限 | ✅ from!=to + MAX_TRANSFER_AMOUNT |
| W5 | `combat_service.py`/`gateway.py` | 战斗发奖无幂等键，可重复领奖 | ✅ 幂等键 + rewarded_combats 防重 |
| W6 | `world_state.py` `move` | 只查范围不查速度，可瞬移 | ✅ MAX_MOVE_SPEED 校验 |
| W7 | 全部服务 | 账本/进度仅内存态，重启即丢 | ✅ 持久化落盘（WorldState/EconomyService） |

## ✅ 额外修复（评审补充）

| 编号 | 位置 | 问题 | 修复状态 |
|------|------|------|:----:|
| DoS | `world_state.py` attack/collect | 字符串/None 类型值触发 TypeError 崩溃 | ✅ isinstance 类型校验 |
| W3' | `combat_service.py` `calc_damage` | base_power 与 atk 复用同一值导致伤害二次方 | ✅ base_power 用固定倍率 |
| 死代码 | `gateway.py` star_core 奖励分支 | `cabi.roll_loot` 不产 star_core，分支不可达 | ✅ 删除死分支 |
| 泄漏 | `combat_service.py` | 战斗胜利后 session 未清理 | ✅ victory 即 pop |

## ✅ 合规项（保留为良好范式）

- 货币用 `int` 记账，无浮点误差（A2）
- 全审计交易流水 `_transactions`（A5）
- 战斗结算用定点数 `cabi.fp_*`（C3）
- 四端 golden hash + `hash_json` 一致性校验（C6）
- 网关校验 session 与 player 绑定（B2）
- token 刷新轮换机制（B4）

---

> 经验库会持续回填：每修复一项、每发现一个新坑，同步更新对应文档。
