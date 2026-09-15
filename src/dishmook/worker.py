"""Killable inference child; it is not a generated-code sandbox."""

import contextlib
import json
import multiprocessing
import os
import time
import threading

from dishmook.backends import BackendError, create_backend
from dishmook.runtime_models import ModelConfig, ModelRequest, ModelResponse


def _entry(connection, config_data, request_data):
    def stop_if_orphaned():
        while True:
            time.sleep(0.1)
            parent = multiprocessing.parent_process()
            if parent is not None and not parent.is_alive():
                os._exit(1)
    threading.Thread(target=stop_if_orphaned, daemon=True).start()
    try:
        # Dependency logs and exceptions must not spill user input or credentials into trace.
        with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            result = create_backend(ModelConfig.model_validate(config_data)).generate(
                ModelRequest.model_validate(request_data))
        message = {"result": result.model_dump()}
    except BackendError as exc:
        message = {"error": str(exc)}
    except BaseException:
        message = {"error": "backend_failed"}
    try:
        connection.send_bytes(json.dumps(message).encode())
    finally:
        connection.close()


def execute(config: ModelConfig, request: ModelRequest, timeout: float,
            *, target=_entry) -> ModelResponse:
    context = multiprocessing.get_context("spawn")
    reader, writer = context.Pipe(duplex=False)
    process = context.Process(target=target, args=(writer, config.model_dump(), request.model_dump()), daemon=True)
    deadline = time.monotonic() + timeout
    try:
        process.start()
        writer.close()
        if not reader.poll(max(0, deadline - time.monotonic())):
            raise BackendError("timeout")
        try:
            data = json.loads(reader.recv_bytes(maxlength=2 * 1024 * 1024))
        except (EOFError, OSError, ValueError):
            raise BackendError("backend_protocol_error") from None
        if time.monotonic() > deadline:
            raise BackendError("timeout")
        if "error" in data:
            raise BackendError(data["error"])
        return ModelResponse.model_validate(data["result"])
    finally:
        if process.pid is not None:
            if process.is_alive():
                process.terminate()
            process.join(timeout=2)
            if process.is_alive():
                process.kill()
                process.join(timeout=2)
        reader.close()
        writer.close()


def _serve(connection, config_data):
    def orphan_watch():
        while True:
            time.sleep(0.1)
            parent = multiprocessing.parent_process()
            if parent is not None and not parent.is_alive():
                os._exit(1)
    threading.Thread(target=orphan_watch, daemon=True).start()
    try:
        backend = create_backend(ModelConfig.model_validate(config_data))
        while True:
            try:
                request_data = json.loads(connection.recv_bytes(maxlength=2 * 1024 * 1024))
            except EOFError:
                return
            try:
                with open(os.devnull, "w") as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                    response = backend.generate(ModelRequest.model_validate(request_data))
                message = {"result": response.model_dump()}
            except BackendError as exc:
                message = {"error": str(exc)}
            except Exception:
                message = {"error": "backend_failed"}
            connection.send_bytes(json.dumps(message).encode())
    finally:
        connection.close()


class WorkerSession:
    """One shared, killable model process. One controller thread per session."""
    def __init__(self):
        self.process = None
        self.connection = None
        self.config = None

    def close(self):
        if self.connection is not None:
            self.connection.close()
        if self.process is not None:
            if self.process.is_alive():
                self.process.terminate()
            self.process.join(timeout=2)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout=2)
        self.process = self.connection = self.config = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __call__(self, config, request, timeout):
        deadline = time.monotonic() + timeout
        data = config.model_dump()
        if self.process is None or not self.process.is_alive() or self.config != data:
            self.close()
            context = multiprocessing.get_context("spawn")
            self.connection, child = context.Pipe()
            self.process = context.Process(target=_serve, args=(child, data), daemon=True)
            self.config = data
            self.process.start()
            child.close()
        try:
            self.connection.send_bytes(request.model_dump_json().encode())
            if not self.connection.poll(max(0, deadline - time.monotonic())):
                raise BackendError("timeout")
            data = json.loads(self.connection.recv_bytes(maxlength=2 * 1024 * 1024))
            if time.monotonic() > deadline:
                raise BackendError("timeout")
            if "error" in data:
                raise BackendError(data["error"])
            return ModelResponse.model_validate(data["result"])
        except BaseException:
            self.close()
            raise
