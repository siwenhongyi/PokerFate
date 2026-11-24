"""活动雷达: what the client is about to run, and what of it the bot cannot do yet.

The client learns of an activity from its tables, which arrive with the hot update weeks
before the activity opens. The radar works from the same place:

    calendar.py   every period in the client's tables: window, testers' date, its tasks
    findings.py   the calendar held against the registry: no code, gaps, short limits (told on
                  every run until done or ignored), ended, hot update (told once)
    worker.py     Radar: in the bot, runs the command line in a subprocess every 6 h, Bark
    cli.py        python -m pf_intercept.headless.lobby [--no-sync] [--json] [--ignore-file F]

The ignore list it reads is core/ignore.py: the project's decisions there, the user's in an
external file over them.
"""
from pf_intercept.headless.lobby.radar.worker import Radar

__all__ = ["Radar"]
