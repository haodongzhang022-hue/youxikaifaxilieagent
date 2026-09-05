"""
bandwidth_scheduler.py - 带宽感知调度器（无状态纯算法资产 · M-A 里程碑 · Issue #135）

防「云渲染限速 + 下载占满」双输。做成无状态策略 + 纯函数，
跨引擎各端（网页/小程序/Unity/UE）复用一个算法实现。

对齐 WP-02 §3.1 调度策略：
输入: is_cloud_active / download_pct / user_pref
输出: download_budget_ratio (下载限速档位，0-100 %)

规则:
  if 云会话激活 && 下载中:
      dl_budget = 剩余带宽 60-70%（优先保 WebRTC QoS）
      if pref = 画质优先: dl_budget = 剩余带宽 40-50%
      if pref = 下载优先: dl_budget = 剩余带宽 80%
  else (云关闭): dl_budget = 100% 全速
  下载达 90%+ 提前触发预释放信号
"""

# 用户偏好枚举
PREF_DEFAULT = "default"       # 平衡（默认）
PREF_QUALITY = "quality"       # 画质优先（更压下载）
PREF_DOWNLOAD = "download"     # 下载优先（更快下完）

# 预释放阈值：下载进度达 90%+ 提前释放云实例信号
PRE_RELEASE_THRESHOLD = 90.0

# 下载中允许的档位范围（云激活时）
QUALITY_LOW, QUALITY_HIGH = 40, 50
DEFAULT_LOW, DEFAULT_HIGH = 60, 70
DOWNLOAD_RATIO = 80

# 用户偏好映射：pref -> 允许的档位区间 (low, high)
_PREF_RANGES = {
    PREF_QUALITY: (QUALITY_LOW, QUALITY_HIGH),
    PREF_DEFAULT: (DEFAULT_LOW, DEFAULT_HIGH),
    PREF_DOWNLOAD: (DOWNLOAD_RATIO, DOWNLOAD_RATIO),
}


def schedule_download_budget(is_cloud_active: bool,
                             download_pct: float,
                             user_pref: str = PREF_DEFAULT) -> dict:
    """
    带宽感知调度主函数（纯函数，无副作用）。

    :param is_cloud_active: 云会话是否激活
    :param download_pct:    当前下载进度（0-100 %）
    :param user_pref:       用户偏好 (PREF_DEFAULT / PREF_QUALITY / PREF_DOWNLOAD)
    :return: dict {
        "download_budget_ratio": int  下载限速档位（0-100）,
        "cloud_budget_ratio": int     云渲染带宽占比（=100-下载档位）,
        "pre_release_signal": bool    是否触发 90%+ 预释放信号,
    }
    """
    download_pct = max(0.0, min(100.0, float(download_pct)))

    # 云未激活 -> 全速后台下载
    if not is_cloud_active:
        return {
            "download_budget_ratio": 100,
            "cloud_budget_ratio": 0,
            "pre_release_signal": download_pct >= PRE_RELEASE_THRESHOLD,
        }

    # 云激活 -> 依据用户偏好选择档位（取区间中值，避免边界抖动）
    low, high = _PREF_RANGES.get(user_pref, _PREF_RANGES[PREF_DEFAULT])
    ratio = (low + high) // 2
    return {
        "download_budget_ratio": ratio,
        "cloud_budget_ratio": 100 - ratio,
        "pre_release_signal": download_pct >= PRE_RELEASE_THRESHOLD,
    }
