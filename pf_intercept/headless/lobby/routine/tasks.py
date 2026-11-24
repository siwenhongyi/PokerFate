"""每日 / 每周 / 挑战任务 (the task lists) and their activity chests. Requests from TaskModel.lua.

Claims every finished task (a monthly-card task only with a running monthly card), then every
point chest the claims unlocked, one chest at a time with a fresh read after each. The daily
and weekly lists go on the needs board, so whoever plays or reports does it for them too. Not
the achievements: those run for ever, and nothing says what one of them is worth.
"""
from __future__ import annotations

from pf_intercept.headless.lobby.core.base import RewardAPIError, Worker, _int

TASK_REFRESH = 10030
CATEGORIES = ((1, "daily"), (2, "weekly"), (6, "challenge"))


class Tasks(Worker):
    name = "tasks"
    title = "每日 / 每周 / 挑战任务"
    pushes = (TASK_REFRESH,)

    def pushed(self, notice_type):
        # Coalesce bursts without postponing an already scheduled refresh.
        svc = self.service
        svc.due[self.name] = min(svc.due[self.name], svc.now() + 0.5)

    async def check(self):
        svc = self.service
        data = await svc._request("/task/list", {})
        rows = (row for _, name in CATEGORIES for row in data.get(name + "_list") or [])
        needs_card = any(row.get("monthly_card_task") and _int(row.get("status")) == 2 for row in rows)
        monthly_card = False
        if needs_card:
            try:
                pay = await svc._request("/player/payInfo", {})
                monthly_card = _int((pay.get("data") or {}).get("monthly_card_exp")) > svc.now()
            except RewardAPIError:
                # Unknown eligibility must not prevent ordinary task claims.
                if svc._auth_failed or svc._stopping:
                    raise
        for category, name in CATEGORIES:
            ids = sorted({_int(row.get("id")) for row in data.get(name + "_list") or []
                          if _int(row.get("status")) == 2 and _int(row.get("id")) > 0
                          and (not row.get("monthly_card_task") or monthly_card)})
            if ids:
                await svc._claim("/task/recReward", {"task_cate": category, "id_arr": ids, "all": False}, name)
                data = await svc._request("/task/list", {})
            # Task claims can unlock point chests in the same pass. Read again
            # after every chest; never retry the same chest within this pass.
            attempted = set()
            while not svc._stopping:
                points = data.get("point_data") or {}
                received = {_int(i) for i in points.get(name + "_reward_id_list") or []}
                available = sorted(
                    (_int(c.get("reward_point")), _int(c.get("id")))
                    for c in data.get(name + "_point_conf_list") or []
                    if _int(c.get("id")) > 0 and "reward_point" in c
                    and _int(c.get("reward_point")) <= _int(points.get(name + "_point"))
                    and _int(c.get("id")) not in received | attempted
                )
                if not available:
                    break
                _, chest_id = available[0]
                attempted.add(chest_id)
                await svc._claim("/task/recPointReward", {"id": chest_id, "task_cate": category}, name + "_points")
                data = await svc._request("/task/list", {})
        svc.needs.want(self.name, [row for name in ("daily", "weekly") for row in data.get(name + "_list") or []])
