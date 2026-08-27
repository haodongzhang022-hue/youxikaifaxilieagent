# ============================================================
# 通用 Agent 身份自适应模块 (Agent Identity)
# 版本: v1.0
# 说明: 让任意 Agent（CodeBuddy / 仓库修复专员 / 代码审查员 / 游戏向经理等）
#       能**自动识别当前所在的仓库上下文**，并据此生成正确的 @ 召唤格式，
#       不再硬编码 `dongdongxiaozu/youxikaifaxilieagent`。
#
#   核心能力（对齐「跨仓库泛化调用」需求）：
#     1. detect_repo_context()：从环境变量 / git remote 自动探测当前仓库
#        （owner + repo_name + full_slug），不依赖任何硬编码；
#     2. build_mention()：根据目标仓库与角色名生成 `@owner/repo(角色名)` 格式；
#     3. decide_mention_strategy()：智能判断——同仓库用简洁格式，
#        跨仓库必须用完整路径格式（带壳），防止权限错位；
#     4. get_codebuddy_mention()：获取本仓库的 CodeBuddy 召唤格式。
#
#   使用方式（所有角色 prompt 中均引用此模块）：
#     from agent_identity import AgentIdentity
#     identity = AgentIdentity()
#     identity.detect_repo_context()
#     identity.get_codebuddy_mention()
#
# 语言: Python 3 (可运行，无需外部依赖)
# ============================================================
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ============================================================
# 仓库上下文数据结构
# ============================================================

@dataclass
class RepoContext:
    """当前仓库上下文（从环境变量 / git remote 探测得到）"""
    owner: str = ""                    # 组织/用户，如 "dongdongxiaozu"
    repo_name: str = ""                # 仓库名，如 "youxikaifaxilieagent"
    full_slug: str = ""                # owner/repo，如 "dongdongxiaozu/youxikaifaxilieagent"
    web_url: str = ""                  # Web 地址
    detection_source: str = "unknown"  # 探测来源: env / git / fallback


# ============================================================
# 环境变量探测
# ============================================================

def _detect_from_env() -> Dict[str, str]:
    """从 CNB 平台环境变量中探测当前仓库上下文。

    优先使用 CNB_REPO_SLUG（格式: owner/repo），
    次选 CNB_GROUP_SLUG + CNB_REPO_NAME 组合，
    最后尝试 CNB_WEB_ENDPOINT / CNB_BUILD_WEB_URL 解析。
    """
    out: Dict[str, str] = {}

    # 方法1: CNB_REPO_SLUG 直接给出完整路径
    slug = os.environ.get("CNB_REPO_SLUG", "") or os.environ.get("CNB_REPO_SLUG_LOWERCASE", "")
    if slug and "/" in slug:
        owner, repo = slug.split("/", 1)
        out["owner"] = owner
        out["repo_name"] = repo
        out["full_slug"] = slug
        out["detection_source"] = "env_cnb_repo_slug"
        return out

    # 方法2: CNB_GROUP_SLUG + CNB_REPO_NAME 组合
    group = os.environ.get("CNB_GROUP_SLUG", "") or os.environ.get("CNB_ROOT_SLUG", "")
    repo = os.environ.get("CNB_REPO_NAME", "")
    if group and repo:
        out["owner"] = group
        out["repo_name"] = repo
        out["full_slug"] = f"{group}/{repo}"
        out["detection_source"] = "env_cnb_group_repo"
        return out

    # 方法3: CNB_BUILD_WEB_URL 中解析
    build_url = os.environ.get("CNB_BUILD_WEB_URL", "")
    if build_url:
        # 格式: https://cnb.cool/owner/repo/-/build/logs/...
        m = re.search(r'https?://[^/]+/([^/]+)/([^/]+)/', build_url)
        if m:
            out["owner"] = m.group(1)
            out["repo_name"] = m.group(2)
            out["full_slug"] = f"{m.group(1)}/{m.group(2)}"
            out["detection_source"] = "env_cnb_build_web_url"
            return out

    return {}


def _detect_from_git() -> Dict[str, str]:
    """从 git remote 探测仓库上下文（适用于本地开发/测试环境）。"""
    try:
        result = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True, text=True, timeout=3)
        url = (result.stdout or "").strip()
        if not url:
            return {}
        # 支持格式:
        #   git@cnb.cool:owner/repo.git
        #   https://cnb.cool/owner/repo.git
        #   https://cnb.cool/owner/repo
        m = re.search(r'(?:[:/])([^/:]+)/([^/:]+?)(?:\.git)?$', url)
        if m:
            owner, repo = m.group(1), m.group(2)
            return {
                "owner": owner,
                "repo_name": repo,
                "full_slug": f"{owner}/{repo}",
                "detection_source": "git_remote",
            }
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return {}


# ============================================================
# AgentIdentity 核心类
# ============================================================

class AgentIdentity:
    """通用 Agent 身份识别与 @ 召唤格式生成器。

    所有角色（CodeBuddy / 仓库修复专员 / 代码审查员 / 游戏向经理 /
    合并确认员等）都应引用本模块来生成跨仓库 / 同仓库的 @ 召唤格式，
    确保：
      - 不写死仓库名（自适应探测）；
      - 同仓库简洁召唤，跨仓库带壳完整格式；
      - 权限最正确（调用本仓库 CodeBuddy 时用完整路径+角色名定位）。
    """

    # 本仓库已注册的 NPC 角色名（对应 .cnb/settings.yml）
    KNOWN_ROLES = [
        "CodeBuddy",
        "仓库修复专员",
        "代码审查员",
        "游戏向经理",
        "合并确认员",
    ]

    def __init__(self) -> None:
        self.repo_context: Optional[RepoContext] = None
        self._detect_once()

    # ---------- 仓库探测 ----------
    def _detect_once(self) -> RepoContext:
        """探测一次仓库上下文（env → git → 保底），缓存结果。"""
        if self.repo_context is not None:
            return self.repo_context

        # 优先环境变量
        env_data = _detect_from_env()
        if env_data:
            self.repo_context = RepoContext(**env_data)
            return self.repo_context

        # 其次 git remote
        git_data = _detect_from_git()
        if git_data:
            self.repo_context = RepoContext(**git_data)
            return self.repo_context

        # 保底：尝试从当前工作目录推断
        # 最后兜底返回空 context
        self.repo_context = RepoContext(
            owner=os.environ.get("CNB_GROUP_SLUG", ""),
            repo_name=os.environ.get("CNB_REPO_NAME", ""),
            full_slug=os.environ.get("CNB_REPO_SLUG", ""),
            detection_source="fallback_env",
        )
        return self.repo_context

    def detect_repo_context(self) -> RepoContext:
        """探测当前仓库上下文。首次调用缓存结果。"""
        return self._detect_once()

    # ---------- 仓库信息查询 ----------
    @property
    def repo_owner(self) -> str:
        return self.repo_context.owner if self.repo_context else ""

    @property
    def repo_name(self) -> str:
        return self.repo_context.repo_name if self.repo_context else ""

    @property
    def repo_slug(self) -> str:
        return self.repo_context.full_slug if self.repo_context else ""

    def is_repo_detected(self) -> bool:
        """仓库上下文是否成功探测到。"""
        return bool(self.repo_context and self.repo_context.full_slug and
                    "/" in self.repo_context.full_slug)

    # ---------- @ 召唤格式生成 ----------
    def build_mention(self, role: str,
                      target_slug: Optional[str] = None) -> str:
        """生成 @ 召唤格式。

        Args:
            role: 角色名（如 "CodeBuddy"、"仓库修复专员"）
            target_slug: 目标仓库 slug（owner/repo）。
                不传时使用当前仓库（self.repo_slug）。

        Returns:
            如 "@dongdongxiaozu/youxikaifaxilieagent(CodeBuddy)"
            或 "@dongdongxiaozu/youxikaifaxilieagent(仓库修复专员)"
        """
        slug = target_slug or self.repo_slug
        if not slug or "/" not in slug:
            # 未探测到仓库时，退化到裸 @ 并告警
            return f"@{role}（⚠️ 仓库未探测到，使用裸格式可能权限受限）"
        return f"@{slug}({role})"

    def get_codebuddy_mention(self) -> str:
        """获取本仓库 CodeBuddy 的完整 @ 召唤格式。"""
        return self.build_mention("CodeBuddy")

    def get_fixer_mention(self) -> str:
        """获取本仓库修复专员（仓库修复专员）的完整 @ 召唤格式。"""
        return self.build_mention("仓库修复专员")

    def get_reviewer_mention(self) -> str:
        """获取本仓库代码审查员的完整 @ 召唤格式。"""
        return self.build_mention("代码审查员")

    # ---------- 智能策略判断 ----------
    def decide_mention_strategy(self,
                                target_slug: Optional[str] = None) -> Dict[str, Any]:
        """判断召唤策略：同仓库 or 跨仓库。

        同仓库：可以用简洁格式（直接 @ 角色名），但建议也带仓库定位更保险；
        跨仓库：必须用完整路径格式 `@owner/repo(角色名)` 才能定位到对应仓库的
                角色，否则会被路由到系统级或错误仓库的 NPC。

        Returns:
            {
                "strategy": "same_repo" | "cross_repo" | "unknown",
                "current_slug": "dongdongxiaozu/youxikaifaxilieagent",
                "target_slug": "dongdongxiaozu/other_repo",
                "mention": "@dongdongxiaozu/other_repo(CodeBuddy)",
                "recommendation": "跨仓库必须用完整格式..."
            }
        """
        target = target_slug or self.repo_slug
        current = self.repo_slug

        if not current or not target or "/" not in current or "/" not in target:
            return {
                "strategy": "unknown",
                "current_slug": current,
                "target_slug": target,
                "mention": self.build_mention("CodeBuddy", target),
                "recommendation": "仓库上下文未探测到，建议确认环境变量后重试。",
            }

        if current == target:
            return {
                "strategy": "same_repo",
                "current_slug": current,
                "target_slug": target,
                "mention": f"@{current}(CodeBuddy)",
                "recommendation": (
                    f"同仓库（{current}），可以直接 @ 角色名，"
                    f"但建议仍使用完整格式 `@{current}(CodeBuddy)` 以消除歧义。"
                ),
            }
        else:
            return {
                "strategy": "cross_repo",
                "current_slug": current,
                "target_slug": target,
                "mention": f"@{target}(CodeBuddy)",
                "recommendation": (
                    f"跨仓库调用：当前在 {current}，目标为 {target}。"
                    f"**必须使用完整格式** `@{target}(CodeBuddy)`（仓库路径+角色名）"
                    f"才能定位到目标仓库的 CodeBuddy，避免被路由到系统级或他仓 NPC。"
                ),
            }

    # ---------- 对外操作建议 ----------
    def get_operational_advice(self) -> str:
        """生成给 Agent 的操作建议文本（用于 prompt 注入 / 运行时输出）。

        每个角色（CodeBuddy / 代码审查员 / 游戏向经理等）在需要 @ 其他角色时，
        都应先读取本方法输出的建议，确保使用正确的格式。
        """
        self._detect_once()

        if not self.is_repo_detected():
            return (
                "⚠️ 当前仓库上下文未能自动识别。请通过环境变量 "
                "`CNB_REPO_SLUG` 或 `CNB_GROUP_SLUG`+`CNB_REPO_NAME` 确认。"
            )

        cb_mention = self.get_codebuddy_mention()
        fixer_mention = self.get_fixer_mention()

        return (
            f"【仓库自适应识别】当前仓库: `{self.repo_slug}`"
            f"（识别来源: {self.repo_context.detection_source if self.repo_context else 'unknown'}）\n"
            f"- 召唤本仓库 CodeBuddy: `{cb_mention}`\n"
            f"- 召唤本仓库修复专员: `{fixer_mention}`\n"
            f"- 同仓库调用: 可裸 @ 角色名，但建议用完整格式消除歧义\n"
            f"- **跨仓库调用: 必须用完整格式 `@{self.repo_slug}(角色名)` 带壳召唤，"
            f"否则会被路由到错误仓库导致权限受限**\n"
            f"- 禁止裸 @CodeBuddy（会命中系统级或他仓，权限不对）\n"
        )


# ============================================================
# 便捷函数（全局单例 / 一次性调用）
# ============================================================

_identity_instance: Optional[AgentIdentity] = None


def get_identity() -> AgentIdentity:
    """获取全局单例 AgentIdentity（避免重复探测）。"""
    global _identity_instance
    if _identity_instance is None:
        _identity_instance = AgentIdentity()
    return _identity_instance


def current_repo_slug() -> str:
    """快速获取当前仓库 slug（owner/repo）。"""
    return get_identity().repo_slug


def current_repo_owner() -> str:
    """快速获取当前仓库所属组织。"""
    return get_identity().repo_owner


def current_repo_name() -> str:
    """快速获取当前仓库名。"""
    return get_identity().repo_name


def codebuddy_mention() -> str:
    """快速获取本仓库 CodeBuddy 的 @ 召唤格式。"""
    return get_identity().get_codebuddy_mention()


def fixer_mention() -> str:
    """快速获取本仓库修复专员的 @ 召唤格式。"""
    return get_identity().get_fixer_mention()


# ============================================================
# 自测（python agent_identity.py 可运行）
# ============================================================

if __name__ == "__main__":
    print("=" * 70)
    print("通用 Agent 身份自适应模块（AgentIdentity）自测")
    print("=" * 70)

    identity = AgentIdentity()
    ctx = identity.detect_repo_context()
    print(f"\n[1] 仓库探测: {ctx.full_slug or '(未探测到)'}")
    print(f"    owner={ctx.owner}, repo_name={ctx.repo_name}")
    print(f"    来源={ctx.detection_source}")

    print(f"\n[2] 本仓库 CodeBuddy 召唤格式: {identity.get_codebuddy_mention()}")
    print(f"    本仓库修复专员召唤格式: {identity.get_fixer_mention()}")

    # 同仓库策略
    print(f"\n[3] 同仓库策略: {identity.repo_slug}")
    if identity.is_repo_detected():
        same = identity.decide_mention_strategy(identity.repo_slug)
        print(f"    strategy={same['strategy']}")
        print(f"    mention={same['mention']}")
        print(f"    建议: {same['recommendation']}")

        # 跨仓库策略
        cross_slug = f"{identity.repo_owner}/some_other_repo"
        cross = identity.decide_mention_strategy(cross_slug)
        print(f"\n[4] 跨仓库策略 (目标: {cross_slug})")
        print(f"    strategy={cross['strategy']}")
        print(f"    mention={cross['mention']}")
        print(f"    建议: {cross['recommendation']}")

    print(f"\n[5] 操作建议:")
    print(identity.get_operational_advice())

    print("AgentIdentity 自测通过 ✅")
