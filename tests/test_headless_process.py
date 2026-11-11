"""Process control uses temporary paths and disposable children, never a live bot."""

import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from pf_intercept.headless import process
from pf_intercept.headless import __main__ as cli


@pytest.fixture(autouse=True)
def _isolate_session_proxy_environment(monkeypatch):
    monkeypatch.setattr(os, "environ", dict(os.environ))


def test_pid_lifecycle_duplicate_and_error_cleanup(tmp_path):
    path = tmp_path / "headless.pid"
    path.write_text("99999999\n")  # Prior crash left a PID, but no live lock.
    with pytest.raises(RuntimeError, match="fake run error"):
        with process.RunningProcess(path):
            assert path.read_text().strip() == str(os.getpid())
            with pytest.raises(process.ProcessControlError, match="已有"):
                with process.RunningProcess(path):
                    pytest.fail("duplicate run acquired the lock")
            raise RuntimeError("fake run error")
    assert not path.exists()
    assert path.with_suffix(".lock").exists()
    with process.RunningProcess(path):
        assert path.exists()
    assert not path.exists()


def test_stale_pid_never_signals_live_unrelated_process(tmp_path, monkeypatch):
    path = tmp_path / "headless.pid"
    path.write_text(str(os.getpid()))
    signals = []
    monkeypatch.setattr(process.os, "kill", lambda *args: signals.append(args))
    assert process.request_stop(path) is None  # Missing lock.
    path.with_suffix(".lock").write_text(json.dumps({
        "pid": os.getpid(), "identity": process._identity(os.getpid()),
    }))
    assert process.request_stop(path) is None  # Stale, unlocked metadata too.
    assert not signals


@pytest.mark.parametrize("damage", ["pid", "metadata", "identity"])
def test_stop_refuses_unverified_pid(tmp_path, monkeypatch, damage):
    path = tmp_path / "headless.pid"
    signals = []
    monkeypatch.setattr(process.os, "kill", lambda *args: signals.append(args))
    with process.RunningProcess(path):
        if damage == "pid":
            path.write_text("-1")
        elif damage == "metadata":
            path.with_suffix(".lock").write_text("not json")
        else:
            monkeypatch.setattr(process, "_identity", lambda _: "a different process start time")
        with pytest.raises(process.ProcessControlError):
            process.request_stop(path)
    assert not signals


def test_stop_sends_sigint_to_python_pid(tmp_path, monkeypatch):
    path = tmp_path / "headless.pid"
    signals = []
    monkeypatch.setattr(process.os, "kill", lambda *args: signals.append(args))
    with process.RunningProcess(path):
        assert process.request_stop(path) == os.getpid()
        assert signals == [(os.getpid(), signal.SIGINT)]
        assert path.exists()  # Removed by the running process only after exit.


def test_owner_exits_during_identity_check(tmp_path, monkeypatch):
    path = tmp_path / "headless.pid"
    owner = process.RunningProcess(path)
    owner.__enter__()
    identity = process._identity(os.getpid())
    signals = []
    monkeypatch.setattr(process.os, "kill", lambda *args: signals.append(args))

    def ended(_):
        owner.__exit__()
        return identity

    monkeypatch.setattr(process, "_identity", ended)
    assert process.request_stop(path) is None
    assert not signals


def test_stop_cli_does_not_initialize_game_or_logging(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_PID_FILE", tmp_path / "headless.pid")
    monkeypatch.setattr(sys, "argv", ["headless", "--stop"])
    monkeypatch.setattr(cli, "_setup_logging", lambda _: pytest.fail("opened bot logging"))
    monkeypatch.setattr(cli, "_run", lambda *args: pytest.fail("started game"))
    assert cli.main() == 0


def test_startup_stop_never_connects_or_joins(monkeypatch):
    async def run():
        stop = asyncio.Event()
        monkeypatch.setattr(cli, "_resume_result", lambda _: (
            SimpleNamespace(servers=[], redacted=lambda: {}), 3, "test",
        ))

        async def probe(servers):
            stop.set()
            return servers

        monkeypatch.setattr(cli, "_order_servers_by_latency", probe)
        monkeypatch.setattr(cli, "HeadlessSession", lambda *args, **kwargs: pytest.fail("connected"))
        args = SimpleNamespace(no_notify=True, session_file=None)
        assert await cli._run(args, stop) == 0

    asyncio.run(run())


def test_startup_stop_after_login_skips_quick_start(monkeypatch):
    async def run():
        stop = asyncio.Event()
        calls = []
        monkeypatch.setattr(cli, "_resume_result", lambda _: (
            SimpleNamespace(uid=123, servers=[SimpleNamespace(server_host="wss://test.example", http_host="")],
                            redacted=lambda: {}), 3, "test",
        ))

        async def probe(servers):
            return servers

        class Session:
            logged_in = connected = True
            stats = {}

            def __init__(self, *args, **kwargs):
                self.bridge = SimpleNamespace(room_id_for_c2s=lambda _: 0)

            async def connect(self, **kwargs):
                stop.set()

            async def quick_start(self, **kwargs):
                pytest.fail("joined despite stop request")

            async def wait_closed(self):
                await asyncio.Event().wait()

            async def close(self, reason):
                calls.append(reason)

        monkeypatch.setattr(cli, "_order_servers_by_latency", probe)
        monkeypatch.setattr(cli, "HeadlessSession", Session)
        args = SimpleNamespace(no_notify=True, session_file=None, profit_lock_bb=None,
                               no_web=True, max_auto_rebuy=5, bb=10000, buyin_bb=100)
        assert await cli._run(args, stop) == 0
        assert calls == ["cli exit"]

    asyncio.run(run())


def test_real_child_stop_and_pid_cleanup_with_inherited_ignored_sigint(tmp_path):
    path = tmp_path / "headless.pid"
    # Exercise main()'s real signal handling and PID ownership without any game
    # connection. Ignored SIGINT reproduces a background/nohup shell launch.
    child_code = """
import asyncio, signal, sys
from pathlib import Path
from types import SimpleNamespace
from pf_intercept.headless import __main__ as cli
cli._PID_FILE = Path(sys.argv[1])
sys.argv = ['headless', '--bb', '10000', '--no-web', '--no-notify', '--no-remote-live']
signal.signal(signal.SIGINT, signal.SIG_IGN)
cli._setup_logging = lambda _: None
cli._resume_result = lambda _: (SimpleNamespace(servers=[SimpleNamespace(server_host='wss://test.example', http_host='')], redacted=lambda: {}), 3, 'test')
async def probe(servers):
    return servers
cli._order_servers_by_latency = probe
class FakeSession:
    logged_in = connected = True
    stats = {}
    def __init__(self, *args, on_frame, **kwargs):
        self.on_frame = on_frame
        self.bridge = SimpleNamespace(room_id_for_c2s=lambda _: 42)
    async def connect(self, **kwargs):
        pass
    async def quick_start(self, **kwargs):
        cli._PID_FILE.with_suffix('.ready').touch()
    async def restore_or_start(self, **kwargs):
        await self.quick_start(**kwargs)
    async def wait_closed(self):
        await asyncio.Event().wait()
    async def send(self, name, fields, **kwargs):
        assert name == 'pb.DelayLeaveRoomREQ' and fields == {'flag': True}
        print('leave_requested', flush=True)
        self.on_frame('pb.LeaveRoomRSP', {'code': 0})
        return True
    async def close(self, reason):
        print('closed', flush=True)
cli.HeadlessSession = FakeSession
raise SystemExit(cli.main())
"""
    child = subprocess.Popen(
        [sys.executable, "-c", child_code, str(path)],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 10
        ready = path.with_suffix(".ready")
        while not ready.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert ready.exists(), "test child failed to reach fake table"
        assert int(path.read_text()) == child.pid
        assert process.request_stop(path) == child.pid
        stdout, stderr = child.communicate(timeout=10)
        assert child.returncode == 0, stderr
        assert "leave_requested" in stdout
        assert "已确认离桌" in stdout
        assert "closed" in stdout
        assert not path.exists()
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=5)
