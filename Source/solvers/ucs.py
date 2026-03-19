from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core import rules
from core.rules import Move as CoreMove
from core.state import Card, State
from utils.metrics import SearchMetrics, measure_search


SourceRef = Tuple[str, int, int]
TargetRef = Tuple[str, int | str]

SearchMove = Tuple[SourceRef, TargetRef]


@dataclass(frozen=True)
class Move:
    card: Card
    source: SourceRef
    target: TargetRef
    depth: int
    score: int


@dataclass
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
    *,
    include_foundation_backmoves: bool = False,
) -> List[Tuple[SearchMove, State]]:
    """Generate legal successors from core rules.

    include_foundation_backmoves is kept for API compatibility and is intentionally
    ignored because core rules do not allow foundation as a source.
    """
    _ = include_foundation_backmoves
    successors: List[Tuple[SearchMove, State]] = []
    for move in rules.enumerate_legal_moves(state):
        nxt = rules.apply_move(state, move)
        successors.append((_core_move_to_refs(state, move), nxt))
    return successors


def _count_foundation_cards(state: State) -> int:
    return sum(state.foundations.values())


def _low_rank_blocker_penalty(state: State) -> int:
    penalty = 0
    attachable_low_cards = 0

    for cascade in state.cascades:
        for idx, card in enumerate(cascade):
            if card.rank not in (1, 2):
                continue
            blockers = len(cascade) - 1 - idx
            if blockers > 0:
                weight = 18 if card.rank == 1 else 12
                penalty += blockers * weight
            else:
                attachable_low_cards += 1

    for card in state.free_cells:
        if card is not None and card.rank in (1, 2):
            attachable_low_cards += 1

    return penalty - (attachable_low_cards * 8)


def _hint_score(state: State) -> int:
    foundation_cards = _count_foundation_cards(state)
    empty_free_cells = sum(1 for card in state.free_cells if card is None)
    empty_tableau = sum(1 for cascade in state.cascades if not cascade)
    blocked_low_penalty = _low_rank_blocker_penalty(state)

    return (
        foundation_cards * 120
        + empty_free_cells * 18
        + empty_tableau * 28
        - blocked_low_penalty
    )


def _progress_score(state: State) -> Tuple[int, int, int]:
    """Higher tuple means better intermediate progress for partial replay."""
    foundation_cards = _count_foundation_cards(state)
    empty_free = sum(1 for c in state.free_cells if c is None)
    empty_cascades = sum(1 for c in state.cascades if len(c) == 0)
    return (foundation_cards, -_heuristic(state), empty_free + empty_cascades)


def _heuristic(state: State) -> int:
    """Heuristic cost used for practical UCS guidance on FreeCell."""
    foundation_cards = _count_foundation_cards(state)
    remaining = 52 - foundation_cards
    if remaining == 0:
        return 0

    next_needed: Dict[str, int] = {suit: state.foundations[suit] + 1 for suit in ("C", "D", "H", "S")}

    blockers = 0
    for suit, rank in next_needed.items():
        if rank > 13:
            continue

        found = False

        for card in state.free_cells:
            if card is not None and card.suit == suit and card.rank == rank:
                found = True
                break

        if found:
            continue

        for cascade in state.cascades:
            for idx, card in enumerate(cascade):
                if card.suit == suit and card.rank == rank:
                    blockers += len(cascade) - 1 - idx
                    found = True
                    break
            if found:
                break

    occupied_free = sum(1 for c in state.free_cells if c is not None)
    return remaining + (2 * blockers) + occupied_free


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


def _card_from_source(state: State, source: SourceRef) -> Optional[Card]:
    location, index, start = source
    if location == "freecell":
        return state.free_cells[index]
    if location == "foundation":
        suit = index if isinstance(index, str) else ("C", "D", "H", "S")[index]
        rank = state.foundations[suit]
        return Card(rank=rank, suit=suit) if rank > 0 else None
    cascade = state.cascades[index]
    if not (0 <= start < len(cascade)):
        return None
    return cascade[start]


def get_hint(
    initial_state: State,
    *,
    max_depth: int = 6,
    max_nodes: int = 25_000,
    max_time_seconds: float = 0.35,
    allow_foundation_backmoves: bool = False,
) -> Optional[Move]:
    """Return the strongest bounded-UCS move from the current state for real-time hinting."""
    start = initial_state.clone()
    start_key = start.as_key()
    start_score = _hint_score(start)
    begin = time.perf_counter()

    frontier: List[Tuple[int, int, int, State]] = []
    tie_breaker = 0
    heapq.heappush(frontier, (0, -start_score, tie_breaker, start))

    visited: Dict[tuple, Tuple[int, int]] = {start_key: (0, start_score)}
    parent: Dict[tuple, Optional[tuple]] = {start_key: None}
    move_from_parent: Dict[tuple, SearchMove] = {}

    best_key = start_key
    best_rank = (-10**9, -10**9, -10**9)
    expanded_nodes = 0

    while frontier and expanded_nodes < max_nodes:
        if (time.perf_counter() - begin) >= max_time_seconds:
            break
        depth, _, _, state = heapq.heappop(frontier)
        state_key = state.as_key()
        current_depth, current_score = visited[state_key]
        if depth != current_depth:
            continue

        if depth > 0:
            rank = (
                current_score,
                _count_foundation_cards(state),
                -depth,
            )
            if rank > best_rank:
                best_rank = rank
                best_key = state_key

        if rules.is_goal(state):
            best_key = state_key
            break

        if depth >= max_depth:
            continue

        expanded_nodes += 1
        for move, next_state in _generate_single_card_moves(
            state,
            include_foundation_backmoves=allow_foundation_backmoves,
        ):
            next_key = next_state.as_key()
            next_depth = depth + 1
            next_score = _hint_score(next_state)
            seen = visited.get(next_key)
            if seen is not None and next_depth > seen[0]:
                continue
            if seen is not None and next_depth == seen[0] and next_score <= seen[1]:
                continue

            visited[next_key] = (next_depth, next_score)
            parent[next_key] = state_key
            move_from_parent[next_key] = move
            tie_breaker += 1
            heapq.heappush(frontier, (next_depth, -next_score, tie_breaker, next_state))

    path = _reconstruct_path(best_key, parent, move_from_parent)
    if not path:
        return None

    first_move = path[0]
    card = _card_from_source(initial_state, first_move[0])
    if card is None:
        return None

    best_depth, best_score = visited.get(best_key, (len(path), start_score))
    return Move(card=card, source=first_move[0], target=first_move[1], depth=best_depth, score=best_score)


def solve_ucs(
    initial_state: State,
    max_nodes: int = 500_000,
    max_time_seconds: float = 30.0,
) -> UCSSearchResult:
    """Run UCS with admissible heuristic (h = cards not on foundation)."""

    def _search() -> Tuple[bool, List[SearchMove], int]:
        start = initial_state.clone()
        start_key = start.as_key()
        h0 = _heuristic(start)

        frontier: List[Tuple[int, int, int, State]] = []
        tie_breaker = 0
        heapq.heappush(frontier, (h0, 0, tie_breaker, start))

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

            for move, next_state in _generate_single_card_moves(state, include_foundation_backmoves=False):
                next_key = next_state.as_key()
                next_g = g_cost + 1
                if next_g < best_g.get(next_key, 10**18):
                    best_g[next_key] = next_g
                    parent[next_key] = key
                    move_from_parent[next_key] = move
                    next_h = _heuristic(next_state)
                    next_f = next_g + next_h
                    next_progress = _progress_score(next_state)
                    if next_progress > best_progress_score:
                        best_progress_score = next_progress
                        best_progress_key = next_key
                    tie_breaker += 1
                    heapq.heappush(frontier, (next_f, next_g, tie_breaker, next_state))

        return False, _reconstruct_path(best_progress_key, parent, move_from_parent), expanded_nodes

    solved, moves, expanded_nodes, metrics = measure_search(_search)
    state_path = _build_state_path(initial_state, moves)
    metrics.expanded_nodes = expanded_nodes
    metrics.solution_steps = len(moves)
    return UCSSearchResult(solved=solved, moves=moves, state_path=state_path, metrics=metrics)
