# 策划线 · Issue #90 跨平台架构增强产出

> 场景：Issue #90「跨平台架构增强」派发策划线 4 个工作包，产出跨平台设计文档。
> 部门流水线顺序：策划 → 程序 → 美术 → 测试 → 项目管理 → 运营

## 产出物清单

| 工作包 | 主责角色 | 产出文件 |
|--------|---------|---------|
| wp_gameplay | lead_designer + system_designer + balance_designer | wp_gameplay_跨平台核心玩法架构.md |
| wp_numeric_model | balance_designer | wp_numeric_model_跨平台数值模型.md |
| wp_combat | combat_designer | wp_combat_引擎无关战斗机制.md |
| wp_narrative | narrative_designer | wp_narrative_跨平台叙事框架.md |

## 核心设计要点

1. **引擎无关抽象层**：玩法/战斗/叙事逻辑与引擎完全解耦，通过接口桥接 Web/Cocos/Unity/UE
2. **程序化生成引擎无关标准**：生成算法输出纯数据，各引擎适配器转换为原生对象
3. **数值一致性**：定点数精度 + 统一配置表 + 服务端权威时间
4. **素材复用**：基础素材通用格式存储，各引擎适配器负责转换
