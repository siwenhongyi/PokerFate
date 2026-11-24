"""The lobby registry: one list of workers, read by the session, the command line and the push
routing; and the service's alerts."""
import asyncio
import json
from unittest.mock import AsyncMock, patch

from pf_intercept.headless import lobby
from pf_intercept.headless.lobby.core.base import Worker
from pf_intercept.headless.lobby.core.service import RewardService


def service(tmp_path, alert=None):
    return RewardService(uid=1, authorization="x", http_base="", chnl=1, version="1", on_credit=AsyncMock(),
                         ready=asyncio.Event(), journal_path=tmp_path / "rewards.jsonl", alert=alert)


def test_the_registry_is_attached_in_order_without_what_is_switched_off(tmp_path):
    svc = lobby.attach(service(tmp_path), None, off={"radar", "auto-dispatch"})
    assert list(svc.workers) == [k.name for k in lobby.WORKERS if k.name not in ("radar", "dispatch")]
    names = [k.name for k in lobby.WORKERS]
    assert len(set(names)) == len(names) and names[-1] == "radar"
    assert lobby.switches() == [k.switch for k in lobby.WORKERS if k.switch]


def test_every_switch_is_a_command_line_flag():
    from pf_intercept.headless import __main__ as cli
    with patch("sys.argv", ["headless", "--no-auto-dispatch", "--no-radar"]):
        args = cli._parse_args()
    assert cli.switched_off(args) == {"auto-dispatch", "radar"}


def test_a_push_wakes_the_workers_that_listen_to_it(tmp_path):
    class Listener(Worker):
        name, pushes = "listener", (777,)
    svc = service(tmp_path)
    svc.attach(Listener(svc, None))
    svc.due["listener"] = svc.now() + 300
    svc.notify(777)
    assert svc.due["listener"] <= svc.now() + 1


def test_an_alert_is_sent_once_or_again_after_every_across_restarts(tmp_path):
    sent, clock = [], [1_000_000.0]

    def svc():
        s = service(tmp_path, alert=lambda title, body: sent.append(title))
        s.now = lambda: clock[0]
        return s
    first = svc()
    first.alert("event", "E", "1")
    first.alert("event", "E", "1")
    first.alert("undone", "U", "2", every=100)
    clock[0] += 50
    svc().alert("event", "E", "1")
    svc().alert("undone", "U", "2", every=100)
    clock[0] += 60
    svc().alert("event", "E", "1")
    svc().alert("undone", "U", "2", every=100)
    assert sent == ["E", "U", "U"]
