# wp_narrative_impl · 剧情/任务系统实现方案

- **工作包**：wp_narrative_impl 剧情/任务系统实现
- **部门**：程序线
- **主责角色**：client_dev + server_dev
- **模块**：narrative
- **产出物类型**：tech_doc（技术实现方案）

## 一、剧情系统实现

**客户端**：
- 对话系统：对话树编辑器 + 运行时解析器（YAML 配置驱动）
- 过场动画：Timeline 编排，支持剧情演出与战斗无缝衔接
- 角色表现：2D Live2D + 表情系统，动态角色卡展示

**服务端**：
- 剧情进度服务：按章节/任务节点持久化剧情推进状态
- 分支选择：分支节点记录选择，后续章节引用影响
- 剧情跳过/回看：已解锁剧情可回看，支持多周目

## 二、任务系统实现

**任务框架**：
- 任务类型：主线 / 支线 / 日常 / 成就
- 任务状态机：未接取 → 进行中 → 可提交 → 已提交 → 已关闭
- 条件系统：任务接受/提交/奖励的条件表达式引擎

**任务数据模型**：

```json
{
  "task_id": "t_001_narrative_act1",
  "type": "main",
  "title": "觉醒之路",
  "stages": [
    {
      "stage_id": "s1",
      "objectives": [
        {"type": "talk_npc", "target": "伊芙", "count": 1},
        {"type": "collect_item", "item": "星核碎片", "count": 5}
      ],
      "reward": {"exp": 100, "currency_soft": 500}
    }
  ],
  "next_task": "t_002_narrative_act1"
}
```

## 三、接口契约

```
GET  /api/v1/narrative/progress    获取剧情进度
POST /api/v1/narrative/advance     推进剧情节点
GET  /api/v1/task/list             获取任务列表
POST /api/v1/task/accept           接受任务
POST /api/v1/task/progress         上报任务进度
POST /api/v1/task/complete         提交任务
```

## 四、验证指标

- 剧情节点加载 < 500ms
- 对话翻页延迟 < 100ms
- 任务进度同步延迟 < 200ms
- 支持 1000 并发玩家同时推进剧情
