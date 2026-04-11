"""Metrics definitions — OpenTelemetry counters and histograms."""

from __future__ import annotations

from opentelemetry import metrics

meter = metrics.get_meter("agent-os")

task_total = meter.create_counter(
    name="agent_os.task.total",
    description="Total tasks submitted",
)

task_success = meter.create_counter(
    name="agent_os.task.success",
    description="Tasks completed successfully",
)

task_failed = meter.create_counter(
    name="agent_os.task.failed",
    description="Tasks that failed",
)

model_cost = meter.create_histogram(
    name="agent_os.model.cost_usd",
    description="Model call cost in USD",
    unit="USD",
)
