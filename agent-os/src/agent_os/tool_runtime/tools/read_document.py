"""Built-in tool: read_document — skeleton."""

from __future__ import annotations

from agent_os.db.models.tool_call import RiskLevel
from agent_os.tool_runtime.schemas import ToolCallResult, ToolDefinition

DEFINITION = ToolDefinition(
    name="read_document",
    description="读取知识库文档",
    input_schema={
        "type": "object",
        "properties": {
            "doc_id": {"type": "string", "description": "文档标识"},
        },
        "required": ["doc_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "metadata": {"type": "object"},
        },
    },
    permissions=["doc.read"],
    risk_level=RiskLevel.LOW,
    approval_required=False,
    timeout_sec=15,
    max_retries=1,
)


async def execute(args: dict) -> ToolCallResult:
    """读取文档内容。MVP 待实现。"""
    doc_id = args.get("doc_id", "")
    # TODO: 从知识库 / 文档存储读取
    raise NotImplementedError
