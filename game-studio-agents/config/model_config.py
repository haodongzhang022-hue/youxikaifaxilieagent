# ============================================================
# 统一模型配置（Single Source of Truth）
# 版本: v2.0
# 说明: 仓库内所有 Agent / 路由 / 强化层统一使用的模型标识。
#       支持「高峰/低峰自动切换」+「历史消耗记录」。
#
#   背景（Issue #126 用户确认 + 后续调整 + 高峰切换）：
#     - 用户确认默认模型由 DeepSeek V4 Flash 切换为 GLM 5.3 Flash；
#     - 由于 DeepSeek 存在高峰拥堵（高峰期响应慢/配额紧张），
#       默认模型池保留两个厂商模型，按时间窗口自动切换：
#         · 高峰期（工作日 9:00-18:00）→ GLM 5.3 Flash（稳定）
#         · 低峰期（其余时段）→ DeepSeek V4 Flash 0731（成本优）
#     - 所有模型切换通过变量（环境变量 / 配置常量）控制，可手动覆写。
#     - 记录每次对话的模型/消耗量到历史文件，1 天后即可用实际
#       数据对比定价，辅助后续模型选型决策。
#
#   使用：各模块通过 `from model_config import DEFAULT_MODEL` 引用统一模型，
#        或 `from model_config import get_auto_model` 获取自动切换后的模型，
#        不散落硬编码模型名，便于统一切换/升级。
# 语言: Python 3 (可运行)
# ============================================================
from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta


# ============================================================
# 一、模型池（两个厂商，按需切换）
# ============================================================

# 默认模型（低峰期优先模型）
DEFAULT_MODEL = "glm-5.3-flash"

# 模型池：所有可切换模型
MODEL_POOL = {
    "glm": {
        "model": "glm-5.3-flash",
        "family": "glm-5.3",
        "snapshot": "flash",
        "vendor": "智谱 GLM",
        "note": "高峰稳定、综合能力强",
    },
    "deepseek": {
        "model": "deepseek-v4-flash-0731",
        "family": "deepseek-v4",
        "snapshot": "flash-0731",
        "vendor": "DeepSeek",
        "note": "低峰成本优、含免费额度",
    },
}

# 模型档位标识（供路由/文档引用）
MODEL_FAMILY = "glm-5.3-flash"
MODEL_SNAPSHOT = "flash"

# 备用/历史模型（迁移前引用，便于回溯）
LEGACY_MODEL_DEEPSEEK_FLASH = "deepseek-v4-flash-0731"  # 历史默认模型，已切换为 GLM
LEGACY_MODEL_PRO = "deepseek-v4-pro"      # 仅历史文档引用，不用于新配置
LEGACY_MODEL_FLASH = "deepseek-v4-flash"  # 旧档位，已收敛到 GLM Flash


# ============================================================
# 二、基于时间的高峰/低峰自动切换
# ============================================================

# ── 切换开关（变量控制）─────────────────────────────────────
# 环境变量 MODEL_AUTO_SWITCH=true 启用自动切换；否则固定用 DEFAULT_MODEL
# 环境变量 MODEL_PEAK_START / MODEL_PEAK_END 自定义高峰时段（默认 09:00-18:00）
# 环境变量 MODEL_PEAK_WEEKDAYS 自定义高峰工作日（默认 Mon-Fri，值为 0-6，逗号分隔）
AUTO_SWITCH_ENV = "MODEL_AUTO_SWITCH"
PEAK_START_ENV = "MODEL_PEAK_START"     # 例如 "09:00"
PEAK_END_ENV = "MODEL_PEAK_END"         # 例如 "18:00"
PEAK_WEEKDAYS_ENV = "MODEL_PEAK_WEEKDAYS"  # 例如 "0,1,2,3,4"（0=周一）

# 默认高峰时段：工作日 09:00-18:00
DEFAULT_PEAK_START = "09:00"
DEFAULT_PEAK_END = "18:00"
DEFAULT_PEAK_WEEKDAYS = "0,1,2,3,4"   # 周一~周五


def _parse_time(s: str) -> time:
    """解析 HH:MM 字符串为 time 对象。"""
    try:
        h, m = s.strip().split(":")
        return time(int(h), int(m))
    except Exception:
        return time(9, 0)


def _parse_weekdays(s: str) -> set[int]:
    """解析工作日配置字符串为 int 集合（0=周一）。"""
    try:
        return {int(x.strip()) for x in s.split(",") if x.strip() != ""}
    except Exception:
        return {0, 1, 2, 3, 4}


def _read_env_flag() -> bool:
    """读取自动切换开关环境变量。"""
    v = os.environ.get(AUTO_SWITCH_ENV, "").strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return True   # 默认开启自动切换


def is_peak_hour(now: datetime | None = None) -> bool:
    """判断当前时间是否处于高峰时段（工作日高峰窗口内）。"""
    now = now or datetime.now()
    peak_start = _parse_time(os.environ.get(PEAK_START_ENV, DEFAULT_PEAK_START))
    peak_end = _parse_time(os.environ.get(PEAK_END_ENV, DEFAULT_PEAK_END))
    weekdays = _parse_weekdays(os.environ.get(PEAK_WEEKDAYS_ENV, DEFAULT_PEAK_WEEKDAYS))

    # 工作日判断（0=周一）
    if now.weekday() not in weekdays:
        return False

    # 时段判断
    t = now.time()
    if peak_start <= peak_end:
        return peak_start <= t <= peak_end
    else:  # 跨午夜窗口（如 22:00-06:00）
        return t >= peak_start or t <= peak_end


def get_peak_model() -> str:
    """获取高峰时段模型。"""
    return MODEL_POOL["glm"]["model"]


def get_offpeak_model() -> str:
    """获取低峰时段模型。"""
    return MODEL_POOL["deepseek"]["model"]


def get_auto_model(now: datetime | None = None) -> str:
    """
    按时间自动选择模型。
    - 高峰（默认工作日 09:00-18:00）→ GLM 5.3 Flash（稳定）
    - 低峰 → DeepSeek V4 Flash 0731（成本优）
    - 可通过环境变量 MODEL_AUTO_SWITCH=false 关闭自动切换，固定用 DEFAULT_MODEL
    - 可通过 MODEL_PEAK_START/END/WEEKDAYS 自定义高峰时段

    Returns: 当前应使用的模型标识字符串
    """
    if not _read_env_flag():
        return DEFAULT_MODEL

    if is_peak_hour(now):
        return get_peak_model()
    return get_offpeak_model()


def get_default_model() -> str:
    """获取当前统一模型标识（单点维护）。兼容旧接口：返回自动切换后的模型。"""
    return get_auto_model()


# ============================================================
# 三、历史消耗记录
# ============================================================

# 消耗记录文件路径（可用环境变量 MODEL_USAGE_LOG 覆盖）
USAGE_LOG_ENV = "MODEL_USAGE_LOG"
DEFAULT_USAGE_LOG = "model_usage_history.jsonl"


def _usage_log_path() -> str:
    """获取消耗记录文件路径。"""
    return os.environ.get(USAGE_LOG_ENV, DEFAULT_USAGE_LOG)


def record_usage(
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_total: int = 0,
    cost: float | None = None,
    context: str = "",
    session_id: str = "",
) -> None:
    """
    记录一次对话的模型消耗，写入 JSONL 历史文件。

    Args:
        model: 使用的模型标识
        tokens_in: 输入 token 数
        tokens_out: 输出 token 数
        tokens_total: 总 token 数（若未传则自动计算）
        cost: 消耗费用（若已知）
        context: 调用场景描述
        session_id: 会话标识
    """
    if tokens_total <= 0 and (tokens_in > 0 or tokens_out > 0):
        tokens_total = tokens_in + tokens_out

    record = {
        "timestamp": datetime.now().isoformat(),
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "tokens_total": tokens_total,
        "cost": cost,
        "context": context,
        "session_id": session_id,
        "peak": is_peak_hour(),
    }

    try:
        log_path = _usage_log_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True) if os.path.dirname(log_path) else None
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass   # 记录失败不阻塞主流程


def read_usage_history(limit: int | None = None) -> list[dict]:
    """读取历史消耗记录，返回记录列表（新→旧）。"""
    records = []
    log_path = _usage_log_path()
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            continue
    except Exception:
        return []

    records.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    if limit and limit > 0:
        return records[:limit]
    return records


def summarize_usage() -> dict:
    """汇总历史消耗：按模型分组统计 token 量与条数。"""
    records = read_usage_history()
    by_model: dict[str, dict] = {}
    for r in records:
        m = r.get("model", "unknown")
        entry = by_model.setdefault(m, {"calls": 0, "tokens_total": 0, "cost": 0.0})
        entry["calls"] += 1
        entry["tokens_total"] += r.get("tokens_total", 0) or 0
        entry["cost"] += r.get("cost") or 0.0

    return {
        "total_calls": len(records),
        "by_model": by_model,
    }


# ============================================================
# 四、模型判断辅助
# ============================================================

def is_flash(model: str) -> bool:
    """判断给定模型标识是否为 Flash 档位。"""
    return "flash" in (model or "").lower()


def model_vendor(model: str) -> str:
    """返回模型所属厂商。"""
    for cfg in MODEL_POOL.values():
        if cfg["model"] == model:
            return cfg["vendor"]
    if "glm" in (model or "").lower():
        return "智谱 GLM"
    if "deepseek" in (model or "").lower():
        return "DeepSeek"
    return "unknown"


# ============================================================
# 五、自测
# ============================================================

if __name__ == "__main__":
    print("=== 统一模型配置自测 ===")
    print(f"  默认模型: {DEFAULT_MODEL}")
    print(f"  模型池: {[m['model'] for m in MODEL_POOL.values()]}")
    print(f"  高峰模型: {get_peak_model()}")
    print(f"  低峰模型: {get_offpeak_model()}")

    # 测试时段判断
    from datetime import datetime as _dt
    peak_t = _dt(2026, 9, 2, 10, 30)    # 周三 10:30 → 高峰
    off_t = _dt(2026, 9, 2, 22, 30)     # 周三 22:30 → 低峰
    weekend_t = _dt(2026, 9, 5, 10, 30)  # 周六 10:30 → 非工作日低峰

    assert is_peak_hour(peak_t), "工作日 10:30 应为高峰"
    assert not is_peak_hour(off_t), "工作日 22:30 应为低峰"
    assert not is_peak_hour(weekend_t), "周六 10:30 应为低峰（非工作日）"
    assert get_auto_model(peak_t) == get_peak_model(), "高峰应选 GLM"
    assert get_auto_model(off_t) == get_offpeak_model(), "低峰应选 DeepSeek"
    assert get_auto_model(weekend_t) == get_offpeak_model(), "周末应选 DeepSeek"

    print(f"  10:30(工作日) → {get_auto_model(peak_t)} ✅")
    print(f"  22:30(工作日) → {get_auto_model(off_t)} ✅")
    print(f"  10:30(周末)   → {get_auto_model(weekend_t)} ✅")

    # 测试消耗记录
    tmp_log = ".tmp_usage_test.jsonl"
    os.environ[USAGE_LOG_ENV] = tmp_log
    record_usage("glm-5.3-flash", tokens_in=100, tokens_out=50, context="自测")
    record_usage("deepseek-v4-flash-0731", tokens_in=200, tokens_out=100, cost=0.01, context="自测")
    recs = read_usage_history()
    assert len(recs) == 2, f"应读到 2 条记录，实际 {len(recs)}"
    summary = summarize_usage()
    assert summary["total_calls"] == 2, "汇总总调用应为 2"
    assert "glm-5.3-flash" in summary["by_model"], "汇总应含 GLM"
    assert "deepseek-v4-flash-0731" in summary["by_model"], "汇总应含 DeepSeek"
    print(f"  消耗记录: {summary}")
    print("  ✅ 消耗记录/汇总正常")

    # 清理测试文件
    if os.path.exists(tmp_log):
        os.remove(tmp_log)
    os.environ.pop(USAGE_LOG_ENV, None)

    # 测试自动切换开关
    os.environ[AUTO_SWITCH_ENV] = "false"
    assert get_auto_model(peak_t) == DEFAULT_MODEL, "关闭自动切换后应固定用默认模型"
    os.environ.pop(AUTO_SWITCH_ENV, None)
    print(f"  关闭自动切换 → {DEFAULT_MODEL} ✅")

    print("\n🟢 统一模型配置自测通过")
