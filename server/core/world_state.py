"""
world_state.py - 服务端权威世界状态管理器

核心原则：所有玩法决策在服务端计算（伤害/掉落/任务进度），
客户端只负责表现层 + 输入采集。服务端权威时间戳保证多端同步。

对齐 wp_server 设计文档中的 WorldStateSync。
"""

import hashlib
import time
from typing import Any, Dict, List, Optional


class WorldState:
    """服务端权威世界状态"""

    SYNC_INTERVAL_MS = 100  # 100ms 同步间隔
    SNAPSHOT_SIZE = 2048    # 快照最大字节数

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
            new_entity["x"] = action.get("x", cur.get("x", 0))
            new_entity["z"] = action.get("z", cur.get("z", 0))
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

        return deltas
