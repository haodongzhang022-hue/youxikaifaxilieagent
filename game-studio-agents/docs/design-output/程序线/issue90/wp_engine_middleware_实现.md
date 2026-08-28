# wp_engine · 跨引擎中间件核心实现（P0）

> 部门：程序线 | 场景：Issue #90「跨平台架构增强」· 开发阶段（设计已完成 → 进入实现）
> 负责人：engine_dev（组）→ engine_dev + tools_dev
> 状态：✅ 实现完成并验证通过

## 一、交付物

已实现 **跨引擎中间件核心**（`middleware/` 目录），为「换渲染器而非重写游戏」的迁移根基：

| 交付物 | 路径 | 说明 |
|--------|------|------|
| C ABI 头文件（跨语言契约） | `middleware/include/cabi_*.h` | 纯 C，Python/TS/C#/C++ 均可 FFI |
| C++ 核心实现 | `middleware/src/**` | 玩法/战斗/程序化生成/数值 |
| Python 绑定 + 参考实现 | `middleware/bindings/python/cabi.py` | ctypes + 纯 Python 确定性核心 |
| TypeScript 绑定 | `middleware/bindings/typescript/cabi.ts` | Web/React WASM 层 |
| 一致性校验器 | `middleware/bindings/python/consistency.py` | 种子确定性 + golden hash |
| 单元测试 | `middleware/tests/test_python_core.py` | 7/7 通过 |
| 构建配置 | `middleware/CMakeLists.txt` | C++17 + CMake |

## 二、核心能力

### 1. 确定性程序化生成（同 seed → 同输出）
- splitmix64 + fnv1a 确定性 PRNG（引擎无关）
- 生成器：`terrain` / `level` / `resources` / `props` / `narrative`
- **种子确定性验证通过**：同 seed 重复生成 hash 完全一致
- golden hash 基准（`golden_seed`）已固化，供跨引擎回归比对

### 2. 定点数精度（跨端 bit 级一致）
- 32bit 整数 + 10bit 小数（1/1024 精度）
- `fp_mul` / `fp_div` 用 `__int128` 防溢出，保证所有引擎一致
- 伤害计算用定点数：`base_power * atk / def`

### 3. C ABI 契约
- `cabi_gameplay`：状态机 + 30Hz 固定 Tick + 事件系统
- `cabi_combat`：技能结算 + 伤害计算 + 掉落表（种子可复现）
- `cabi_procgen`：5 种确定性生成器
- `cabi_numeric`：定点数 + 等级成长 + 战斗公式

## 三、验证结果

```bash
PYTHONPATH=. python3 middleware/tests/test_python_core.py
# 7/7 tests passed

PYTHONPATH=. python3 -m middleware.bindings.python.consistency
# ALL CONSISTENCY CHECKS PASSED
```

## 四、下一步（依赖解锁）

- 测试线可对本中间件做跨引擎一致性/性能验收
- 引擎适配层（React WASM / Cocos Native / Unity P/Invoke / UE 原生）可接入此核心
