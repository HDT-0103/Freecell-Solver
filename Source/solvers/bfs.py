from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Set, Tuple

try:
	from core import rules
	from core.rules import Move as CoreMove
	from core.state import State
	from utils.metrics import SearchMetrics, measure_search
except ModuleNotFoundError:
	from Source.core import rules
	from Source.core.rules import Move as CoreMove
	from Source.core.state import State
	from Source.utils.metrics import SearchMetrics, measure_search


SourceRef = Tuple[str, int, int]
TargetRef = Tuple[str, int | str]
SearchMove = Tuple[SourceRef, TargetRef]
StateKey = Tuple[Tuple[Tuple[int, ...], ...], Tuple[int, ...], Tuple[int, int, int, int]]

_SUIT_TO_ID = {"H": 0, "D": 1, "C": 2, "S": 3}


@dataclass
class BFSSearchResult:
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


def _move_priority(move: CoreMove) -> Tuple[int, int]:
	if move.dst_type == rules.LOCATION_FOUNDATION:
		return (0, move.count)
	if move.src_type == rules.LOCATION_FREE_CELL and move.dst_type == rules.LOCATION_CASCADE:
		return (1, -move.count)
	if move.src_type == rules.LOCATION_CASCADE and move.dst_type == rules.LOCATION_CASCADE:
		return (2, -move.count)
	if move.dst_type == rules.LOCATION_FREE_CELL:
		return (3, move.count)
	return (4, move.count)


def _encode_card(card) -> int:
	# 0 is reserved for None in free cells.
	return card.rank * 4 + _SUIT_TO_ID[card.suit] + 1


def _fast_state_key(state: State) -> StateKey:
	# Faster than hashing dataclass Card objects directly in State.as_key().
	cascades_key = tuple(tuple(_encode_card(card) for card in cascade) for cascade in state.cascades)
	free_cells_key = tuple(0 if card is None else _encode_card(card) for card in state.free_cells)
	foundations_key = (
		state.foundations["H"],
		state.foundations["D"],
		state.foundations["C"],
		state.foundations["S"],
	)
	return (cascades_key, free_cells_key, foundations_key)


def _is_inverse_move(move: CoreMove, previous_move: Optional[CoreMove]) -> bool:
	if previous_move is None:
		return False
	return (
		move.src_type == previous_move.dst_type
		and move.dst_type == previous_move.src_type
		and move.src_index == previous_move.dst_index
		and move.dst_index == previous_move.src_index
		and move.count == previous_move.count
	)


def _generate_moves(state: State) -> List[Tuple[CoreMove, SearchMove, State]]:
	successors: List[Tuple[CoreMove, SearchMove, State]] = []
	for move in sorted(rules.enumerate_legal_moves(state), key=_move_priority):
		nxt = rules.apply_move(state, move)
		successors.append((move, _core_move_to_refs(state, move), nxt))
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


def _reconstruct_path(
	goal_key: StateKey,
	parent: Dict[StateKey, Optional[StateKey]],
	move_from_parent: Dict[StateKey, SearchMove],
) -> List[SearchMove]:
	path: List[SearchMove] = []
	cursor = goal_key
	while parent[cursor] is not None:
		path.append(move_from_parent[cursor])
		cursor = parent[cursor]  # type: ignore[assignment]
	path.reverse()
	return path


def solve_bfs(
	initial_state: State,
	max_nodes: int = 500_000,
	max_time_seconds: float = 30.0,
) -> BFSSearchResult:
	"""Iterative BFS graph search.

	Rule: once a node has entered frontier, it is marked reached immediately and
	can never be enqueued again.
	"""

	def _search() -> Tuple[bool, List[SearchMove], int]:
		start = initial_state.clone()
		start_key = _fast_state_key(start)
		begin = time.perf_counter()

		# Queue entries: (state_key, state, move_from_parent)
		frontier: Deque[Tuple[StateKey, State, Optional[CoreMove]]] = deque([(start_key, start, None)])

		# Reached set includes both frontier and already-expanded nodes.
		reached: Set[StateKey] = {start_key}

		# Parent links let us reconstruct solution without copying full path per node.
		parent: Dict[StateKey, Optional[StateKey]] = {start_key: None}
		move_from_parent: Dict[StateKey, SearchMove] = {}

		best_partial_key = start_key
		best_progress = _progress_score(start)
		expanded_nodes = 0

		while frontier:
			if expanded_nodes >= max_nodes:
				break
			if (time.perf_counter() - begin) >= max_time_seconds:
				break

			state_key, state, incoming_move = frontier.popleft()

			progress = _progress_score(state)
			if progress > best_progress:
				best_progress = progress
				best_partial_key = state_key

			if rules.is_goal(state):
				return True, _reconstruct_path(state_key, parent, move_from_parent), expanded_nodes

			expanded_nodes += 1

			for core_move, move, next_state in _generate_moves(state):
				# Safe pruning: immediate reversal only returns to parent state.
				if _is_inverse_move(core_move, incoming_move):
					continue

				next_key = _fast_state_key(next_state)

				# Strict BFS graph-search rule:
				# once discovered (enqueued), never enqueue again.
				if next_key in reached:
					continue

				reached.add(next_key)
				parent[next_key] = state_key
				move_from_parent[next_key] = move

				next_progress = _progress_score(next_state)
				if next_progress > best_progress:
					best_progress = next_progress
					best_partial_key = next_key

				if rules.is_goal(next_state):
					return True, _reconstruct_path(next_key, parent, move_from_parent), expanded_nodes

				frontier.append((next_key, next_state, core_move))

		return False, _reconstruct_path(best_partial_key, parent, move_from_parent), expanded_nodes

	solved, moves, expanded_nodes, metrics = measure_search(_search)
	state_path = _build_state_path(initial_state, moves)
	metrics.expanded_nodes = expanded_nodes
	metrics.solution_steps = len(moves)
	return BFSSearchResult(solved=solved, moves=moves, state_path=state_path, metrics=metrics)
