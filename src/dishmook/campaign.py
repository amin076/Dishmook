"""Staged multi-agent research with deterministic allocations and durable child runs."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import hashlib
from importlib.resources import files
import json
from pathlib import Path
from typing import Literal
import uuid

from pydantic import Field, model_validator

from dishmook.domain import Agent, Entity, Identifier, Problem
from dishmook.runtime import canonical, code_revision, now, prepare, resume, scrub
from dishmook.runtime_models import ExecutionSpec, Limits, ModelConfig
from dishmook.storage import Store, run_directory, run_lock
from dishmook.worker import WorkerSession


def roles():
    return json.loads(files("dishmook").joinpath("data/agents.json").read_text())


class CampaignSpec(Entity):
    problem: Problem
    model: ModelConfig = Field(default_factory=ModelConfig)
    agent_count: Literal[1, 5, 10, 20, 50] = 10
    active_agents: list[Identifier] | None = None
    self_reflection: bool = False
    max_rounds: int = Field(default=0, strict=True, ge=0, le=3)
    workers: Literal[1, 2] = 1
    total_output_tokens: int = Field(default=16384, strict=True, ge=1)
    total_input_tokens: int = Field(default=1048576, strict=True, ge=1)
    max_input_tokens: int = Field(default=16384, strict=True, ge=1)
    context_chars: int = Field(default=12000, strict=True, ge=0, le=20000)
    timeout_seconds: float = Field(default=600, gt=0, le=86400, allow_inf_nan=False)
    seed: int = Field(default=42, strict=True, ge=0, le=2**32-1)

    @model_validator(mode="after")
    def check(self):
        if self.self_reflection and self.agent_count != 1:
            raise ValueError("Self reflection is the single-agent baseline")
        if self.active_agents is not None:
            allowed = {r["agent"]["agent_id"] for r in roles()}
            if len(self.active_agents) != self.agent_count or len(set(self.active_agents)) != self.agent_count:
                raise ValueError("Active agent count must match unique selected IDs")
            if not set(self.active_agents) <= allowed or "agent-50" not in self.active_agents:
                raise ValueError("Select known roles including the final editor")
        return self


def selected_roles(spec):
    all_roles = roles()
    if spec.active_agents:
        return [r for r in all_roles if r["agent"]["agent_id"] in spec.active_agents]
    choices = {1:[50], 5:[1,20,21,41,50], 10:[1,7,16,20,21,23,31,38,41,50],
               20:[1,4,7,10,11,16,17,20,21,23,25,27,31,34,37,38,41,44,49,50],
               50:list(range(1,51))}
    return [r for r in all_roles if r["index"] in choices[spec.agent_count]]


def plan(spec):
    selected = selected_roles(spec)
    jobs = []
    for role in selected:
        # Reviewers inspect prior groups; editor inspects every prior role.
        stage = ord(role["group"]) - ord("A")
        if role["index"] == 50:
            stage = 5
        jobs.append({"id": f"task-{len(jobs):03d}", "role": role, "stage": stage, "round":0})
    if spec.self_reflection:
        jobs.append({"id":f"task-{len(jobs):03d}", "role":selected[-1], "stage":6, "round":0})
    reviewer = next((r for r in selected if r["group"] == "E" and r["index"] != 50), selected[-1])
    for round_no in range(1,spec.max_rounds+1):
        for offset, role in enumerate([reviewer, selected[-1]]):
            jobs.append({"id":f"task-{len(jobs):03d}","role":role,"stage":6+round_no*2+offset,"round":round_no})
    if min(spec.total_output_tokens, spec.total_input_tokens) < len(jobs):
        raise ValueError("Budget cannot allocate at least one token to each planned task")
    for index, job in enumerate(jobs):
        job.update(status="pending", result=None, dependencies=[j["id"] for j in jobs if j["stage"] < job["stage"]],
                   output_allocation=spec.total_output_tokens//len(jobs)+(index<spec.total_output_tokens%len(jobs)),
                   input_allocation=min(spec.max_input_tokens, spec.total_input_tokens//len(jobs)),
                   worker_slot=index % spec.workers)
    return jobs


class CampaignStore(Store):
    def export(self, state):
        def write_json(name, value):
            self.write(name,json.dumps(value,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
        self.write("queue.jsonl", "".join(json.dumps(j,ensure_ascii=False)+"\n" for j in state["jobs"]))
        write_json("manifest.json", {k:v for k,v in state.items() if k not in {"jobs","spec"}})
        write_json("plan.json",state["spec"])
        completed=[j for j in state["jobs"] if j["result"] and j["result"].get("claim")]
        self.write("claims.jsonl","".join(json.dumps(j["result"]["claim"],ensure_ascii=False)+"\n" for j in completed))
        self.write("events.jsonl","".join(json.dumps({"seq":seq,**json.loads(payload)},ensure_ascii=False)+"\n"
                   for seq,payload in self.connection.execute("SELECT seq,payload FROM events ORDER BY seq")))
        write_json("metrics.json", metrics(state))
        final=final_result(state)
        text=final["claim"]["text"] if final and final.get("claim") else "No completed synthesis."
        self.write("final_report.md",f"# Dishmook campaign\n\nStatus: {state['status']}\n\n"
                   f"Backend: {state['spec']['model']['backend']}\n\n{text}\n\n"
                   "All model claims remain unverified. Agreement and duplication are not independent evidence.\n")


def final_result(state):
    editors=[j for j in state["jobs"] if j["role"]["index"]==50 and j["status"] != "skipped"]
    return editors[-1]["result"] if editors else None


def metrics(state):
    results=[j["result"] for j in state["jobs"] if j["result"]]
    texts=[" ".join(r["claim"]["text"].lower().split()) for r in results if r.get("claim")]
    return {"planned_tasks":len(state["jobs"]),"completed_tasks":sum(j["status"]=="completed" for j in state["jobs"]),
            "failed_tasks":sum(j["status"]=="failed" for j in state["jobs"]),"skipped_tasks":sum(j["status"]=="skipped" for j in state["jobs"]),
            "charged_output_tokens":sum(r["charged"] for r in results),
            "known_output_tokens":sum(r["output_tokens"] for r in results),
            "known_input_tokens":sum(r["input_tokens"] for r in results),
            "output_budget":state["spec"]["total_output_tokens"],"input_budget":state["spec"]["total_input_tokens"],
            "exact_text_duplicate_count":len(texts)-len(set(texts)),
            "repaired_output_count":sum((r.get("output_parse") or {}).get("mode")=="latex_text_escape" for r in results),
            "invalid_citations":sum(len(r.get("invalid_citations",[])) for r in results),
            "wall_seconds":sum(r.get("wall_seconds",0) for r in results),
            "generation_seconds":sum(r.get("generation_seconds",0) for r in results),
            "peak_vram_bytes":max((r.get("peak_vram_bytes") or 0 for r in results),default=0) or None,
            "estimated_service_cost_usd":0,
            "real_model_backend":state["spec"]["model"]["backend"]!="fake"}


def prepare_campaign(root, spec, campaign_id=None):
    spec=CampaignSpec.model_validate(scrub(spec.model_dump()))
    if spec.model.local_path:
        spec.model.local_path=str(Path(spec.model.local_path).resolve())
    data=spec.model_dump()
    campaign_id=campaign_id or "campaign-"+uuid.uuid4().hex
    path=run_directory(Path(root),campaign_id)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.mkdir()
    (path/"tasks").mkdir()
    with run_lock(path):
        store=CampaignStore(path,create=True)
        try:
            state={"schema_version":1,"run_id":campaign_id,"spec":data,"spec_sha256":hashlib.sha256(canonical(data).encode()).hexdigest(),
                   "jobs":plan(spec),"status":"prepared","attempts":0,"created_at":now(),"updated_at":now(),
                   "code_revision":code_revision(),"active_agents":[r["agent"]["agent_id"] for r in selected_roles(spec)]}
            store.commit(state,"campaign_prepared")
            store.export(state)
        finally:
            store.close()
    return campaign_id


def context_for(state, job, limit):
    parents=[j for j in state["jobs"] if j["id"] in job["dependencies"] and j["result"] and j["result"].get("claim")]
    entries=[]
    # Equal text allowance makes earlier groups visible rather than only the last few agents.
    per=max(0,(limit-100*len(parents))//max(1,len(parents)))
    for parent in parents:
        claim=parent["result"]["claim"]
        entry={"claim_id":claim["claim_id"],"agent":parent["role"]["agent"]["agent_id"],"text":claim["text"][:per]}
        if len(canonical(entries+[entry])) > limit:
            break
        entries.append(entry)
    return canonical(entries),{e["claim_id"] for e in entries}


def _execute_job(path, state, job, session):
    spec=CampaignSpec.model_validate(state["spec"])
    context, visible=context_for(state,job,spec.context_chars)
    problem=spec.problem.model_copy(deep=True)
    problem.documents.append("Prior agent candidates (unverified; possibly truncated): "+context)
    agent=Agent.model_validate(job["role"]["agent"])
    agent.max_output_tokens=job["output_allocation"]
    agent.timeout_seconds=int(spec.timeout_seconds)+1
    model=spec.model.model_copy(deep=True)
    if model.device=="cuda":
        model.cuda_index+=job["worker_slot"]
    child_spec=ExecutionSpec(problem=problem,agent=agent,model=model,seed=spec.seed,output_mode="research",
        limits=Limits(max_input_tokens=job["input_allocation"],max_output_tokens=job["output_allocation"],
                      total_output_tokens=job["output_allocation"],max_attempts=1,timeout_seconds=spec.timeout_seconds))
    child_root=path/"tasks"
    child_path=run_directory(child_root,job["id"])
    if not child_path.exists():
        prepare(child_root,child_spec,job["id"])
    result=resume(child_root,job["id"],runner=session)
    candidate=result.get("candidate") or {}
    metadata=(result.get("response") or {}).get("metadata",{})
    return {"status":result["status"],"claim":result["claim"],"candidate":candidate,"output_parse":result.get("output_parse"),
            "charged":result["charged"],"input_tokens":result["input_tokens"],"output_tokens":result["output_tokens"],
            "failure_reason":result["failure_reason"],"invalid_citations":[c for c in candidate.get("citations",[]) if c not in visible],
            "wall_seconds":sum(a.get("wall_seconds",0) for a in result["attempt_history"]),
            "generation_seconds":metadata.get("generation_seconds",0),"peak_vram_bytes":metadata.get("peak_vram_bytes")}


def resume_campaign(root, campaign_id, *, max_tasks=None, session_factory=WorkerSession):
    if max_tasks is not None and max_tasks < 0:
        raise ValueError("max_tasks must be nonnegative")
    path=run_directory(Path(root),campaign_id)
    with run_lock(path), ExitStack() as stack:
        store=CampaignStore(path)
        stack.callback(store.close)
        state=store.read()
        if state["schema_version"]!=1 or hashlib.sha256(canonical(state["spec"]).encode()).hexdigest()!=state["spec_sha256"]:
            raise ValueError("Campaign configuration integrity failed")
        spec=CampaignSpec.model_validate(state["spec"])
        if state["status"] in {"completed","completed_with_failures"}:
            store.export(state)
            return state
        sessions=[stack.enter_context(session_factory()) for _ in range(spec.workers)]
        processed=0
        for stage in sorted({j["stage"] for j in state["jobs"]}):
            group=[j for j in state["jobs"] if j["stage"]==stage and j["status"] not in {"completed","failed","skipped"}]
            for start in range(0,len(group),spec.workers):
                batch=group[start:start+spec.workers]
                if max_tasks is not None:
                    batch=batch[:max(0,max_tasks-processed)]
                    if not batch:
                        state.update(status="paused",updated_at=now())
                        store.commit(state,"campaign_paused")
                        store.export(state)
                        return state
                for job in batch:
                    if job["round"]>0:
                        prior=[j for j in state["jobs"] if j["round"]==job["round"]-1 and j["role"]["group"]=="E"]
                        unresolved=any((j["result"] or {}).get("candidate",{}).get("disagreements") for j in prior)
                        if not unresolved:
                            job["status"]="skipped"
                            state.update(updated_at=now())
                            store.commit(state,"round_skipped",{"task_id":job["id"]})
                            continue
                    job["status"]="running"
                    state.update(status="running",updated_at=now(),attempts=state["attempts"]+1)
                    store.commit(state,"task_started",{"task_id":job["id"]})
                active=[j for j in batch if j["status"]=="running"]
                # Each batch has distinct sessions even when selected task indices have the same parity.
                def invoke(pair):
                    index,job=pair
                    return _execute_job(path,state,job,sessions[index])
                with ThreadPoolExecutor(max_workers=spec.workers) as pool:
                    results=list(pool.map(invoke,enumerate(active)))
                for job,result in zip(active,results):
                    job.update(result=result,status="completed" if result["status"]=="completed" else "failed")
                    state.update(updated_at=now())
                    store.commit(state,"task_committed",{"task_id":job["id"],"status":job["status"]})
                    processed+=1
                infrastructure={"gpu_unavailable","local_model_missing","local_backend_dependencies_missing","model_snapshot_changed"}
                if any(r.get("failure_reason") in infrastructure for r in results):
                    state.update(status="blocked",updated_at=now())
                    store.commit(state,"infrastructure_blocked")
                    store.export(state)
                    return state
                store.export(state)
        state.update(status="completed_with_failures" if any(j["status"]=="failed" for j in state["jobs"]) else "completed",updated_at=now())
        store.commit(state,"campaign_finished")
        store.export(state)
        return state
