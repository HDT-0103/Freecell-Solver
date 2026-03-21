from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core import rules
from core.rules import Move as CoreMove
from core.state import Card, State
from utils.metrics import SearchMetrics, measure_search

# Re-use type aliases from ucs convention
SourceRef = Tuple[str, int, int]
TargetRef = Tuple[str, int | str]
SearchMove = Tuple[SourceRef, TargetRef]


@dataclass
class DFSSearchResult:
    solved: bool
    moves: List[SearchMove]
    state_path: List[State]
    metrics: SearchMetrics


# ------------------------------------------------------------------
# Shared helpers (same logic as ucs.py)
# ------------------------------------------------------------------

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


def _generate_moves(state: State) -> List[Tuple[SearchMove, State]]:
    successors: List[Tuple[SearchMove, State]] = []
    for move in rules.enumerate_legal_moves(state):
        nxt = rules.apply_move(state, move)
        successors.append((_core_move_to_refs(state, move), nxt))
    return successors


def _count_foundation_cards(state: State) -> int:
    return sum(state.foundations.values())


def _progress_score(state: State) -> Tuple[int, int]:
    foundation_cards = _count_foundation_cards(state)
    empty_free = sum(1 for c in state.free_cells if c is None)
    return (foundation_cards, empty_free)


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


# ------------------------------------------------------------------
# DFS search
# ------------------------------------------------------------------

def solve_dfs(
    initial_state: State,
    max_nodes: int = 500_000,
    max_time_seconds: float = 30.0,
    max_depth: int = 200,
) -> DFSSearchResult:
    """Iterative DFS with visited set to avoid cycles.

    Uses an explicit stack instead of recursion to avoid Python stack overflow.
    Tracks the best partial solution found (most foundation cards placed).
    """

    def _search() -> Tuple[bool, List[SearchMove], int]:
        start = initial_state.clone()
        start_key = start.as_key()
        begin = time.perf_counter()

        # Stack entries: (state, move_path_so_far)
        # Using list of (SearchMove) as path from root to this node
        stack: List[Tuple[State, List[SearchMove]]] = [(start, [])]

        visited: Dict[tuple, int] = {start_key: 0}  # key → depth first seen

        best_partial_moves: List[SearchMove] = []
        best_progress = _progress_score(start)
        expanded_nodes = 0

        while stack:
            if expanded_nodes >= max_nodes:
                break
            if (time.perf_counter() - begin) >= max_time_seconds:
                break

            state, path = stack.pop()

            if rules.is_goal(state):
                return True, path, expanded_nodes

            current_depth = len(path)
            if current_depth >= max_depth:
                continue

            # Track best partial solution
            progress = _progress_score(state)
            if progress > best_progress:
                best_progress = progress
                best_partial_moves = list(path)

            expanded_nodes += 1

            # Push successors in reverse order so highest-priority is popped first
            successors = _generate_moves(state)
            # Sort: prefer moves that send cards to foundation first
            successors.sort(
                key=lambda x: _count_foundation_cards(x[1]),
                reverse=False,   # push best last so it's popped first
            )

            for move, next_state in successors:
                next_key = next_state.as_key()
                next_depth = current_depth + 1

                # Only revisit if we reach with a strictly shallower depth
                if visited.get(next_key, 10**18) <= next_depth:
                    continue

                visited[next_key] = next_depth
                stack.append((next_state, path + [move]))

        return False, best_partial_moves, expanded_nodes

    solved, moves, expanded_nodes, metrics = measure_search(_search)
    state_path = _build_state_path(initial_state, moves)
    metrics.expanded_nodes = expanded_nodes
    metrics.solution_steps = len(moves)
    return DFSSearchResult(solved=solved, moves=moves, state_path=state_path, metrics=metrics)