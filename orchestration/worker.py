"""Worker: polls the task queue and runs the workflow and activities. Leave it running."""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from orchestration.activities import dbt_build, generate_data, run_metric_tests
from orchestration.workflow import TASK_QUEUE, PipelineWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233")
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[PipelineWorkflow],
        activities=[generate_data, dbt_build, run_metric_tests],
        activity_executor=ThreadPoolExecutor(max_workers=4),  # activities are regular (sync) functions
    )
    print(f"Worker listening on '{TASK_QUEUE}'. Press Ctrl+C to stop.")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
