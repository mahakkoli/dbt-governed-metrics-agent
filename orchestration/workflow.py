"""The pipeline workflow: generate data, build and test the dbt models, then test the metrics layer.

Workflow code only orchestrates: it decides order, timeouts and retries.
All real work (files, databases, commands) happens in activities.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from orchestration.activities import dbt_build, generate_data, run_metric_tests

TASK_QUEUE = "analytics-pipeline"

RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,  # wait 2s, then 4s
    maximum_attempts=3,
)


@workflow.defn
class PipelineWorkflow:
    @workflow.run
    async def run(self) -> dict[str, str]:
        results = {}
        for step, timeout in [
            (generate_data, timedelta(minutes=2)),
            (dbt_build, timedelta(minutes=10)),
            (run_metric_tests, timedelta(minutes=2)),
        ]:
            results[step.__name__] = await workflow.execute_activity(
                step, start_to_close_timeout=timeout, retry_policy=RETRY
            )
        return results
