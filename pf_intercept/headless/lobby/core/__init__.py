"""调度核心: what every lobby worker runs on, knowing none of them.

    service.py   RewardService: runs the attached workers in order, routes the server's pushes,
                 owns the HTTP line, the reward journal, the reward ledger and the alerts
    base.py      Worker and Activity, Period (the period the server names, read from the client's
                 table), the game's clock and the readers of the server's answers
    needs.py     Needs: what the task lists lack, between those who read tasks and those who act
"""
