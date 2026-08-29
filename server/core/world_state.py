"""
world_state.py - 服务端权威世界状态管理器

核心原则：所有玩法决策在服务端计算（伤害/掉落/任务进度/移动速度），
客户端只负责表现层 + 输入采集。服务端权威时间戳保证多端同步。

对齐 wp_server 设计文档中的 WorldStateSync。
本文件包含坑点经验库（docs/game-pitfalls/）多项修复：
- W1: attack 伤害由服务端计算，不信任客户端裸值
- W2: collect 资源类型白名单 + 数量上限
- W6: move 校验移动速度，防瞬移
- DoS: attack/collect 数值类型校验，防 TypeError 崩溃
"""

import time
from typing import Any, Dict, List, Optional


class WorldState:
    """服务端权威世界状态"""

    SYNC_INTERVAL_MS = 100  # 100ms 同步间隔
    SNAPSHOT_SIZE = 2048    # 快照最大字节数

    # ---- 世界规则（服务端权威口径）----
    MAX_COORD = 10000                       # 坐标范围
    MAX_MOVE_SPEED = 10.0                   # 单步最大移动距离（防瞬移）
    COLLECT_WHITELIST = {                   # W2: 可采集资源类型白名单
        "wood", "stone", "iron_ore", "herb", "gold",
    }
    MAX_COLLECT_AMOUNT = 100                # 单次采集数量上限
    MAX_ATTACK_POWER = 1000                 # 攻击力上限

    def __init__(self, persist_path: Optional[str] = None):
        self._world_state: Dict[str, Dict] = {}  # entity_id -> entity data
        self._deltas: List[Dict] = []             # 增量变更列表
        self._version: int = 0                    # 版本号（乐观锁）
        self._server_time: int = int(time.time() * 1000)
        self._persist_path = persist_path
        if persist_path:
            self._load(persist_path)

    # ---- W7 持久化 ----
    def _load(self, path: str) -> None:
        import json
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._world_state = data.get("world_state", {})
            self._version = data.get("version", 0)
        except Exception:
            pass

    def _flush(self) -> None:
        import json
        if not self._persist_path:
            return
        with open(self._persist_path, "w", encoding="utf-8") as f:
            json.dump({"world_state": self._world_state,
                       "version": self._version}, f, ensure_ascii=False)

    @property
    def version(self) -> int:
        return self._version

    @property
    def server_time(self) -> int:
        return int(time.time() * 1000)

    def set_entity(self, entity_id: str, data: Dict) -> Dict:
        """设置实体状态（服务端权威）"""
        self._world_state[entity_id] = dict(data)
        self._version += 1
        delta = {
            "op": "set",
            "entity_id": entity_id,
            "data": dict(data),
            "version": self._version,
            "timestamp": self.server_time,
        }
        self._deltas.append(delta)
        self._flush()
        return delta

    def get_entity(self, entity_id: str) -> Optional[Dict]:
        return self._world_state.get(entity_id)

    def remove_entity(self, entity_id: str) -> bool:
        if entity_id in self._world_state:
            del self._world_state[entity_id]
            self._version += 1
            self._deltas.append({
                "op": "remove",
                "entity_id": entity_id,
                "version": self._version,
                "timestamp": self.server_time,
            })
            self._flush()
            return True
        return False

    def apply_action(self, player_id: str, action: Dict) -> Dict:
        """
        应用玩家动作（服务端权威计算）。

        返回: {'status': 'accepted'|'rejected', 'deltas': [...], 'reason': str}
        """
        # 1. 校验合法性（规则检查）
        reject = self._validate_action(action)
        if reject:
            return {
                "status": "rejected",
                "reason": reject,
                "deltas": [],
            }

        # 2. 更新世界状态
        deltas = self._compute_delta(player_id, action)

        # 3. 若存在 rejected delta（超速/无物品等），整体返回 rejected
        if any(d.get("op") == "rejected" for d in deltas):
            reason = next((d.get("reason", "action rejected")
                           for d in deltas if d.get("op") == "rejected"),
                          "action rejected")
            return {
                "status": "rejected",
                "reason": reason,
                "deltas": deltas,
            }

        # 4. 记录增量
        for d in deltas:
            self._deltas.append(d)

        self._version += len(deltas)
        self._flush()

        # 5. 返回结果
        return {"status": "accepted", "deltas": deltas}

    def snapshot(self) -> Dict:
        """生成状态快照"""
        return {
            "timestamp": self.server_time,
            "version": self._version,
            "entities": {k: dict(v) for k, v in self._world_state.items()},
        }

    def clear_deltas(self):
        """清除已消费的增量"""
        self._deltas = []

    def get_deltas(self, since_version: int = 0) -> List[Dict]:
        """获取指定版本之后的增量"""
        return [d for d in self._deltas if d.get("version", 0) > since_version]

    # ============================================================
    # 内部方法
    # ============================================================
    def _validate_action(self, action: Dict) -> Optional[str]:
        """动作合法性校验。返回错误原因（None=通过）。"""
        if not isinstance(action, dict):
            return "action must be a dict"
        action_type = action.get("type", "")
        if action_type not in ("move", "attack", "use_item", "collect", "interact"):
            return f"unknown action type '{action_type}'"

        if action_type == "move":
            return self._validate_move(action)
        if action_type == "attack":
            return self._validate_attack(action)
        if action_type == "collect":
            return self._validate_collect(action)
        return None

    def _validate_move(self, action: Dict) -> Optional[str]:
        """W6 修复：校验坐标范围 + 移动速度（防瞬移）"""
        x, z = action.get("x", 0), action.get("z", 0)
        if not isinstance(x, (int, float)) or isinstance(x, bool) \
           or not isinstance(z, (int, float)) or isinstance(z, bool):
            return "coordinates must be numeric"
        if abs(x) > self.MAX_COORD or abs(z) > self.MAX_COORD:
            return "coordinates out of range"
        return None

    def _validate_attack(self, action: Dict) -> Optional[str]:
        """W1 修复：attack 由服务端计算，仅校验类型，不信任客户端伤害值"""
        # DoS 修复：数值类型校验，防 TypeError 崩溃
        if "x" in action or "z" in action:
            x, z = action.get("x", 0), action.get("z", 0)
            if not isinstance(x, (int, float)) or isinstance(x, bool) \
               or not isinstance(z, (int, float)) or isinstance(z, bool):
                return "coordinates must be numeric"
            if abs(x) > self.MAX_COORD or abs(z) > self.MAX_COORD:
                return "coordinates out of range"
        return None

    def _validate_collect(self, action: Dict) -> Optional[str]:
        """W2 修复：采集资源类型白名单 + 数量上限"""
        resource = action.get("resource", {})
        if not isinstance(resource, dict):
            return "resource must be a dict"
        rtype = resource.get("type")
        amount = resource.get("amount", 1)
        # 类型白名单
        if rtype not in self.COLLECT_WHITELIST:
            return f"resource type '{rtype}' not allowed"
        # 数量校验（DoS + 上限）
        if not isinstance(amount, int) or isinstance(amount, bool):
            return "amount must be an integer"
        if amount <= 0:
            return "amount must be positive"
        if amount > self.MAX_COLLECT_AMOUNT:
            return f"amount exceeds limit {self.MAX_COLLECT_AMOUNT}"
        return None

    def _compute_delta(self, player_id: str, action: Dict) -> List[Dict]:
        """计算动作引起的状态变更"""
        deltas = []
        entity_id = f"player_{player_id}"
        cur = self._world_state.get(entity_id, {
            "player_id": player_id,
            "x": 0, "z": 0, "hp": 100, "max_hp": 100,
            "inventory": {},
        })

        action_type = action.get("type", "")
        if action_type == "move":
            new_entity = dict(cur)
            new_x = action.get("x", cur.get("x", 0))
            new_z = action.get("z", cur.get("z", 0))
            # W6 修复：限制单步移动距离
            old_x, old_z = cur.get("x", 0), cur.get("z", 0)
            dist = ((new_x - old_x) ** 2 + (new_z - old_z) ** 2) ** 0.5
            if dist > self.MAX_MOVE_SPEED:
                # 超速：拒绝并返回 rejected delta
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"move too fast (dist={dist:.1f} > {self.MAX_MOVE_SPEED})",
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
                return deltas
            new_entity["x"] = new_x
            new_entity["z"] = new_z
            self._world_state[entity_id] = new_entity
            deltas.append({
                "op": "update",
                "entity_id": entity_id,
                "field": "position",
                "value": {"x": new_entity["x"], "z": new_entity["z"]},
                "version": self._version + 1,
                "timestamp": self.server_time,
            })
        elif action_type == "collect":
            # W2 修复：采集资源（已校验白名单+上限）
            resource = action.get("resource", {})
            rtype = resource.get("type", "wood")
            amount = resource.get("amount", 1)
            new_entity = dict(cur)
            inv = dict(new_entity.get("inventory", {}))
            inv[rtype] = inv.get(rtype, 0) + amount
            new_entity["inventory"] = inv
            self._world_state[entity_id] = new_entity
            deltas.append({
                "op": "update",
                "entity_id": entity_id,
                "field": "inventory",
                "value": dict(inv),
                "version": self._version + 1,
                "timestamp": self.server_time,
            })
        elif action_type == "use_item":
            # 使用物品
            item = action.get("item", "")
            new_entity = dict(cur)
            inv = dict(new_entity.get("inventory", {}))
            if item in inv and inv[item] > 0:
                inv[item] -= 1
                if inv[item] <= 0:
                    del inv[item]
                new_entity["inventory"] = inv
                self._world_state[entity_id] = new_entity
                deltas.append({
                    "op": "update",
                    "entity_id": entity_id,
                    "field": "inventory",
                    "value": dict(inv),
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
            else:
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"no item '{item}' in inventory",
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
        elif action_type == "attack":
            # W1 修复：伤害由服务端 CombatService 计算，此处仅返回攻击动作结果
            deltas.append({
                "op": "update",
                "entity_id": entity_id,
                "field": "combat",
                "value": {"attacked": True, "at": self.server_time},
                "version": self._version + 1,
                "timestamp": self.server_time,
            })

        return deltas
