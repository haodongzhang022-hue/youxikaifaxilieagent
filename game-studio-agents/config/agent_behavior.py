# ============================================================
# 游戏开发 Agent 行为逻辑框架
# 版本: v0.1
# 说明: 定义 Agent 的通用行为逻辑模式，
#       包括决策流程、状态机、消息处理和协作协议。
# 语言: 伪代码 / 结构化定义
# ============================================================

"""
============================================================
Agent 行为逻辑通用架构
============================================================

每个 Agent 由以下核心组件组成：

┌─────────────────────────────────────────────────────┐
│                    Agent Core                        │
├────────────┬────────────┬────────────┬──────────────┤
│  Knowledge │  Decision  │   State    │   Message    │
│    Base    │   Engine   │  Machine   │    Handler   │
│  (知识库)   │ (决策引擎)  │  (状态机)  │  (消息处理)   │
├────────────┴────────────┴────────────┴──────────────┤
│                 Task Executor (任务执行器)           │
├─────────────────────────────────────────────────────┤
│             Output / Artifacts (产出物)              │
└─────────────────────────────────────────────────────┘
"""

# ============================================================
# 1. Agent 通用生命周期
# ============================================================

AGENT_LIFECYCLE = {
    "states": [
        "BOOT",           # 启动，加载配置与知识库
        "IDLE",           # 空闲，等待任务
        "RECEIVING",      # 接收任务/消息
        "ANALYZING",      # 分析需求
        "PLANNING",       # 制定计划
        "EXECUTING",      # 执行任务
        "VERIFYING",      # 验证产出
        "DELIVERING",     # 交付产出
        "WAITING_REVIEW", # 等待上级审核
        "HANDLING_FEEDBACK", # 处理反馈
        "REPORTING",      # 汇报状态
        "ERROR",          # 异常状态
        "STOPPED"         # 停止
    ],
    "transitions": {
        "BOOT": ["IDLE"],
        "IDLE": ["RECEIVING", "REPORTING", "STOPPED"],
        "RECEIVING": ["ANALYZING", "IDLE"],
        "ANALYZING": ["PLANNING", "ERROR"],
        "PLANNING": ["EXECUTING", "ANALYZING"],
        "EXECUTING": ["VERIFYING", "ERROR"],
        "VERIFYING": ["DELIVERING", "EXECUTING", "ERROR"],
        "DELIVERING": ["WAITING_REVIEW", "IDLE"],
        "WAITING_REVIEW": ["IDLE", "HANDLING_FEEDBACK"],
        "HANDLING_FEEDBACK": ["EXECUTING", "DELIVERING", "REPORTING"],
        "REPORTING": ["IDLE"],
        "ERROR": ["ANALYZING", "IDLE", "STOPPED"]
    }
}


# ============================================================
# 2. Agent 通用行为循环
# ============================================================

def agent_main_loop(agent):
    """
    Agent 主循环：监听消息 → 处理 → 执行 → 交付
    """
    while agent.status != "STOPPED":
        # 1. 监听消息
        message = agent.listen()
        if message:
            # 2. 解析消息
            intent = agent.parse_message(message)

            # 3. 更新状态机
            agent.state_machine.transition(intent)

            # 4. 处理任务
            result = agent.process(intent, message)

            # 5. 产出与交付
            agent.deliver(result)

            # 6. 上报状态
            agent.report_status()

        # 心跳检测
        agent.heartbeat()


# ============================================================
# 3. Agent 决策引擎模式
# ============================================================

class DecisionEngine:
    """
    决策引擎：混合规则 + 知识库 + LLM 推理
    """

    def __init__(self, agent):
        self.agent = agent
        self.rules = agent.config["rules"]          # 规则集
        self.knowledge = agent.knowledge_base        # 知识库
        self.llm = agent.llm                         # 大模型推理（可选）

    def decide(self, context):
        """
        决策流程：
        1. 规则匹配（快速路径）
        2. 知识库查询（辅助信息）
        3. LLM 推理（复杂决策）
        4. 输出决策 + 理由
        """
        # 第一步：规则匹配
        for rule in self.rules:
            if self._match_rule(rule, context):
                return self._execute_rule(rule, context)

        # 第二步：知识库辅助
        knowledge_hits = self.knowledge.query(context)
        context["knowledge"] = knowledge_hits

        # 第三步：LLM 推理（复杂决策）
        if self._needs_llm(context):
            decision = self.llm.reason(context)
            return {
                "decision": decision["action"],
                "reason": decision["reasoning"],
                "confidence": decision["confidence"],
                "source": "llm_reasoning"
            }

        # 默认：返回可选方案 + 推荐
        return {
            "decision": "NEED_HUMAN_REVIEW",
            "options": self._generate_options(context),
            "reason": "无法自动决策，需要人工确认",
            "source": "unknown"
        }

    def _match_rule(self, rule, context):
        """规则匹配：判断当前上下文是否触发规则"""
        conditions = rule.get("conditions", [])
        return all(
            context.get(cond["key"]) == cond["value"]
            for cond in conditions
        )

    def _needs_llm(self, context):
        """判断是否需要用 LLM 推理"""
        complexity = context.get("complexity", 0)
        return complexity > 5  # 复杂度阈值


# ============================================================
# 4. Agent 消息通信协议
# ============================================================

MESSAGE_TYPES = {
    "TASK_ASSIGN": {
        "description": "分配任务",
        "required_fields": ["task_id", "assignee", "inputs", "deadline", "priority"]
    },
    "TASK_REVIEW": {
        "description": "任务审核请求",
        "required_fields": ["task_id", "submitter", "artifacts", "review_notes"]
    },
    "REVIEW_RESULT": {
        "description": "审核结果",
        "required_fields": ["review_id", "result", "comments", "revise_requirements"]
    },
    "ARTIFACT_DELIVERY": {
        "description": "产出物交付",
        "required_fields": ["task_id", "artifact_type", "artifact_url", "metadata"]
    },
    "BUG_REPORT": {
        "description": "Bug 报告",
        "required_fields": ["bug_id", "severity", "description", "steps", "expected", "actual"]
    },
    "APPROVAL_REQUEST": {
        "description": "审批请求",
        "required_fields": ["request_id", "approver", "subject", "context"]
    },
    "APPROVAL_RESULT": {
        "description": "审批结果",
        "required_fields": ["request_id", "approved", "comments"]
    },
    "STATUS_REPORT": {
        "description": "状态汇报",
        "required_fields": ["agent_id", "status", "progress", "blockers"]
    },
    "NOTIFICATION": {
        "description": "通知消息",
        "required_fields": ["notification_id", "type", "content"]
    }
}


# 消息示例
MESSAGE_EXAMPLE = {
    "id": "msg_20260101_001",
    "type": "TASK_ASSIGN",
    "from": "lead_designer",
    "to": "system_designer",
    "task_id": "task_001",
    "inputs": {
        "title": "背包系统设计",
        "requirement": "支持物品分类、堆叠、使用、丢弃",
        "constraints": ["存储上限1000格", "支持离线整理"]
    },
    "deadline": "2026-01-15",
    "priority": "HIGH",
    "timestamp": "2026-01-01T09:00:00Z"
}


# ============================================================
# 5. Agent 协作流程模板
# ============================================================

def collaboration_workflow(workflow_type):
    """
    协作流程模板
    """
    workflows = {
        # ---- 策划 → 程序 → 测试 主流水线 ----
        "feature_pipeline": [
            {"step": "lead_designer.define",        "desc": "主策划定义功能需求"},
            {"step": "system_designer.design",      "desc": "系统策划设计详细方案"},
            {"step": "ui_ux.design_ui",             "desc": "UI/UX 设计界面"},
            {"step": "client_dev.implement",        "desc": "客户端程序实现功能"},
            {"step": "server_dev.implement",        "desc": "服务端程序实现逻辑"},
            {"step": "qa_engineer.test",            "desc": "测试工程师验证质量"},
            {"step": "project_manager.accept",      "desc": "项目经理验收完成"}
        ],

        # ---- Bug 处理流程 ----
        "bug_fix_pipeline": [
            {"step": "qa_engineer.report",          "desc": "QA 报告 Bug"},
            {"step": "project_manager.triage",      "desc": "PM 分类定级"},
            {"step": "client_dev.fix",              "desc": "客户端程序修复"},
            {"step": "qa_engineer.verify",          "desc": "QA 回归验证"},
            {"step": "release_manager.release",     "desc": "版本管理发版"}
        ],

        # ---- 版本发布流程 ----
        "release_pipeline": [
            {"step": "release_manager.plan",        "desc": "版本管理规划"},
            {"step": "qa_engineer.test_all",        "desc": "全量测试"},
            {"step": "release_manager.gate",        "desc": "版本门禁检查"},
            {"step": "release_manager.release",     "desc": "发布执行"},
            {"step": "data_analyst.monitor",        "desc": "数据监控验证"}
        ]
    }
    return workflows.get(workflow_type, [])


# ============================================================
# 6. 核心岗位 Agent 行为逻辑示例
# ============================================================

"""
以下为关键岗位的 Agent 行为逻辑详细定义
"""

# ---------- 6.1 系统策划 Agent ----------
SYSTEM_DESIGNER_BEHAVIOR = {
    "agent_id": "system_designer",
    "input_accept": ["TASK_ASSIGN", "REVIEW_RESULT"],
    "input_emits": ["ARTIFACT_DELIVERY", "TASK_REVIEW", "STATUS_REPORT"],

    "behavior": {
        "on_TASK_ASSIGN": """
            1. 解析任务：提取需求、约束、截止时间
            2. 检查知识库：搜索类似系统设计模板
            3. 制定设计计划：规则设计→交互设计→数据设计
            4. 执行设计：生成设计文档（含规则、流程、异常处理）
            5. 自检：完整性检查（规则覆盖、边界情况、数据一致性）
            6. 提交审核：TASK_REVIEW 发给主策划
            7. 等待反馈：收到 REVIEW_RESULT 后处理修订意见
        """,
        "on_REVIEW_RESULT": """
            1. 解析审核意见：通过 / 打回 + 修订要求
            2. 若通过：交付产出物 ARTIFACT_DELIVERY
            3. 若打回：按修订要求重新设计 → 再次提交
            4. 更新知识库：记录本次设计经验
        """
    },

    "decision_rules": [
        {
            "name": "设计完整性检查",
            "conditions": [
                {"key": "rule_coverage", "op": ">=", "value": 0.9},
                {"key": "edge_cases", "op": ">=", "value": 3},
                {"key": "data_consistent", "op": "==", "value": True}
            ],
            "action": "PASS_REVIEW",
            "fallback": "REVISE_DESIGN"
        },
        {
            "name": "复杂度控制",
            "conditions": [
                {"key": "system_complexity", "op": "<=", "value": 7}
            ],
            "action": "ACCEPT",
            "fallback": "SIMPLIFY"
        }
    ]
}


# ---------- 6.2 客户端程序员 Agent ----------
CLIENT_DEV_BEHAVIOR = {
    "agent_id": "client_dev",
    "input_accept": ["TASK_ASSIGN", "BUG_REPORT", "REVIEW_RESULT"],
    "input_emits": ["ARTIFACT_DELIVERY", "TASK_REVIEW", "STATUS_REPORT", "BUG_FIXED"],

    "behavior": {
        "on_TASK_ASSIGN": """
            1. 解析任务：设计文档、需求、技术约束
            2. 技术方案：选择实现技术路线
            3. 编码实现：按设计文档实现功能
            4. 自测：编写单元测试并执行
            5. 代码检查：静态分析 + 规范检查
            6. 提交审核：CodeReview 给技术总监
            7. 联调：与策划/美术联调
            8. 交付：ARTIFACT_DELIVERY 给 QA
        """,
        "on_BUG_REPORT": """
            1. 解析 Bug：严重度、复现步骤
            2. 定位问题：分析代码定位根因
            3. 修复：编写修复代码
            4. 回归：验证修复效果
            5. 反馈：BUG_FIXED + 修复说明
        """,
        "on_REVIEW_RESULT": """
            1. 通过：进入联调/交付
            2. 打回：按意见修改 → 重新提交
        """
    },

    "decision_rules": [
        {
            "name": "代码质量门禁",
            "conditions": [
                {"key": "test_coverage", "op": ">=", "value": 0.8},
                {"key": "static_analysis_passed", "op": "==", "value": True},
                {"key": "no_critical_bug", "op": "==", "value": True}
            ],
            "action": "PASS_REVIEW",
            "fallback": "FIX_AND_RETRY"
        },
        {
            "name": "性能指标",
            "conditions": [
                {"key": "fps", "op": ">=", "value": 60},
                {"key": "memory_usage", "op": "<=", "value": "80%"}
            ],
            "action": "ACCEPT",
            "fallback": "OPTIMIZE"
        }
    ]
}


# ---------- 6.3 QA 测试 Agent ----------
QA_BEHAVIOR = {
    "agent_id": "qa_engineer",
    "input_accept": ["ARTIFACT_DELIVERY", "BUG_FIXED"],
    "input_emits": ["BUG_REPORT", "TASK_REVIEW", "STATUS_REPORT", "QUALITY_REPORT"],

    "behavior": {
        "on_ARTIFACT_DELIVERY": """
            1. 接收版本/功能交付物
            2. 分析需求与设计文档
            3. 编写测试用例（功能/边界/异常）
            4. 执行测试
            5. 记录 Bug 并提交 BUG_REPORT
            6. 编写质量报告 QUALITY_REPORT
            7. 质量评估：放行 or 打回
        """,
        "on_BUG_FIXED": """
            1. 验证修复：按原复现步骤回归
            2. 验证通过：关闭 Bug
            3. 验证失败：重新激活 Bug
        """
    },

    "decision_rules": [
        {
            "name": "版本放行判断",
            "conditions": [
                {"key": "critical_bug_count", "op": "==", "value": 0},
                {"key": "high_bug_count", "op": "<=", "value": 5},
                {"key": "test_coverage", "op": ">=", "value": 0.9}
            ],
            "action": "RELEASE",
            "fallback": "HOLD_VERSION"
        }
    ]
}


# ---------- 6.4 项目经理 Agent ----------
PM_BEHAVIOR = {
    "agent_id": "project_manager",
    "input_accept": ["STATUS_REPORT", "APPROVAL_REQUEST", "BUG_REPORT"],
    "input_emits": ["TASK_ASSIGN", "APPROVAL_RESULT", "NOTIFICATION", "STATUS_REPORT"],

    "behavior": {
        "on_STATUS_REPORT": """
            1. 收集各岗位状态
            2. 分析进度偏差
            3. 识别阻塞与风险
            4. 更新项目计划
            5. 必要时协调资源
        """,
        "on_APPROVAL_REQUEST": """
            1. 审核请求内容
            2. 检查与项目目标一致性
            3. 资源/进度影响评估
            4. 决策：批准 / 拒绝 / 需调整
            5. 发送 APPROVAL_RESULT
        """
    },

    "decision_rules": [
        {
            "name": "进度风险预警",
            "conditions": [
                {"key": "schedule_delay", "op": ">=", "value": "2 days"}
            ],
            "action": "ESCALATE",
            "fallback": "TRACK_NORMAL"
        }
    ]
}


# ============================================================
# 7. 跨 Agent 协作时序图（伪代码）
# ============================================================

def feature_development_sequence():
    """
    功能开发完整协作时序
    """
    sequence = [
        # 阶段1: 需求定义
        ("producer", "lead_designer", "TASK_ASSIGN", {"task": "define_game_vision"}),
        ("lead_designer", "system_designer", "TASK_ASSIGN", {"task": "design_backpack_system"}),

        # 阶段2: 设计
        ("system_designer", "lead_designer", "TASK_REVIEW", {"design_doc": "backpack_design.md"}),
        ("lead_designer", "system_designer", "REVIEW_RESULT", {"result": "APPROVED"}),
        ("system_designer", "ui_ux", "TASK_ASSIGN", {"task": "design_ui"}),
        ("system_designer", "client_dev", "TASK_ASSIGN", {"task": "implement_system"}),
        ("system_designer", "server_dev", "TASK_ASSIGN", {"task": "implement_logic"}),

        # 阶段3: 实现
        ("ui_ux", "client_dev", "ARTIFACT_DELIVERY", {"ui_resources": "ui_package.zip"}),
        ("client_dev", "tech_director", "TASK_REVIEW", {"code": "client_code"}),
        ("tech_director", "client_dev", "REVIEW_RESULT", {"result": "APPROVED"}),
        ("client_dev", "qa_engineer", "ARTIFACT_DELIVERY", {"build": "client_v1.2.3"}),

        # 阶段4: 测试
        ("qa_engineer", "client_dev", "BUG_REPORT", {"bug": "items_cannot_stack"}),
        ("client_dev", "qa_engineer", "BUG_FIXED", {"fix": "fixed_stacking_logic"}),
        ("qa_engineer", "project_manager", "QUALITY_REPORT", {"report": "all_tests_passed"}),

        # 阶段5: 验收
        ("project_manager", "producer", "STATUS_REPORT", {"progress": "feature_complete"}),
        ("producer", "project_manager", "APPROVAL_RESULT", {"result": "APPROVED"})
    ]
    return sequence


# ============================================================
# 8. Agent 异常处理模式
# ============================================================

class ErrorHandler:
    """
    异常处理模式
    """
    def __init__(self, agent):
        self.agent = agent
        self.max_retries = 3
        self.escalation_threshold = 2

    def handle_error(self, error, context):
        """
        异常处理策略：
        1. 分类错误
        2. 重试机制
        3. 降级处理
        4. 升级给上级
        """
        error_type = self._classify(error)

        if error_type == "TRANSIENT":    # 暂时性错误
            return self._retry(context)

        if error_type == "CONFIG":        # 配置错误
            return self._reload_config(context)

        if error_type == "DEPENDENCY":    # 依赖缺失
            return self._request_resource(context)

        if error_type == "CRITICAL":      # 严重错误
            return self._escalate(context)

        return self._escalate(context)

    def _retry(self, context):
        """重试机制"""
        retry_count = context.get("retry_count", 0)
        if retry_count < self.max_retries:
            return {"action": "RETRY", "delay": 2 ** retry_count}
        return self._escalate(context)

    def _escalate(self, context):
        """升级给上级"""
        return {
            "action": "ESCALATE",
            "to": context.get("superior", "project_manager"),
            "error_info": context.get("error", {})
        }


# ============================================================
# 9. 知识库管理
# ============================================================

class KnowledgeBase:
    """
    Agent 知识库：存储岗位领域知识、历史经验、决策依据
    """
    def __init__(self, agent_id):
        self.agent_id = agent_id
        self.documents = {}
        self.experience = []       # 历史经验
        self.templates = {}        # 模板库

    def query(self, context):
        """查询相关知识"""
        results = []
        for doc in self.documents.values():
            if self._match(doc, context):
                results.append(doc)
        return results

    def learn(self, experience):
        """记录经验"""
        self.experience.append({
            "timestamp": time.now(),
            "context": experience["context"],
            "action": experience["action"],
            "result": experience["result"]
        })

    def get_template(self, template_type):
        """获取模板"""
        return self.templates.get(template_type)


# ============================================================
# 10. 迭代路线图
# ============================================================

ITERATION_ROADMAP = {
    "v0.1": "岗位定义 + 行为逻辑框架（本文件）",
    "v0.2": "Agent消息通信协议实现（消息总线/队列）",
    "v0.3": "单个Agent的自动执行（如系统策划可自动写设计文档）",
    "v0.4": "多Agent协作流水线（策划→程序→测试自动流转）",
    "v0.5": "质量闭环（自动测试+自动反馈+自动迭代）",
    "v0.6": "数据驱动决策（数值调优自动化）",
    "v0.7": "全流程Agent替代 + 人工监督模式"
}
