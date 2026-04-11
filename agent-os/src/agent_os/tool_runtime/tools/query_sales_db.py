"""Built-in tool: query_sales_db — skeleton."""

from __future__ import annotations

from agent_os.db.models.tool_call import RiskLevel
from agent_os.tool_runtime.schemas import ToolCallResult, ToolDefinition

DEFINITION = ToolDefinition(
    name="query_sales_db",
    description="查询销售数据库，支持 SQL SELECT 语句",
    input_schema={
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "SQL 查询语句，仅支持 SELECT"},
        },
        "required": ["sql"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "rows": {"type": "array"},
            "total": {"type": "integer"},
            "error": {"type": "string"},
        },
    },
    permissions=["data.read"],
    risk_level=RiskLevel.MEDIUM,
    approval_required=False,
    timeout_sec=30,
    max_retries=1,
)


async def execute(args: dict) -> ToolCallResult:
    """执行 SQL 查询。MVP 仅校验 SQL 关键字。"""
    sql = args.get("sql", "")
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        return ToolCallResult(
            tool_name="query_sales_db",
            status="failed",
            error="仅支持 SELECT 查询",
        )
    # TODO: 接入实际数据库连接执行查询
    raise NotImplementedError
