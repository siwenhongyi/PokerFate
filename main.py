"""PokerFate — Entry point for bot vs bot simulation."""

import argparse
import random
from pokerfate.bot.poker_bot import PokerBot
from pokerfate.engine.game_engine import GameEngine


def make_simple_bot(name: str, equity_iterations: int = 500) -> PokerBot:
    """Create a PokerFate bot."""
    return PokerBot(name=name, equity_iterations=equity_iterations)


def make_random_bot():
    """A simple random-action bot for benchmarking."""
    import random
    from pokerfate.core.game_state import GameState, Action, ActionType

    def decide(gs: GameState, player_id: int) -> Action:
        player = next((p for p in gs.players if p.player_id == player_id), None)
        if player is None:
            return Action(ActionType.FOLD)
        to_call = gs.to_call(player)
        r = random.random()
        if to_call == 0:
            if r < 0.6:
                return Action(ActionType.CHECK)
            else:
                bet = random.uniform(gs.big_blind, max(gs.big_blind * 3, gs.pot * 0.75))
                return Action(ActionType.RAISE, min(bet, player.stack))
        else:
            if r < 0.35:
                return Action(ActionType.FOLD)
            elif r < 0.70:
                return Action(ActionType.CALL, min(to_call, player.stack))
            else:
                raise_to = gs.current_bet * 2.5
                return Action(ActionType.RAISE, min(raise_to, player.stack))

    return decide


def run_simulation(
    num_hands: int = 500,
    starting_stack: float = 200.0,
    big_blind: float = 2.0,
    verbose_hands: int = 0,
    seed: int = None,
    vs_random: bool = False,
):
    if seed is not None:
        random.seed(seed)

    bot0 = make_simple_bot("PokerFate", equity_iterations=500)

    if vs_random:
        random_decide = make_random_bot()
        bots = {
            0: lambda gs, pid: bot0.decide(gs, pid),
            1: random_decide,
        }
        names = {0: "PokerFate", 1: "RandomBot"}
    else:
        bot1 = make_simple_bot("Challenger", equity_iterations=500)
        bots = {
            0: lambda gs, pid: bot0.decide(gs, pid),
            1: lambda gs, pid: bot1.decide(gs, pid),
        }
        names = {0: "PokerFate", 1: "Challenger"}

    engine = GameEngine(
        bots=bots,
        player_names=names,
        starting_stacks={0: starting_stack, 1: starting_stack},
        big_blind=big_blind,
        small_blind=big_blind / 2,
        verbose=False,
    )

    print(f"\n{'='*50}")
    print(f"  PokerFate Bot Simulation")
    print(f"  Hands: {num_hands} | Stack: {starting_stack} | BB: {big_blind}")
    print(f"{'='*50}\n")

    # Print first N hands verbosely
    if verbose_hands > 0:
        engine.verbose = True
        for i in range(min(verbose_hands, num_hands)):
            if sum(1 for v in engine.stacks.values() if v > 0) < 2:
                break
            engine.play_hand()
        engine.verbose = False
        remaining = num_hands - verbose_hands
    else:
        remaining = num_hands

    # Play remaining hands silently
    if remaining > 0:
        deltas = engine.play_session(remaining)
    else:
        deltas = {pid: engine.stacks[pid] - starting_stack for pid in [0, 1]}

    # Results
    print(f"\n{'='*50}")
    print("  RESULTS")
    print(f"{'='*50}")
    for pid, name in names.items():
        delta = engine.stacks[pid] - starting_stack
        bb_per_100 = (delta / starting_stack) * 100 / (num_hands / 100)
        sign = "+" if delta >= 0 else ""
        print(f"  {name:15s}: {sign}{delta:+8.1f} chips  ({sign}{bb_per_100:.1f} BB/100)")

    print(f"\n  Total hands played: {engine.hand_count}")
    for pid, name in names.items():
        print(f"  {name} final stack: {engine.stacks[pid]:.1f}")
    print()


def main():
    parser = argparse.ArgumentParser(description="PokerFate Texas Hold'em AI Simulation")
    parser.add_argument('--hands', type=int, default=500, help='Number of hands to play')
    parser.add_argument('--stack', type=float, default=200.0, help='Starting stack in chips')
    parser.add_argument('--bb', type=float, default=2.0, help='Big blind size')
    parser.add_argument('--verbose', type=int, default=3, help='Number of hands to print verbosely')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    parser.add_argument('--vs-random', action='store_true', help='Play vs random bot instead of clone')
    args = parser.parse_args()

    run_simulation(
        num_hands=args.hands,
        starting_stack=args.stack,
        big_blind=args.bb,
        verbose_hands=args.verbose,
        seed=args.seed,
        vs_random=args.vs_random,
    )


if __name__ == '__main__':
    main()
