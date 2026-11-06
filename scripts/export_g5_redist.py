"""Export G5 redist PlayerStats binaries into population-prior JSON.

The G5 files are .NET BinaryWriter streams of PlayerStats:

    int32 player_count
    repeated:
      string player_name
      string poker_client
      int32 table_type
      int32 vpip_positive
      int32 vpip_total
      int32 preflop_len
      repeated preflop_len: int32 bet_raise, int32 check_call, int32 fold
      int32 postflop_len
      repeated postflop_len: int32 bet_raise, int32 check_call, int32 fold

This script exports aggregate priors only. It intentionally does not export
raw player identities because G5 redist players are not PokerFate identities.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable


DEFAULT_INPUT = Path("pokerfate/g5/redist/full_stats_list_6max_2m.bin")
DEFAULT_OUTPUT = Path("data/derived/g5_population_prior_6max.json")

POSITIONS_6MAX = ("SmallBlind", "BigBlind", "UTG", "HJ", "CutOff", "Button")
STREETS = ("Flop", "Turn", "River")
PREV_ACTIONS_POSTFLOP = ("Raise", "Call", "Check")
PREV_ACTIONS_PREFLOP_SECOND = ("Check", "Raise")


@dataclass(frozen=True)
class ActionStats:
    bet_raise: int
    check_call: int
    fold: int

    @property
    def total(self) -> int:
        return self.bet_raise + self.check_call + self.fold


class DotNetReader:
    def __init__(self, file: BinaryIO) -> None:
        self.file = file

    def read_int32(self) -> int:
        raw = self.file.read(4)
        if len(raw) != 4:
            raise EOFError("unexpected EOF while reading int32")
        return struct.unpack("<i", raw)[0]

    def read_string(self) -> str:
        length = self._read_7bit_encoded_int()
        raw = self.file.read(length)
        if len(raw) != length:
            raise EOFError("unexpected EOF while reading string")
        return raw.decode("utf-8")

    def _read_7bit_encoded_int(self) -> int:
        value = 0
        shift = 0
        while True:
            b = self.file.read(1)
            if len(b) != 1:
                raise EOFError("unexpected EOF while reading 7-bit int")
            byte = b[0]
            value |= (byte & 0x7F) << shift
            if byte & 0x80 == 0:
                return value
            shift += 7
            if shift >= 35:
                raise ValueError("invalid 7-bit encoded int")


class RateSummary:
    def __init__(self, bins: int) -> None:
        self.bins = bins
        self.n = 0
        self.sum = 0.0
        self.sum_sq = 0.0
        self.min = math.inf
        self.max = -math.inf
        self.hist = [0 for _ in range(bins)]

    def add(self, value: float) -> None:
        x = max(0.0, min(1.0, float(value)))
        self.n += 1
        self.sum += x
        self.sum_sq += x * x
        self.min = min(self.min, x)
        self.max = max(self.max, x)
        ind = min(self.bins - 1, int(x * self.bins))
        self.hist[ind] += 1

    def to_dict(self) -> dict:
        mean = self.sum / self.n if self.n else 0.0
        var = max(0.0, self.sum_sq / self.n - mean * mean) if self.n else 0.0
        return {
            "n": self.n,
            "mean": round(mean, 6),
            "stdev": round(math.sqrt(var), 6),
            "min": round(self.min, 6) if self.n else None,
            "max": round(self.max, 6) if self.n else None,
            "hist_bins": self.bins,
            "hist": self.hist,
        }


class BinaryRateSummary:
    def __init__(self, bins: int) -> None:
        self.positive = 0
        self.total = 0
        self.all_players = RateSummary(bins)
        self.g5_prior_eligible = RateSummary(bins)

    def add(self, positive: int, total: int, *, min_samples: int) -> None:
        self.positive += positive
        self.total += total
        if total > 0:
            rate = positive / total
            self.all_players.add(rate)
            if total > min_samples:
                self.g5_prior_eligible.add(rate)

    def to_dict(self) -> dict:
        return {
            "pooled_positive": self.positive,
            "pooled_total": self.total,
            "pooled_rate": round(self.positive / self.total, 6) if self.total else 0.0,
            "all_players": self.all_players.to_dict(),
            "g5_prior_eligible": self.g5_prior_eligible.to_dict(),
        }


class SpotAgg:
    def __init__(self, bins: int) -> None:
        self.players_with_samples = 0
        self.players_g5_prior_eligible = 0
        self.bet_raise = 0
        self.check_call = 0
        self.fold = 0
        self.br_rates = RateSummary(bins)
        self.cc_rates = RateSummary(bins)
        self.fold_rates = RateSummary(bins)
        self.br_rates_eligible = RateSummary(bins)
        self.cc_rates_eligible = RateSummary(bins)
        self.fold_rates_eligible = RateSummary(bins)

    @property
    def total(self) -> int:
        return self.bet_raise + self.check_call + self.fold

    def add(self, stats: ActionStats, *, min_samples: int) -> None:
        total = stats.total
        self.bet_raise += stats.bet_raise
        self.check_call += stats.check_call
        self.fold += stats.fold
        if total <= 0:
            return

        br = stats.bet_raise / total
        cc = stats.check_call / total
        fo = stats.fold / total
        self.players_with_samples += 1
        self.br_rates.add(br)
        self.cc_rates.add(cc)
        self.fold_rates.add(fo)
        if total > min_samples:
            self.players_g5_prior_eligible += 1
            self.br_rates_eligible.add(br)
            self.cc_rates_eligible.add(cc)
            self.fold_rates_eligible.add(fo)

    def to_dict(self, index: int, params: dict) -> dict:
        total = self.total
        return {
            "index": index,
            "params": params,
            "players_with_samples": self.players_with_samples,
            "players_g5_prior_eligible": self.players_g5_prior_eligible,
            "samples": {
                "total": total,
                "bet_raise": self.bet_raise,
                "check_call": self.check_call,
                "fold": self.fold,
            },
            "pooled_probabilities": {
                "bet_raise": round(self.bet_raise / total, 6) if total else 0.0,
                "check_call": round(self.check_call / total, 6) if total else 0.0,
                "fold": round(self.fold / total, 6) if total else 0.0,
            },
            "player_rate_summary": {
                "all_players": {
                    "bet_raise": self.br_rates.to_dict(),
                    "check_call": self.cc_rates.to_dict(),
                    "fold": self.fold_rates.to_dict(),
                },
                "g5_prior_eligible": {
                    "bet_raise": self.br_rates_eligible.to_dict(),
                    "check_call": self.cc_rates_eligible.to_dict(),
                    "fold": self.fold_rates_eligible.to_dict(),
                },
            },
        }


def sixmax_preflop_params() -> list[dict]:
    params: list[dict] = []
    for pos in POSITIONS_6MAX:
        params.append(_preflop_param(pos, 0, 0, 6, "Fold", False))
        params.append(_preflop_param(pos, 1, 0, 6, "Fold", False))
        params.append(_preflop_param(pos, 0, 1, 6, "Fold", False))
        params.append(_preflop_param(pos, 1, 1, 6, "Fold", False))
        params.append(_preflop_param(pos, 0, 2, 6, "Fold", False))

    for prev_action in PREV_ACTIONS_PREFLOP_SECOND:
        for in_pos in (False, True):
            for num_players in (2, 3):
                params.append(_preflop_param("BigBlind", 0, 1, num_players, prev_action, in_pos))
                params.append(_preflop_param("BigBlind", 1, 1, num_players, prev_action, in_pos))
                params.append(_preflop_param("BigBlind", 0, 2, num_players, prev_action, in_pos))

    return params


def _preflop_param(
    position: str,
    num_callers: int,
    num_raises: int,
    num_active_players: int,
    previous_action: str,
    in_position_on_flop: bool,
) -> dict:
    return {
        "position": position,
        "num_callers": num_callers,
        "num_raises": num_raises,
        "num_active_players": num_active_players,
        "previous_action": previous_action,
        "in_position_on_flop": in_position_on_flop,
        "forced_action": position != "BigBlind" or num_raises > 0,
    }


def sixmax_postflop_params() -> list[dict]:
    params: list[dict] = []
    for street in STREETS:
        for round_no in (0, 1):
            for prev_action in PREV_ACTIONS_POSTFLOP:
                for num_bets in (0, 1, 2):
                    for in_position in (False, True):
                        for num_players in (2, 3):
                            params.append(
                                {
                                    "street": street,
                                    "round": round_no,
                                    "previous_action": prev_action,
                                    "num_bets": num_bets,
                                    "in_position": in_position,
                                    "num_players": num_players,
                                    "forced_action": num_bets > 0,
                                }
                            )
    return params


def read_action_stats(reader: DotNetReader, count: int) -> list[ActionStats]:
    return [
        ActionStats(reader.read_int32(), reader.read_int32(), reader.read_int32())
        for _ in range(count)
    ]


def pfr_counts(preflop_stats: list[ActionStats], preflop_params: list[dict]) -> tuple[int, int]:
    positive = 0
    total = 0
    for stats, params in zip(preflop_stats, preflop_params):
        if params["num_raises"] == 0:
            positive += stats.bet_raise
            total += stats.total
    return positive, total


def aggression_counts(
    postflop_stats: list[ActionStats],
    postflop_params: list[dict],
) -> tuple[int, int]:
    forced_check_call = 0
    bet_raise = 0
    for stats, params in zip(postflop_stats, postflop_params):
        if params["num_bets"] > 0:
            forced_check_call += stats.check_call
        bet_raise += stats.bet_raise
    return bet_raise, bet_raise + forced_check_call


def wtp_counts(postflop_stats: list[ActionStats], postflop_params: list[dict]) -> tuple[int, int]:
    positive = 0
    total = 0
    for stats, params in zip(postflop_stats, postflop_params):
        if params["num_bets"] > 0:
            positive += stats.check_call + stats.bet_raise
            total += stats.total
    return positive, total


def export_population_prior(
    input_path: Path,
    *,
    min_samples: int,
    base_bins: int,
    spot_bins: int,
) -> dict:
    preflop_params = sixmax_preflop_params()
    postflop_params = sixmax_postflop_params()
    preflop_aggs = [SpotAgg(spot_bins) for _ in preflop_params]
    postflop_aggs = [SpotAgg(spot_bins) for _ in postflop_params]

    base = {
        "vpip": BinaryRateSummary(base_bins),
        "pfr": BinaryRateSummary(base_bins),
        "aggression": BinaryRateSummary(base_bins),
        "wtp": BinaryRateSummary(base_bins),
    }
    clients: dict[str, int] = {}
    table_types: dict[str, int] = {}

    with input_path.open("rb") as file:
        reader = DotNetReader(file)
        player_count = reader.read_int32()
        for player_index in range(player_count):
            _player_name = reader.read_string()
            client = reader.read_string()
            table_type = reader.read_int32()
            vpip_positive = reader.read_int32()
            vpip_total = reader.read_int32()
            preflop_len = reader.read_int32()
            preflop_stats = read_action_stats(reader, preflop_len)
            postflop_len = reader.read_int32()
            postflop_stats = read_action_stats(reader, postflop_len)

            if preflop_len != len(preflop_params):
                raise ValueError(
                    f"unexpected preflop_len={preflop_len} at player {player_index}; "
                    f"expected {len(preflop_params)}"
                )
            if postflop_len != len(postflop_params):
                raise ValueError(
                    f"unexpected postflop_len={postflop_len} at player {player_index}; "
                    f"expected {len(postflop_params)}"
                )

            clients[client] = clients.get(client, 0) + 1
            table_types[str(table_type)] = table_types.get(str(table_type), 0) + 1
            base["vpip"].add(vpip_positive, vpip_total, min_samples=min_samples)
            pfr_positive, pfr_total = pfr_counts(preflop_stats, preflop_params)
            base["pfr"].add(pfr_positive, pfr_total, min_samples=min_samples)
            agg_positive, agg_total = aggression_counts(postflop_stats, postflop_params)
            base["aggression"].add(agg_positive, agg_total, min_samples=min_samples)
            wtp_positive, wtp_total = wtp_counts(postflop_stats, postflop_params)
            base["wtp"].add(wtp_positive, wtp_total, min_samples=min_samples)

            for agg, stats in zip(preflop_aggs, preflop_stats):
                agg.add(stats, min_samples=min_samples)
            for agg, stats in zip(postflop_aggs, postflop_stats):
                agg.add(stats, min_samples=min_samples)

        trailing = file.read(1)
        if trailing:
            raise ValueError("unexpected trailing bytes after reading PlayerStats list")

    return {
        "schema_version": 1,
        "source": {
            "path": str(input_path),
            "format": "G5.Logic.PlayerStats BinaryWriter list",
            "player_count": player_count,
            "clients": dict(sorted(clients.items())),
            "table_types": dict(sorted(table_types.items())),
            "min_samples_for_g5_prior": min_samples,
        },
        "base_stats": {name: summary.to_dict() for name, summary in base.items()},
        "preflop_spots": [
            agg.to_dict(index, params)
            for index, (agg, params) in enumerate(zip(preflop_aggs, preflop_params))
        ],
        "postflop_spots": [
            agg.to_dict(index, params)
            for index, (agg, params) in enumerate(zip(postflop_aggs, postflop_params))
        ],
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--min-samples",
        type=int,
        default=20,
        help="G5 prior eligibility threshold. G5 uses total > 20.",
    )
    parser.add_argument("--base-bins", type=int, default=100)
    parser.add_argument("--spot-bins", type=int, default=20)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    payload = export_population_prior(
        args.input,
        min_samples=args.min_samples,
        base_bins=args.base_bins,
        spot_bins=args.spot_bins,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2, sort_keys=True)
        file.write("\n")

    print(f"wrote {args.out}")
    print(f"players: {payload['source']['player_count']}")
    print(f"preflop spots: {len(payload['preflop_spots'])}")
    print(f"postflop spots: {len(payload['postflop_spots'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
