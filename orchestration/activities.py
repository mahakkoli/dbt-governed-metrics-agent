"""Activities: the real work, one per pipeline step.

Each activity runs a command in the project folder. Exit codes decide whether a
failure is worth retrying:
- Permanent (e.g. a failed dbt test): rerunning gives the same answer, so we
  raise a non-retryable error and stop immediately.
- Anything else (e.g. a crash or a locked database file): may be transient,
  so Temporal retries it with backoff.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANSI_COLORS = re.compile(r"\x1b\[[0-9;]*m")
# Prefer the dbt installed next to the running Python (the project's .venv)
DBT = shutil.which("dbt", path=str(Path(sys.executable).parent)) or shutil.which("dbt") or "dbt"


def _run(step: str, cmd: list[str], permanent_exit_codes: set[int]) -> str:
    activity.logger.info("Running %s (attempt %s)", step, activity.info().attempt)
    result = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    output = ANSI_COLORS.sub("", result.stdout + result.stderr).strip()
    summary = output.splitlines()[-1] if output else ""

    if result.returncode == 0:
        return summary
    if result.returncode in permanent_exit_codes:
        raise ApplicationError(
            f"{step} failed (exit {result.returncode}); retrying won't help: {summary}",
            non_retryable=True,
        )
    raise RuntimeError(f"{step} crashed (exit {result.returncode}): {summary}")


@activity.defn
def generate_data() -> str:
    # Demo switch: set PIPELINE_FLAKY=1 to make the first attempt fail,
    # so the retry shows up in the Temporal UI.
    if os.getenv("PIPELINE_FLAKY") == "1" and activity.info().attempt == 1:
        raise RuntimeError("Simulated transient failure: warehouse file locked")
    # The generator is idempotent (fixed seed, create-or-replace), so any failure is safe to retry.
    return _run("generate_data", [sys.executable, "generator/generate_data.py"], permanent_exit_codes=set())


@activity.defn
def dbt_build() -> str:
    # dbt exit code 1 = a model or test failed (permanent); 2 = unhandled error (may be transient)
    return _run("dbt_build", [DBT, "build"], permanent_exit_codes={1})


@activity.defn
def run_metric_tests() -> str:
    # pytest exit code 1 = tests failed (permanent)
    return _run("run_metric_tests", [sys.executable, "-m", "pytest", "-q", "metrics/"], permanent_exit_codes={1})
