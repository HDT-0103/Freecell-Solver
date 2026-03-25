from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    from core import rules
    from core.rules import Move as CoreMove
    from core.state import Card, State
    from utils.metrics import SearchMetrics, measure_search
except ModuleNotFoundError:
    from Source.core import rules
    from Source.core.rules import Move as CoreMove
    from Source.core.state import Card, State
    from Source.utils.metrics import SearchMetrics, measure_search

# ── Type aliases (same as ucs.py) ─────────────────────────────────────────────
SourceRef  = Tuple[str, int, int]
TargetRef  = Tuple[str, int | str]
SearchMove = Tuple[SourceRef, TargetRef]


@dataclass
class DFSSearchResult:
    solved: bool
    moves: List[SearchMove]
    state_path: List[State]
    metrics: SearchMetrics


# ── Shared helpers (same logic as ucs.py) ─────────────────────────────────────

def _core_move_to_refs(state: State, move: CoreMove) -> SearchMove:
    if move.src_type == rules.LOCATION_CASCADE:
        source = ("cascade", move.src_index,
                  len(state.cascades[move.src_index]) - move.count)
    else:
        source = ("freecell", move.src_index, 0)

    if move.dst_type == rules.LOCATION_CASCADE:
        target: TargetRef = ("cascade", move.dst_index)
    elif move.dst_type == rules.LOCATION_FREE_CELL:
        target = ("freecell", move.dst_index)
    else:
        target = ("foundation", move.dst_index)

    return (source, target)


def _refs_to_core_move(state: State,
                       source: SourceRef,
                       target: TargetRef) -> Optional[CoreMove]:
    src_type, src_index, src_start = source
    dst_type, dst_index = target

    if src_type == "cascade":
        if not (0 <= src_index < len(state.cascades)):
            return None
        cascade = state.cascades[src_index]
        if not (0 <= src_start < len(cascade)):
            return None
        count        = len(cascade) - src_start
        src_type_core = rules.LOCATION_CASCADE
    elif src_type == "freecell":
        count        = 1
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

    move = CoreMove(src_type_core, src_index, dst_type_core, dst_index,
                    count=count)
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
    empty_free       = sum(1 for c in state.free_cells if c is None)
    return (foundation_cards, empty_free)


def _build_state_path(start_state: State,
                      moves_seq: List[SearchMove]) -> List[State]:
    path: List[State] = [start_state.clone()]
    cursor = start_state.clone()
    for source, target in moves_seq:
        move = _refs_to_core_move(cursor, source, target)
        if move is None:
            break
        cursor = rules.apply_move(cursor, move)
        path.append(cursor.clone())
    return path


# ── IDS core ──────────────────────────────────────────────────────────────────

# Sentinel returned when the DLS finds a node deeper than the limit
_CUTOFF = "CUTOFF"


def _dls(
    state:        State,
    path:         List[SearchMove],
    visited:      Dict[tuple, int],
    depth_limit:  int,
    expanded:     list,          # mutable counter [total_expanded]
    begin:        float,
    max_nodes:    int,
    max_time:     float,
    best:         list,          # mutable [best_moves, best_progress]
) -> str | bool:
    """
    Depth-Limited Search (recursive DFS up to depth_limit).

    Returns:
        True          — goal found, `path` contains the solution moves
        False         — exhausted this branch, no solution and no cutoff
        _CUTOFF       — hit the depth limit (signal to IDS to deepen)
    """
    # Resource check
    if expanded[0] >= max_nodes or (time.perf_counter() - begin) >= max_time:
        return False

    # Goal check (early — check before expanding)
    if rules.is_goal(state):
        return True

    # Depth limit reached → signal cutoff
    if len(path) >= depth_limit:
        return _CUTOFF

    expanded[0] += 1

    # Track best partial solution
    progress = _progress_score(state)
    if progress > best[1]:
        best[1] = progress
        best[0] = list(path)

    # Generate and order successors:
    # prefer moves that send cards to foundation (greedy ordering inside DFS)
    successors = _generate_moves(state)
    successors.sort(key=lambda x: _count_foundation_cards(x[1]), reverse=True)

    cutoff_occurred = False

    for move, next_state in successors:
        next_key   = next_state.as_key()
        next_depth = len(path) + 1

        # Repeated-state check — allow revisit only at strictly shallower depth
        if visited.get(next_key, 10**18) <= next_depth:
            continue

        visited[next_key] = next_depth
        path.append(move)

        result = _dls(next_state, path, visited, depth_limit,
                      expanded, begin, max_nodes, max_time, best)

        if result is True:
            return True          # solution found — propagate up immediately
        if result is _CUTOFF:
            cutoff_occurred = True

        path.pop()
        # restore visited depth so sibling branches can try this state

    return _CUTOFF if cutoff_occurred else False


# ── Public API ────────────────────────────────────────────────────────────────

def solve_dfs(
    initial_state:    State,
    max_nodes:        int   = 500_000,
    max_time_seconds: float = 30.0,
    max_depth:        int   = 200,
    start_depth:      int   = 1,
    depth_step:       int   = 1,
) -> DFSSearchResult:
    """
    Iterative Deepening Search (IDS) FreeCell solver.

    IDS runs DLS repeatedly with depth limits 1, 2, 3, … up to max_depth.
    This gives BFS-like optimality (shortest solution) with DFS-like memory.
    Repeated states within each DLS iteration are tracked via a visited dict
    keyed by state hash to avoid cycles.

    Args:
        initial_state:    Starting FreeCell state.
        max_nodes:        Hard cap on total node expansions across all iterations.
        max_time_seconds: Wall-clock time budget.
        max_depth:        Maximum depth limit to try.
        start_depth:      Initial depth limit (default 1).
        depth_step:       How much to increase the depth limit each iteration.
    """

    def _search() -> Tuple[bool, List[SearchMove], int]:
        begin    = time.perf_counter()
        expanded = [0]                       # shared mutable counter
        best     = [[], (-1, -1)]            # [best_moves, best_progress]

        for depth_limit in range(start_depth, max_depth + 1, depth_step):
            # Resource exhausted before deepening further
            if expanded[0] >= max_nodes:
                break
            if (time.perf_counter() - begin) >= max_time_seconds:
                break

            path    = []
            visited = {initial_state.as_key(): 0}

            result = _dls(
                initial_state, path, visited,
                depth_limit, expanded, begin,
                max_nodes, max_time_seconds, best,
            )

            if result is True:
                # Solution found at this depth
                return True, list(path), expanded[0]

            if result is False:
                # Search space fully exhausted — no solution exists
                break

            # result is _CUTOFF → increase depth and retry

        return False, best[0], expanded[0]

    solved, moves, expanded_nodes, metrics = measure_search(_search)
    state_path = _build_state_path(initial_state, moves)
    metrics.expanded_nodes  = expanded_nodes
    metrics.solution_steps  = len(moves)
    return DFSSearchResult(solved=solved, moves=moves,
                           state_path=state_path, metrics=metrics)