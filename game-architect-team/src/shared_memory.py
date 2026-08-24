# ============================================================
# 共享记忆库 (SharedMemory)
# 版本: v1.0
# 说明: 游戏向架构师团队的共享记忆模块。
#       核心机制（对应 docs/03-shared-memory.md）：
#       - 以功能单位(space)为粒度共享，非全局
#       - 只存结构化二次/三次整理内容(content/task/skill)，非完整记忆
#       - 只增不改不减（immutable）：写入后不可删改，仅标记 superseded
#       - 修改只追加：修订时追加新版本(version+1)，通过 prev_mem_id 形成版本链
#       - 权重机制：追加的新版本 weight 更高，检索 relevance×weight 优先
# 语言: Python 3 (可运行, 零依赖)
# ============================================================
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime())


@dataclass
class SharedMemoryRecord:
    """共享记忆记录（结构化、不可变、可追加版本）"""
    mem_id: str                  # loc://memory.<space>.<kind>.<seq>
    space: str                   # 功能单位空间（如 backpack_system）
    kind: str                    # content / task / skill
    content: Dict[str, Any]      # 结构化内容（JSON）
    owner: str                   # 负责 agent
    version: int = 1             # 版本号（追加递增）
    weight: float = 1.0          # 检索权重（新版本更高）
    status: str = "active"       # active / superseded
    created_at: str = field(default_factory=now_iso)
    prev_mem_id: Optional[str] = None  # 前驱记录（被追加覆盖的旧版本）

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mem_id": self.mem_id,
            "space": self.space,
            "kind": self.kind,
            "content": self.content,
            "owner": self.owner,
            "version": self.version,
            "weight": self.weight,
            "status": self.status,
            "created_at": self.created_at,
            "prev_mem_id": self.prev_mem_id,
        }


class SharedMemory:
    """
    共享记忆库（内存实现，结构清晰、可序列化落盘）
    核心不变量：
      1. 只增不改不减：已有记录不可删除、不可修改内容
      2. 修改只追加：修订=新增高版本记录，原记录标 superseded
      3. 权重递增：追加的新版本 weight 更高，检索 relevance×weight 优先
    """

    def __init__(self, space_seed: str = "root"):
        self.space_seed = space_seed
        self._records: Dict[str, SharedMemoryRecord] = {}   # "mem_id#version" -> record（同一功能条目多版本并存）
        self._seq: Dict[str, int] = {}                       # (space,kind) -> 序号
        self._acl: Dict[str, Dict[str, str]] = {}            # space -> {agent: r|w|rw|none}

    # ---------------- 权限（ACL） ----------------
    def set_acl(self, space: str, agent: str, perm: str):
        """设置空间访问权限：r|w|rw|none"""
        self._acl.setdefault(space, {})[agent] = perm

    def can_read(self, space: str, agent: str) -> bool:
        p = self._acl.get(space, {}).get(agent, "rw")  # 默认同空间可读写
        return p in ("r", "rw")

    def can_write(self, space: str, agent: str) -> bool:
        p = self._acl.get(space, {}).get(agent, "rw")
        return p in ("w", "rw")

    # ---------------- 追加（只增） ----------------
    def add_record(self, space: str, kind: str, content: Dict[str, Any],
                   owner: str, acl_check: Optional[str] = None) -> SharedMemoryRecord:
        """追加一条新记录（只增，不可覆盖已有记录）"""
        if acl_check and not self.can_write(space, acl_check):
            raise PermissionError(f"agent {acl_check} 无 {space} 写权限")
        kind = kind if kind in ("content", "task", "skill") else "content"
        seq = self._seq.get((space, kind), 0) + 1
        self._seq[(space, kind)] = seq
        mem_id = f"loc://memory.{space}.{kind}.{seq:03d}"
        rec = SharedMemoryRecord(
            mem_id=mem_id, space=space, kind=kind,
            content=dict(content), owner=owner,
        )
        self._records[f"{mem_id}#{rec.version}"] = rec
        return rec

    # ---------------- 修订（只追加，不覆盖） ----------------
    def revise(self, mem_id: str, new_content: Dict[str, Any],
               weight_delta: float = 0.5, acl_check: Optional[str] = None) -> SharedMemoryRecord:
        """
        修订一条记录：不修改原记录，而是追加一个更高版本（version+1）。
        原记录标记 superseded，新记录通过 prev_mem_id 链接到旧记录。
        新版本 weight = 旧版本 weight + weight_delta（修改部分权重更高）。
        """
        old = self.get_latest(mem_id)
        if not old:
            raise KeyError(f"记录不存在: {mem_id}")
        if acl_check and not self.can_write(old.space, acl_check):
            raise PermissionError(f"agent {acl_check} 无 {old.space} 写权限")
        # 追加新版本（从当前最新版本派生出下一版本号）
        latest = self._find_latest(old.space, old.kind, old.mem_id)
        new_version = latest.version + 1
        new_weight = latest.weight + weight_delta  # 修改追加部分权重更高
        # 同一功能条目 mem_id 不变，但 dict 键带 version 以保证不可变并存
        new_rec = SharedMemoryRecord(
            mem_id=latest.mem_id, space=old.space, kind=old.kind,
            content=dict(new_content), owner=acl_check or old.owner,
            version=new_version, weight=new_weight,
            prev_mem_id=latest.mem_id,   # 指向最新被追加覆盖的旧版本
        )
        # 原（最新）记录标记 superseded（其物理行保留，不可删改）
        latest.status = "superseded"
        self._records[f"{new_rec.mem_id}#{new_version}"] = new_rec
        return new_rec

    def _find_latest(self, space: str, kind: str, base_mem_id: str) -> SharedMemoryRecord:
        """在 (space,kind) 内找到某功能条目当前最新版本记录（= get_latest）"""
        return self.get_latest(base_mem_id)

    # ---------------- 查询（relevance × weight） ----------------
    def query(self, space: str, kind: Optional[str] = None, topk: int = 10,
              keyword: str = "", acl_check: Optional[str] = None) -> List[SharedMemoryRecord]:
        """
        检索共享记忆。按 (relevance×weight) 排序，默认取各功能条目最新版本。
        - relevance 由关键词匹配度估计（后续可接入语义向量）
        - weight 使最新追加版本优先
        """
        if acl_check and not self.can_read(space, acl_check):
            raise PermissionError(f"agent {acl_check} 无 {space} 读权限")
        # 收集该空间候选，过滤 superseded 的旧版本，只保留每个 mem_id 最新 active
        latest_by_id: Dict[str, SharedMemoryRecord] = {}
        for r in self._records.values():
            if r.space != space:
                continue
            if kind and r.kind != kind:
                continue
            if r.status != "active":
                continue
            cur = latest_by_id.get(r.mem_id)
            if cur is None or r.version > cur.version:
                latest_by_id[r.mem_id] = r
        # 计算 relevance（关键词匹配）
        def relevance(r: SharedMemoryRecord) -> float:
            if not keyword:
                return 1.0
            hay = json.dumps(r.content, ensure_ascii=False).lower()
            return 1.0 if keyword.lower() in hay else 0.0

        scored = sorted(
            latest_by_id.values(),
            key=lambda r: relevance(r) * r.weight,
            reverse=True,
        )
        return scored[:topk]

    # ---------------- 版本链回溯 ----------------
    def get_version(self, mem_id: str, version: int) -> Optional[SharedMemoryRecord]:
        """按 mem_id + 指定版本号取记录（用于回溯历史版本）"""
        return self._records.get(f"{mem_id}#{version}")

    def get_latest(self, mem_id: str) -> Optional[SharedMemoryRecord]:
        best = None
        for r in self._records.values():
            if r.mem_id == mem_id and (best is None or r.version > best.version):
                best = r
        return best

    def get_history(self, mem_id: str) -> List[SharedMemoryRecord]:
        """返回某功能条目的完整版本链（从旧到新）"""
        chain = [r for r in self._records.values() if r.mem_id == mem_id]
        return sorted(chain, key=lambda r: r.version)

    # ---------------- 统计 ----------------
    def stats(self) -> Dict[str, Any]:
        total = len(self._records)
        by_kind = {}
        for r in self._records.values():
            by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
        # 不可变性校验：被 superseded 的记录数量
        superseded = sum(1 for r in self._records.values() if r.status == "superseded")
        return {
            "total_records": total,
            "by_kind": by_kind,
            "superseded": superseded,
            "active": total - superseded,
        }

    # ---------------- 序列化 / 落盘 ----------------
    def to_json(self) -> str:
        return json.dumps(
            {"records": [r.to_dict() for r in self._records.values()],
             "acl": self._acl, "seq": self._seq},
            ensure_ascii=False, indent=2,
        )

    @classmethod
    def from_json(cls, data: str) -> "SharedMemory":
        obj = json.loads(data)
        sm = cls()
        for d in obj.get("records", []):
            rec = SharedMemoryRecord(**{k: d[k] for k in
                ("mem_id", "space", "kind", "content", "owner", "version",
                 "weight", "status", "created_at", "prev_mem_id") if k in d})
            sm._records[f"{rec.mem_id}#{rec.version}"] = rec
        sm._acl = obj.get("acl", {})
        sm._seq = {tuple(k.split("|")): v for k, v in obj.get("seq", {}).items()}
        return sm


# ============================================================
# 演示 / 自测
# ============================================================
if __name__ == "__main__":
    sm = SharedMemory()
    # 功能单位空间：backpack_system（背包系统）
    sm.set_acl("backpack_system", "游戏·程序·主管", "rw")
    sm.set_acl("backpack_system", "游戏·数值策划", "r")

    # 写入内容记忆（二次整理）
    r1 = sm.add_record("backpack_system", "content",
                       {"规则": "容量=20格", "堆叠上限": 99, "作者": "游戏·策划·主管"},
                       "游戏·策划·主管")
    print("追加记录:", r1.mem_id, "v", r1.version, "w", r1.weight)

    # 写入任务记忆
    sm.add_record("backpack_system", "task",
                  {"任务": "实现背包UI", "依赖": "系统设计", "状态": "进行中"},
                  "游戏·程序·主管")
    # 写入技能记忆（三次整理）
    sm.add_record("backpack_system", "skill",
                  {"技能": "背包系统通用实现playbook", "步骤": ["建模", "UI", "联调"]},
                  "游戏·架构·总师")

    # 修订：修改只追加（容量改版），原记录保留，新版本权重更高
    r_new = sm.revise(r1.mem_id, {"规则": "容量=20格", "堆叠上限": 999, "作者": "游戏·架构·总师"})
    print("修订追加: v", r_new.version, "w", r_new.weight, "(原记录仍保留)")

    # 查询：按 relevance×weight，最新追加优先
    print("\n查询'堆叠上限'命中（relevance×weight排序）:")
    for r in sm.query("backpack_system", keyword="堆叠上限"):
        print(f"  {r.mem_id} v{r.version} w{r.weight} {r.content}")

    # 版本链回溯
    print("\n版本链回溯:")
    for r in sm.get_history(r1.mem_id):
        print(f"  v{r.version} w{r.weight} {r.content} status={r.status}")

    # 不可变性校验
    print("\n统计:", sm.stats())
    # 原记录 v1 必须保留且不可变
    v1 = sm.get_version(r1.mem_id, 1)
    assert v1 is not None and v1.content["堆叠上限"] == 99, "原记录不可变（不被修改）"
    assert v1.status == "superseded", "原记录标记 superseded 但保留"
    # 新版本 v2 为当前生效
    v2 = sm.get_latest(r1.mem_id)
    assert v2.version == 2 and v2.weight == 1.5, "新版本追加且权重更高"
    # 版本链完整
    assert len(sm.get_history(r1.mem_id)) == 2, "版本链保留全部历史"
    print("✅ 只增不改不减 + 修改只追加 + 权重递增机制验证通过")

    # 权限校验
    try:
        sm.query("backpack_system", keyword="堆叠上限", acl_check="游戏·数值策划")
        print("✅ ACL 读权限校验通过")
    except PermissionError as e:
        print("ACL 读权限异常:", e)
