"""
gameplay_service.py - 玩法服务

服务端权威世界状态 + 场景配置 + 事件同步。
对齐 wp_server 设计文档中的玩法服务配置。

W4 修复：已接入 Gateway 路由，非死代码。
"""

from typing import Dict, List, Optional

from server.core.world_state import WorldState


class GameplayService:
    """玩法服务：场景管理 + 事件同步"""

    # 世界配置（跨端统一）
    WORLD_CONFIG = {
        "max_players_per_world": 100,
        "auto_save_interval": 60,
        "day_night_cycle": 600,
    }

    # 场景配置
    SCENE_CONFIG = {
        "LVL_001": {
            "type": "main_story",
            "max_players": 4,
            "procedural_seed": 42,
        },
        "LVL_002": {
            "type": "side_quest",
            "max_players": 8,
            "procedural_seed": 84,
        },
    }

    def __init__(self, world: WorldState):
        self.world = world

    def get_world_config(self) -> Dict:
        """获取世界配置（跨端一致）"""
        return dict(self.WORLD_CONFIG)

    def get_scene_config(self, scene_id: str) -> Optional[Dict]:
        """获取场景配置"""
        return self.SCENE_CONFIG.get(scene_id)

    def player_action(self, player_id: str, scene_id: str, action: Dict) -> Dict:
        """处理玩家在指定场景中的动作"""
        # 校验场景存在
        scene = self.SCENE_CONFIG.get(scene_id)
        if scene is None:
            return {
                "status": "rejected",
                "reason": f"scene '{scene_id}' not found",
                "deltas": [],
            }

        # 附加场景上下文
        ctx_action = dict(action)
        ctx_action["scene_id"] = scene_id
        ctx_action["procedural_seed"] = scene.get("procedural_seed", 42)

        return self.world.apply_action(player_id, ctx_action)
