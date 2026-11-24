"""活动: what the game runs in periods. Each module plays every period of one kind: the
server names the period, the client's table says when it runs and what it pays.

    checkin.py     累签活动 (tpl_event_check_in)
    theme.py       主题活动 tasks (tpl_theme_activity); their rows go on the board
    monopoly.py    大富翁 (tpl_monopoly_activity): dice, board, milestones; rows on the board
    dispatch.py    协会经营 / 派遣 (tpl_constdata Dispatch_Start / _End)
    battlepass.py  通行证 (tpl_battle_pass_info); its rows go on the board
"""
