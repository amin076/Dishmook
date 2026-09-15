"""Small offline CLI: schema export and a fixture-only bootstrap smoke check."""

import argparse
import json
import sys
import sqlite3
from pathlib import Path

from pydantic import ValidationError

from dishmook import __version__
from dishmook.domain import Agent, Claim, Evidence, Problem, Run, Task
from dishmook.inference import FakeModelBackend

ENTITIES = {cls.__name__.lower(): cls for cls in (Problem, Agent, Task, Claim, Evidence, Run)}


def smoke(seed: int) -> dict:
    problem = Problem(problem_id="smoke-problem", title="Infrastructure fixture",
                      statement="Check the offline data contracts; do not solve science.")
    agent = Agent(agent_id="smoke-agent", role="Fixture reviewer", instructions="Produce fake output only.")
    task = Task(task_id="smoke-task", problem_id=problem.problem_id,
                agent_id=agent.agent_id, input_text=problem.statement)
    run = Run(run_id="smoke-run", problem_id=problem.problem_id, seed=seed,
              active_agents=[agent.agent_id])
    claim = FakeModelBackend().generate(problem, agent, task, run)
    run.status = "completed"
    return {"run": run.model_dump(), "claim": claim.model_dump(),
            "notice": "Phase 0 fixture only. No model inference, persistence, resume or tool execution."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dishmook")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    from dishmook.research_cli import COMMANDS, dispatch, register
    register(sub)
    check = sub.add_parser("smoke", help="Run the offline Fake Backend fixture")
    check.add_argument("--seed", type=int, default=0)
    schema = sub.add_parser("schema", help="Print an entity JSON Schema")
    schema.add_argument("entity", choices=ENTITIES)
    launch = sub.add_parser("run", help="Execute one offline single-agent problem")
    launch.add_argument("--spec", type=Path, required=True)
    launch.add_argument("--runs-dir", type=Path, default=Path("runs"))
    launch.add_argument("--run-id")
    launch.add_argument("--prepare-only", action="store_true")
    resume_parser = sub.add_parser("resume", help="Resume an existing immutable run")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument("--runs-dir", type=Path, default=Path("runs"))
    fingerprint = sub.add_parser("fingerprint-model", help="Hash an already downloaded model directory")
    fingerprint.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        exit_code = 0
        if args.command in COMMANDS:
            output, exit_code = dispatch(args)
        elif args.command == "smoke":
            output = smoke(args.seed)
        elif args.command == "schema":
            output = ENTITIES[args.entity].model_json_schema()
        elif args.command == "fingerprint-model":
            from dishmook.backends import snapshot_fingerprint
            if not args.directory.is_dir():
                raise ValueError("Missing model directory")
            output = {"snapshot_sha256": snapshot_fingerprint(args.directory)}
        else:
            from dishmook.runtime import prepare, resume
            from dishmook.runtime_models import ExecutionSpec
            if args.command == "run":
                with args.spec.open("rb") as stream:
                    data = stream.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024:
                    raise ValueError("Spec too large")
                spec = ExecutionSpec.model_validate_json(data)
                run_id = prepare(args.runs_dir, spec, args.run_id)
                state = {"run_id": run_id, "status": "prepared", "failure_reason": None}
                if not args.prepare_only:
                    state = resume(args.runs_dir, run_id)
            else:
                state = resume(args.runs_dir, args.run_id)
            output = {key: state[key] for key in ("run_id", "status", "failure_reason")}
            exit_code = 0 if state["status"] in {"completed", "prepared"} else 1
    except KeyboardInterrupt:
        print("Run interrupted. Resume the existing run ID to recover its checkpoint.", file=sys.stderr)
        return 130
    except (ValidationError, ValueError, OSError, sqlite3.Error):
        # Do not echo potentially sensitive validation inputs.
        print("Invalid configuration, unavailable run, or unsafe path. Check the spec and run directory.", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code
