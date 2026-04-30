"""169 preflop hand-class equities vs a random opponent (5 community cards).

Replaces the old hand-coded preflop strength formula
(``score = hi*13 + lo + 3·suited``) which had two known defects:

  - AKs vs AKo collapsed to the same clipped value (the `+3 if suited`
    bump + final `min(1.0, score/180)` clip made them identical near
    the top), so AKs/AKo had indistinguishable prior weights.
  - TT vs 22 happened to order correctly only because the pair formula
    `156 + hi*2` is monotone; non-pairs could still interleave wrongly
    (e.g. AQs vs JJ).

This table is Monte-Carlo-sourced:

  method   — pick one representative combo per class, sample N opponent
             2-card hands + 5 community cards uniformly, evaluate showdown
  iters    — 20,000 per class (standard error ≈ 0.0035 per equity value)
  source   — frozen table generated offline from 20,000 MC samples per class
  verification — script sanity-checks against AA/KK/QQ/AKs/AKo/JJ/TT/22/
                 T9s/32o anchors within 0.012

The absolute order of near-equal classes (e.g. AJs vs AKo, ∆≈0.001) may
wobble across MC seeds — that's fine for the `reset_hand` use case where
percentiles get bucketed into raise/call/fold tiers; a pair of near-tied
classes sits on the same tier either way.
"""
from __future__ import annotations

from typing import Dict


# Equity vs one random opponent on an all-in preflop showdown.
# Ordered by equity descending for readability; lookup by class string.
PREFLOP_EQUITY: Dict[str, float] = {
    'AA':  0.8504, 'KK':  0.8210, 'QQ':  0.7943, 'JJ':  0.7769,
    'TT':  0.7509, '99':  0.7203, '88':  0.6889, '77':  0.6679,
    'AKs': 0.6668, 'AQs': 0.6635, 'AJs': 0.6622, 'AKo': 0.6501,
    'AQo': 0.6484, 'ATs': 0.6467, 'AJo': 0.6377, 'KQs': 0.6343,
    '66':  0.6333, 'ATo': 0.6293, 'A9s': 0.6288, 'KJs': 0.6209,
    'KTs': 0.6183, 'A8s': 0.6169, 'KQo': 0.6164, 'A7s': 0.6140,
    '55':  0.6062, 'A9o': 0.6055, 'A8o': 0.6007, 'QJs': 0.5996,
    'QTs': 0.5981, 'A6s': 0.5975, 'KJo': 0.5957, 'K9s': 0.5946,
    'A5s': 0.5946, 'KTo': 0.5944, 'A7o': 0.5874, 'A4s': 0.5844,
    'A3s': 0.5836, 'QJo': 0.5821, 'K8s': 0.5810, 'Q9s': 0.5780,
    'A5o': 0.5779, 'A6o': 0.5778, 'JTs': 0.5777, 'K7s': 0.5756,
    'A2s': 0.5756, '44':  0.5710, 'QTo': 0.5709, 'K9o': 0.5698,
    'K6s': 0.5668, 'K8o': 0.5648, 'A4o': 0.5636, 'K5s': 0.5593,
    'Q8s': 0.5586, 'A3o': 0.5575, 'J9s': 0.5555, 'JTo': 0.5544,
    'K7o': 0.5535, 'Q9o': 0.5533, 'K4s': 0.5474, 'A2o': 0.5453,
    'K6o': 0.5444, 'Q8o': 0.5438, 'J8s': 0.5426, 'K3s': 0.5382,
    'T9s': 0.5382, '33':  0.5367, 'K5o': 0.5366, 'Q7s': 0.5361,
    'Q6s': 0.5358, 'J9o': 0.5320, 'K2s': 0.5316, 'Q5s': 0.5281,
    'J7s': 0.5245, 'K4o': 0.5236, 'Q4s': 0.5205, 'K3o': 0.5201,
    'T8s': 0.5200, 'J8o': 0.5171, 'Q7o': 0.5160, 'T9o': 0.5134,
    'Q3s': 0.5134, 'J6s': 0.5114, 'T7s': 0.5091, 'Q6o': 0.5082,
    'K2o': 0.5060, '98s': 0.5037, 'J5s': 0.5026, '22':  0.5019,
    'Q2s': 0.4989, 'J7o': 0.4973, 'Q5o': 0.4961, '97s': 0.4942,
    'T8o': 0.4929, 'Q4o': 0.4902, 'T6s': 0.4881, 'J4s': 0.4862,
    '98o': 0.4832, 'T7o': 0.4823, 'Q3o': 0.4816, 'J3s': 0.4806,
    'J6o': 0.4751, '96s': 0.4744, 'T5s': 0.4741, 'J5o': 0.4740,
    'Q2o': 0.4729, 'J2s': 0.4721, '87s': 0.4719, 'T4s': 0.4703,
    '97o': 0.4642, 'J4o': 0.4612, 'T3s': 0.4604, 'T6o': 0.4603,
    '86s': 0.4582, '95s': 0.4558, '87o': 0.4499, 'T2s': 0.4494,
    '76s': 0.4493, 'J3o': 0.4489, '85s': 0.4429, '96o': 0.4420,
    'J2o': 0.4381, 'T5o': 0.4377, '94s': 0.4368, 'T4o': 0.4352,
    '86o': 0.4351, '75s': 0.4336, 'T3o': 0.4332, '93s': 0.4324,
    '65s': 0.4281, '92s': 0.4273, '84s': 0.4259, '95o': 0.4259,
    '76o': 0.4246, '74s': 0.4227, 'T2o': 0.4186, '54s': 0.4183,
    '64s': 0.4125, '94o': 0.4099, '83s': 0.4088, '75o': 0.4065,
    '85o': 0.4064, '73s': 0.4052, '53s': 0.4037, '93o': 0.4036,
    '65o': 0.3999, '82s': 0.3993, '63s': 0.3955, '92o': 0.3902,
    '84o': 0.3892, '74o': 0.3888, '43s': 0.3881, '54o': 0.3869,
    '72s': 0.3857, '64o': 0.3823, '52s': 0.3777, '62s': 0.3751,
    '83o': 0.3742, '82o': 0.3693, '73o': 0.3655, '42s': 0.3651,
    '53o': 0.3625, '32s': 0.3621, '63o': 0.3573, '43o': 0.3481,
    '72o': 0.3434, '62o': 0.3409, '52o': 0.3391, '32o': 0.3270,
    '42o': 0.3253,
}

# Sanity — must always cover all 169 classes.
assert len(PREFLOP_EQUITY) == 169, f"table has {len(PREFLOP_EQUITY)} classes, expected 169"
