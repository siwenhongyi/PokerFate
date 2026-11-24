"""PID ownership and validated SIGINT stopping (macOS/Linux, no game connection)."""

from __future__ import annotations

import fcntl
import json
import os
import signal
import subprocess
from pathlib import Path


class ProcessControlError(RuntimeError):
    """A running instance or an unverifiable PID prevents the requested action."""


def _identity(pid: int) -> str:
    # Start time distinguishes PID reuse; full argv also distinguishes wrappers.
    # Force a stable locale, since start and stop may use different terminals.
    try:
        result = subprocess.run(
            ["ps", "-ww", "-p", str(pid), "-o", "lstart=", "-o", "args="],
            capture_output=True, text=True, timeout=3,
            env={**os.environ, "LC_ALL": "C"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProcessControlError("无法核验进程身份，未发送停止信号") from exc
    if result.returncode not in (0, 1):
        raise ProcessControlError("ps 查询失败，未发送停止信号")
    return result.stdout.strip()


def _try_lock(file) -> bool:
    try:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except BlockingIOError:
        return False


class RunningProcess:
    """Hold a permanent lock inode; publish the Python PID for this run only.

    Never unlink the .lock file: concurrent starters must all lock the same
    inode. The OS releases its lock even after SIGKILL; stale PID files can
    therefore be safely replaced on the next start.
    """

    def __init__(self, pid_path: Path):
        self.pid_path = pid_path
        self.lock_path = pid_path.with_suffix(".lock")
        self.pid = os.getpid()
        self._file = None

    def __enter__(self):
        self.pid_path.parent.mkdir(parents=True, exist_ok=True)
        file = self.lock_path.open("a+", encoding="utf-8")
        if not _try_lock(file):
            file.close()
            raise ProcessControlError("已有实例运行；请先用本入口的 --stop 优雅停止")
        self._file = file
        temporary = self.pid_path.with_name(f".{self.pid_path.name}.{self.pid}.tmp")
        try:
            identity = _identity(self.pid)
            if not identity:
                raise ProcessControlError("无法获取当前进程身份，取消启动")
            file.seek(0)
            file.truncate()
            json.dump({"pid": self.pid, "identity": identity}, file)
            file.flush()
            temporary.write_text(f"{self.pid}\n", encoding="ascii")
            temporary.replace(self.pid_path)
        except BaseException:
            file.close()
            self._file = None
            raise
        finally:
            temporary.unlink(missing_ok=True)
        return self

    def __exit__(self, *exc):
        try:
            if self.pid_path.exists() and self.pid_path.read_text().strip() == str(self.pid):
                self.pid_path.unlink()
        finally:
            self._file.close()
            self._file = None


def request_stop(pid_path: Path) -> int | None:
    """Signal the verified, lock-owning run; None means no managed run is alive."""
    try:
        file = pid_path.with_suffix(".lock").open("r+", encoding="utf-8")
    except FileNotFoundError:
        return None
    with file:
        if _try_lock(file):
            # A plain PID file without a live owner is never sufficient to kill.
            return None
        try:
            pid = int(pid_path.read_text(encoding="ascii").strip())
            record = json.load(file)
            if pid <= 1 or record["pid"] != pid or not record["identity"]:
                raise ValueError("invalid PID record")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ProcessControlError("PID 记录缺失或损坏，未发送停止信号；若正在启动，请稍后重试") from exc
        if _identity(pid) != record["identity"]:
            raise ProcessControlError(f"PID {pid} 的进程身份不符或已退出，未发送停止信号")
        # The owner may have exited or a new run may have started during ps.
        if _try_lock(file):
            return None
        file.seek(0)
        if file.read() != json.dumps(record):
            raise ProcessControlError("运行实例已变更，未发送停止信号；请重试")
        try:
            os.kill(pid, signal.SIGINT)
        except ProcessLookupError:
            return None
        return pid
