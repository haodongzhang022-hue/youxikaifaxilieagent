# 04. 创意工坊模组（Mod）数据规范

借鉴落地的统一载体是"模组（Mod）"。本规范定义 Mod 的目录结构、Manifest 字段与校验规则，保证任何 Mod 都**可插拔、可开关、可回滚**。

## 1. Mod 目录结构

```
mods/
└── <mod_id>/
    ├── manifest.yaml          # 元数据（必填）
    ├── visual/                # 视觉改造资源（可选）
    │   ├── ui/                #   UI 布局/样式
    │   ├── assets/            #   图片/图标/字体
    │   └── effects/           #   动效/镜头
    ├── presentation/          # 展现方式配置（可选）
    │   ├── hud.yaml           #   HUD 信息架构
    │   ├── guides/            #   引导/教程
    │   └── narrative/         #   叙事呈现
    ├── feature/               # 功能模块（可选）
    │   ├── logic/             #   玩法逻辑代码
    │   ├── systems/           #   系统配置/数值
    │   └── events/            #   事件循环
    └── preview/               # 预览截图/说明（推荐）
```

## 2. manifest.yaml 字段

```yaml
apiVersion: reference-mod/v1
kind: ReferenceMod

metadata:
  id: <mod_id>                  # 全局唯一
  name: <中文名>
  sourceGame: <来源游戏>
  borrowedMechanism: <借鉴机制>
  version: 1.0.0
  author: <作者/Agent>
  createdAt: <ISO8601>
  tags: [<玩法标签>]

scope:                            # 落地范围
  - visual                         # 视觉
  - presentation                   # 展现
  - feature                        # 功能

compatibility:                     # 兼容性
  baseGameVersion: <主游戏版本>
  conflicts: [<冲突的 Mod id>]
  requires: [<依赖的 Mod id>]

runtime:
  enabledByDefault: false
  safeToggle: true                # 是否支持运行时开关
  rollbackPoint: <回滚快照标识>

review:
  level: <L0|L1|L2|L3>
  status: pending|approved|rejected
```

## 3. 校验规则（Mod 必须满足）

- **隔离性**：Mod 只能引用 Manifest 声明的资源与系统，不得越权改主游戏基线。
- **可逆性**：必须声明 `rollbackPoint`，卸载时能恢复到主游戏基线。
- **可开关性**：`safeToggle: true` 时，运行时开关不得造成存档损坏。
- **完整性**：scope 声明了某项，就必须包含对应目录且能被沙盒加载。
- **合规性**：不得包含受版权/专利保护的美术或代码直拷（仅机制实现）。

## 4. Mod 生命周期

```
创建(草稿) → 沙盒验证(通过) → 审核(approved) → 发布(可启用)
                                    └─(rejected) → 打回修改/归档放弃
启用后：运行时开关 enabled/disabled
任意时刻：按 rollbackPoint 一键回滚到基线
```

## 5. 版本与快照

- 每个 Mod 独立版本号，遵循语义化版本（`MAJOR.MINOR.PATCH`）。
- 主游戏每次变更都生成基线快照，作为 Mod 回滚的参照点。
- Mod 列表统一登记在 `mods/manifest-index.yaml`，供游戏启动时加载。
