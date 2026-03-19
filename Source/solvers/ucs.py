from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.state import CardData, DragInfo, GameState, SourceRef, TargetRef
from core.rules import FOUNDATION_SUITS
from utils.metrics import SearchMetrics, measure_search


SearchMove = Tuple[SourceRef, TargetRef]


@dataclass(frozen=True)
class Move:
	card: CardData
	source: SourceRef
	target: TargetRef
	depth: int
	score: int


@dataclass
class UCSSearchResult:
	solved: bool
	moves: List[SearchMove]
	state_path: List[GameState]
	metrics: SearchMetrics


def _try_apply_move(state: GameState, source: SourceRef, target: TargetRef) -> Optional[GameState]:
	next_state = state.clone()
	drag = next_state.pick_cards(source)
	if drag is None:
		return None
	if next_state.apply_drop(drag, target):
		return next_state
	next_state.cancel_drag(drag)
	return None


def _iter_single_card_sources(state: GameState) -> List[Tuple[SourceRef, CardData]]:
	sources: List[Tuple[SourceRef, CardData]] = []

	for src_idx, card in enumerate(state.free_cells):
		if card is not None:
			sources.append((("freecell", src_idx, 0), card))

	for src_idx, cascade in enumerate(state.cascades):
		if cascade:
			sources.append((("cascade", src_idx, len(cascade) - 1), cascade[-1]))

	return sources


def _generate_single_card_moves(
	state: GameState,
	*,
	include_foundation_backmoves: bool = False,
) -> List[Tuple[SearchMove, GameState]]:
	"""Generate legal successors with single-card moves.

	Single-card branching keeps UCS practical for an interactive GUI demo.
	"""
	successors: List[Tuple[SearchMove, GameState]] = []

	for source, card in _iter_single_card_sources(state):
		drag = DragInfo(cards=[card], source=source)

		for f_idx in range(4):
			target = ("foundation", f_idx)
			if state.can_drop(drag, target):
				nxt = _try_apply_move(state, source, target)
				if nxt is not None:
					successors.append(((source, target), nxt))

		if source[0] != "freecell":
			for fc_idx in range(4):
				target = ("freecell", fc_idx)
				if state.can_drop(drag, target):
					nxt = _try_apply_move(state, source, target)
					if nxt is not None:
						successors.append(((source, target), nxt))

		for c_idx in range(8):
			target = ("cascade", c_idx)
			if state.can_drop(drag, target):
				nxt = _try_apply_move(state, source, target)
				if nxt is not None:
					successors.append(((source, target), nxt))

	if include_foundation_backmoves:
		for foundation_idx, pile in enumerate(state.foundations):
			if not pile:
				continue
			card = pile[-1]
			if card.rank > 3:
				continue
			source: SourceRef = ("foundation", foundation_idx, len(pile) - 1)
			drag = DragInfo(cards=[card], source=source)
			for cascade_idx in range(8):
				target = ("cascade", cascade_idx)
				if state.can_drop(drag, target):
					nxt = _try_apply_move(state, source, target)
					if nxt is not None:
						successors.append(((source, target), nxt))

	for src_idx, cascade in enumerate(state.cascades):
		n = len(cascade)
		if n < 2:
			continue

		max_tail = 1
		for pos in range(n - 2, -1, -1):
			if cascade[pos + 1].can_stack_on(cascade[pos]):
				max_tail += 1
			else:
				break

		for dst_idx in range(8):
			if dst_idx == src_idx:
				continue

			max_len = min(max_tail, state._max_movable(dst_idx))
			if max_len < 2:
				continue

			dst_col = state.cascades[dst_idx]
			chosen_len = 0
			for move_len in range(max_len, 1, -1):
				bottom_card = cascade[n - move_len]
				if not dst_col or bottom_card.can_stack_on(dst_col[-1]):
					chosen_len = move_len
					break

			if chosen_len == 0:
				continue

			start_depth = n - chosen_len
			source = ("cascade", src_idx, start_depth)
			target = ("cascade", dst_idx)
			nxt = _try_apply_move(state, source, target)
			if nxt is not None:
				successors.append(((source, target), nxt))

	return successors


def _count_foundation_cards(state: GameState) -> int:
	return sum(len(pile) for pile in state.foundations)


def _low_rank_blocker_penalty(state: GameState) -> int:
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


def _hint_score(state: GameState) -> int:
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


def _progress_score(state: GameState) -> Tuple[int, int, int]:
	"""Higher tuple means better intermediate progress for partial replay."""
	foundation_cards = _count_foundation_cards(state)
	empty_free = sum(1 for c in state.free_cells if c is None)
	empty_cascades = sum(1 for c in state.cascades if len(c) == 0)
	return (foundation_cards, -_heuristic(state), empty_free + empty_cascades)


def _heuristic(state: GameState) -> int:
	"""Heuristic cost used for practical UCS guidance on FreeCell."""
	foundation_cards = _count_foundation_cards(state)
	remaining = 52 - foundation_cards
	if remaining == 0:
		return 0

	next_needed: Dict[str, int] = {}
	for idx, suit in enumerate(FOUNDATION_SUITS):
		next_needed[suit] = len(state.foundations[idx]) + 1

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


def _build_state_path(start_state: GameState, moves_seq: List[SearchMove]) -> List[GameState]:
	path: List[GameState] = [start_state.clone()]
	cursor = start_state.clone()
	for source, target in moves_seq:
		drag = cursor.pick_cards(source)
		if drag is None:
			break
		if not cursor.apply_drop(drag, target):
			cursor.cancel_drag(drag)
			break
		path.append(cursor.clone())
	return path


def _card_from_source(state: GameState, source: SourceRef) -> Optional[CardData]:
	location, index, start = source
	if location == "freecell":
		return state.free_cells[index]
	if location == "foundation":
		pile = state.foundations[index]
		return pile[-1] if pile else None
	cascade = state.cascades[index]
	if not (0 <= start < len(cascade)):
		return None
	return cascade[start]


def get_hint(
	initial_state: GameState,
	*,
	max_depth: int = 6,
	max_nodes: int = 25_000,
	max_time_seconds: float = 0.35,
	allow_foundation_backmoves: bool = True,
) -> Optional[Move]:
	"""Return the strongest bounded-UCS move from the current state for real-time hinting."""
	start = initial_state.clone()
	start_key = start.to_hashable()
	start_score = _hint_score(start)
	begin = time.perf_counter()

	frontier: List[Tuple[int, int, int, GameState]] = []
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
		state_key = state.to_hashable()
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

		if state.is_won():
			best_key = state_key
			break

		if depth >= max_depth:
			continue

		expanded_nodes += 1
		for move, next_state in _generate_single_card_moves(
			state,
			include_foundation_backmoves=allow_foundation_backmoves,
		):
			next_key = next_state.to_hashable()
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
	initial_state: GameState,
	max_nodes: int = 500_000,
	max_time_seconds: float = 30.0,
) -> UCSSearchResult:
	"""Run UCS with admissible heuristic (h = cards not on foundation)."""

	def _search() -> Tuple[bool, List[SearchMove], int]:
		start = initial_state.clone()
		start_key = start.to_hashable()
		h0 = _heuristic(start)

		frontier: List[Tuple[int, int, int, GameState]] = []
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

			f_cost, g_cost, _, state = heapq.heappop(frontier)
			key = state.to_hashable()

			if g_cost > best_g.get(key, 10**18):
				continue

			if state.is_won():
				return True, _reconstruct_path(key, parent, move_from_parent), expanded_nodes

			expanded_nodes += 1

			current_progress = _progress_score(state)
			if current_progress > best_progress_score:
				best_progress_score = current_progress
				best_progress_key = key

			for move, next_state in _generate_single_card_moves(state, include_foundation_backmoves=False):
				next_key = next_state.to_hashable()
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
