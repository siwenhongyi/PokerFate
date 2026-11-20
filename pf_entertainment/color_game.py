"""Color game packets used by the daily excursion task."""

def color_bet(level: int, stake: int, source: int) -> dict:
    return {'bets': [{'id': 101, 'value': stake}], 'lvl': level, 'from_game_type': source}


def color_profit(response: dict, stake: int) -> int:
    """Net result of one round. ``profit`` is the payout including the stake."""
    actual = sum(int(b.get('value', 0)) for b in response.get('bets', []))
    if actual != stake:
        raise ValueError('unexpected color game stake')
    # The wire format leaves zero fields out: a colour that paid nothing has no ``profit``.
    return sum(int(p.get('profit', 0)) for p in response.get('profits', [])) - actual
