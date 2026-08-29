"""
client_core - 客户端纯逻辑类库（引擎无关）

对齐 Issue #112「游戏向架构师的开发」· wp_client 逻辑/表现分离。
核心设计：
  - 纯逻辑层不依赖任何引擎 API（Cocos/Unity/UE 均不依赖）
  - 引擎表现层通过 adapter 接口桥接
  - 核心逻辑可跨语言翻译（TS → C# → C++）
  - 数值/算法为纯数学，无 I/O 副作用
"""
__version__ = "1.0.0"
