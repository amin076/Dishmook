"""SQLite is authoritative; JSON artifacts are replaceable projections."""

import contextlib
import json
import os
from pathlib import Path
import sqlite3

from pydantic import TypeAdapter

from dishmook.domain import Identifier


def run_directory(root: Path, run_id: str) -> Path:
    TypeAdapter(Identifier).validate_python(run_id)
    root = root.resolve()
    path = root / run_id
    if path.is_symlink() or path.resolve().parent != root:
        raise ValueError("Unsafe run directory")
    return path


@contextlib.contextmanager
def run_lock(path: Path):
    """OS lock released after process death; no stale PID-file guessing."""
    file = path / "run.lock"
    if file.is_symlink():
        raise ValueError("Unsafe lock path")
    with file.open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise ValueError("Run is already active") from None
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


class Store:
    def __init__(self, path: Path, *, create=False):
        self.path = path
        db = path / "state.sqlite3"
        if db.is_symlink() or (not create and not db.is_file()):
            raise ValueError("Run state is missing or unsafe")
        self.connection = sqlite3.connect(db)
        self.connection.execute("PRAGMA synchronous=FULL")
        if create:
            self.connection.executescript("""
                CREATE TABLE state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
                CREATE TABLE events (seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TRIGGER events_no_update BEFORE UPDATE ON events BEGIN
                    SELECT RAISE(ABORT, 'append-only events'); END;
                CREATE TRIGGER events_no_delete BEFORE DELETE ON events BEGIN
                    SELECT RAISE(ABORT, 'append-only events'); END;
            """)

    def close(self):
        self.connection.close()

    def read(self):
        row = self.connection.execute("SELECT payload FROM state WHERE id=1").fetchone()
        if row is None:
            raise ValueError("Run initialization incomplete")
        return json.loads(row[0])

    def commit(self, state: dict, kind: str, details: dict | None = None):
        event = {"kind": kind, "attempt": state["attempts"], "time": state["updated_at"],
                 "details": details or {}}
        with self.connection:
            self.connection.execute("INSERT INTO state VALUES(1, ?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                                    (json.dumps(state, ensure_ascii=False),))
            self.connection.execute("INSERT INTO events(payload) VALUES(?)", (json.dumps(event, ensure_ascii=False),))

    def write(self, name: str, data: str):
        destination = self.path / name
        temp = self.path / (name + ".tmp")
        if destination.is_symlink() or temp.is_symlink():
            raise ValueError("Unsafe artifact path")
        with temp.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, destination)

    def export(self, state: dict):
        def dump(obj):
            return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        self.write("manifest.json", dump({k: v for k, v in state.items() if k not in {"spec", "claim", "response"}}))
        self.write("problem.json", dump(state["spec"]["problem"]))
        self.write("plan.json", dump({"agent": state["spec"]["agent"], "model": state["spec"]["model"],
                                      "limits": state["spec"]["limits"], "seed": state["spec"]["seed"]}))
        self.write("claims.jsonl", json.dumps(state["claim"], ensure_ascii=False) + "\n" if state["claim"] else "")
        events = [json.dumps({"seq": seq, **json.loads(payload)}, ensure_ascii=False)
                  for seq, payload in self.connection.execute("SELECT seq,payload FROM events ORDER BY seq")]
        self.write("events.jsonl", "\n".join(events) + "\n")
        self.write("metrics.json", dump({"attempts": state["attempts"], "charged_output_tokens": state["charged"],
                                        "known_input_tokens": state["input_tokens"], "known_output_tokens": state["output_tokens"],
                                        "unknown_reserved_tokens": state["charged"] - state["output_tokens"],
                                        "token_unit": state["token_unit"], "estimated_service_cost_usd": 0}))
        self.write("trace.json", dump({"request": state.get("request"), "response": state["response"]}))
        claim = state["claim"]["text"] if state["claim"] else "No accepted candidate."
        self.write("final_report.md", f"# Dishmook single-agent run\n\nStatus: {state['status']}\n\n{claim}\n\n"
                   "Scientific verification: unverified. No tools or independent validators were executed.\n")
