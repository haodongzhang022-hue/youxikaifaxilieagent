# ============================================================
# 信息接口层 · 启动入口
# 版本: v0.9
# 说明: 启动 FastAPI 服务。
#
#   python3 api/main.py                  # 默认 127.0.0.1:8000（仅本机）
#   PORT=9000 python3 api/main.py        # 指定端口
#   HOST=0.0.0.0 API_TOKEN=<token> python3 api/main.py  # 跨机访问（务必配置鉴权）
#
#   /ai/*          AI 专用机器接口（供 AI 读取，结构化/低冗余/聚合/可溯源）
#   /dashboard/*   人类可视化通用接口（供前端渲染，L0-L3 渐进式）
#   /docs          交互式 API 文档（Swagger UI）
#
# 安全：默认仅绑定本机 127.0.0.1；需跨机访问时显式设 HOST=0.0.0.0，
#       并务必设置 API_TOKEN 启用 Bearer 鉴权，避免工作包/风险/事件信息泄露。
# ============================================================
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn  # noqa: E402

from app import app  # noqa: E402


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print("=" * 60)
    print("游戏开发指挥中枢 · 信息接口层 v0.9")
    print("  /ai/*         AI 专用机器接口")
    print("  /dashboard/*  人类可视化通用接口")
    print("  /docs         交互式 API 文档")
    print(f"服务地址: http://{host}:{port}")
    if not os.environ.get("API_TOKEN"):
        print("⚠ 注意: 未设置 API_TOKEN，接口无鉴权；跨机访问前务必配置。")
    print("=" * 60)
    uvicorn.run(app, host=host, port=port, reload=False)
