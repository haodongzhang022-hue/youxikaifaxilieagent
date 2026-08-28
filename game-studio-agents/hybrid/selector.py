# -*- coding: utf-8 -*-
"""
IncrementalSelector · 变更感知增量测试选择器
============================================
把「每次 PR 推送全量跑 30+ 测试脚本」优化为「只跑受变更影响的测试」。

核心能力：
  - `changed_files(base, head)`  用 git diff 获取两个提交间的变更文件
  - `select(changed)`            给定变更文件 → 返回需运行的测试清单（含依赖传播）
  - `incremental(base, head)`    一键：git diff → 受影响测试（增量选择）
  - `full_suite()`               全量兜底（全部已注册测试）

与 TestRegistry 的关系：
  - 本模块消费 `hybrid.registry`（registry.json 的接口层）；
  - 变更范围感知 = git diff + registry 覆盖映射 + 依赖传播闭包。

本模块是纯逻辑 + git 子进程，无额外外部依赖。
"""
import subprocess


class IncrementalSelector(object):
    """变更感知增量测试选择器。"""

    def __init__(self, root_dir=None, registry=None):
        self.root_dir = root_dir or "."
        self._registry = registry

    # ---------- registry 数据访问 ----------
    def _registry_module(self):
        """获取 registry 接口模块（支持注入覆盖）。"""
        if self._registry is not None:
            return self._registry
        # 动态插入 hybrid 包路径，适配脚本在仓库根目录 / 子目录运行
        import sys
        here = __file__.rsplit("/", 2)[0]  # game-studio-agents/hybrid
        root = here.rsplit("/", 1)[0]       # game-studio-agents
        if root not in sys.path:
            sys.path.insert(0, root)
        from hybrid import registry as reg
        return reg

    def _all_tests(self):
        return self._registry_module().all_tests()

    # ---------- git diff ----------
    def changed_files(self, base="HEAD~1", head="HEAD"):
        """获取 base 到 head 之间变更的文件清单。

        默认比较上一个提交到当前提交（单提交增量）。
        也支持 base='origin/main' 等任意 git 引用。
        返回值：变更文件路径 list（新增/修改/删除）。
        """
        cmd = ["git", "-c", "core.quotepath=false", "diff", "--name-only", base, head]
        proc = subprocess.run(
            cmd, capture_output=True, text=True,
            cwd=self.root_dir, timeout=30,
        )
        if proc.returncode != 0:
            raise RuntimeError("git diff failed: %s" % proc.stderr[-500:])
        return [f for f in proc.stdout.strip().split("\n") if f.strip()]

    def changed_files_workdir(self):
        """获取工作区未提交的变更文件清单（含暂存区）。"""
        files = []
        for args in (["git", "-c", "core.quotepath=false", "diff", "--name-only"],
                     ["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"]):
            proc = subprocess.run(
                args, capture_output=True, text=True,
                cwd=self.root_dir, timeout=30,
            )
            if proc.returncode == 0:
                for f in proc.stdout.strip().split("\n"):
                    if f.strip() and f not in files:
                        files.append(f.strip())
        return files

    # ---------- 选择逻辑 ----------
    def select(self, changed_files):
        """给定变更文件清单 → 返回需运行的测试脚本路径 list。

        内部用 registry 数据完成映射 + 依赖传播。
        """
        if not changed_files:
            return []
        reg = self._registry_module()
        return reg.affected_tests(changed_files)

    def incremental(self, base="HEAD~1", head="HEAD"):
        """一键增量选择：git diff → 受影响测试。"""
        files = self.changed_files(base, head)
        return self.select(files)

    def incremental_workdir(self):
        """一键增量选择：工作区变更 → 受影响测试。"""
        files = self.changed_files_workdir()
        return self.select(files)

    # ---------- 全量兜底 ----------
    def full_suite(self):
        """返回全部已注册测试（全量兜底）。"""
        return self._all_tests()


# 便捷单例
default_selector = IncrementalSelector()
