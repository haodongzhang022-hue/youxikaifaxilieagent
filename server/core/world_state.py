"""
world_state.py - 服务端权威世界状态管理器

核心原则：所有玩法决策在服务端计算（伤害/掉落/任务进度），
客户端只负责表现层 + 输入采集。服务端权威时间戳保证多端同步。

对齐 wp_server 设计文档中的 WorldStateSync。
"""

import hashlib
import json
import time
from typing import Any, Dict, List, Optional


class WorldState:
    """服务端权威世界状态"""

    SYNC_INTERVAL_MS = 100  # 100ms 同步间隔
    SNAPSHOT_SIZE = 2048    # 快照最大字节数
    MAX_MOVE_SPEED = 100    # W6: 每 tick 最大移动速度（防瞬移）
    MAX_COLLECT_AMOUNT = 10  # W2: 单次采集数量上限
    VALID_RESOURCE_TYPES = frozenset({"wood", "stone", "iron", "herb", "gold"})  # W2: 白名单

    def __init__(self):
        self._world_state: Dict[str, Dict] = {}  # entity_id -> entity data
        self._deltas: List[Dict] = []             # 增量变更列表
        self._version: int = 0                    # 版本号（乐观锁）
        self._server_time: int = int(time.time() * 1000)

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
            return True
        return False

    def apply_action(self, player_id: str, action: Dict) -> Dict:
        """
        应用玩家动作（服务端权威计算）。

        返回: {'status': 'accepted'|'rejected', 'deltas': [...], 'reason': str}
        W2 修复：单条 rejected delta 应导致整体 rejected。
        """
        # 1. 校验合法性（规则检查）
        if not self._validate_action(action):
            return {
                "status": "rejected",
                "reason": "action violates game rules",
                "deltas": [],
            }

        # 2. 更新世界状态
        deltas = self._compute_delta(player_id, action)

        # W2: 如果存在 rejected delta，整体 rejected
        for d in deltas:
            if d.get("op") == "rejected":
                return {
                    "status": "rejected",
                    "reason": d.get("reason", "action rejected"),
                    "deltas": deltas,
                }

        # 3. 记录增量
        for d in deltas:
            self._deltas.append(d)

        self._version += len(deltas)

        # 4. 返回结果
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
    def _validate_action(self, action: Dict) -> bool:
        """动作合法性校验"""
        action_type = action.get("type", "")
        if action_type not in ("move", "attack", "use_item", "collect", "interact"):
            return False
        # 位置范围校验
        x, z = action.get("x", 0), action.get("z", 0)
        if abs(x) > 10000 or abs(z) > 10000:
            return False
        return True

    def _compute_delta(self, player_id: str, action: Dict) -> List[Dict]:
        """计算动作引起的状态变更"""
        deltas = []
        entity_id = f"player_{player_id}"
        cur = self._world_state.get(entity_id, {
            "player_id": player_id,
            "x": 0, "z": 0, "hp": 100, "max_hp": 100,
            "inventory": {},
        })

        # 根据动作类型更新
        action_type = action.get("type", "")
        if action_type == "move":
            new_entity = dict(cur)
            old_x = cur.get("x", 0)
            old_z = cur.get("z", 0)
            new_x = action.get("x", old_x)
            new_z = action.get("z", old_z)
            # W6: 速度校验 - 单 tick 移动距离不能超过 MAX_MOVE_SPEED
            dist = abs(new_x - old_x) + abs(new_z - old_z)
            if dist > self.MAX_MOVE_SPEED:
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"move exceeds max speed ({self.MAX_MOVE_SPEED})",
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
            # 采集资源，服务端权威计算
            resource = action.get("resource", {})
            rtype = resource.get("type", "wood")
            amount = resource.get("amount", 1)
            # W2: 资源类型白名单 + 数量上限
            if rtype not in self.VALID_RESOURCE_TYPES:
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"invalid resource type '{rtype}'",
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
                return deltas
            if amount <= 0 or amount > self.MAX_COLLECT_AMOUNT:
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"invalid collect amount {amount}",
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
                return deltas
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
        elif action_type in ("attack", "interact"):
            # W1 修复：attack/interact 加服务端权威结算逻辑
            new_entity = dict(cur)
            target = action.get("target", "")
            target_entity = self._world_state.get(target)
            if target_entity is None:
                deltas.append({
                    "op": "rejected",
                    "entity_id": entity_id,
                    "reason": f"target '{target}' not found",
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
                return deltas
            # 攻击：对目标造成伤害（服务端权威）
            if action_type == "attack":
                dmg = action.get("damage", 5)
                # 攻击伤害上限校验
                if dmg <= 0 or dmg > 100:
                    deltas.append({
                        "op": "rejected",
                        "entity_id": entity_id,
                        "reason": f"invalid damage {dmg}",
                        "version": self._version + 1,
                        "timestamp": self.server_time,
                    })
                    return deltas
                target_new = dict(target_entity)
                hp = target_new.get("hp", 100) - dmg
                target_new["hp"] = max(0, hp)
                self._world_state[target] = target_new
                deltas.append({
                    "op": "update",
                    "entity_id": target,
                    "field": "hp",
                    "value": target_new["hp"],
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })
            else:
                # interact：交互标记
                new_entity["last_interact"] = {
                    "target": target,
                    "ts": self.server_time,
                }
                self._world_state[entity_id] = new_entity
                deltas.append({
                    "op": "update",
                    "entity_id": entity_id,
                    "field": "last_interact",
                    "value": new_entity["last_interact"],
                    "version": self._version + 1,
                    "timestamp": self.server_time,
                })

        return deltas

    # W7: 持久化支持
    def persist(self, filepath: str) -> bool:
        """持久化世界状态到磁盘"""
        try:
            data = {
                'world_state': self._world_state,
                'version': self._version,
            }
            with open(filepath, 'w') as f:
                json.dump(data, f)
            return True
        except Exception:
            return False

    def load(self, filepath: str) -> bool:
        """从磁盘加载世界状态"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            self._world_state = data.get('world_state', {})
            self._version = data.get('version', 0)
            return True
        except Exception:
            return False
