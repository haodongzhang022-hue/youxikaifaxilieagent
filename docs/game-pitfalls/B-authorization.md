# B 权限与越权坑点

> 危害等级：🔴 越权 = 任意玩家可操作他人资源（打别人的怪、花别人的钱、改别人的档）。
> 是服务端最大的安全黑洞之一。**每个操作入口都必须校验「调用者 == 资源所有者」。**

---

## <a name="B1"></a>B1 操作未校验调用者与资源所有者（IDOR / 越权）

- **现象**：`process_attack(combat_id, ...)` 只按 `combat_id` 取会话，未校验
  `session.player_id == 调用者 player_id`。任意玩家拿到别人的 `combat_id` 即可
  攻击其会话并领取奖励；同样可调 `end_combat` 结束他人战斗。
- **危害**：越权攻击/领奖/销毁他人战斗；配合刷钱可扩散。
- **复现**：A 玩家 start_combat，B 玩家用 A 的 combat_id 调 process_attack。
- **检测**：对每个 `combat_id/entity_id/quest_id` 的操作，确认有 owner 校验。
- **修复**：`process_attack/end_combat` 入口校验 `session.player_id == caller`。
- **本仓现状**：✅ **已命中 C2**。`CombatService.process_attack` 无 owner 校验。**必须修复。**

---

## B2 客户端可指定他人 player_id（身份伪造）

- **现象**：接口接受客户端传入 `player_id`/`to_player` 而不强制绑定登录态。
- **危害**：可冒充他人领取/操作。
- **检测**：确认所有 player 相关参数都来自服务端 session，而非客户端可改字段。
- **本仓现状**：⚠️ 网关校验了 `player_id == verify_session(token)`，✅ 大部分已挡；
  但 `_handle_economy` 中 `to_player` 来自客户端（转账目标，允许，正常），
  from 已绑定 session，✅。

---

## B3 管理/调试接口未隔离（后门泄漏）

- **现象**：GM/调试/充值接口未加独立鉴权，随主入口暴露。
- **危害**：被黑后直接改数据。
- **检测**：确认所有管理接口有独立更高权限鉴权 + 审计。
- **本仓现状**：✅ 无独立管理入口暴露。

---

## B4 会话令牌可被复用/未过期

- **现象**：token 校验失败返回 session_expired 但未强制下线/轮换；token 无过期时间。
- **危害**：token 泄露长期有效。
- **修复**：token 带过期 + 刷新轮换 + 异地登录踢下线。
- **本仓现状**：✅ 有 refresh_session 轮换机制，良好。

---

## B5 跨端共享会话安全边界

- **现象**：多端绑定后，任一端的会话泄漏都等于全端泄漏；未做端级风险隔离。
- **危害**：一端被黑，全端沦陷。
- **修复**：绑定端提供独立 token / 设备指纹 / 风险标记。
- **本仓现状**：⚠️ 有 bind_platform 多端绑定，但未做端级 token 隔离与设备风控。

---
