# ============================================================
# 通用 Agent 身份自适应模块 (Agent Identity)
# 版本: v1.2
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
#     4. get_codebuddy_mention()：获取本仓库的 CodeBuddy 召唤格式；
#     5. get_review_operational_advice()：**面向评审 NPC 的自适应操作建议**，
#        —— 根据「当前触发评审的仓库」探测组织名 + 仓库名（都不写死），
#          再生成带壳 `@组织/仓库(CodeBuddy)` 召唤格式，供评审输出操作建议。
#
#   v1.1 新增：
#     - 增强 git 探测：从当前目录**向上查找 .git** 解析 remote，保证评审在
#       子目录 / 非仓库根目录也能可靠探测到「当前被评审的仓库」；
#     - 新增 get_review_operational_advice()：评审 NPC 生成召唤 CodeBuddy 的
#       操作建议时调用，组织名 / 仓库名全部自适应，跨仓可用，禁止写死。
#
#   v1.2 新增（修复「检测本组织 / 仓库能力」误识别）：
#     - **env 权威优先 + 交叉校验**：平台注入的 CNB_REPO_SLUG 为最权威来源，
#       当 git remote 探测到的仓库与平台 slug 不一致时，**以平台 slug 为准**
#       （env_over_git），杜绝把本仓库误识别成其他仓库（如借鉴的
#       dongjiagoushi）；
#     - **git remote 遍历兜底**：不再只读 origin，遍历全部 remote 解析，
#       优先返回与平台权威 slug / 仓库名一致的 remote；env 完全缺失时再回退；
#     - **env 候选增强**：新增 CNB_PULL_REQUEST_SLUG / CNB_REPO_URL_HTTPS
#       等候选变量 + slug 归一化（去空白 / 去 .git），提高 env 命中率。
#
#   使用方式（所有角色 prompt 中均引用此模块）：
#     from agent_identity import AgentIdentity
#     identity = AgentIdentity()
#     identity.detect_repo_context()
#     identity.get_codebuddy_mention()
#     identity.get_review_operational_advice()   # 评审 NPC 专用
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

def _slug_normalize(slug: str) -> str:
    """规范化仓库 slug：去掉首尾空白、可选 .git 后缀，不做大小写转换（保留原文）。"""
    slug = (slug or "").strip().rstrip("/")
    if slug.endswith(".git"):
        slug = slug[:-4]
    return slug


def _detect_from_env() -> Dict[str, str]:
    """从 CNB 平台环境变量中探测当前仓库上下文。

    优先使用 CNB_REPO_SLUG（格式: owner/repo），
    次选 CNB_GROUP_SLUG + CNB_REPO_NAME 组合，
    再尝试 CNB_PULL_REQUEST_SLUG / CNB_REPO_URL_HTTPS / CNB_BUILD_WEB_URL 解析。

    **权威性说明**：平台流水线注入的 CNB_REPO_SLUG / CNB_REPO_NAME 是判定
    当前组织 + 仓库的**最权威来源**，任何 git remote 探测都不得覆盖它，
    避免把「本仓库」误识别成其他仓库（例如借鉴的 dongjiagoushi）。
    """
    out: Dict[str, str] = {}

    def _hit(owner: str, repo: str, src: str) -> Dict[str, str]:
        owner = owner.strip()
        repo = _slug_normalize(repo)
        if owner and repo and "/" not in repo:
            return {
                "owner": owner,
                "repo_name": repo,
                "full_slug": f"{owner}/{repo}",
                "detection_source": src,
            }
        return {}

    # 方法1: CNB_REPO_SLUG 直接给出完整路径（最权威）
    for var in ("CNB_REPO_SLUG", "CNB_REPO_SLUG_LOWERCASE"):
        slug = _slug_normalize(os.environ.get(var, ""))
        if slug and "/" in slug:
            owner, repo = slug.split("/", 1)
            hit = _hit(owner, repo, "env_cnb_repo_slug")
            if hit:
                return hit

    # 方法2: CNB_PULL_REQUEST_SLUG（平台在 PR/Issue 上下文注入）
    pr_slug = _slug_normalize(os.environ.get("CNB_PULL_REQUEST_SLUG", ""))
    if pr_slug and "/" in pr_slug:
        owner, repo = pr_slug.split("/", 1)
        hit = _hit(owner, repo, "env_cnb_pr_slug")
        if hit:
            return hit

    # 方法3: CNB_GROUP_SLUG + CNB_REPO_NAME 组合
    group = os.environ.get("CNB_GROUP_SLUG", "") or os.environ.get("CNB_ROOT_SLUG", "")
    repo = os.environ.get("CNB_REPO_NAME", "")
    if group and repo:
        hit = _hit(group, repo, "env_cnb_group_repo")
        if hit:
            return hit

    # 方法4: CNB_REPO_URL_HTTPS（格式: https://cnb.cool/owner/repo）
    repo_url = _slug_normalize(os.environ.get("CNB_REPO_URL_HTTPS", ""))
    if repo_url:
        m = re.search(r'https?://[^/]+/([^/]+)/([^/]+)$', repo_url)
        if m:
            hit = _hit(m.group(1), m.group(2), "env_cnb_repo_url_https")
            if hit:
                return hit

    # 方法5: CNB_BUILD_WEB_URL 中解析
    build_url = os.environ.get("CNB_BUILD_WEB_URL", "")
    if build_url:
        # 格式: https://cnb.cool/owner/repo/-/build/logs/...
        m = re.search(r'https?://[^/]+/([^/]+)/([^/]+)/', build_url)
        if m:
            hit = _hit(m.group(1), m.group(2), "env_cnb_build_web_url")
            if hit:
                return hit

    return {}


def _git_root(start: str) -> Optional[str]:
    """从 start 目录向上查找 .git 所在目录（git 仓库根）。

    评审 NPC 可能在被评审仓库的任意子目录执行，向上查找可保证
    无论工作目录在哪层都能定位到仓库根，进而探测 remote。
    """
    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, ".git")) or os.path.isfile(os.path.join(cur, ".git")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _parse_remote_url(url: str) -> Optional[Dict[str, str]]:
    """从 git remote URL 解析 owner/repo。

    支持格式:
      git@cnb.cool:owner/repo.git
      https://cnb.cool/owner/repo.git
      https://cnb.cool/owner/repo
      ssh://git@cnb.cool/owner/repo.git
    """
    url = _slug_normalize(url)
    if not url:
        return None
    m = re.search(r'(?:[:/])([^/:]+)/([^/:]+?)(?:\.git)?$', url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    repo = _slug_normalize(repo)
    if owner and repo and "/" not in repo:
        return {
            "owner": owner,
            "repo_name": repo,
            "full_slug": f"{owner}/{repo}",
        }
    return None


def _detect_from_git(start: Optional[str] = None) -> Dict[str, str]:
    """从 git remote 探测仓库上下文（适用于本地开发/测试环境 / env 缺失场景）。

    会从 start（默认当前目录）**向上查找 .git** 定位仓库根后，**遍历全部
    remote** 解析 owner/repo；若平台注入的 CNB_REPO_SLUG / CNB_REPO_NAME
    存在（已知本仓库），则**优先返回与之一致的 remote**——当 git 探测结果
    与平台权威 slug 冲突时，以平台注入的 slug 为准，防止把本仓库误识别成
    其他仓库（例如借鉴的 dongjiagoushi）。
    """
    try:
        root = _git_root(start or os.getcwd())
        if root is None:
            return {}

        # 读取平台权威 slug（若存在），用于 git 结果交叉校验
        env_slug = (_slug_normalize(os.environ.get("CNB_REPO_SLUG", ""))
                    or _slug_normalize(os.environ.get("CNB_REPO_SLUG_LOWERCASE", "")))
        env_repo_name = _slug_normalize(os.environ.get("CNB_REPO_NAME", ""))

        # 列出所有 remote（遍历，不只 origin，增强多 remote 场景健壮性）
        r = subprocess.run(
            ["git", "-C", root, "remote"],
            capture_output=True, text=True, timeout=3)
        remotes = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
        if not remotes:
            remotes = ["origin"]

        candidates = []
        for remote in remotes:
            res = subprocess.run(
                ["git", "-C", root, "config", "--get", f"remote.{remote}.url"],
                capture_output=True, text=True, timeout=3)
            url = (res.stdout or "").strip()
            parsed = _parse_remote_url(url)
            if parsed:
                # 记录 remote 别名，便于多 remote 场景下按 origin 优先排序
                parsed["_remote"] = remote
                candidates.append(parsed)

        if not candidates:
            return {}

        # 交叉校验：优先返回与平台权威 slug 一致的候选
        for cand in candidates:
            if env_slug and cand["full_slug"] == env_slug:
                cand["detection_source"] = "git_remote_matches_env"
                return cand
            if env_repo_name and cand["repo_name"] == env_repo_name:
                cand["detection_source"] = "git_remote_matches_env_repo"
                return cand

        # 平台权威 slug 存在但 git 探测到不同仓库：以平台为准，绝不误识别
        if env_slug and "/" in env_slug:
            owner, repo = env_slug.split("/", 1)
            return {
                "owner": owner,
                "repo_name": repo,
                "full_slug": f"{owner}/{repo}",
                "detection_source": "env_over_git",
            }

        # 无平台权威时，返回第一个可解析的 remote（用 origin 优先）
        candidates.sort(key=lambda c: 0 if c.get("_remote") == "origin" else 1)
        out = dict(candidates[0])
        out["detection_source"] = "git_remote"
        return out

    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
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
        # 核心编排角色
        "CodeBuddy",
        "仓库修复专员",
        "代码审查员",
        "游戏向经理",
        "合并确认员",
        # 六大部门 NPC（按流水线顺序）
        "策划线",
        "程序线",
        "美术线",
        "测试线",
        "项目管理",
        "运营线",
        # 跨部门服务圈（非六大执行部门）
        "协作支持圈",
    ]

    def __init__(self) -> None:
        self.repo_context: Optional[RepoContext] = None
        self._detect_once()

    # ---------- 仓库探测 ----------
    def _detect_once(self) -> RepoContext:
        """探测一次仓库上下文（env → git → 保底），缓存结果。"""
        if self.repo_context is not None:
            return self.repo_context

        # 优先环境变量（平台注入的 CNB_REPO_SLUG 为最权威来源）
        env_data = _detect_from_env()
        if env_data:
            self.repo_context = RepoContext(**env_data)
            return self.repo_context

        # 其次 git remote（向上查找 .git 定位仓库根，健壮探测）。
        # _detect_from_git 内部已做交叉校验：若平台权威 slug 存在但 git
        # 探测到别的仓库，会以平台 slug 为准（env_over_git），绝不误识别成
        # 其他仓库（例如借鉴的 dongjiagoushi）。
        git_data = _detect_from_git()
        if git_data:
            self.repo_context = RepoContext(**git_data)
            return self.repo_context

        # 保底：尝试从当前工作目录推断
        # 最后兜底返回空 context
        self.repo_context = RepoContext(
            owner=os.environ.get("CNB_GROUP_SLUG", "") or os.environ.get("CNB_ROOT_SLUG", ""),
            repo_name=os.environ.get("CNB_REPO_NAME", ""),
            full_slug=os.environ.get("CNB_REPO_SLUG", "") or os.environ.get("CNB_PULL_REQUEST_SLUG", ""),
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

    def get_review_operational_advice(self,
                                      target_slug: Optional[str] = None) -> str:
        """评审 NPC 专用：基于「当前触发评审的仓库」自适应生成召唤 CodeBuddy 的操作建议。

        关键点：
          - **组织名 / 仓库名都不写死**，通过 AgentIdentity 探测当前被评审仓库，
            得到 `owner/repo` 后构造 `@owner/repo(CodeBuddy)` 带壳召唤；
          - 支持跨仓：target_slug 不传时用当前仓库（即触发评审的仓库），
            传了则按目标仓库生成（如评审在 A 仓、被评审对象是 B 仓时用 B 仓壳）；
          - 输出可直接粘贴进 PR 评论的操作建议文本，杜绝用裸 @CodeBuddy。

        Returns:
            可直接输出的 Markdown 操作建议文本。
        """
        self._detect_once()

        target = target_slug or self.repo_slug
        if not target or "/" not in target:
            return (
                "⚠️ 当前被评审仓库未能自动识别。请通过环境变量 "
                "`CNB_REPO_SLUG` 或 `CNB_GROUP_SLUG`+`CNB_REPO_NAME` 确认，"
                "再以 `@组织/仓库(CodeBuddy)` 完整格式召唤本仓库 CodeBuddy，禁止裸 @CodeBuddy。"
            )

        owner, repo = target.split("/", 1)
        cb_mention = self.build_mention("CodeBuddy", target)
        return (
            f"【召唤本仓库 CodeBuddy · 仓库自适应识别】\n"
            f"当前触发评审的仓库为 `{target}`（组织 `{owner}` / 仓库 `{repo}`，"
            f"识别来源: {self.repo_context.detection_source if self.repo_context else 'unknown'}）。\n"
            f"请召唤本仓库 CodeBuddy，**必须用带壳完整格式**：\n"
            f"  `{cb_mention}`\n"
            f"- 组织名 `{owner}` 与仓库名 `{repo}` 均**自适应探测**，随当前被评审仓库变化，"
            f"不写死固定路径；\n"
            f"- **禁止裸 `@CodeBuddy`**（会命中系统级或他仓 CodeBuddy，权限不对、无法推送）；\n"
            f"- 仅本仓库 CodeBuddy（`{cb_mention}`）具备推送/合并/关闭权限，可完成闭环。\n"
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


def review_operational_advice(target_slug: Optional[str] = None) -> str:
    """评审 NPC 专用：获取召唤本仓库 CodeBuddy 的自适应操作建议。"""
    return get_identity().get_review_operational_advice(target_slug)


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

    print(f"\n[6] 评审 NPC 召唤 CodeBuddy 操作建议（仓库自适应，不写死）:")
    print(identity.get_review_operational_advice())

    print("AgentIdentity 自测通过 ✅")
