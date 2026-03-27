from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core import rules
from core.rules import Move as CoreMove
from core.state import State
from utils.metrics import SearchMetrics, measure_search


SourceRef = Tuple[str, int, int]
TargetRef = Tuple[str, int | str]

SearchMove = Tuple[SourceRef, TargetRef]


@dataclass(frozen=True)
class UCSSearchResult:
    solved: bool
    moves: List[SearchMove]
    state_path: List[State]
    metrics: SearchMetrics


def _core_move_to_refs(state: State, move: CoreMove) -> SearchMove:
    if move.src_type == rules.LOCATION_CASCADE:
        source = ("cascade", move.src_index, len(state.cascades[move.src_index]) - move.count)
    else:
        source = ("freecell", move.src_index, 0)

    if move.dst_type == rules.LOCATION_CASCADE:
        target: TargetRef = ("cascade", move.dst_index)
    elif move.dst_type == rules.LOCATION_FREE_CELL:
        target = ("freecell", move.dst_index)
    else:
        target = ("foundation", move.dst_index)

    return (source, target)


def _refs_to_core_move(state: State, source: SourceRef, target: TargetRef) -> Optional[CoreMove]:
    src_type, src_index, src_start = source
    dst_type, dst_index = target

    if src_type == "cascade":
        if not (0 <= src_index < len(state.cascades)):
            return None
        cascade = state.cascades[src_index]
        if not (0 <= src_start < len(cascade)):
            return None
        count = len(cascade) - src_start
        src_type_core = rules.LOCATION_CASCADE
    elif src_type == "freecell":
        count = 1
        src_type_core = rules.LOCATION_FREE_CELL
    else:
        return None

    if dst_type == "cascade":
        dst_type_core = rules.LOCATION_CASCADE
    elif dst_type == "freecell":
        dst_type_core = rules.LOCATION_FREE_CELL
    elif dst_type == "foundation":
        dst_type_core = rules.LOCATION_FOUNDATION
    else:
        return None

    move = CoreMove(src_type_core, src_index, dst_type_core, dst_index, count=count)
    return move if rules.is_legal_move(state, move) else None


def _generate_single_card_moves(
    state: State,
) -> List[Tuple[SearchMove, State]]:
    """Generate legal successors from core rules."""
    successors: List[Tuple[SearchMove, State]] = []
    for move in rules.enumerate_legal_moves(state):
        nxt = rules.apply_move(state, move)
        successors.append((_core_move_to_refs(state, move), nxt))
    return successors


def _count_foundation_cards(state: State) -> int:
    return sum(state.foundations.values())


def _progress_score(state: State) -> Tuple[int, int, int]:
    """Higher tuple means better intermediate progress for partial replay."""
    foundation_cards = _count_foundation_cards(state)
    empty_free = sum(1 for c in state.free_cells if c is None)
    empty_cascades = sum(1 for c in state.cascades if len(c) == 0)
    return (foundation_cards, empty_free + empty_cascades, 0)


def _reconstruct_path(
    key: tuple,
    parent: Dict[tuple, Optional[tuple]],
    move_from_parent: Dict[tuple, SearchMove],
) -> List[SearchMove]:
    path: List[SearchMove] = []
    cursor = key
    while parent[cursor] is not None:
        path.append(move_from_parent[cursor])
        cursor = parent[cursor]  # type: ignore[assignment]
    path.reverse()
    return path


def _build_state_path(start_state: State, moves_seq: List[SearchMove]) -> List[State]:
    path: List[State] = [start_state.clone()]
    cursor = start_state.clone()
    for source, target in moves_seq:
        move = _refs_to_core_move(cursor, source, target)
        if move is None:
            break
        cursor = rules.apply_move(cursor, move)
        path.append(cursor.clone())
    return path


def get_move_cost(move: SearchMove, state: State) -> int:
    """Return dynamic UCS step cost based on move type and immediate board effect."""
    source, target = move
    src_type, src_index, src_start = source
    dst_type, _ = target

    if dst_type == "foundation":
        return 1

    # Reward creating a new empty cascade by moving the whole source cascade away.
    if src_type == "cascade":
        cascade = state.cascades[src_index]
        if len(cascade) > 0 and src_start == 0:
            return 5

    if src_type == "cascade" and dst_type == "cascade":
        return 10

    if dst_type == "freecell":
        return 50

    return 10


def solve_ucs(
    initial_state: State,
    max_nodes: int = 500_000,
    max_time_seconds: float = 30.0,
) -> UCSSearchResult:
    """Run pure Uniform-Cost Search (UCS) with unit step cost."""

    def _search() -> Tuple[bool, List[SearchMove], int]:
        start = initial_state.clone()
        start_key = start.as_key()

        frontier: List[Tuple[int, int, int, State]] = []
        tie_breaker = 0
        heapq.heappush(frontier, (0, 0, tie_breaker, start))

        best_g: Dict[tuple, int] = {start_key: 0}
        parent: Dict[tuple, Optional[tuple]] = {start_key: None}
        move_from_parent: Dict[tuple, SearchMove] = {}

        best_progress_key = start_key
        best_progress_score = _progress_score(start)

        expanded_nodes = 0
        begin = time.perf_counter()

        while frontier:
            if expanded_nodes >= max_nodes:
                break
            if (time.perf_counter() - begin) >= max_time_seconds:
                break

            _, g_cost, _, state = heapq.heappop(frontier)
            key = state.as_key()

            if g_cost > best_g.get(key, 10**18):
                continue

            if rules.is_goal(state):
                return True, _reconstruct_path(key, parent, move_from_parent), expanded_nodes

            expanded_nodes += 1

            current_progress = _progress_score(state)
            if current_progress > best_progress_score:
                best_progress_score = current_progress
                best_progress_key = key

            for move, next_state in _generate_single_card_moves(state):
                next_key = next_state.as_key()
                next_g = g_cost + get_move_cost(move, state)
                if next_g < best_g.get(next_key, 10**18):
                    best_g[next_key] = next_g
                    parent[next_key] = key
                    move_from_parent[next_key] = move
                    next_progress = _progress_score(next_state)
                    if next_progress > best_progress_score:
                        best_progress_score = next_progress
                        best_progress_key = next_key
                    tie_breaker += 1
                    heapq.heappush(frontier, (next_g, next_g, tie_breaker, next_state))

        return False, _reconstruct_path(best_progress_key, parent, move_from_parent), expanded_nodes

    solved, moves, expanded_nodes, metrics = measure_search(_search)
    state_path = _build_state_path(initial_state, moves)
    metrics.expanded_nodes = expanded_nodes
    metrics.solution_steps = len(moves)
    return UCSSearchResult(solved=solved, moves=moves, state_path=state_path, metrics=metrics)
