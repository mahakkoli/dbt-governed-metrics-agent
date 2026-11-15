"""MCP server exposing the governed metrics layer to an AI agent.

The agent gets exactly three tools and no raw SQL access, so every number
it reports comes from a definition in metrics/metrics.yml.
"""

from __future__ import annotations

import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from metrics.metrics import MetricError, describe_metric, list_metrics, query_metric  # noqa: E402

ANSWERING_RULES = """\
You answer business questions using governed metrics only. Rules:
1. Data covers 2025-04-01 to 2026-09-01. Always say which period an answer covers.
2. If the user gives no period: for "current", "typical" or "now" questions use the
   latest month (2026-09-01); for totals, say you used the full range.
3. For growth questions, state the two periods you compared. Mention anything left out
   because it didn't exist in the earlier period (e.g. accounts that signed up later),
   and flag percentage growth from a very small base.
4. If no metric directly answers the question, say so first. If you then infer an
   answer from other metrics, label it clearly as an inference and explain its limits.
5. Use each row's `display` value when quoting numbers.
"""

mcp = MCPServer("cloud-usage-metrics", instructions=ANSWERING_RULES)

USD_METRICS = {"revenue", "revenue_per_active_account"}


def humanize(value: float, usd: bool = False) -> str:
    """Readable version of a number: 11300000000 -> '11.3B', 245328 -> '$245.3K'."""
    sign = "-" if value < 0 else ""
    value = abs(value)
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if value >= size:
            text = f"{value / size:.1f}".rstrip("0").rstrip(".") + suffix
            break
    else:
        text = f"{value:,.2f}".rstrip("0").rstrip(".") if value % 1 else f"{value:,.0f}"
    return f"{sign}${text}" if usd else f"{sign}{text}"


@mcp.tool(name="list_metrics")
def list_metrics_tool() -> list[dict]:
    """List every governed metric with its label and description.

    Call this first to find which metric answers the user's question.
    """
    return list_metrics()


@mcp.tool(name="describe_metric")
def describe_metric_tool(name: str) -> dict:
    """Show a metric's exact definition, the time grains it supports, and the
    dimensions it can be grouped or filtered by. Use it to explain an answer."""
    try:
        return describe_metric(name)
    except MetricError as exc:
        return {"error": str(exc)}


@mcp.tool(name="query_metric")
def query_metric_tool(
    name: str,
    time_grain: str | None = "month",
    group_by: list[str] | None = None,
    filters: dict[str, str | list[str]] | None = None,
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """Get numbers for one governed metric. This is the only way to get data.

    Each row includes a readable `display` value (e.g. "11.3B", "$245.3K").
    Use the display values when answering; use the raw numbers only for math.

    Args:
        name: metric name from list_metrics, e.g. "revenue".
        time_grain: "month", "quarter", "year", or null for a single total.
        group_by: dimensions to break down by, e.g. ["region"] or ["plan"].
        filters: dimension values to keep, e.g. {"plan": "business"} or {"region": ["eu-west", "us-east"]}.
        start: first month to include, as YYYY-MM-DD (data runs 2025-04-01 to 2026-09-01).
        end: last month to include, as YYYY-MM-DD.
    """
    try:
        rows = query_metric(
            name, time_grain=time_grain, group_by=group_by, filters=filters, start=start, end=end
        )
        for row in rows:
            value = row.get(name)
            if isinstance(value, (int, float)):
                row["display"] = humanize(value, usd=name in USD_METRICS)
        return {"metric": name, "definition": describe_metric(name)["sql"], "rows": rows}
    except MetricError as exc:
        return {"error": str(exc)}


if __name__ == "__main__":
    mcp.run()