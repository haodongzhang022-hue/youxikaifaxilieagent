# ============================================================
# 通用 Agent 仓库身份解析模块（Agent Identity Resolver）
# 版本: v1.0
# 说明: 解决"跨仓库召唤"时 @ 提及身份写死导致权限受限的问题。
#
# 背景问题
# ---------
# 仓库里的 NPC（CodeBuddy / 代码审查员 / 游戏向经理…）可能在**其它仓库**
# 被跨仓库召唤。旧写法把「召唤目标」写死成 `@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)`
# （本仓库路径 + 角色名）。但当本仓库 NPC 被**外部仓库**触发、需要在那个仓库
# 推送/合并/关闭时，写死的身份是本仓库的 CodeBuddy——它在目标仓库**没有权限**，
# 只有**目标仓库自己**的 CodeBuddy 才具备那里 的 push/merge/close 权限。
# 于是跨仓库协作时权限就成了受限的瓶颈。
#
# 本模块（通用化适配层）解决这个问题：
#   1. 自动读取运行环境，识别「当前仓库」（本 NPC 注册所在仓库）
#      与「工作仓库」（本次被触发时真正在改的 PR/Issue 所在仓库）；
#   2. 判定是「同仓库」还是「跨仓库」触发：
#       - 同仓库：无需适配，直接用当前仓库的 CodeBuddy（或当前角色）即可；
#       - 跨仓库：必须把 @ 提及身份**动态指向工作仓库的对应角色**，
#         因为只有工作仓库绑定的 CodeBuddy 才具备那里的推送/合并/关闭权限；
#   3. 输出可直接复制的「@owner/repo(角色名)」完整召唤格式，
#      供 NPC 在评论中定位到**有正确权限**的仓库级角色。
#
# 兼顾去重：先检测仓库，同仓库不重复适配；跨仓库才按工作仓库动态重定向。
#
# 通用化：不写死仓库/组织名，角色名可参数化（CodeBuddy / 代码审查员 /
#         游戏向经理 / 合并确认员…），任何仓库、任何角色都能复用本模块。
#
# 语言: Python 3 (可运行)
# 依赖: 仅标准库（os / re / urllib.parse / dataclasses）
# ============================================================
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


# ============================================================
# 一、环境变量读取与默认
# ============================================================

# CNB 平台在 npc:go / 流水线运行时会注入以下环境变量（见平台运行时约定）：
#   CNB_NPC_SLUG          : 当前 NPC 注册所在仓库的完整 slug，形如 "owner/repo"
#   CNB_NPC_SLUG_LOWERCASE: 同上，小写形式
#   CNB_ROOT_SLUG         : 组织/命名空间，形如 "dongdongxiaozu"
#   CNB_GROUP_SLUG        : 组织 slug，形如 "dongdongxiaozu"
#   CNB_REPO_NAME         : 当前仓库名，形如 "youxikaifaxilieagent"
#   CNB_EVENT_URL         : 触发本次执行的 Issue/PR/评论 URL，含工作仓库路径
#                          形如 "https://cnb.cool/owner/repo/-/issues/32"
#   CNB_NPC_NAME          : 当前 NPC 角色名，形如 "CodeBuddy"
#
# 这些变量未注入时（本地演示 / 自测），可从 git remote 兜底推导当前仓库。

def _env(name: str, default: str = "") -> str:
    """读取环境变量，去首尾空白。"""
    return os.environ.get(name, default).strip()


def _git_remote_slug() -> Optional[str]:
    """从 git remote 兜底推导当前仓库 slug（本地演示时用）。"""
    try:
        import subprocess
        out = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        # 匹配 https://host/owner/repo(.git) 或 git@host:owner/repo(.git)
        m = re.search(r"[:/]([^/]+/[^/]+?)(?:\.git)?$", out)
        return m.group(1) if m else None
    except Exception:  # noqa: BLE001
        return None


# ============================================================
# 二、仓库 slug 解析
# ============================================================

def _parse_slug(slug: str) -> Optional[tuple]:
    """把 "owner/repo" 解析为 (owner, repo)；非 "owner/repo" 形式返回 None。"""
    slug = (slug or "").strip()
    if not slug or "/" not in slug:
        return None
    parts = slug.split("/")
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def _slug_from_env() -> Optional[str]:
    """从环境变量解析当前仓库 slug，优先级 CNB_NPC_SLUG > owner/name 组合。"""
    s = _env("CNB_NPC_SLUG") or _env("CNB_NPC_SLUG_LOWERCASE")
    if s and "/" in s:
        return s
    owner = _env("CNB_ROOT_SLUG") or _env("CNB_GROUP_SLUG")
    name = _env("CNB_REPO_NAME")
    if owner and name:
        return f"{owner}/{name}"
    return None


def _work_slug_from_event_url() -> Optional[str]:
    """从 CNB_EVENT_URL 解析「工作仓库」slug。

    CNB_EVENT_URL 形如 https://cnb.cool/owner/repo/-/issues/32
    或 https://cnb.cool/owner/repo/-/pulls/12，取其中 owner/repo 即为
    真正被处理的 PR/Issue 所在仓库。跨仓库召唤时它通常 ≠ 当前仓库。
    """
    url = _env("CNB_EVENT_URL")
    if not url:
        return None
    try:
        path = urlparse(url).path  # /owner/repo/-/issues/32
        segs = [s for s in path.split("/") if s]
        # 期望 [owner, repo, "-", "issues"/"pulls", number]
        if len(segs) >= 2 and segs[2] == "-":
            return f"{segs[0]}/{segs[1]}"
    except Exception:  # noqa: BLE001
        return None
    return None


# ============================================================
# 三、身份解析核心
# ============================================================

@dataclass(frozen=True)
class AgentIdentity:
    """解析结果：当前角色应在哪一仓库、以何种 @ 提及定位。"""
    current_slug: str          # 当前 NPC 注册所在仓库，如 "owner/repo"
    work_slug: str             # 本次被触发时真正工作的仓库
    role_name: str             # 目标角色名，如 "CodeBuddy"
    is_cross_repo: bool        # 是否跨仓库触发（工作仓库 ≠ 当前仓库）
    mention_slug: str          # 应使用的 @ 提及仓库 slug（已适配）
    mention: str               # 完整召唤格式 " @owner/repo(角色名)"
    hint: str                  # 面向 NPC 的处置建议文本

    @property
    def same_repo(self) -> bool:
        """同仓库触发（无需跨仓库适配）。"""
        return not self.is_cross_repo


def resolve_identity(role_name: Optional[str] = None,
                     current_slug: Optional[str] = None,
                     work_slug: Optional[str] = None) -> AgentIdentity:
    """解析当前角色的仓库身份，产出自适应的 @ 提及召唤格式。

    参数（均可省略，省略时自动从环境变量推导）：
      - role_name   : 目标角色名，默认取当前 NPC 名（CNB_NPC_NAME），兜底 "CodeBuddy"
      - current_slug: 当前 NPC 注册所在仓库；默认从 CNB_NPC_SLUG 推导
      - work_slug   : 工作仓库；默认从 CNB_EVENT_URL 推导
    """
    role = (role_name or "").strip() or _env("CNB_NPC_NAME") or "CodeBuddy"

    cur = current_slug or _slug_from_env() or _git_remote_slug() or ""
    work = work_slug or _work_slug_from_event_url() or cur

    # 归一化：去掉首尾斜杠，确保不写死组织名
    cur = cur.strip("/")
    work = work.strip("/")

    is_cross = bool(cur and work) and cur != work

    # 核心：跨仓库时 @ 提及必须指向「工作仓库」的对应角色，
    #       因为只有工作仓库绑定的 CodeBuddy 才具备那里的推送/合并权限。
    mention_slug = work if is_cross else cur
    mention_slug = mention_slug or work or cur

    if is_cross:
        hint = (
            f"检测到跨仓库触发：当前仓库 [{cur}] ≠ 工作仓库 [{work}]。"
            f"本角色（{role}）在 {work} 没有写权限，"
            f"请在评论中用「@{mention_slug}({role})」完整格式点名 {work} 仓库绑定的 "
            f"{role}（其具备那里的 push/merge/close 权限），不要用本仓库或裸 @。"
        )
    else:
        hint = (
            f"检测到同仓库触发：工作仓库 [{work}] 即当前仓库。"
            f"无需跨仓库适配，用「@{mention_slug}({role})」即可定位本仓库 {role}。"
        )

    return AgentIdentity(
        current_slug=cur,
        work_slug=work,
        role_name=role,
        is_cross_repo=is_cross,
        mention_slug=mention_slug,
        mention=f"@{mention_slug}({role})",
        hint=hint,
    )


# ============================================================
# 四、便捷封装
# ============================================================

def codebuddy_mention() -> str:
    """返回应使用的 CodeBuddy 完整召唤格式（跨仓库自动指向工作仓库）。"""
    return resolve_identity("CodeBuddy").mention


def reviewer_mention() -> str:
    """返回应使用的「代码审查员」完整召唤格式（跨仓库自动指向工作仓库）。"""
    return resolve_identity("代码审查员").mention


def producer_mention() -> str:
    """返回应使用的「游戏向经理」完整召唤格式（跨仓库自动指向工作仓库）。"""
    return resolve_identity("游戏向经理").mention


# ============================================================
# 五、演示 / 自测
# ============================================================

def demo():
    print("=" * 66)
    print("通用 Agent 仓库身份解析（Agent Identity Resolver）")
    print("  自适应 @ 提及：同仓库不重复适配，跨仓库按工作仓库动态重定向")
    print("=" * 66)

    # 场景 A：同仓库触发（本仓库内部闭环，无需适配）
    print("\n[场景 A] 同仓库触发（本仓库 PR 评审闭环）")
    a = resolve_identity("CodeBuddy",
                         current_slug="dongdongxiaozu/youxikaifaxilieagent",
                         work_slug="dongdongxiaozu/youxikaifaxilieagent")
    print(f"  当前仓库 : {a.current_slug}")
    print(f"  工作仓库 : {a.work_slug}")
    print(f"  是否跨仓库: {a.is_cross_repo}")
    print(f"  @ 提及   : {a.mention}")
    print(f"  建议     : {a.hint}")
    assert not a.is_cross_repo, "同仓库不应判为跨仓库"

    # 场景 B：跨仓库触发（外部仓库 @ 本仓库 CodeBuddy，需重定向到工作仓库）
    print("\n[场景 B] 跨仓库触发（外部仓库调用本仓库角色，需重定向）")
    b = resolve_identity("CodeBuddy",
                         current_slug="dongdongxiaozu/youxikaifaxilieagent",
                         work_slug="dongdongxiaozu/other-game-repo")
    print(f"  当前仓库 : {b.current_slug}")
    print(f"  工作仓库 : {b.work_slug}")
    print(f"  是否跨仓库: {b.is_cross_repo}")
    print(f"  @ 提及   : {b.mention}")
    print(f"  建议     : {b.hint}")
    assert b.is_cross_repo, "工作仓库不同应判为跨仓库"
    assert b.mention_slug == "dongdongxiaozu/other-game-repo", "跨仓库必须指向工作仓库"

    # 场景 C：组织/仓库名均不同（更彻底的跨组织跨仓库）
    print("\n[场景 C] 跨组织跨仓库触发（组织也不同）")
    c = resolve_identity("代码审查员",
                         current_slug="alice/game-series",
                         work_slug="bob/unrelated-repo")
    print(f"  当前仓库 : {c.current_slug}")
    print(f"  工作仓库 : {c.work_slug}")
    print(f"  是否跨仓库: {c.is_cross_repo}")
    print(f"  @ 提及   : {c.mention}")
    print(f"  建议     : {c.hint}")
    assert c.is_cross_repo and c.mention_slug == "bob/unrelated-repo", "跨组织也应重定向"

    # 场景 D：角色参数化（不同角色通用）
    print("\n[场景 D] 角色参数化（代码审查员 / 游戏向经理 通用）")
    d1 = resolve_identity("代码审查员", work_slug="bob/unrelated-repo")
    d2 = resolve_identity("游戏向经理", work_slug="bob/unrelated-repo")
    print(f"  代码审查员 @ 提及: {d1.mention}")
    print(f"  游戏向经理 @ 提及: {d2.mention}")
    assert d1.mention_slug == "bob/unrelated-repo"
    assert d2.mention_slug == "bob/unrelated-repo"

    # 场景 E：从真实环境变量推导（演示无环境时的兜底）
    print("\n[场景 E] 从环境变量推导（无则兜底当前仓库 / CodeBuddy）")
    e = resolve_identity()
    print(f"  当前仓库 : {e.current_slug or '(未检测到)'}")
    print(f"  工作仓库 : {e.work_slug or '(未检测到)'}")
    print(f"  是否跨仓库: {e.is_cross_repo}")
    print(f"  @ 提及   : {e.mention}")
    print(f"  建议     : {e.hint}")

    print("\n结果: 🟢 身份解析模块自测通过")
    return 0


def _cli():
    """命令行入口：--mention [角色名]  只输出应使用的 @ 召唤格式。

    供 .cnb.yml 的 NPC 提示 / 脚本在运行期调用：
        python3 agent_identity_resolver.py --mention CodeBuddy
    """
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--mention":
        role = args[1] if len(args) > 1 else None
        print(resolve_identity(role).mention)
        return 0
    if args and args[0] == "--cross-repo":
        ident = resolve_identity()
        print("yes" if ident.is_cross_repo else "no")
        return 0
    return demo()


if __name__ == "__main__":
    raise SystemExit(_cli())
