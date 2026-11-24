"""大厅事务: everything the bot does in the lobby besides poker.

    service.py   RewardService: runs the workers, their HTTP line, journal and reward ledger
    base.py      Worker / Activity, Period (the period the server names, from the client's table)
    needs.py     Needs: what the task lists lack, between those who read tasks and those who act
    radar.py     活动雷达: hot update sync, the activity calendar, what nothing here can do

The registry below is the only list of workers: the session attaches them in this order, the
command line has a ``--no-<flag>`` for each that has a switch, the service routes pushes by
their ``pushes``, the radar reads their ``tables`` and ``does``. A new activity is one module,
one test file and one line here.

The order is a pass's order. Sources of tasks come before those who act on them: the sign-in
right after the task lists (a pass task may count it), the mail next (what it brings is in the
bag before the activities read it), the activities, then those who play or report for the
tasks every source lacks, and the radar last.
"""
from pf_intercept.headless.lobby.activities.battlepass import BattlePass
from pf_intercept.headless.lobby.activities.checkin import CheckIn
from pf_intercept.headless.lobby.activities.creator import Creator
from pf_intercept.headless.lobby.activities.dispatch import Dispatch
from pf_intercept.headless.lobby.doers.football import Football
from pf_intercept.headless.lobby.doers.gifts import Gifts
from pf_intercept.headless.lobby.routine.fund import Fund
from pf_intercept.headless.lobby.routine.mail import Mail
from pf_intercept.headless.lobby.activities.monopoly import Monopoly
from pf_intercept.headless.lobby.radar import Radar
from pf_intercept.headless.lobby.doers.reports import Reports
from pf_intercept.headless.lobby.doers.sidegames import SideGames
from pf_intercept.headless.lobby.routine.signin import SignIn
from pf_intercept.headless.lobby.routine.tasks import Tasks
from pf_intercept.headless.lobby.activities.theme import Theme

WORKERS = (
    Fund,           # 发展基金
    Tasks,          # 每日 / 每周 / 挑战任务
    SignIn,         # 七日签到
    Mail,           # 邮件
    CheckIn,        # 累签活动
    Theme,          # 主题活动
    Creator,        # 创作者活动（创作盛典）
    Monopoly,       # 大富翁（蓝湾漫游）
    Dispatch,       # 协会经营（派遣）
    BattlePass,     # 通行证
    SideGames,      # 彩球机 / 弹球
    Football,       # 足球竞猜
    Reports,        # 任务上报
    Gifts,          # 礼物：送礼、回收、碎片商城
    Radar,          # 活动雷达
)


def switches():
    """(flag, help) of every worker that can be switched off, in the registry's order."""
    return [kind.switch for kind in WORKERS if kind.switch]


def attach(service, session, off=()):
    """Attach every registered worker whose switch is not in ``off``."""
    for kind in WORKERS:
        if kind.switch is None or kind.switch[0] not in off:
            service.attach(kind(service, session))
    return service
