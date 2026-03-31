"""
Game state tracker.  Updated by proxy.py whenever a watched S2C message arrives.

Card encoding follows the game convention (integer IDs).
Suit  = card // 13   (0=Spade 1=Heart 2=Diamond 3=Club)
Rank  = card  % 13   (0=2 … 12=A)
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class PlayerInfo:
    seat_id: int
    chips:   int = 0
    is_fold: bool = False
    cards:   list[int] = field(default_factory=list)   # only visible for self


@dataclass
class GameState:
    # Table meta
    game_id:    str  = ""
    room_id:    int  = 0
    dealer:     int  = -1
    small_blind: int = -1
    big_blind:  int  = -1

    # Hand state
    stage:      int  = 0     # 1=preflop 2=flop 3=turn 4=river
    board:      list[int] = field(default_factory=list)
    pot:        list[int] = field(default_factory=list)

    # My hand
    my_seat_id:    int       = -1
    my_cards:      list[int] = field(default_factory=list)

    # Action turn
    action_seat_id:  int  = -1
    call_need_chips: int  = 0
    min_chipin:      int  = 0
    max_chipin:      int  = 0

    # All seats
    players: dict[int, PlayerInfo] = field(default_factory=dict)

    # Is a hand currently in progress?
    in_hand: bool = False


# Singleton updated by proxy
state = GameState()


def update(type_name: str, msg: dict, my_seat_id: int | None = None) -> None:
    """Apply a decoded server→client message to the global state."""

    if my_seat_id is not None:
        state.my_seat_id = my_seat_id

    if type_name == "pb.DealerInfoRSP":
        state.dealer      = msg.get("dealer", -1)
        state.small_blind = msg.get("small_blind", -1)
        state.big_blind   = msg.get("big_blind", -1)
        state.game_id     = msg.get("gameid", "")
        state.board       = []
        state.pot         = []
        state.in_hand     = True
        state.stage       = 0
        state.players     = {}
        for si in msg.get("start_info", []):
            seat = si["seatid"]
            state.players[seat] = PlayerInfo(seat_id=seat, chips=si.get("chips", 0))

    elif type_name == "pb.HandCardRSP":
        cards = [msg[k] for k in ("card1", "card2", "card3", "card4") if k in msg and msg[k]]
        state.my_cards = cards
        if state.my_seat_id >= 0:
            if state.my_seat_id not in state.players:
                state.players[state.my_seat_id] = PlayerInfo(seat_id=state.my_seat_id)
            state.players[state.my_seat_id].cards = cards

    elif type_name == "pb.RoundStartBRC":
        state.stage = msg.get("stage", state.stage)
        state.board.extend(msg.get("board", []))

    elif type_name == "pb.ActionNotifyBRC":
        state.action_seat_id  = msg.get("seatid", 0)  # pb omits field when value is 0
        state.call_need_chips = msg.get("call_need_chips", 0)
        state.min_chipin      = msg.get("min_chipin", 0)
        state.max_chipin      = msg.get("max_chipin", 0)

    elif type_name == "pb.ActionBRC":
        seat = msg.get("seatid", 0)  # pb omits field when value is 0
        if seat in state.players:
            state.players[seat].chips   = msg.get("hand_chips", state.players[seat].chips)
            state.players[seat].is_fold = msg.get("action_type") == 1  # FOLD

    elif type_name == "pb.RoundOverBRC":
        state.pot = msg.get("pool", [])

    elif type_name == "pb.WinnerRSP":
        state.in_hand = False
        state.action_seat_id = -1

    elif type_name == "pb.ShowHandRSP":
        for info in msg.get("info", []):
            seat = info.get("seatid", 0)  # pb omits field when value is 0
            cards = [info[k] for k in ("card1", "card2", "card3", "card4") if k in info and info[k]]
            if seat in state.players:
                state.players[seat].cards = cards

    elif type_name == "pb.ShowMyCardBRC":
        for info in msg.get("info", []):
            seat = info.get("seatid", 0)  # pb omits field when value is 0
            # hand_cards is repeated int32; 0 = slot not shown
            cards = [c for c in info.get("hand_cards", []) if c]
            if seat in state.players and cards:
                existing = state.players[seat].cards
                if len(cards) > len(existing):
                    state.players[seat].cards = cards
