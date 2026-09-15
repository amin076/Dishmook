import json
from pathlib import Path

import pytest

from dishmook.backends import BackendError,FakeBackend
from dishmook.campaign import CampaignSpec,CampaignStore,context_for,final_result,metrics,plan,prepare_campaign,resume_campaign,roles
from dishmook.domain import Problem
from dishmook.runtime_models import ModelResponse,ModelConfig,ModelRequest
from dishmook.worker import WorkerSession


def spec(count=10,**kwargs):
    return CampaignSpec(problem=Problem(problem_id="test",title="Test",statement="Assess the supplied problem."),agent_count=count,**kwargs)


def test_roles_have_all_fifty_distinct_responsibilities():
    data=roles()
    assert len(data)==50
    assert len({r["agent"]["agent_id"] for r in data})==50
    assert {g:sum(r["group"]==g for r in data) for g in "ABCDE"}==dict.fromkeys("ABCDE",10)


@pytest.mark.parametrize("count",[1,5,10,20,50])
def test_allocations_cover_entire_budget_and_dependencies_are_prior(count):
    data=spec(count,max_rounds=1,total_output_tokens=16387)
    jobs=plan(data)
    assert sum(j["output_allocation"] for j in jobs)==16387
    assert sum(j["input_allocation"] for j in jobs)<=data.total_input_tokens
    for j in jobs:
        assert all(next(p for p in jobs if p["id"]==dependency)["stage"]<j["stage"] for dependency in j["dependencies"])


def test_fifty_agent_real_worker_campaign_pauses_resumes_and_is_idempotent(tmp_path):
    run_id=prepare_campaign(tmp_path,spec(50,max_rounds=1))
    first=resume_campaign(tmp_path,run_id,max_tasks=13)
    assert first["status"]=="paused"
    assert metrics(first)["completed_tasks"]==13
    prior=[j["result"] for j in first["jobs"][:13]]
    final=resume_campaign(tmp_path,run_id)
    assert final["status"]=="completed"
    assert metrics(final)["completed_tasks"]==50
    assert metrics(final)["skipped_tasks"]==2
    assert prior==[j["result"] for j in final["jobs"][:13]]
    assert metrics(final)["charged_output_tokens"]<=final["spec"]["total_output_tokens"]
    before=(tmp_path/run_id/"events.jsonl").read_bytes()
    assert resume_campaign(tmp_path,run_id)==final
    assert (tmp_path/run_id/"events.jsonl").read_bytes()==before


def test_two_workers_produce_same_claims_as_sequential(tmp_path):
    one=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(10)))
    two=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(10,workers=2)))
    assert [j["result"]["claim"] for j in one["jobs"]]==[j["result"]["claim"] for j in two["jobs"]]


def test_editor_receives_claims_from_all_groups(tmp_path):
    state=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(50)))
    editor=state["jobs"][-1]
    text,visible=context_for(state,editor,12000)
    entries=json.loads(text)
    assert len(entries)==49
    assert all(entry["text"] for entry in entries)
    assert len(visible)>0


class DisputingSession:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def __call__(self,config,request,timeout):
        text=json.dumps({"text":"A disputed candidate.","answer":1,"citations":["nonexistent"],"disagreements":["An assumption remains unresolved."]})
        return ModelResponse(text=text,input_tokens=10,output_tokens=len(text),token_unit="utf8_bytes")


def test_dispute_rounds_are_bounded_and_citations_are_checked(tmp_path):
    state=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(10,max_rounds=2)),session_factory=DisputingSession)
    assert metrics(state)["completed_tasks"]==14
    assert metrics(state)["invalid_citations"]==14
    assert metrics(state)["exact_text_duplicate_count"]==13
    assert final_result(state)["claim"]["status"]=="unverified"


def test_child_commit_before_parent_commit_is_recovered(tmp_path,monkeypatch):
    run_id=prepare_campaign(tmp_path,spec(5))
    original=CampaignStore.commit
    tripped=False
    def crash(self,state,kind,details=None):
        nonlocal tripped
        if kind=="task_committed" and not tripped:
            tripped=True
            raise OSError("simulated controller failure")
        return original(self,state,kind,details)
    monkeypatch.setattr(CampaignStore,"commit",crash)
    with pytest.raises(OSError):
        resume_campaign(tmp_path,run_id)
    monkeypatch.setattr(CampaignStore,"commit",original)
    state=resume_campaign(tmp_path,run_id)
    assert state["status"]=="completed"
    import sqlite3
    with sqlite3.connect(tmp_path/run_id/"tasks/task-000/state.sqlite3") as db:
        child=json.loads(db.execute("SELECT payload FROM state").fetchone()[0])
        assert child["attempts"]==1


def test_worker_session_reuses_process():
    request=ModelRequest(messages=[{"role":"user","content":"test"}],seed=1,max_input_tokens=1000,max_output_tokens=256)
    with WorkerSession() as session:
        first=session(ModelConfig(),request,10)
        pid=session.process.pid
        assert session(ModelConfig(),request,10)==first
        assert session.process.pid==pid


def test_failed_task_is_visible_not_silently_successful(tmp_path):
    state=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(5,total_output_tokens=5)))
    assert state["status"]=="completed_with_failures"
    assert metrics(state)["failed_tasks"]==5
    assert metrics(state)["charged_output_tokens"]<=5


def test_no_cpu_nf4_or_unknown_roles():
    with pytest.raises(ValueError):
        ModelConfig(quantization="nf4")
    with pytest.raises(ValueError):
        spec(1,active_agents=["unknown"])
    with pytest.raises(ValueError):
        spec(5,self_reflection=True)


class UnavailableSession(DisputingSession):
    def __call__(self,*args):
        raise BackendError("gpu_unavailable")


def test_infrastructure_failure_stops_campaign(tmp_path):
    state=resume_campaign(tmp_path,prepare_campaign(tmp_path,spec(50)),session_factory=UnavailableSession)
    assert state["status"]=="blocked"
    assert metrics(state)["failed_tasks"]==1
    assert sum(j["status"]=="pending" for j in state["jobs"])==49


def test_idle_worker_exits_cleanly_on_close():
    request=ModelRequest(messages=[{"role":"user","content":"test"}],seed=1,max_input_tokens=1000,max_output_tokens=256)
    session=WorkerSession()
    session(ModelConfig(),request,10)
    process=session.process
    session.close()
    assert not process.is_alive()
    assert process.exitcode == 0
