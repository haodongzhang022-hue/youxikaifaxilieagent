# ============================================================
# 游戏向架构师团队 · 端到端演示
# 说明：用游戏向架构师团队完成一个游戏功能框架的开发（作为测试）。
# 流程：游戏·架构·总师(架构) → 游戏·制作·经理(派活) → 策划(设计)
#       → 程序(实现) → 测试(验收) → 游戏·架构·总师助理(阶段边界审查/阶段不对就算错)，
#       全程共享记忆(只增不改只追加)。
# 同时演示"条件触发"：数值失衡→游戏·数值策划；引擎阶段越界→游戏·架构·总师助理纠偏。
# 语言: Python 3 (可运行, 零依赖)
# ============================================================
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from shared_memory import SharedMemory


# ============================================================
# 一、游戏向架构师团队角色（轻量人设，演示协作）
# ============================================================
class GameRole:
    """游戏向团队角色基类"""
    def __init__(self, name: str, space: str, memory: SharedMemory):
        self.name = name
        self.space = space
        self.memory = memory

    def act(self, task: str) -> dict:
        raise NotImplementedError


class GameArchitect(GameRole):
    """游戏·架构·总师：游戏向架构八步"""
    def act(self, task: str) -> dict:
        steps = ["调研品类", "玩法→系统→数值→关卡→经济拓扑", "可行性(引擎/性能/手感)",
                 "里程碑方案", "分工协作规则", "进度对齐", "索引建立", "汇报复盘"]
        arch = {
            "玩法": "回合制RPG",
            "系统": ["背包", "装备", "战斗", "任务"],
            "数值": "成长曲线v1",
            "关卡": "主线1-5",
            "经济": "金币/材料循环v1",
            "引擎": "Godot 4",
            "主线": "背包→装备→战斗→任务",
        }
        # 写入共享记忆（content 二次整理）
        self.memory.add_record(self.space, "content",
                               {"类型": "顶层架构", "架构": arch, "架构八步": steps},
                               self.name)
        print(f"[游戏·架构·总师] 完成游戏系统顶层架构，写入共享记忆")
        return {"arch": arch, "steps": steps}


class GameProducer(GameRole):
    """游戏·制作·经理：里程碑 + DAG 派活"""
    def act(self, task: str, arch: dict) -> dict:
        plan = {
            "milestone": ["M1玩法原型", "M2垂直切片", "M3软封", "M4硬封"],
            "dag": {"架构": ["策划"], "策划": ["程序", "美术"], "程序+美术": ["测试"]},
            "fractal": "按功能小组并行：背包组/战斗组/任务组",
        }
        self.memory.add_record(self.space, "task",
                               {"类型": "里程碑计划", "计划": plan},
                               self.name)
        print(f"[游戏·制作·经理] 排定里程碑 + DAG 派活 + 分形小组并行")
        return plan


class GameDesigner(GameRole):
    """游戏·策划·主管：承接架构，出系统设计"""
    def act(self, task: str, arch: dict) -> dict:
        design = {
            "背包": "容量20格,堆叠99",
            "战斗": "回合制,技能CD",
            "任务": "主线+支线",
        }
        # 写入共享记忆（content）
        rec = self.memory.add_record(self.space, "content",
                                     {"类型": "系统设计", "设计": design}, self.name)
        print(f"[游戏·策划·主管] 完成系统设计，写入共享记忆 ({rec.mem_id})")
        return design


class GameProgrammer(GameRole):
    """游戏·程序·主管：实现 + 发现平衡问题触发数值策划"""
    def act(self, task: str, design: dict) -> dict:
        # 程序实现
        impl = {"背包": "backpack.gd", "战斗": "combat.gd"}
        self.memory.add_record(self.space, "task",
                               {"类型": "实现", "代码": impl, "状态": "自测通过"}, self.name)
        print(f"[游戏·程序·主管] 实现 {list(impl.values())}，自测通过")
        # 条件触发演示：发现战斗数值可能失衡 → 触发游戏·数值策划
        self.memory.add_record(self.space, "task",
                               {"类型": "触发信号", "信号": "战斗数值失衡", "触发": "游戏·数值策划"},
                               self.name)
        print(f"[条件触发] 战斗数值疑似失衡 → 自动引入 游戏·数值策划")
        return impl


class GameBalance(GameRole):
    """游戏·数值策划：被条件触发，做平衡调优"""
    def act(self, task: str) -> dict:
        balance = {"战斗": "技能CD从5s→6s,伤害系数0.9", "依据": "模拟方差检测"}
        self.memory.add_record(self.space, "content",
                               {"类型": "平衡调优", "平衡": balance}, self.name)
        print(f"[游戏·数值策划](被触发) 平衡调优：{balance}")
        return balance


class GameQA(GameRole):
    """游戏·测试·主管：验收门禁"""
    def act(self, task: str) -> dict:
        result = {"信号灯": "绿灯", "用例": 20, "通过": 20, "阻塞": 0}
        self.memory.add_record(self.space, "task",
                               {"类型": "验收", "结果": result}, self.name)
        print(f"[游戏·测试·主管] 验收通过（信号灯绿灯）")
        return result


class GameChiefAssistant(GameRole):
    """游戏·架构·总师助理：引擎阶段纠偏专项 / 改错改框架 / 阶段边界检查（阶段不对就算错）
    参考 dongjiagoushi 架构·总师助理：专角色专用，保总师主线上下文纯净。"""
    def act(self, task: str, engine_stage: str = "cocos") -> dict:
        # 阶段边界检查：发现当前阶段引擎能力之外的越界实现 → 标记阶段越界并纠偏
        stage_boundary = {
            "cocos": {"allowed": ["UI", "本地存档", "轻量登录", "简单排行榜"],
                      "forbidden": ["帧同步战斗校验", "大规模同屏物理", "C++级内存池"]},
            "unity": {"allowed": ["复杂UI", "AssetBundle热更", "高并发WebSocket", "纯C#核心库"],
                      "forbidden": ["每帧子弹轨迹计算(Go)", "极致底层C++优化"]},
            "ue":    {"allowed": ["C++渲染管线", "同源C++战斗库", "Go网关高并发"],
                      "forbidden": ["草台班子式无状态弱约束架构"]},
        }
        boundary = stage_boundary.get(engine_stage, stage_boundary["cocos"])
        # 示例：检测到一个越界项
        violation = "帧同步战斗校验（本应在unity/ue阶段，cocos阶段强行实现=过度设计）"
        result = {
            "引擎阶段": engine_stage,
            "阶段边界(允许)": boundary["allowed"],
            "阶段越界(禁止)": boundary["forbidden"],
            "检测到越界": violation,
            "定性": "阶段越界(阶段不对就算错)",
            "处置": "[回转] 打回实现，标记[阶段越界]，在cocos阶段用轻量同步，战斗校验推迟到unity/ue",
            "目标进度尺": {"goal_total": "该阶段验收", "current": "已收敛", "distance": "待进入下一阶段"},
        }
        self.memory.add_record(self.space, "task",
                               {"类型": "阶段边界审查", "结果": result}, self.name)
        print(f"[游戏·架构·总师助理](引擎阶段纠偏) 检测到阶段越界，打回纠偏")
        return result


# ============================================================
# 二、主流程
# ============================================================
def main():
    print("=" * 60)
    print("游戏向架构师团队 · 游戏功能框架开发（端到端测试）")
    print("=" * 60)

    # 共享记忆：以"战斗系统"为功能单位
    memory = SharedMemory()
    space = "combat_system"
    memory.set_acl(space, "游戏·数值策划", "r")

    # 组建游戏向团队
    architect = GameArchitect("游戏·架构·总师", space, memory)
    producer  = GameProducer("游戏·制作·经理", space, memory)
    designer  = GameDesigner("游戏·策划·主管", space, memory)
    programmer= GameProgrammer("游戏·程序·主管", space, memory)
    balance   = GameBalance("游戏·数值策划", space, memory)
    qa        = GameQA("游戏·测试·主管", space, memory)

    print("\n--- ① 常规流程主线 ---")
    arch = architect.act("顶层架构")
    plan = producer.act("里程碑", arch)
    design = designer.act("系统设计", arch)
    impl = programmer.act("实现", design)

    print("\n--- ② 条件触发：数值失衡引入数值策划 ---")
    balance.act("平衡调优")

    print("\n--- ③ 测试验收 ---")
    qa.act("验收")

    print("\n--- ③.5 阶段边界审查（阶段不对就算错）→ 引入 游戏·架构·总师助理 ---")
    chief_assistant = GameChiefAssistant("游戏·架构·总师助理", space, memory)
    chief_assistant.act("阶段边界审查", engine_stage="cocos")

    print("\n--- ④ 共享记忆查询（relevance×weight）---")
    print("查询'战斗'共享记忆：")
    for r in memory.query(space, keyword="战斗"):
        print(f"  {r.mem_id} v{r.version} w{r.weight} {r.content}")

    print("\n--- ⑤ 共享记忆不可变 + 只追加验证 ---")
    # 修订战斗平衡：追加 v2，权重更高
    target = None
    for r in memory.get_history("loc://memory.combat_system.content.001"):
        if r.version == 1:
            target = r
    if target:
        new = memory.revise(target.mem_id,
                            {"类型": "平衡调优", "平衡": {"战斗": "技能CD 6s→5s(手感回调)", "依据": "玩家反馈"}})
        print(f"修订追加: v{new.version} w{new.weight}（原 v1 保留，status=superseded）")
    # 展示不可变
    v1 = memory.get_version("loc://memory.combat_system.content.001", 1)
    assert v1 is not None and v1.status == "superseded", "原记录保留"
    print("✅ 原记录不可变保留；新版本追加且权重更高")

    print("\n--- ⑥ 共享记忆统计 ---")
    print(" ", memory.stats())

    print("\n" + "=" * 60)
    print("✅ 游戏向架构师团队框架开发测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
