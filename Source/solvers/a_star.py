from __future__ import annotations

import heapq
from dataclasses import dataclass
from itertools import count
from typing import Callable

from Source.core import rules
from Source.core.rules import Move
from Source.core.state import State


Heuristic = Callable[[State], int]


@dataclass(frozen=True)
class AStarResult:
    solved: bool
    moves: list[Move]
    state_path: list[State]
    expanded_nodes: int
    generated_nodes: int
    heuristic_name: str


def heuristic_zero(state: State) -> int:
    return 0


def heuristic_foundation_gap(state: State) -> int:
    return 52 - sum(state.foundations.values())


def heuristic_mobility(state: State) -> int:
    remaining = heuristic_foundation_gap(state)
    occupied_free_cells = sum(1 for card in state.free_cells if card is not None)
    empty_cascades = sum(1 for cascade in state.cascades if not cascade)
    return remaining + occupied_free_cells - empty_cascades


def heuristic_blocking(state: State) -> int:
    remaining = heuristic_foundation_gap(state)
    blockers = 0

    for suit, foundation_rank in state.foundations.items():
        next_rank = foundation_rank + 1
        if next_rank > 13:
            continue

        for cascade in state.cascades:
            for index, card in enumerate(cascade):
                if card.suit == suit and card.rank == next_rank:
                    blockers += len(cascade) - index - 1
                    break
            else:
                continue
            break

    return remaining + blockers


HEURISTICS: dict[str, Heuristic] = {
    'zero': heuristic_zero,
    'foundation_gap': heuristic_foundation_gap,
    'mobility': heuristic_mobility,
    'blocking': heuristic_blocking,
}


def get_heuristic(heuristic: str | Heuristic) -> tuple[str, Heuristic]:
    if callable(heuristic):
        return getattr(heuristic, '__name__', 'custom'), heuristic

    try:
        return heuristic, HEURISTICS[heuristic]
    except KeyError as exc:
        available = ', '.join(sorted(HEURISTICS))
        raise ValueError(f"Unknown heuristic '{heuristic}'. Available: {available}") from exc


def reconstruct_solution(goal_state: State) -> tuple[list[Move], list[State]]:
    moves: list[Move] = []
    state_path: list[State] = []
    cursor: State | None = goal_state

    while cursor is not None:
        state_path.append(cursor)
        if cursor.move is not None:
            moves.append(cursor.move)
        cursor = cursor.parent

    state_path.reverse()
    moves.reverse()
    return moves, state_path


def solve_a_star(
    initial_state: State,
    heuristic: str | Heuristic = 'foundation_gap',
    max_nodes: int | None = None,
) -> AStarResult:
    heuristic_name, heuristic_fn = get_heuristic(heuristic)

    start = initial_state.clone(parent=None, move=None, g=0, h=0)
    start.h = heuristic_fn(start)

    if rules.is_goal(start):
        moves, state_path = reconstruct_solution(start)
        return AStarResult(
            solved=True,
            moves=moves,
            state_path=state_path,
            expanded_nodes=0,
            generated_nodes=1,
            heuristic_name=heuristic_name,
        )

    frontier: list[tuple[int, int, int, State]] = []
    tie_breaker = count()
    heapq.heappush(frontier, (start.g + start.h, start.h, next(tie_breaker), start))

    best_cost: dict[tuple, int] = {start.as_key(): 0}
    expanded_nodes = 0
    generated_nodes = 1

    while frontier:
        _, _, _, current = heapq.heappop(frontier)
        current_key = current.as_key()
        if current.g != best_cost.get(current_key):
            continue

        if rules.is_goal(current):
            moves, state_path = reconstruct_solution(current)
            return AStarResult(
                solved=True,
                moves=moves,
                state_path=state_path,
                expanded_nodes=expanded_nodes,
                generated_nodes=generated_nodes,
                heuristic_name=heuristic_name,
            )

        if max_nodes is not None and expanded_nodes >= max_nodes:
            break

        expanded_nodes += 1

        for move in rules.enumerate_legal_moves(current):
            next_state = rules.apply_move(current, move)
            next_state.h = heuristic_fn(next_state)
            next_key = next_state.as_key()

            if next_state.g >= best_cost.get(next_key, float('inf')):
                continue

            best_cost[next_key] = next_state.g
            generated_nodes += 1
            heapq.heappush(
                frontier,
                (next_state.g + next_state.h, next_state.h, next(tie_breaker), next_state),
            )

    return AStarResult(
        solved=False,
        moves=[],
        state_path=[start],
        expanded_nodes=expanded_nodes,
        generated_nodes=generated_nodes,
        heuristic_name=heuristic_name,
    )
