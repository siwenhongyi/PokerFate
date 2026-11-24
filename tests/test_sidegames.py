"""彩球机 / 弹球: one entry for every caller. Scripted game replies, no real requests."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest

from pf_intercept.headless.lobby.core import base as lb
from pf_intercept.headless.lobby.routine import fund as fd
from pf_intercept.headless.lobby.core import needs as nd
from pf_intercept.headless.lobby.core import service as sv
from pf_intercept.headless.lobby.routine import tasks as tk
from pf_intercept.headless.lobby.doers import sidegames as sg
from pf_intercept.headless.lobby.activities.monopoly import Monopoly
from pf_intercept.headless.lobby.doers.sidegames import COLOR, MAX_PLAYS, PINBALL, SideGames, minimum_bet
from tests.test_dispatch import ScriptedHTTP, journal, lua_table

NOW = 1795400000        # 2026-11-23 10:13 UTC+8
HOLDEM = 10010101


class Table:
    """The socket side: the stakes on offer and a result for every round."""

    def __init__(self, wallet=5_000_000):
        self.wallet, self.rounds, self.asked = wallet, [], []
        self.on_sidegame_result = AsyncMock()

    def bankroll_dashboard(self):
        return {} if self.wallet is None else {"wallet_chips": self.wallet}

    def table_game(self):
        return 0

    async def activity_request(self, name, fields):
        self.asked.append(name)
        if name == "GetSideGameConf":
            conf = {"balls": [1], "tpl_conf": [{"id": 1, "balance": 0, "chips1": 1000, "chips": [1000]}]}
            return {"game_type": fields["game_type"], "conf": json.dumps(conf)}
        self.rounds.append(name)
        if name == "ColorGameAction":
            return {"bets": [{"id": 101, "value": 1000}], "profits": [{"id": 101}], "ids": [102, 103, 104]}
        assert name == "PinballAction"
        return {"action_result": {"balls": [{"reward": 500}]}}


def setup(tmp_path, replies=(), *, table=None, now=NOW):
    http = ScriptedHTTP(replies)
    ready = asyncio.Event()
    ready.set()
    svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                           chnl=3, version="1.7.0", on_credit=AsyncMock(), ready=ready, post=http,
                           journal_path=tmp_path / "rewards.jsonl")
    clock = [now]
    svc.now = lambda: clock[0]
    table = table or Table()
    svc.attach(tk.Tasks(svc, table))
    svc.attach(SideGames(svc, table))
    return svc, table, http, clock


@pytest.fixture(autouse=True)
def no_pauses(monkeypatch):
    # Only this module's pause between rounds; asyncio.sleep itself stays what it is.
    monkeypatch.setattr(sg, "asyncio", Mock(sleep=lambda seconds: asyncio.sleep(0)))


def goal(game, need, done, *, kind=101, status=1):
    return {"id": need, "task_id": 1, "task_type": kind, "status": status, "value": [game, need], "current_value": done}


def test_the_tasks_this_plays_for_are_in_the_clients_tables():
    for name in ("dailytasks", "weeklytasks"):
        rounds = [r for r in lua_table(name) if r["task_type"] == "101"
                  and r["value"].strip("{}").split(",")[0] in (str(COLOR), str(PINBALL))]
        assert len(rounds) >= 10 and all("10100001" in r["rewards"] for r in rounds)


def test_side_games_keep_lowest_stake_as_wallet_grows():
    for game in (COLOR, PINBALL):
        conf = {'balls': [1], 'tpl_conf': [
            {'id': 4, 'balance': 100000000, 'chips1': 100000, 'chips': [100000]},
            {'id': 2, 'balance': 1000000, 'chips1': 1000, 'chips': [1000]},
            {'id': 1, 'balance': 0, 'chips1': 1000, 'chips': [1000]},
        ]}
        assert minimum_bet(conf, game, 500) is None
        assert minimum_bet(conf, game, 1000) == (1, 1000)
        assert minimum_bet(conf, game, 100000001) == (1, 1000)
        conf['tpl_conf'] = conf['tpl_conf'][:1]
        assert minimum_bet(conf, game, 100000001) is None


def test_a_losing_colour_round_is_a_known_result(tmp_path):
    """The wire format drops zero fields, so the colour that lost carries no ``profit``."""
    async def run():
        session = Mock()
        session.bankroll_dashboard.return_value = {'wallet_chips': 5_000_000}
        session.table_game.return_value = 0
        session.on_sidegame_result = AsyncMock()
        conf = {'tpl_conf': [{'id': 1, 'balance': 0, 'chips1': 1000}]}
        bet = [{'id': 101, 'value': 1000}]
        session.activity_request = AsyncMock(side_effect=[
            {'game_type': COLOR, 'conf': json.dumps(conf)},
            {'bets': bet, 'profits': [{'id': 101}], 'ids': [102, 103, 104]},
            {'bets': bet, 'profits': [{'id': 101, 'profit': 3000}], 'ids': [101, 101, 105]},
        ])
        svc, _, _, _ = setup(tmp_path, table=session)
        assert await svc.workers["sidegames"].play(COLOR, 2) == 2
        assert [(r['event'], r.get('net')) for r in journal(tmp_path)] == [
            ('sidegame_attempt', None), ('sidegame_result', -1000),
            ('sidegame_attempt', None), ('sidegame_result', 2000)]
        assert [c.args for c in session.on_sidegame_result.await_args_list] == [(-1000,), (2000,)]
        svc._on_credit.assert_not_awaited()             # nothing uncertain, nothing claimed
        assert not svc.uncertain
    asyncio.run(run())


def test_side_game_without_a_cheap_stake_is_skipped_for_the_day(tmp_path):
    async def run():
        session = Mock()
        session.bankroll_dashboard.return_value = {'wallet_chips': 5_000_000}
        conf = {'tpl_conf': [{'id': 3, 'balance': 0, 'chips1': 10000}]}
        session.activity_request = AsyncMock(return_value={'game_type': COLOR, 'conf': json.dumps(conf)})
        svc, _, _, _ = setup(tmp_path, table=session)
        assert await svc.workers["sidegames"].play(COLOR, 2) == 0
        assert svc.workers["sidegames"].left(COLOR) == 0            # callers stop asking for this game today
        assert session.activity_request.await_count == 1
        assert [(r['event'], r['game']) for r in journal(tmp_path)] == [('sidegame_skipped', COLOR)]
        restarted = SideGames(svc, session)
        assert (restarted.left(COLOR), restarted.left(PINBALL)) == (0, MAX_PLAYS)
        # No wallet reading yet: nothing is asked, nothing is given up for the day.
        session.bankroll_dashboard.return_value = {}
        assert await restarted.play(PINBALL, 2) == 0
        assert restarted.left(PINBALL) == MAX_PLAYS and session.activity_request.await_count == 1
    asyncio.run(run())


def test_the_days_limit_is_one_for_everybody_and_survives_a_restart(tmp_path):
    async def run():
        svc, table, _, clock = setup(tmp_path)
        games = svc.workers["sidegames"]
        # A few rounds per pass, whatever is lacking.
        assert await games.play(COLOR, 500) == sg.ROUNDS_PER_PASS == 5
        assert await games.play(COLOR, 1) == 1 and games.left(COLOR) == MAX_PLAYS - 6
        for _ in range(40):
            await games.play(COLOR, 500)
        assert games.left(COLOR) == 0 and table.rounds.count("ColorGameAction") == MAX_PLAYS == 100
        assert await games.play(COLOR, 5) == 0 and games.left(PINBALL) == MAX_PLAYS
        # Every round was at the cheapest stake, and the losses went to the side-game ledger.
        attempts = journal(tmp_path, "sidegame_attempt")
        assert {(r["stake"], r["level"], r["day"]) for r in attempts} == {(1000, 1, "2026-11-23")}
        assert table.on_sidegame_result.await_count == 100
        # A restart on the same game day counts what the journal holds. The rows the excursion
        # wrote before this entry existed have the same shape.
        again = SideGames(svc, table)
        assert again.left(COLOR) == 0 and again.left(PINBALL) == MAX_PLAYS
        # The game day turns at 03:00 UTC+8.
        clock[0] = 1795460400 - 1                       # 2026-11-24 02:59:59
        assert games.left(COLOR) == 0
        clock[0] += 1
        assert games.left(COLOR) == MAX_PLAYS
    asyncio.run(run())


def test_gaps_are_read_from_any_task_list_and_only_for_tasks_that_count_rounds():
    rows = [goal(COLOR, 3, 2),                          # one round short
            goal(COLOR, 25, 20),                        # five short: the larger gap is the game's
            goal(PINBALL, 15, 15, status=2),            # finished, waiting to be collected
            goal(PINBALL, 6, 6, status=3),              # collected
            goal(PINBALL, 500000, 0, kind=103),         # counts chips bet: never a reason to play
            goal(HOLDEM, 30, 4),                        # a game of its own on the board
            {"task_type": 101, "status": 1, "value": [COLOR], "current_value": 0},     # not this shape
            {"task_type": 101, "status": 1, "value": {"a": COLOR}}, None, "row"]
    # The board holds every game; who plays a game reads its own (hold'em is nobody's to add to).
    assert nd.Needs.gaps(rows) == {COLOR: 5, HOLDEM: 26}
    assert nd.Needs.gaps([goal(PINBALL, 10, 12), goal(COLOR, "40", "38")]) == {COLOR: 2}     # overshoot is no gap
    assert nd.Needs.gaps([]) == nd.Needs.gaps(None) == {}


def test_one_round_counts_for_every_source_so_the_largest_gap_is_played_not_the_sum(tmp_path):
    async def run():
        svc, table, _, _ = setup(tmp_path)
        games = svc.workers["sidegames"]
        for kind in ("tasks", "monopoly", "battlepass", "sidegames"):
            svc.due[kind] = NOW + 300
        svc.due["dispatch"] = NOW + 300
        svc.needs.want("tasks", [goal(COLOR, 3, 0), goal(PINBALL, 1, 0)])      # the daily tasks lack 3 and 1
        svc.needs.want("battlepass", [goal(COLOR, 20, 8)])                     # the pass lacks 12
        svc.needs.want("monopoly", [goal(COLOR, 30, 23), goal(PINBALL, 2, 0)])
        await games.check()
        # Colour: five of the twelve this pass. Pinball: two, which are also the one the tasks lack.
        assert (table.rounds.count("ColorGameAction"), table.rounds.count("PinballAction")) == (5, 2)
        colour, pinball = journal(tmp_path, "sidegame_demand")
        assert (colour["game"], colour["rounds"], colour["wanted"]) == (
            COLOR, 5, {"tasks": 3, "battlepass": 12, "monopoly": 7})
        assert (pinball["rounds"], pinball["wanted"]) == (2, {"tasks": 1, "monopoly": 2})
        # Whoever was served reads its list again, and the next rounds follow; nobody else is disturbed.
        assert (svc.due["tasks"], svc.due["battlepass"], svc.due["monopoly"], svc.due["sidegames"]) == (NOW + 15,) * 4
        assert svc.due["dispatch"] == NOW + 300
        # Until they report again, what was played is taken off every gap: twelve colour rounds
        # in all satisfy the three of them, not 3 + 12 + 7.
        for _ in range(5):
            await games.check()
        assert (table.rounds.count("ColorGameAction"), table.rounds.count("PinballAction")) == (12, 2)
        assert [r["rounds"] for r in journal(tmp_path, "sidegame_demand") if r["game"] == COLOR] == [5, 5, 2]
    asyncio.run(run())


def test_a_source_that_stops_reporting_drops_out_and_a_new_one_only_has_to_report(tmp_path):
    async def run():
        svc, table, _, clock = setup(tmp_path)
        games = svc.workers["sidegames"]
        svc.needs.want("monopoly", [goal(PINBALL, 30, 0)])
        clock[0] += nd.Needs.STALE_SEC + 1              # the activity ended: its worker reports no more
        svc.needs.want("tasks", [goal(COLOR, 3, 1)])
        await games.check()
        assert table.rounds == ["ColorGameAction"] * 2 and "monopoly" not in svc.needs.reports
        # A source nobody has heard of: it reports, it is served. A name that is no check is not woken.
        svc.needs.want("next_years_event", [goal(PINBALL, 4, 1)])
        await games.check()
        assert table.rounds.count("PinballAction") == 3
        # A fresh report replaces the old one: the list is the authority, not what was guessed here.
        svc.needs.want("tasks", [goal(COLOR, 6, 5)])
        await games.check()
        assert table.rounds.count("ColorGameAction") == 3
    asyncio.run(run())


def test_nothing_is_played_when_nothing_is_lacking_or_the_day_is_used_up(tmp_path):
    async def run():
        svc, table, _, _ = setup(tmp_path)
        games = svc.workers["sidegames"]
        svc.due["sidegames"] = NOW + 300
        await games.check()                             # nobody reported
        svc.needs.want("tasks", [goal(COLOR, 15, 15, status=3), goal(PINBALL, 340, 340, status=2)])
        await games.check()                             # nothing lacking
        games.load()
        games.plays = {COLOR: MAX_PLAYS, PINBALL: MAX_PLAYS}
        svc.needs.want("tasks", [goal(COLOR, 340, 100), goal(PINBALL, 340, 100)])
        await games.check()                             # lacking, and the day is used up
        assert table.asked == [] and svc.due["sidegames"] == NOW + 300 and not journal(tmp_path)
    asyncio.run(run())


def test_the_three_sources_report_what_they_read(tmp_path):
    from pf_intercept.headless.lobby.activities import battlepass as bp

    async def run():
        tasks = {"code": 0, "daily_list": [goal(PINBALL, 6, 3)], "weekly_list": [goal(COLOR, 40, 31)],
                 "challenge_list": [goal(COLOR, 5000, 0)]}          # an achievement: not played for
        detail = {"code": 0, "battle_pass_id": 1001, "weekly_list": [goal(COLOR, 20, 16)],
                  "list": [goal(PINBALL, 100000, 5000, kind=103)]}
        svc, table, http, _ = setup(tmp_path, [("/task/list", tasks), ("/task/battlePassDetail", detail)])
        await svc.workers["tasks"].check()
        assert svc.needs.reports["tasks"][:2] == (NOW, {PINBALL: 3, COLOR: 9})
        assert await bp.BattlePass(svc, table).detail() is not None
        assert svc.needs.reports["battlepass"][:2] == (NOW, {COLOR: 4})
        assert not http.replies and table.rounds == []              # reporting plays nothing by itself

        async def game(name, fields):
            return {"act_id": 30001} if name == "GetMonopolyActData" else {"item_list": []}
        table.activity_request = game
        svc.now = lambda: 1795500000                                # inside 蓝湾漫游 (30001)
        trip = Monopoly(svc, table)
        trip.tasks = AsyncMock(return_value=[
            {"id": 1, "task_id": 100201, "task_type": 101, "status": 1, "value": [COLOR, 30], "current_value": 12},
            {"id": 2, "task_id": 100301, "task_type": 101, "status": 1, "value": [10020101, 5], "current_value": 3}])
        await trip.check()
        # Whatever it counts, rounds of a side game or hands of Omaha: the activity says what it
        # lacks, and that alone is enough for it to be played, with or without the other sources.
        assert svc.needs.reports["monopoly"][:2] == (1795500000, {COLOR: 18, 10020101: 2})
        assert svc.needs.lacking(10020101) == {"monopoly": 2}
        # With side games switched off the sources do everything else as before.
        svc.workers.pop("sidegames")
        http.replies.extend([("/task/list", tasks), ("/task/battlePassDetail", detail)])
        await svc.workers["tasks"].check()
        await bp.BattlePass(svc, table).detail()
        await trip.check()
        assert not http.replies
    asyncio.run(run())


def test_the_reward_worker_plays_until_the_lists_lack_nothing(tmp_path, monkeypatch):
    """The whole loop against a server that counts each round for both lists, as the game does."""
    from tests.test_headless_rewards import eventually

    async def run():
        monkeypatch.setattr(sg, "COMEBACK_SEC", .01)
        table = Table()
        played = lambda: table.rounds.count("ColorGameAction")
        reads = []

        def post(url, payload, **kwargs):
            endpoint = url.removeprefix("https://game.example")
            reads.append(endpoint)
            if endpoint == "/task/list":
                done = played()         # daily: 6 of 10 at the start; weekly: 33 of 40
                return {"code": 0, "daily_list": [goal(COLOR, 10, 6 + done, status=1 if done < 4 else 3)],
                        "weekly_list": [goal(COLOR, 40, 33 + done, status=1 if done < 7 else 3)],
                        "challenge_list": [], "point_data": {}}
            assert endpoint == "/activity/rebateStatus", endpoint
            return {"code": 0, "status": 0}

        ready = asyncio.Event()
        ready.set()
        svc = sv.RewardService(uid=42, authorization="session-secret", http_base="https://game.example",
                               chnl=3, version="1.7.0", on_credit=AsyncMock(), ready=ready, post=post,
                               journal_path=tmp_path / "rewards.jsonl")
        svc.observe_server_time(NOW)
        svc.attach(fd.Fund(svc, None))
        svc.attach(tk.Tasks(svc, None))
        svc.attach(SideGames(svc, table))
        svc.start()
        await eventually(lambda: played() >= 7)
        await asyncio.sleep(.2)
        await svc.close()
        # Seven rounds: what the weekly task lacked, which covered the four of the daily one.
        assert played() == 7 and table.rounds.count("PinballAction") == 0
        assert [r["rounds"] for r in journal(tmp_path, "sidegame_demand")] == [5, 2]
        assert reads.count("/task/list") >= 3           # read again after each batch
    asyncio.run(run())
