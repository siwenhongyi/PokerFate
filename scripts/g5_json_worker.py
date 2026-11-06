#!/usr/bin/env python3
"""JSON-line worker that adapts G5Gym.PythonAPI to PokerFate.

This script intentionally lives outside pokerfate/g5 so the vendored g5 tree
can remain untouched. It requires a built G5Gym assembly and pythonnet.
When --dll is omitted, the worker searches the usual g5 build folders.

Protocol:
    stdin  {"id":1,"method":"create_game","params":{...}}
    stdout {"id":1,"ok":true,"result":{...}}
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import re
import shutil
import sys
import traceback
from pathlib import Path
from typing import Any


class G5Worker:
    def __init__(self, dll_path: str | None = None):
        self.dll_path = dll_path or ""
        self.api = None
        self.num_players = 0
        self.recent_hands_count = 100
        self.game_name = "pokerfate"
        self.players: list[dict[str, Any]] = []
        self._python_api_cls = None

    def dispatch(self, method: str, params: dict[str, Any]) -> Any:
        handlers = {
            "preflight": self.preflight,
            "create_game": self.create_game,
            "start_hand": self.start_hand,
            "hole_cards": self.hole_cards,
            "board": self.board,
            "action": self.action,
            "decide": self.decide,
            "seed_player_stats": self.seed_player_stats,
            "finish_hand": self.finish_hand,
        }
        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"unknown method: {method}")
        return handler(params)

    def preflight(self, params: dict[str, Any]) -> dict[str, Any]:
        dll = self._resolve_dll_path()
        self._prepare_runtime_files(dll)
        cls = self._load_python_api()
        recent_hands = int(params.get("recent_hands_count", self.recent_hands_count))
        charts_level = int(params.get("preflop_charts_level", 4))
        randomly_sample = bool(params.get("randomly_sample_actions", False))
        api = cls(2, recent_hands)
        try:
            api.createGame(
                "__pokerfate_g5_preflight__",
                self._string_array(["uid:preflight_hero", "uid:preflight_villain"]),
                self._int_array([400, 400]),
                0,
                0,
                4,
                randomly_sample,
                charts_level,
            )
        finally:
            api.Dispose()
        return {"dll": str(dll), "runtime_dir": str(dll.parent)}

    def create_game(self, params: dict[str, Any]) -> dict[str, Any]:
        players = list(params.get("players") or [])
        if not 2 <= len(players) <= 6:
            raise ValueError("g5 supports 2-6 players")

        recent_hands = int(params.get("recent_hands_count", self.recent_hands_count))
        self._ensure_api(num_players=len(players), recent_hands_count=recent_hands)

        self.game_name = str(params.get("game_name") or self.game_name)
        self.players = players
        names = [str(p.get("name") or p.get("player_id")) for p in players]
        stacks = [int(round(float(p.get("stack") or 0))) for p in players]
        hero_index = int(params.get("hero_index", 0))
        button_index = int(params.get("button_index", 0))
        big_blind = int(round(float(params.get("big_blind") or 0)))
        randomly_sample = bool(params.get("randomly_sample_actions", False))
        charts_level = int(params.get("preflop_charts_level", 4))

        self.api.createGame(
            self.game_name,
            self._string_array(names),
            self._int_array(stacks),
            hero_index,
            button_index,
            big_blind,
            randomly_sample,
            charts_level,
        )
        return {"game_name": self.game_name, "num_players": len(players)}

    def start_hand(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        self.game_name = str(params.get("game_name") or self.game_name)
        self._sync_players(list(params.get("players") or self.players))
        button_index = int(params.get("button_index", 0))
        sitting_out = [int(x) for x in (params.get("sitting_out_indices") or [])]
        self.api.startNewHand(self.game_name, button_index, self._int_list(sitting_out))
        return {"player_to_act": int(self.api.getPlayerToActInd(self.game_name))}

    def hole_cards(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        cards = list(params.get("cards") or [])
        if len(cards) < 2:
            raise ValueError("hole_cards requires two cards")
        self.api.dealHoleCards(self.game_name, str(cards[0]), str(cards[1]))
        return {}

    def board(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        street = str(params.get("street") or "").lower()
        cards = [str(c) for c in (params.get("cards") or [])]
        if street == "flop":
            if len(cards) != 3:
                raise ValueError("flop requires exactly three cards")
            self.api.goToFlop(self.game_name, cards[0], cards[1], cards[2])
        elif street == "turn":
            if len(cards) != 1:
                raise ValueError("turn requires exactly one card")
            self.api.goToTurn(self.game_name, cards[0])
        elif street == "river":
            if len(cards) != 1:
                raise ValueError("river requires exactly one card")
            self.api.goToRiver(self.game_name, cards[0])
        else:
            raise ValueError(f"unsupported board street: {street}")
        return {"player_to_act": int(self.api.getPlayerToActInd(self.game_name))}

    def action(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        expected = int(params.get("player_index", -1))
        actual = int(self.api.getPlayerToActInd(self.game_name))
        if expected != actual:
            raise ValueError(f"player to act mismatch: expected {expected}, actual {actual}")

        action = str(params.get("action") or "").lower()
        amount_added = int(round(float(params.get("amount_added") or 0)))
        if action == "fold":
            self.api.playerFolds(self.game_name)
        elif action in {"check", "call"}:
            self.api.playerCheckCalls(self.game_name)
        elif action == "raise":
            self.api.playerBetRaisesBy(self.game_name, amount_added)
        else:
            raise ValueError(f"unsupported action: {action}")
        return {"player_to_act": int(self.api.getPlayerToActInd(self.game_name))}

    def decide(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        hero_index = int(params.get("hero_index", -1))
        actual = int(self.api.getPlayerToActInd(self.game_name))
        if hero_index != actual:
            raise ValueError(f"hero is not to act: expected {hero_index}, actual {actual}")
        amount_to_call = int(self.api.getAmountToCall(self.game_name))
        hero_money_in_pot = int(self.api.getStakesSize(self.game_name, hero_index))
        result = self.api.calculateHeroAction(self.game_name)
        return {
            "action": str(result.actionType),
            "byAmount": int(result.byAmount),
            "amountToCall": amount_to_call,
            "heroMoneyInPot": hero_money_in_pot,
            "checkCallEV": float(result.checkCallEV),
            "betRaiseEV": float(result.betRaiseEV),
            "timeSpentSeconds": float(result.timeSpentSeconds),
            "message": str(result.message),
            "ranges": self._player_ranges_169(),
        }

    def seed_player_stats(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        players = list(params.get("players") or [])
        if not players:
            return {"seeded": 0}
        result = self.api.seedPlayerStatsJson(json.dumps(players, ensure_ascii=False))
        seeded = 0
        try:
            seeded = int(result.seeded)
        except Exception:
            try:
                seeded = int(result.get("seeded", 0))
            except Exception:
                seeded = 0
        return {"seeded": seeded}

    def finish_hand(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_api()
        winnings = [int(round(float(x or 0))) for x in (params.get("winnings") or [])]
        winnings = (winnings + [0, 0, 0, 0, 0, 0])[:6]
        self.api.finishHand(self.game_name, *winnings)
        return {}

    def _ensure_api(self, *, num_players: int, recent_hands_count: int) -> None:
        if (
            self.api is not None
            and self.num_players == num_players
            and self.recent_hands_count == recent_hands_count
        ):
            return
        if self.api is not None:
            try:
                self.api.Dispose()
            except Exception:
                pass
        cls = self._load_python_api()
        self.api = cls(num_players, recent_hands_count)
        self.num_players = num_players
        self.recent_hands_count = recent_hands_count

    def _require_api(self) -> None:
        if self.api is None:
            raise RuntimeError("create_game must be called before this method")

    def _sync_players(self, players: list[dict[str, Any]]) -> None:
        if not players:
            return
        self.players = players
        for idx, player in enumerate(players):
            name = str(player.get("name") or player.get("player_id"))
            stack = int(round(float(player.get("stack") or 0)))
            self.api.setPlayerName(self.game_name, idx, name)
            self.api.setStackSize(self.game_name, idx, stack)

    def _player_ranges_169(self) -> list[dict[str, Any]]:
        ranges: list[dict[str, Any]] = []
        for idx, player in enumerate(self.players):
            try:
                raw = self.api.getPlayerRange(self.game_name, idx)
                range_map = self._normalize_range_map(raw)
            except Exception:
                range_map = {}
            ranges.append({
                "player_index": idx,
                "player_id": int(player.get("player_id", idx)),
                "name": str(player.get("name") or player.get("player_id") or idx),
                "display_name": str(player.get("display_name") or ""),
                "range_169": range_map,
            })
        return ranges

    @classmethod
    def _normalize_range_map(cls, raw: Any) -> dict[str, float]:
        out: dict[str, float] = {}
        for key, value in cls._dict_items(raw):
            norm_key = cls._normalize_range_key(str(key))
            if not norm_key:
                continue
            try:
                prob = float(value or 0.0)
            except (TypeError, ValueError):
                continue
            if prob <= 0.0:
                continue
            out[norm_key] = out.get(norm_key, 0.0) + prob
        total = sum(out.values())
        if total > 0.0:
            out = {key: value / total for key, value in out.items()}
        return dict(sorted(out.items()))

    @staticmethod
    def _dict_items(raw: Any):
        if raw is None:
            return []
        if isinstance(raw, dict):
            return list(raw.items())
        items = getattr(raw, "items", None)
        if callable(items):
            try:
                return list(items())
            except Exception:
                pass
        out = []
        try:
            iterator = iter(raw)
        except TypeError:
            return out
        for item in iterator:
            key = getattr(item, "Key", None)
            value = getattr(item, "Value", None)
            if key is None and isinstance(item, (list, tuple)) and len(item) >= 2:
                key, value = item[0], item[1]
            if key is not None:
                out.append((key, value))
        return out

    @classmethod
    def _normalize_range_key(cls, key: str) -> str:
        text = str(key or "").strip()
        if not text:
            return ""
        if re.fullmatch(r"[AKQJT2-9]{2}([so])?", text):
            return text
        suffix = ""
        if text[-1:] in {"s", "o"}:
            suffix = text[-1]
            text = text[:-1]
        r1, rest = cls._consume_rank_token(text)
        r2, rest = cls._consume_rank_token(rest)
        if not r1 or not r2 or rest:
            return ""
        if r1 == r2:
            return f"{r1}{r2}"
        if not suffix:
            return ""
        rank_order = "23456789TJQKA"
        if rank_order.index(r1) < rank_order.index(r2):
            r1, r2 = r2, r1
        return f"{r1}{r2}{suffix}"

    @staticmethod
    def _consume_rank_token(text: str) -> tuple[str, str]:
        rank_words = [
            ("Deuce", "2"),
            ("Three", "3"),
            ("Four", "4"),
            ("Five", "5"),
            ("Six", "6"),
            ("Seven", "7"),
            ("Eight", "8"),
            ("Nine", "9"),
            ("Ten", "T"),
            ("Jack", "J"),
            ("Queen", "Q"),
            ("King", "K"),
            ("Ace", "A"),
        ]
        for word, rank in rank_words:
            if text.startswith(word):
                return rank, text[len(word):]
        if text[:1] in set("AKQJT98765432"):
            return text[:1], text[1:]
        return "", text

    def _load_python_api(self):
        if self._python_api_cls is not None:
            return self._python_api_cls
        dll = self._resolve_dll_path()
        if not dll.exists():
            raise RuntimeError(f"G5Gym assembly not found: {dll}")
        self._prepare_runtime_files(dll)
        self._ensure_dotnet_root()

        pythonnet = importlib.import_module("pythonnet")
        pythonnet.load("coreclr")
        clr = importlib.import_module("clr")
        system = importlib.import_module("System")

        system.Console.SetOut(system.Console.Error)
        clr.AddReference(str(dll))
        self._python_api_cls = importlib.import_module("G5Gym").PythonAPI
        return self._python_api_cls

    @staticmethod
    def _ensure_dotnet_root() -> None:
        if os.environ.get("DOTNET_ROOT"):
            return

        candidates: list[Path] = []
        dotnet_bin = shutil.which("dotnet")
        if dotnet_bin:
            resolved = Path(dotnet_bin).resolve()
            candidates.append(resolved.parent.parent / "libexec")

        candidates.extend([
            Path("/opt/homebrew/opt/dotnet/libexec"),
            Path("/usr/local/opt/dotnet/libexec"),
            Path("/usr/share/dotnet"),
        ])
        candidates.extend(
            sorted(Path("/opt/homebrew/Cellar/dotnet").glob("*/libexec"), reverse=True)
        )
        candidates.extend(
            sorted(Path("/usr/local/Cellar/dotnet").glob("*/libexec"), reverse=True)
        )

        for candidate in candidates:
            if (candidate / "host/fxr").exists():
                os.environ["DOTNET_ROOT"] = str(candidate)
                return

    def _resolve_dll_path(self) -> Path:
        if self.dll_path:
            return Path(self.dll_path).expanduser().resolve()

        root = Path(__file__).resolve().parent.parent
        g5_root = root / "pokerfate/g5"
        candidates = [
            g5_root / "src/G5Gym/bin/Release/net8.0/G5Gym.dll",
            g5_root / "src/G5Gym/bin/Debug/net8.0/G5Gym.dll",
        ]
        candidates.extend(
            sorted(g5_root.glob("**/G5Gym.dll"))
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
        searched = ", ".join(str(p) for p in candidates[:6])
        raise RuntimeError(f"G5Gym.dll not found; searched: {searched}")

    def _prepare_runtime_files(self, dll: Path) -> None:
        root = Path(__file__).resolve().parent.parent
        redist = root / "pokerfate/g5/redist"
        runtime_dir = dll.parent
        if not redist.exists():
            raise RuntimeError(f"g5 redist directory not found: {redist}")

        for name in (
            "PreFlopEquities.txt",
            "full_stats_list_hu.bin",
            "full_stats_list_6max.bin",
        ):
            self._copy_if_needed(redist / name, runtime_dir / name)

        charts_src = redist / "PreFlopCharts" / "200bb"
        charts_dst = runtime_dir / "PreFlopCharts" / "200bb"
        if not charts_src.exists():
            raise RuntimeError(f"g5 preflop charts not found: {charts_src}")
        self._copy_chart_txt_files(charts_src, charts_dst)

        if platform.system() != "Windows":
            # G5.Logic currently builds this path with backslashes. On POSIX that
            # becomes one directory name under the Release/Debug folder.
            compat_charts_dst = (
                runtime_dir.parent
                / f"{runtime_dir.name}\\PreFlopCharts\\200bb\\"
            )
            self._copy_chart_txt_files(charts_src, compat_charts_dst)

        native_dst = runtime_dir / "DecisionMaking.dll"
        if not native_dst.exists():
            native_src = self._find_native_decision_making(root)
            if native_src is not None:
                self._copy_if_needed(native_src, native_dst)
        if not native_dst.exists():
            raise RuntimeError(
                "g5 native DecisionMaking.dll not found. Build "
                "pokerfate/g5/src/DecisionMaking first; on POSIX the "
                "compiled libdec_making.so is copied as DecisionMaking.dll."
            )

    @staticmethod
    def _copy_if_needed(src: Path, dst: Path) -> None:
        if not src.exists():
            raise RuntimeError(f"required g5 runtime file not found: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            return
        shutil.copy2(src, dst)

    def _copy_chart_txt_files(self, src_dir: Path, dst_dir: Path) -> None:
        dst_dir.mkdir(parents=True, exist_ok=True)
        count = 0
        for src in src_dir.rglob("*.txt"):
            rel = src.relative_to(src_dir)
            self._copy_if_needed(src, dst_dir / rel)
            count += 1
        if count == 0:
            raise RuntimeError(f"no g5 preflop chart txt files found in {src_dir}")

    @staticmethod
    def _find_native_decision_making(root: Path) -> Path | None:
        g5_root = root / "pokerfate/g5"
        candidates = [
            g5_root / "src/DecisionMaking/DecisionMaking.dll",
            g5_root / "src/DecisionMaking/libdec_making.so",
            g5_root / "src/DecisionMaking/libdec_making.dylib",
            g5_root / "dl/gym/DecisionMaking.dll",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    @staticmethod
    def _int_array(values: list[int]):
        system = importlib.import_module("System")
        return system.Array[system.Int32](values)

    @staticmethod
    def _string_array(values: list[str]):
        system = importlib.import_module("System")
        return system.Array[system.String](values)

    @staticmethod
    def _int_list(values: list[int]):
        system = importlib.import_module("System")
        generic = importlib.import_module("System.Collections.Generic")
        out = generic.List[system.Int32]()
        for value in values:
            out.Add(int(value))
        return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dll", default="")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    worker = G5Worker(args.dll)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            request_id = request.get("id")
            result = worker.dispatch(
                str(request.get("method") or ""),
                dict(request.get("params") or {}),
            )
            response = {"id": request_id, "ok": True, "result": result}
        except Exception as exc:
            if args.debug:
                traceback.print_exc(file=sys.stderr)
            request_id = None
            try:
                request_id = json.loads(line).get("id")
            except Exception:
                pass
            response = {"id": request_id, "ok": False, "error": str(exc)}
        print(json.dumps(response, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
