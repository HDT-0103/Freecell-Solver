from __future__ import annotations

import heapq
import time
import tracemalloc
from dataclasses import dataclass
from itertools import count
from typing import Callable, TypeAlias

try:
    from core import rules
    from core.rules import Move
    from core.state import State
    from utils.metrics import SearchMetrics
except ModuleNotFoundError:
    from Source.core import rules
    from Source.core.rules import Move
    from Source.core.state import State
    from Source.utils.metrics import SearchMetrics


Heuristic = Callable[[State], int]
FrontierEntry: TypeAlias = tuple[float, int, int, State]
ProgressScore: TypeAlias = tuple[int, int, int, int]
TOTAL_CARDS = 52
SUIT_ORDER = {'C': 0, 'D': 1, 'H': 2, 'S': 3}


@dataclass(frozen=True)
class AStarResult:
    solved: bool
    moves: list[Move]
    state_path: list[State]
    expanded_nodes: int
    generated_nodes: int
    heuristic_name: str
    metrics: SearchMetrics


def _card_identity(card) -> tuple[int, int]:
    return (card.rank, SUIT_ORDER[card.suit])


def _search_key(state: State) -> tuple:
    canonical_free_cells = tuple(
        sorted(
            (card for card in state.free_cells if card is not None),
            key=_card_identity,
        )
    )
    canonical_cascades = tuple(
        sorted(
            (tuple(cascade) for cascade in state.cascades),
            key=lambda cascade: tuple(_card_identity(card) for card in cascade),
        )
    )
    return (
        canonical_cascades,
        canonical_free_cells,
        tuple((suit, state.foundations[suit]) for suit in ('C', 'D', 'H', 'S')),
    )


def _foundation_cards(state: State) -> int:
    return sum(state.foundations.values())


def _open_slots(state: State) -> int:
    empty_free_cells = sum(1 for card in state.free_cells if card is None)
    empty_cascades = sum(1 for cascade in state.cascades if not cascade)
    return empty_free_cells + empty_cascades


def heuristic_foundation_gap(state: State) -> int:
    return TOTAL_CARDS - _foundation_cards(state)


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
    'foundation_gap': heuristic_foundation_gap,
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


def _build_result(
    *,
    state: State,
    solved: bool,
    expanded_nodes: int,
    generated_nodes: int,
    heuristic_name: str,
    elapsed_seconds: float,
    peak_memory_bytes: int,
) -> AStarResult:
    moves, state_path = reconstruct_solution(state)
    return AStarResult(
        solved=solved,
        moves=moves,
        state_path=state_path,
        expanded_nodes=expanded_nodes,
        generated_nodes=generated_nodes,
        heuristic_name=heuristic_name,
        metrics=SearchMetrics(
            elapsed_seconds=elapsed_seconds,
            peak_memory_bytes=peak_memory_bytes,
            expanded_nodes=expanded_nodes,
            solution_steps=len(moves),
        ),
    )


def _progress_score(state: State) -> ProgressScore:
    return (_foundation_cards(state), _open_slots(state), -state.h, -state.g)


def _frontier_priority(state: State, heuristic_weight: float) -> tuple[float, int]:
    return (state.g + heuristic_weight * state.h, state.h)


def _move_priority(move: Move) -> tuple[int, int]:
    if move.dst_type == rules.LOCATION_FOUNDATION:
        return (0, move.count)
    if move.src_type == rules.LOCATION_FREE_CELL and move.dst_type == rules.LOCATION_CASCADE:
        return (1, -move.count)
    if move.src_type == rules.LOCATION_CASCADE and move.dst_type == rules.LOCATION_CASCADE:
        return (2, -move.count)
    if move.dst_type == rules.LOCATION_FREE_CELL:
        return (3, move.count)
    return (4, move.count)


class AStarSearchSession:
    def __init__(
        self,
        initial_state: State,
        *,
        heuristic: str | Heuristic = 'foundation_gap',
        heuristic_weight: float = 1.0,
    ) -> None:
        if heuristic_weight <= 0:
            raise ValueError("heuristic_weight must be > 0")

        heuristic_name, heuristic_fn = get_heuristic(heuristic)
        start = initial_state.clone(parent=None, move=None, g=0, h=0)
        start.h = heuristic_fn(start)

        self.heuristic_name = heuristic_name
        self.heuristic_fn = heuristic_fn
        self.heuristic_weight = heuristic_weight
        self.frontier: list[FrontierEntry] = []
        self.tie_breaker = count()
        self.best_cost: dict[tuple, int] = {_search_key(start): 0}
        self.expanded_nodes = 0
        self.generated_nodes = 1
        self.best_state = start
        self.best_progress = _progress_score(start)
        self.elapsed_seconds = 0.0
        self.peak_memory_bytes = 0
        self._solved_state: State | None = start if rules.is_goal(start) else None
        self._exhausted = False

        if self._solved_state is None:
            priority, secondary = _frontier_priority(start, heuristic_weight)
            heapq.heappush(
                self.frontier,
                (priority, secondary, next(self.tie_breaker), start),
            )

    @property
    def solved(self) -> bool:
        return self._solved_state is not None

    @property
    def exhausted(self) -> bool:
        return self._exhausted

    def _update_measurements(self, *, advance_begin: float, stop_tracing: bool) -> None:
        self.elapsed_seconds += time.perf_counter() - advance_begin
        if tracemalloc.is_tracing():
            _, peak = tracemalloc.get_traced_memory()
            self.peak_memory_bytes = max(self.peak_memory_bytes, peak)
            if stop_tracing:
                tracemalloc.stop()

    def _finalize_advance(
        self,
        *,
        state: State,
        solved: bool,
        advance_begin: float,
        stop_tracing: bool,
    ) -> AStarResult:
        self._update_measurements(advance_begin=advance_begin, stop_tracing=stop_tracing)
        return _build_result(
            state=state,
            solved=solved,
            expanded_nodes=self.expanded_nodes,
            generated_nodes=self.generated_nodes,
            heuristic_name=self.heuristic_name,
            elapsed_seconds=self.elapsed_seconds,
            peak_memory_bytes=self.peak_memory_bytes,
        )

    def advance(
        self,
        *,
        max_nodes: int | None = None,
        max_time_seconds: float | None = None,
    ) -> AStarResult:
        stop_tracing = False
        if not tracemalloc.is_tracing():
            tracemalloc.start()
            stop_tracing = True
        advance_begin = time.perf_counter()

        if self._solved_state is not None:
            return self._finalize_advance(
                state=self._solved_state,
                solved=True,
                advance_begin=advance_begin,
                stop_tracing=stop_tracing,
            )

        step_begin = time.perf_counter()
        step_expanded = 0

        try:
            while self.frontier:
                if max_time_seconds is not None and (time.perf_counter() - step_begin) >= max_time_seconds:
                    break
                if max_nodes is not None and step_expanded >= max_nodes:
                    break

                _, _, _, current = heapq.heappop(self.frontier)
                current_key = _search_key(current)
                if current.g != self.best_cost.get(current_key):
                    continue

                if rules.is_goal(current):
                    self._solved_state = current
                    return self._finalize_advance(
                        state=current,
                        solved=True,
                        advance_begin=advance_begin,
                        stop_tracing=stop_tracing,
                    )

                self.expanded_nodes += 1
                step_expanded += 1

                current_progress = _progress_score(current)
                if current_progress > self.best_progress:
                    self.best_progress = current_progress
                    self.best_state = current

                for move in sorted(rules.enumerate_legal_moves(current), key=_move_priority):
                    next_state = rules.apply_move(current, move)
                    next_state.h = self.heuristic_fn(next_state)
                    next_key = _search_key(next_state)

                    if next_state.g >= self.best_cost.get(next_key, float('inf')):
                        continue

                    self.best_cost[next_key] = next_state.g
                    self.generated_nodes += 1
                    next_progress = _progress_score(next_state)
                    if next_progress > self.best_progress:
                        self.best_progress = next_progress
                        self.best_state = next_state
                    priority, secondary = _frontier_priority(next_state, self.heuristic_weight)
                    heapq.heappush(
                        self.frontier,
                        (priority, secondary, next(self.tie_breaker), next_state),
                    )

            if not self.frontier:
                self._exhausted = True

            return self._finalize_advance(
                state=self.best_state,
                solved=False,
                advance_begin=advance_begin,
                stop_tracing=stop_tracing,
            )
        except Exception:
            self._update_measurements(advance_begin=advance_begin, stop_tracing=stop_tracing)
            raise


def solve_a_star(
    initial_state: State,
    heuristic: str | Heuristic = 'foundation_gap',
    max_nodes: int | None = None,
    max_time_seconds: float | None = None,
    heuristic_weight: float = 1.0,
) -> AStarResult:
    session = AStarSearchSession(
        initial_state,
        heuristic=heuristic,
        heuristic_weight=heuristic_weight,
    )
    return session.advance(max_nodes=max_nodes, max_time_seconds=max_time_seconds)
