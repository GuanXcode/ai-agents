# Agent OS 技术实现指南（MVP 版）

本文档给出一个可落地的 Agent OS 技术方案，目标是在 4~8 周内做出可运行、可观测、可治理的最小系统。

## 1. 目标与边界

### 1.1 目标

- 支持单 Agent 到多 Agent 的任务执行
- 支持工具调用、状态持久化与失败重试
- 提供基础安全控制、日志追踪与成本监控

### 1.2 非目标

- 不追求一次性覆盖所有业务场景
- 不实现复杂自治策略（先人机协同）
- 不绑定单一模型厂商

## 2. 参考架构

```text
[Client/API]
    |
    v
[Gateway]
    |
    v
[Orchestrator] <----> [Policy Engine]
    |   |   \
    |   |    \----> [Memory Service] ----> [Vector DB / KV / SQL]
    |   |
    |   \-------> [Tool Runtime] -------> [Internal APIs / SaaS / Code Sandbox]
    |
    \-----------> [Model Router] -------> [LLM Providers]

All services -> [Observability Stack: logs, traces, metrics, eval]
```

## 3. 核心模块设计

### 3.1 Gateway（入口层）

- 职责：鉴权、限流、请求标准化、租户隔离
- 输入：`task_request`
- 输出：内部统一任务对象 `task_envelope`

建议接口：

```json
{
  "task_id": "uuid",
  "tenant_id": "t_001",
  "user_id": "u_001",
  "goal": "生成本周销售分析",
  "constraints": {
    "budget_usd": 2.0,
    "deadline_sec": 120
  },
  "context_refs": ["doc:weekly_sales", "sheet:q1_pipeline"]
}
```

### 3.2 Orchestrator（编排层）

- 职责：任务拆解、步骤调度、重试、超时、回滚
- 关键能力：
- 状态机：`PENDING -> RUNNING -> WAITING_HUMAN -> SUCCEEDED/FAILED`
- 幂等执行：基于 `task_id + step_id`
- 重试策略：指数退避 + 最大重试次数

### 3.3 Model Router（模型路由）

- 职责：按任务类型选择模型，控制成本与延迟
- 路由规则示例：
- 规划类任务：高推理模型
- 信息抽取：轻量模型
- 代码执行：代码专长模型

### 3.4 Tool Runtime（工具运行时）

- 职责：统一工具注册、参数校验、权限检查、执行与结果回传
- 最佳实践：
- 工具输入输出统一 JSON Schema
- 所有写操作要求 `approval_required=true`
- 每次调用记录审计日志（谁、何时、调用什么、结果如何）

工具注册示例：

```json
{
  "name": "query_sales_db",
  "description": "查询销售数据",
  "input_schema": {
    "type": "object",
    "properties": {
      "sql": {"type": "string"}
    },
    "required": ["sql"]
  },
  "permissions": ["data.read"],
  "risk_level": "medium"
}
```

### 3.5 Memory Service（记忆服务）

- 短期记忆：当前会话上下文（最近 N 轮）
- 长期记忆：用户偏好、历史任务摘要、知识片段
- 建议策略：
- 写入前摘要化，避免无序膨胀
- 读取时按 `task_intent + tenant_scope` 检索

### 3.6 Policy Engine（策略与治理）

- 职责：在执行前和执行中做策略判定
- 核心策略：
- 预算上限（token/cost）
- 数据边界（租户隔离、字段脱敏）
- 工具白名单（角色级别）
- 高风险动作人工确认

### 3.7 Observability（可观测）

- 日志：结构化 JSON，最少包含 `trace_id/task_id/step_id`
- 指标：成功率、P95 延迟、单任务成本、工具失败率
- 追踪：一步一 Trace Span，关联模型调用与工具调用
- 评估：离线基准集 + 在线抽样回放

## 4. 数据模型（最小集合）

### 4.1 tasks

- `task_id` (PK)
- `tenant_id`
- `status`
- `goal`
- `created_at`
- `updated_at`

### 4.2 task_steps

- `step_id` (PK)
- `task_id` (FK)
- `agent_role`
- `action_type` (`plan|reason|tool_call|human_gate`)
- `input`
- `output`
- `status`
- `cost_tokens`

### 4.3 tool_calls

- `call_id` (PK)
- `task_id` (FK)
- `tool_name`
- `args_json`
- `result_json`
- `risk_level`
- `approved_by`

## 5. 运行流程（单任务）

1. 客户端提交任务到 Gateway
2. Gateway 完成鉴权并生成 `task_envelope`
3. Orchestrator 创建执行计划（steps）
4. 每个 step 进入 Model Router 推理或 Tool Runtime 执行
5. Policy Engine 对高风险 step 触发人工确认
6. 结果写入 Memory 与任务存储
7. Observability 记录全链路日志和指标
8. 返回最终结果与执行摘要

## 6. 安全与合规基线

- 最小权限：默认拒绝，按角色放行
- 敏感数据：传输与存储加密，日志脱敏
- 审计可追溯：保留任务级调用证据链
- 租户隔离：数据库行级策略 + 存储命名空间隔离

## 7. MVP 里程碑（4 周示例）

### Week 1

- 完成 Gateway、Task Schema、基础任务状态机
- 接入 1 个模型提供方

### Week 2

- 完成 Tool Runtime（2~3 个只读工具）
- 接入基础记忆检索（向量库或 KV）

### Week 3

- 上线 Policy Engine（预算、白名单、人工确认）
- 打通 Trace/Metric/Log

### Week 4

- 建立评测集和回归流程
- 小流量灰度发布，收集失败样本迭代

## 8. 验收标准（建议）

- 任务成功率 >= 85%（定义明确的任务集）
- 高风险写操作 100% 经过策略校验
- 单任务全链路可追踪（trace 覆盖率 100%）
- 平均成本与延迟在预算范围内

## 9. 后续演进方向

- 多 Agent 协作图（Planner/Executor/Reviewer）
- 记忆质量评估与自动压缩
- 自动化故障归因（模型、工具、数据、策略）
- A/B 路由与策略实验平台

