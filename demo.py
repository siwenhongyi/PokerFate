"""PokerFate 控制台输出 demo — 模拟 3 手牌。

底池根据 bot 的实际决策动态计算，避免硬编码与实际行动不一致。
"""
from pokerfate.api import PokerFateAPI, PlayerInfo, ActionEvent

api = PokerFateAPI(my_player_id=0, big_blind=2.0, autosave_path=None, log_file=None)

SB, BB = 1.0, 2.0

# ── Hand 1: BTN AKs，开局加注，翻牌顶对，对手弃牌 ──
stack0, stack1 = 200.0, 200.0
api.new_hand(players=[
    PlayerInfo(0, "PokerFate", stack0, "BTN"),
    PlayerInfo(1, "GPT-4o",   stack1, "BB"),
], dealer_id=0)
api.deal_hole_cards(["As", "Ks"])
api.notify_action(ActionEvent(1, "raise", BB, "preflop"))     # BB post

# Preflop: pot=SB+BB=3, bot 已投 SB=1
d = api.request_action("preflop", pot=SB+BB, current_bet=BB, to_call=BB-SB, my_stack=stack0)
api.notify_action(ActionEvent(1, "call", 0.0, "preflop"))
# GPT 跟注到 bot 的加注额，双方各投 d.amount → 翻牌底池
flop_pot = d.amount * 2
api.deal_board(["Ah", "7d", "2c"], street="flop", pot=flop_pot)

api.notify_action(ActionEvent(1, "check", 0.0, "flop"))
d2 = api.request_action("flop", pot=flop_pot, current_bet=0.0, to_call=0.0,
                         my_stack=stack0 - d.amount)
api.notify_action(ActionEvent(1, "fold", 0.0, "flop"))
win_pot = flop_pot
api.hand_over(winner_ids=[0], pot=win_pot,
              final_stacks={0: stack0 - d.amount + win_pot, 1: stack1 - d.amount})

# ── Hand 2: BB 72o，对手开加，弃牌 ──
stack0 = api._session_stacks[0]
stack1 = api._session_stacks[1]
api.new_hand(players=[
    PlayerInfo(0, "PokerFate", None, "BB"),
    PlayerInfo(1, "GPT-4o",   None, "BTN"),
], dealer_id=1)
api.deal_hole_cards(["7h", "2c"])
opp_raise = 6.0
api.notify_action(ActionEvent(1, "raise", opp_raise, "preflop"))
d = api.request_action("preflop", pot=SB+BB+opp_raise-SB, current_bet=opp_raise,
                        to_call=opp_raise-BB, my_stack=stack0)
if d.action == "fold":
    api.hand_over(winner_ids=[1], pot=SB+BB+opp_raise-SB,
                  final_stacks={0: stack0 - BB, 1: stack1 - SB + SB + BB + opp_raise - SB})
else:
    # 若跟注/加注走简化路径
    api.hand_over(winner_ids=[1], pot=opp_raise * 2,
                  final_stacks={0: stack0 - opp_raise, 1: stack1 + opp_raise})

# ── Hand 3: BTN QQ，翻牌三条，对手翻牌下注，bot 加注，对手跟注，转牌弃牌 ──
stack0 = api._session_stacks[0]
stack1 = api._session_stacks[1]
api.new_hand(players=[
    PlayerInfo(0, "PokerFate", None, "BTN"),
    PlayerInfo(1, "GPT-4o",   None, "BB"),
], dealer_id=0)
api.deal_hole_cards(["Qh", "Qs"])
api.notify_action(ActionEvent(1, "raise", BB, "preflop"))

d = api.request_action("preflop", pot=SB+BB, current_bet=BB, to_call=BB-SB, my_stack=stack0)
api.notify_action(ActionEvent(1, "call", 0.0, "preflop"))
flop_pot = d.amount * 2

api.deal_board(["Qd", "7h", "2s"], street="flop", pot=flop_pot)
opp_bet = round(flop_pot * 0.4)   # GPT 下注约 40% 底池
api.notify_action(ActionEvent(1, "raise", opp_bet, "flop"))
d2 = api.request_action("flop", pot=flop_pot + opp_bet, current_bet=opp_bet,
                         to_call=opp_bet, my_stack=stack0 - d.amount)
api.notify_action(ActionEvent(1, "call", 0.0, "flop"))
# bot 加注到 d2.amount，GPT 跟注后双方各投 d2.amount → 翻牌共加入 d2.amount×2
turn_pot = flop_pot + d2.amount * 2 if d2.action == "raise" else flop_pot + opp_bet * 2

api.deal_board(["Tc"], street="turn", pot=turn_pot)
api.notify_action(ActionEvent(1, "check", 0.0, "turn"))
d3 = api.request_action("turn", pot=turn_pot, current_bet=0.0, to_call=0.0,
                         my_stack=stack0 - d.amount - (d2.amount if d2.action == "raise" else opp_bet))
api.notify_action(ActionEvent(1, "fold", 0.0, "turn"))
api.hand_over(winner_ids=[0], pot=turn_pot,
              final_stacks={0: stack0 - d.amount - (d2.amount if d2.action == "raise" else opp_bet) + turn_pot,
                            1: stack1 - d.amount - (d2.amount if d2.action == "raise" else opp_bet)})

api.session_summary()
