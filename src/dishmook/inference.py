"""Deterministic test double. Does not solve problems or execute input."""

import hashlib
import json

from dishmook.domain import Agent, Claim, CostPolicy, Problem, Run, Task


class FakeModelBackend:
    model_id = "dishmook-fake"
    revision = "v1"

    def generate(self, problem: Problem, agent: Agent, task: Task, run: Run) -> Claim:
        # Revalidate at the trust boundary, including nested configuration.
        problem = Problem.model_validate(problem.model_dump())
        agent = Agent.model_validate(agent.model_dump())
        task = Task.model_validate(task.model_dump())
        run = Run.model_validate(run.model_dump())
        CostPolicy.model_validate(run.policy.model_dump())
        if task.problem_id != problem.problem_id or run.problem_id != problem.problem_id:
            raise ValueError("Problem references do not match")
        if task.agent_id != agent.agent_id or agent.agent_id not in run.active_agents:
            raise ValueError("Agent references do not match")
        if task.status != "pending" or run.status != "created":
            raise ValueError("Fake smoke accepts only pending tasks in created runs")
        payload = json.dumps({"problem": problem.model_dump(), "agent": agent.model_dump(),
                              "task": task.model_dump(), "seed": run.seed},
                             sort_keys=True, ensure_ascii=False).encode("utf-8")
        digest = hashlib.sha256(payload).hexdigest()[:20]
        return Claim(claim_id=f"fake-{digest}", producer_agent_id=agent.agent_id,
                     text="FAKE output: infrastructure test only; no scientific result.")
