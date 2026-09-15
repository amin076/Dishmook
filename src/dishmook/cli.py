"""Small offline CLI: schema export and a fixture-only bootstrap smoke check."""

import argparse
import json
import sys

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
    check = sub.add_parser("smoke", help="Run the offline Fake Backend fixture")
    check.add_argument("--seed", type=int, default=0)
    schema = sub.add_parser("schema", help="Print an entity JSON Schema")
    schema.add_argument("entity", choices=ENTITIES)
    args = parser.parse_args(argv)
    try:
        output = smoke(args.seed) if args.command == "smoke" else ENTITIES[args.entity].model_json_schema()
    except (ValidationError, ValueError):
        # Do not echo potentially sensitive validation inputs.
        print("Invalid smoke configuration; seed must be a nonnegative integer.", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
