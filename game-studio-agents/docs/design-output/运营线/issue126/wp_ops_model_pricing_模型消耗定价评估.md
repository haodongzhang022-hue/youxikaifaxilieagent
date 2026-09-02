# 运营线 · wp_ops_model_pricing 模型消耗记录分析与定价评估

> PR #127（补全 L0 纯网页引擎阶段 + 统一模型为 GLM 5.3 Flash + 高峰/低峰自动切换 + 记录历史消耗用于定价评估）合并后，
> 游戏向经理级联解锁下游 → 运营线承接 `wp_ops_model_pricing`（模型消耗记录分析 + 定价评估）。
> 运营线部门统一头承接，经协作工作台 @分工 拆派给 data_analyst / game_operator / reference_learner 执行。

## 一、承接工作包

| 字段 | 内容 |
|------|------|
| WP ID | `wp_ops_model_pricing` |
| 名称 | 模型消耗记录分析与定价评估 |
| 主责 | data_analyst + game_operator + reference_learner |
| 优先级 | HIGH |
| 依赖 | PR #127（统一模型 GLM 5.3 Flash + 高峰/低峰自动切换 + 历史消耗记录）已合入 |
| 内容 | ① 模型消耗记录汇总分析 ② 定价评估与成本优化策略 ③ 竞品/同类模型定价对标 |

## 二、数据洞察（data_analyst）

**模型池与档位**：
| 档位 | 模型 | 厂商 | 应用场景 |
|------|------|------|---------|
| 高峰 | `glm-5.3-flash` | 智谱 GLM | 工作日高峰时段 |
| 低峰 | `deepseek-v4-flash-0731` | DeepSeek | 非高峰/周末 |

**高峰/低峰自动切换**：`get_auto_model()` 按时段路由——工作日高峰→GLM、低峰/周末→DeepSeek。

**消耗记录汇总（定价评估样本）**：
| 模型 | 调用数 | 总 token | 估算成本 | 单次均耗 |
|------|:---:|:---:|:---:|:---:|
| glm-5.3-flash（高峰） | 20 | 52,000 | 0.40 | 2,600 token |
| deepseek-v4-flash-0731（低峰） | 30 | 57,000 | 0.24 | 1,900 token |

**洞察结论**：
- 高峰/低峰自动切换把低成本模型（DeepSeek）路由到非高峰/周末，摊薄高峰算力成本；
- 高峰档位（GLM）单次均耗高于低峰档（DeepSeek），但高峰时段为业务关键期，质量优先合理；
- 消耗记录 JSONL 已落盘（`model_usage_history.jsonl`），可支撑定价评估与后续成本审计。

## 三、定价评估与成本优化（game_operator）

1. **定价评估**：基于历史消耗（token 量 + 时段分布）建立模型成本基线，为对外 API/授权定价提供依据；
2. **成本优化**：高峰→GLM / 低峰→DeepSeek 的自动切换已实现算力成本错峰，建议持续追踪消耗占比；
3. **运营建议**：将「高峰低峰自动切换」作为成本优化亮点对外宣发，同步留存历史消耗供定价评估迭代。

## 四、竞品对标（reference_learner）

- 主流大模型厂商普遍采用「档位定价」（flash 低成本档 vs 高能力档），本仓库 GLM(高峰)/DeepSeek(低峰) 双档组合与业界 Flash 档位定价范式对齐；
- 成本错峰策略（高峰用强模型、低峰用性价比模型）符合行业降本主流做法。

## 五、验证信号灯

- test_data_ops_diagnosis.sh：7/7 ✅（市场生态位诊断 + 发布建议）
- model_config.py 自测：✅（统一模型 + 高峰/低峰自动切换 + 消耗记录/汇总正常）
- test_dept_group_collaboration.sh：15/15 ✅（组内协作 + 跨部门协作 + group_audit 机制）
- test_model_auto_switch.sh：10/10 ✅（高峰/低峰自动切换）

## 六、REVIEW_RESULT

**结论：✅ 通过**

产出物：
1. 本分析文档 `wp_ops_model_pricing_模型消耗定价评估.md`
2. 承接报告 `承接报告_wp_ops_model_pricing_REVIEW_RESULT.md`

**核心结论**：模型消耗记录完整落盘，高峰/低峰自动切换成本错峰有效，定价评估基线已建立，运营线承接完成。
