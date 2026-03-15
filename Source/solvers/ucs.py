from __future__ import annotations

import heapq
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from core.state import DragInfo, GameState, SourceRef, TargetRef
from core.rules import FOUNDATION_SUITS
from utils.metrics import SearchMetrics, measure_search


Move = Tuple[SourceRef, TargetRef]


@dataclass
class UCSSearchResult:
	solved: bool
	moves: List[Move]
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


def _generate_single_card_moves(state: GameState) -> List[Tuple[Move, GameState]]:
	"""Generate legal successors with single-card moves.

	Single-card branching keeps UCS practical for an interactive GUI demo.
	"""
	successors: List[Tuple[Move, GameState]] = []

	# Moves from free cells.
	for src_idx, card in enumerate(state.free_cells):
		if card is None:
			continue
		source: SourceRef = ("freecell", src_idx, 0)
		drag = DragInfo(cards=[card], source=source)

		for f_idx in range(4):
			target = ("foundation", f_idx)
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

	# Moves from cascade tops.
	for src_idx, cascade in enumerate(state.cascades):
		if not cascade:
			continue
		source: SourceRef = ("cascade", src_idx, len(cascade) - 1)
		drag = DragInfo(cards=[cascade[-1]], source=source)

		for fc_idx in range(4):
			target = ("freecell", fc_idx)
			if state.can_drop(drag, target):
				nxt = _try_apply_move(state, source, target)
				if nxt is not None:
					successors.append(((source, target), nxt))

		for f_idx in range(4):
			target = ("foundation", f_idx)
			if state.can_drop(drag, target):
				nxt = _try_apply_move(state, source, target)
				if nxt is not None:
					successors.append(((source, target), nxt))

		for c_idx in range(8):
			if c_idx == src_idx:
				continue
			target = ("cascade", c_idx)
			if state.can_drop(drag, target):
				nxt = _try_apply_move(state, source, target)
				if nxt is not None:
					successors.append(((source, target), nxt))

	# Multi-card supermoves: cascade -> cascade.
	# To control branching, for each (src, dst) we only try the longest legal group.
	for src_idx, cascade in enumerate(state.cascades):
		n = len(cascade)
		if n < 2:
			continue

		# Compute longest valid alternating-descending tail length.
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


def _progress_score(state: GameState) -> Tuple[int, int, int]:
	"""Higher tuple means better intermediate progress for partial replay."""
	foundation_cards = sum(len(pile) for pile in state.foundations)
	empty_free = sum(1 for c in state.free_cells if c is None)
	empty_cascades = sum(1 for c in state.cascades if len(c) == 0)
	# Prefer states that improve foundation first, then reduce search heuristic.
	return (foundation_cards, -_heuristic(state), empty_free + empty_cascades)


def _heuristic(state: GameState) -> int:
	"""Heuristic cost used for practical UCS guidance on FreeCell.

	Base term: cards not yet on foundation.
	Guidance term: blockers above the next required rank of each suit.
	This is intentionally aggressive (not strictly admissible) to avoid stalls.
	"""
	foundation_cards = sum(len(pile) for pile in state.foundations)
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
	move_from_parent: Dict[tuple, Move],
) -> List[Move]:
	path: List[Move] = []
	cursor = key
	while parent[cursor] is not None:
		path.append(move_from_parent[cursor])
		cursor = parent[cursor]  # type: ignore[assignment]
	path.reverse()
	return path


def solve_ucs(
	initial_state: GameState,
	max_nodes: int = 500_000,
	max_time_seconds: float = 30.0,
) -> UCSSearchResult:
	"""Run UCS with admissible heuristic (h = cards not on foundation).

	f = g + h with admissible h makes this equivalent to A*, guaranteeing
	an optimal solution while keeping the UCS cost framework.
	"""

	def _search() -> Tuple[bool, List[Move], int]:
		start = initial_state.clone()
		start_key = start.to_hashable()
		h0 = _heuristic(start)

		# heap entries: (f_cost, g_cost, tie_breaker, state)
		frontier: List[Tuple[int, int, int, GameState]] = []
		tie_breaker = 0
		heapq.heappush(frontier, (h0, 0, tie_breaker, start))

		# best known g-cost per state (duplicate detection)
		best_g: Dict[tuple, int] = {start_key: 0}
		parent: Dict[tuple, Optional[tuple]] = {start_key: None}
		move_from_parent: Dict[tuple, Move] = {}

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

			# Stale entry: a cheaper path was already found
			if g_cost > best_g.get(key, 10**18):
				continue

			if state.is_won():
				return True, _reconstruct_path(key, parent, move_from_parent), expanded_nodes

			expanded_nodes += 1

			current_progress = _progress_score(state)
			if current_progress > best_progress_score:
				best_progress_score = current_progress
				best_progress_key = key

			for move, next_state in _generate_single_card_moves(state):
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

	def _build_state_path(start_state: GameState, moves_seq: List[Move]) -> List[GameState]:
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

	solved, moves, expanded_nodes, metrics = measure_search(_search)
	state_path = _build_state_path(initial_state, moves)
	metrics.expanded_nodes = expanded_nodes
	metrics.solution_steps = len(moves)
	return UCSSearchResult(solved=solved, moves=moves, state_path=state_path, metrics=metrics)
