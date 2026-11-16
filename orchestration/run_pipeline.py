"""Start one pipeline run and print each step's result."""

import asyncio
from datetime import datetime

from temporalio.client import Client

from orchestration.workflow import TASK_QUEUE, PipelineWorkflow


async def main() -> None:
    client = await Client.connect("localhost:7233")
    run_id = f"pipeline-{datetime.now():%Y%m%d-%H%M%S}"
    result = await client.execute_workflow(PipelineWorkflow.run, id=run_id, task_queue=TASK_QUEUE)
    print(f"{run_id} finished:")
    for step, summary in result.items():
        print(f"  {step}: {summary}")


if __name__ == "__main__":
    asyncio.run(main())
