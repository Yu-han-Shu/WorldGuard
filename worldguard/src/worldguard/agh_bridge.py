"""Local process controls and legacy CLI recipe. LIVE uses the bounded official Host adapter."""

import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path


class LiveBlocked(RuntimeError):
    pass


def readiness(config=None):
    config = config or {}
    return {
        "available": False,
        "runtime_mode": "LIVE_AGNES",
        "status": "BLOCKED_EXTERNAL",
        "reasons": [
            "MODEL_BUDGET_NOT_APPROVED"
            if not config.get("external_model_calls_allowed")
            else "BOUNDED_HOST_CONTEXT_REQUIRED",
            "USE_CONFIGURED_API_LIVE_RUNTIME",
        ],
    }


def prepare_session(agh_root, home, workspace, route, model, profile="local-dev"):
    """Return a launch recipe without starting AGH, loading keys, or enabling requests."""
    entry = Path(agh_root).resolve() / "packages/cli/dist/local/agnes.mjs"
    if not entry.is_file():
        raise LiveBlocked("AGH_ENTRY_MISSING")
    for value in (route, model, profile):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", value):
            raise ValueError("INVALID_AGH_IDENTIFIER")
    workspace, home = Path(workspace).resolve(), Path(home).resolve()
    if not workspace.is_dir() or not home.is_dir():
        raise ValueError("AGH_DIRECTORY_MISSING")
    return {
        "argv": ["node", str(entry), "-p", "--mode", "json", "--standalone",
                 "--cwd", str(workspace), "--preset", "worldguard-bounded",
                 "--model", f"primary={route}/{model}"],
        "environment": {"AGH_HOME": str(home), "AGNES_PROFILE": profile},
        "prompt_transport": "stdin",
        "executed": False,
        "readiness": readiness(),
    }


class _WindowsJob:
    """Own descendants of this local adapter, without spawning slow taskkill."""

    def __init__(self, process):
        import ctypes
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.AssignProcessToJobObject.restype = wintypes.BOOL
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.TerminateJobObject.restype = wintypes.BOOL
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            error = ctypes.get_last_error()
            self.api.CloseHandle(self.handle)
            self.handle = None
            raise ctypes.WinError(error)

    def terminate(self):
        if self.handle and not self.api.TerminateJobObject(self.handle, 1):
            import ctypes
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def _kill_tree(process, job=None):
    if job is not None:
        job.terminate()
    elif os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       capture_output=True, check=False, timeout=10)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def run_local_process(argv, *, env=None, timeout_seconds=15, cancel=None, max_output_bytes=1_000_000):
    """Bound a local CLI probe. No shell, model prompt, or automatic retry.

    Used for no-model probes and tested against local child processes. This is not
    an authorization path for LIVE. Cancellation is a threading.Event-like object.
    """
    if not 0 < timeout_seconds <= 600 or not 0 < max_output_bytes <= 10_000_000:
        raise ValueError("INVALID_PROCESS_LIMIT")
    if cancel is not None and cancel.is_set():
        return {"exit_code": None, "status": "CANCELLED", "stdout": "", "stderr": ""}
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, env=env,
            start_new_session=os.name != "nt",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        job = None
        deadline, status = time.monotonic() + timeout_seconds, "COMPLETED"
        try:
            if os.name == "nt":
                job = _WindowsJob(process)
            while process.poll() is None:
                if cancel is not None and cancel.is_set():
                    status = "CANCELLED"
                elif time.monotonic() >= deadline:
                    status = "TIMEOUT"
                elif os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > max_output_bytes:
                    status = "OUTPUT_LIMIT"
                if status != "COMPLETED":
                    _kill_tree(process, job)
                    break
                time.sleep(0.02)
        finally:
            if process.poll() is None:
                _kill_tree(process, job)
            if job is not None:
                try:
                    job.terminate()
                finally:
                    job.close()
        if os.fstat(stdout.fileno()).st_size + os.fstat(stderr.fileno()).st_size > max_output_bytes:
            status = "OUTPUT_LIMIT"
        stdout.seek(0)
        stderr.seek(0)
        return {
            "exit_code": process.returncode, "status": status,
            "stdout": stdout.read(max_output_bytes).decode("utf-8", errors="replace"),
            "stderr": stderr.read(max_output_bytes).decode("utf-8", errors="replace"),
        }


def cli_help(agh_root, home, profile="local-dev", timeout_seconds=15):
    entry = Path(agh_root) / "packages/cli/dist/local/agnes.mjs"
    if not entry.is_file():
        raise LiveBlocked("AGH_ENTRY_MISSING")
    env = dict(os.environ, AGH_HOME=str(Path(home).resolve()), AGNES_PROFILE=profile)
    return run_local_process(["node", str(entry), "--help"], env=env, timeout_seconds=timeout_seconds)


def run_live(config=None, *, service=None, run_id=None):
    if service is not None and run_id is not None and service.live is not None:
        return service.live.execute(service, run_id)
    raise LiveBlocked("; ".join(readiness(config)["reasons"]))
