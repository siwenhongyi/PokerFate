"""Online calibrators keep only the most recent samples per key.

The bias they learn is "current tracker vs current pool"; samples drift with
code versions and the player pool, so an all-time mean goes stale.
"""

from pokerfate.strategy.range_v2 import hero_eq_calibrator as heq
from pokerfate.strategy.range_v2.hero_eq_calibrator import HeroEquityCalibrator


def test_hero_eq_record_keeps_only_recent_window():
    cal = HeroEquityCalibrator()
    n = heq._MAX_SAMPLES_PER_KEY
    for i in range(n + 50):
        cal.record('medium', 'river', 1, 0.5, 1.0 if i >= 50 else 0.0)
    assert cal.sample_count('medium', 'river', 1) == n
    # The 50 oldest (actual=0) samples fell out of the window.
    assert cal.bias_for('medium', 'river', 1) == 0.5


def test_hero_eq_from_dict_trims_to_window():
    n = heq._MAX_SAMPLES_PER_KEY
    pairs = [[0.5, 0.0]] * 200 + [[0.5, 1.0]] * n
    cal = HeroEquityCalibrator.from_dict({'strong|river|1|bet': pairs})
    assert cal.sample_count('strong', 'river', 1, 'bet') == n
    assert cal.bias_for('strong', 'river', 1, 'bet') == 0.5


