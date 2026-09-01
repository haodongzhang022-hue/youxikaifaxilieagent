# ============================================================
# 统一模型配置（Single Source of Truth）
# 版本: v1.1
# 说明: 仓库内所有 Agent / 路由 / 强化层统一使用的模型标识。
#       本仓库统一采用 GLM 5.3 Flash 作为默认模型。
#
#   背景（Issue #126 用户确认 + 后续调整）：
#     - 用户确认默认模型由 DeepSeek V4 Flash 切换为 GLM 5.3 Flash；
#     - GLM 5.3 Flash 综合能力强于原 DeepSeek Flash 档位；
#     - 统一模型标识，避免跨档位/跨厂商行为不一致。
#
#   使用：各模块通过 `from model_config import DEFAULT_MODEL` 引用统一模型，
#        不散落硬编码模型名，便于统一切换/升级。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations


# ============================================================
# 一、统一模型标识
# ============================================================

# 默认模型：GLM 5.3 Flash
DEFAULT_MODEL = "glm-5.3-flash"

# 模型档位标识（供路由/文档引用）
MODEL_FAMILY = "glm-5.3-flash"
MODEL_SNAPSHOT = "flash"

# 备用/历史模型（迁移前引用，便于回溯）
LEGACY_MODEL_DEEPSEEK_FLASH = "deepseek-v4-flash-0731"  # 历史默认模型，已切换为 GLM
LEGACY_MODEL_PRO = "deepseek-v4-pro"      # 仅历史文档引用，不用于新配置
LEGACY_MODEL_FLASH = "deepseek-v4-flash"  # 旧档位，已收敛到 GLM Flash

# 模型档位说明
MODEL_PROFILE = {
    "family": MODEL_FAMILY,
    "snapshot": MODEL_SNAPSHOT,
    "default": DEFAULT_MODEL,
    "billing": {
        "cloud": "按量付费（含免费额度）",
        "local": "opencode 付费订阅",
    },
    "usage": "统一模型配置，全部 Agent/路由/强化层共用",
}


def get_default_model() -> str:
    """获取当前统一模型标识（单点维护）。"""
    return DEFAULT_MODEL


def is_flash(model: str) -> bool:
    """判断给定模型标识是否为 Flash 档位。"""
    return "flash" in (model or "").lower()


# ============================================================
# 二、自测
# ============================================================

if __name__ == "__main__":
    print("=== 统一模型配置自测 ===")
    print(f"  默认模型: {DEFAULT_MODEL}")
    print(f"  模型族: {MODEL_FAMILY} (快照 {MODEL_SNAPSHOT})")
    print(f"  计费: 云端={MODEL_PROFILE['billing']['cloud']} / 本地={MODEL_PROFILE['billing']['local']}")
    print(f"  is_flash(default)={is_flash(DEFAULT_MODEL)}")
    assert is_flash(DEFAULT_MODEL), "默认模型应为 Flash 档位"
    print("\n🟢 统一模型配置自测通过")
