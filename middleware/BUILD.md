# 构建说明

## 前置
- C++17 编译器（g++ / clang++）
- CMake >= 3.16

## 构建
```bash
cd middleware
mkdir -p build && cd build
cmake ..
make
ctest   # 运行 C++ 核心自测（test_core）
```

## 产物
- `libgame_middleware.a`：C++ 核心静态库（纯逻辑，引擎无关）
- `libgame_middleware_abi.so` / `.dll` / `.dylib`：C ABI 动态库（供各语言 FFI）
- WASM（Emscripten）：`game_middleware.wasm`（Web 端）

## Python 绑定
无 C 编译器时使用纯 Python 参考实现（确定性核心与 C++ 一致）：
```bash
PYTHONPATH=. python3 -m middleware.bindings.python.consistency
```

有编译产物时设 `GAME_MIDDLEWARE_LIB=libgame_middleware_abi.so` 走 ctypes 真 C++。
