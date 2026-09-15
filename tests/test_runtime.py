import json
import multiprocessing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import pytest
from pydantic import ValidationError

from dishmook.backends import BackendError, FakeBackend
from dishmook.cli import main
from dishmook.runtime import prepare, resume
from dishmook.runtime_models import ExecutionSpec, ModelConfig, ModelRequest, ModelResponse
from dishmook.storage import Store, run_directory, run_lock
from dishmook.worker import execute


@pytest.fixture
def spec():
    return ExecutionSpec.model_validate_json(Path("problems/examples/free_fall.json").read_text())


def fake_runner(config, request, timeout):
    return FakeBackend().generate(request)


def slow_child(connection, config, request):
    time.sleep(20)


def broken_child(connection, config, request):
    connection.close()


def read_state(root, run_id):
    store = Store(root / run_id)
    try:
        return store.read()
    finally:
        store.close()


def events(root, run_id):
    return (root / run_id / "events.jsonl").read_bytes()


def test_real_worker_determinism_and_completed_resume(tmp_path, spec):
    first = resume(tmp_path, prepare(tmp_path, spec))
    second = resume(tmp_path, prepare(tmp_path, spec))
    assert first["status"] == second["status"] == "completed"
    assert first["claim"] == second["claim"]
    assert first["claim"]["status"] == "unverified"
    assert first["charged"] == first["output_tokens"] > 0
    before = events(tmp_path, first["run_id"])
    def forbidden(*args):
        pytest.fail("Completed resume must not call the model")
    third = resume(tmp_path, first["run_id"], runner=forbidden)
    assert third == first
    assert events(tmp_path, first["run_id"]) == before


def test_worker_timeout_reaps_child():
    req = ModelRequest(messages=[], seed=1, max_input_tokens=10, max_output_tokens=10)
    previous = {p.pid for p in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(BackendError, match="timeout"):
        execute(ModelConfig(), req, 0.2, target=slow_child)
    assert time.monotonic() - started < 5
    assert {p.pid for p in multiprocessing.active_children()} == previous


def test_worker_crash_is_reported():
    req = ModelRequest(messages=[], seed=1, max_input_tokens=10, max_output_tokens=10)
    with pytest.raises(BackendError, match="backend_protocol_error"):
        execute(ModelConfig(), req, 10, target=broken_child)


def test_timeout_is_persisted_and_cannot_get_free_retries(tmp_path, spec):
    spec.limits.total_output_tokens = 256
    def timeout(*args):
        raise BackendError("timeout")
    run_id = prepare(tmp_path, spec)
    failed = resume(tmp_path, run_id, runner=timeout)
    assert failed["failure_reason"] == "timeout"
    assert failed["charged"] == 256
    exhausted = resume(tmp_path, run_id, runner=fake_runner)
    assert exhausted["status"] == "exhausted"
    assert exhausted["attempts"] == 1


def test_interrupted_attempt_reserves_budget_and_resumes(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    def interrupt(*args):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        resume(tmp_path, run_id, runner=interrupt)
    interrupted = read_state(tmp_path, run_id)
    assert interrupted["status"] == "running"
    assert interrupted["charged"] == 256
    result = resume(tmp_path, run_id, runner=fake_runner)
    assert result["status"] == "completed"
    assert result["attempts"] == 2
    assert result["charged"] == 256 + result["output_tokens"]
    assert b'"kind": "interrupted"' in events(tmp_path, run_id)


def test_actual_process_death_releases_lock_and_preserves_reservation(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    script = "from pathlib import Path; import os,sys; from dishmook.runtime import resume\ndef die(*a): os._exit(23)\nresume(Path(sys.argv[1]),sys.argv[2],runner=die)"
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path), run_id], timeout=15)
    assert result.returncode == 23
    state = resume(tmp_path, run_id, runner=fake_runner)
    assert state["status"] == "completed"
    assert state["attempts"] == 2
    assert state["charged"] == 256 + state["output_tokens"]


def test_commit_before_export_crash_does_not_duplicate_inference(tmp_path, spec, monkeypatch):
    run_id = prepare(tmp_path, spec)
    original = Store.export
    def fail_export(*args):
        raise OSError("simulated disk error")
    monkeypatch.setattr(Store, "export", fail_export)
    with pytest.raises(OSError):
        resume(tmp_path, run_id, runner=fake_runner)
    monkeypatch.setattr(Store, "export", original)
    def forbidden(*args):
        pytest.fail("A durable result must not be recomputed")
    state = resume(tmp_path, run_id, runner=forbidden)
    assert state["attempts"] == 1
    assert len((tmp_path / run_id / "claims.jsonl").read_text().splitlines()) == 1


@pytest.mark.parametrize("bad_json", ["not JSON", '{"text":"ok","status":"supported"}', '{"text":" "}', "[]"])
def test_invalid_output_records_usage_and_failure(tmp_path, spec, bad_json):
    def malformed(*args):
        return ModelResponse(text=bad_json, input_tokens=10, output_tokens=20, token_unit="utf8_bytes")
    state = resume(tmp_path, prepare(tmp_path, spec), runner=malformed)
    assert state["status"] == "failed"
    assert state["failure_reason"] == "invalid_model_json"
    assert state["charged"] == state["output_tokens"] == 20
    assert state["claim"] is None


def test_limits_reach_adapter_and_agent_limits_apply(tmp_path, spec):
    spec.agent.max_output_tokens = 7
    spec.agent.timeout_seconds = 1
    def check(config, request, timeout):
        assert request.max_output_tokens == 7
        assert timeout == 1
        return fake_runner(config, request, timeout)
    state = resume(tmp_path, prepare(tmp_path, spec), runner=check)
    assert state["output_tokens"] == 7
    assert state["failure_reason"] == "invalid_model_json"


def test_max_attempts_survives_multiple_resume_calls(tmp_path, spec):
    spec.limits.max_attempts = 1
    def bad(*args):
        return ModelResponse(text="no", input_tokens=1, output_tokens=2, token_unit="utf8_bytes")
    run_id = prepare(tmp_path, spec)
    resume(tmp_path, run_id, runner=bad)
    state = resume(tmp_path, run_id, runner=bad)
    assert state["status"] == "exhausted"
    assert state["attempts"] == 1


def test_input_budget_rejection(tmp_path, spec):
    spec.limits.max_input_tokens = 1
    state = resume(tmp_path, prepare(tmp_path, spec), runner=fake_runner)
    assert state["failure_reason"] == "input_budget_exceeded"


def test_output_overrun_rejected(tmp_path, spec):
    def overrun(*args):
        return ModelResponse(text='{"text":"ok"}', input_tokens=1, output_tokens=257, token_unit="utf8_bytes")
    state = resume(tmp_path, prepare(tmp_path, spec), runner=overrun)
    assert state["failure_reason"] == "output_budget_exceeded"
    assert state["claim"] is None


def test_secret_redaction_before_storage_and_inference(tmp_path, spec, monkeypatch):
    secret = "private-value-123456789"
    monkeypatch.setenv("EXAMPLE_API_KEY", secret)
    spec.problem.statement += " " + secret + " password=anothersecret"
    def check(config, request, timeout):
        assert secret not in str(request.messages)
        assert "anothersecret" not in str(request.messages)
        raise RuntimeError("Do not log " + secret)
    run_id = prepare(tmp_path, spec)
    state = resume(tmp_path, run_id, runner=check)
    assert state["failure_reason"] == "backend_failed"
    for path in (tmp_path / run_id).iterdir():
        assert secret.encode() not in path.read_bytes()
        assert b"anothersecret" not in path.read_bytes()


@pytest.mark.parametrize("run_id", ["../outside", "/outside", "bad/path", "bad\\path"])
def test_no_path_traversal(tmp_path, spec, run_id):
    with pytest.raises(ValueError):
        prepare(tmp_path, spec, run_id)


def test_existing_run_and_lock_are_protected(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    with pytest.raises(FileExistsError):
        prepare(tmp_path, spec, run_id)
    with run_lock(tmp_path / run_id):
        with pytest.raises(ValueError, match="already active"):
            resume(tmp_path, run_id)


def test_symlink_run_is_rejected(tmp_path):
    destination = tmp_path / "target"
    destination.mkdir()
    try:
        (tmp_path / "link").symlink_to(destination, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation requires Windows privileges")
    with pytest.raises(ValueError, match="Unsafe"):
        run_directory(tmp_path, "link")


def test_append_only_journal(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    store = Store(tmp_path / run_id)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="append-only"):
            store.connection.execute("DELETE FROM events")
    finally:
        store.close()


def test_corrupted_projection_rebuilt_from_database(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    state = resume(tmp_path, run_id, runner=fake_runner)
    (tmp_path / run_id / "manifest.json").write_text("truncated{")
    (tmp_path / run_id / "events.jsonl").write_text("truncated{")
    assert resume(tmp_path, run_id, runner=fake_runner) == state
    assert json.loads((tmp_path / run_id / "manifest.json").read_text())["status"] == "completed"
    assert len(events(tmp_path, run_id).splitlines()) == 3


def test_config_change_on_resume_is_detected(tmp_path, spec):
    run_id = prepare(tmp_path, spec)
    store = Store(tmp_path / run_id)
    state = store.read()
    state["spec"]["seed"] += 1
    store.commit(state, "test_tamper")
    store.close()
    with pytest.raises(ValueError, match="integrity"):
        resume(tmp_path, run_id, runner=fake_runner)


def test_cli_prepare_and_resume(tmp_path, capsys):
    args = ["--runs-dir", str(tmp_path)]
    assert main(["run", "--spec", "problems/examples/free_fall.json", "--run-id", "cli-test", "--prepare-only", *args]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "prepared"
    assert main(["resume", "cli-test", *args]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"


@pytest.mark.parametrize("data", [{"backend":"remote"}, {"paid_api_allowed":True},
                                   {"paid_compute_allowed":True}, {"backend":"huggingface","revision":"main","local_path":"models"}])
def test_model_policy_stays_zero_paid(data):
    with pytest.raises(ValidationError):
        ModelConfig(**data)
