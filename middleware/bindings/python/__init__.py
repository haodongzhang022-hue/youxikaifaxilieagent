"""跨引擎中间件 Python 绑定包（原型层）"""
from .cabi import GameMiddleware, MiddlewareError
__all__ = ["GameMiddleware", "MiddlewareError"]
