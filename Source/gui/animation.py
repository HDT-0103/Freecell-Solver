from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import pygame

from core.state import Card, State
from gui.interface import BoardRenderer

@dataclass
class AnimationStatus:
	active: bool = False
	finished: bool = False
	total_moves: int = 0
	applied_moves: int = 0
	failed: bool = False


class SolverAnimator:
	"""Animate a solution path of core State snapshots with smooth transitions."""

	def __init__(self, step_delay_ms: int = 500, transition_frames: int = 10) -> None:
		self.step_delay_ms = step_delay_ms
		self.transition_frames = transition_frames
		self._solution_path: List[State] = []
		self._index = 0
		self._last_step_tick = 0
		self._clock = pygame.time.Clock()

		self._in_transition = False
		self._transition_frame = 0
		self._moving_card: Optional[Card] = None
		self._start_pos: Optional[Tuple[int, int]] = None
		self._end_pos: Optional[Tuple[int, int]] = None
		self._pending_state: Optional[State] = None

		self.status = AnimationStatus()

	@property
	def is_animating(self) -> bool:
		return self.status.active

	def animate_solution(self, solution_path: List[State]) -> None:
		"""Start animation from a list of core states."""
		self._solution_path = [s.clone() for s in solution_path]
		self._index = 0
		self._last_step_tick = pygame.time.get_ticks()
		self._in_transition = False
		self._transition_frame = 0
		self._moving_card = None
		self._start_pos = None
		self._end_pos = None
		self._pending_state = None

		total_moves = max(0, len(self._solution_path) - 1)
		self.status = AnimationStatus(
			active=total_moves > 0,
			finished=(total_moves == 0),
			total_moves=total_moves,
			applied_moves=0,
			failed=False,
		)

	def clear(self) -> None:
		self._solution_path = []
		self._index = 0
		self._last_step_tick = 0
		self._in_transition = False
		self._transition_frame = 0
		self._moving_card = None
		self._start_pos = None
		self._end_pos = None
		self._pending_state = None
		self.status = AnimationStatus(active=False, finished=False)

	def _find_moved_card(
		self,
		board: BoardRenderer,
		prev_state: State,
		next_state: State,
	) -> Tuple[Optional[Card], Optional[Tuple[int, int]], Optional[Tuple[int, int]]]:
		move = next_state.move
		if move is not None:
			moved_card: Optional[Card] = None
			if move.src_type == 'cascade':
				src = prev_state.cascades[move.src_index]
				if len(src) >= move.count:
					# For multi-card moves, animate the top card of the moved block.
					moved_card = src[-1]
			elif move.src_type == 'free_cell':
				moved_card = prev_state.free_cells[move.src_index]

			if moved_card is not None:
				prev_positions = board.get_card_positions(prev_state)
				next_positions = board.get_card_positions(next_state)
				start_pos = prev_positions.get(moved_card)
				end_pos = next_positions.get(moved_card)
				if start_pos is not None and end_pos is not None and start_pos != end_pos:
					return moved_card, start_pos, end_pos

		prev_positions = board.get_card_positions(prev_state)
		next_positions = board.get_card_positions(next_state)

		best_card: Optional[Card] = None
		best_start: Optional[Tuple[int, int]] = None
		best_end: Optional[Tuple[int, int]] = None
		best_dist = -1

		for card, new_pos in next_positions.items():
			old_pos = prev_positions.get(card)
			if old_pos is None or old_pos == new_pos:
				continue
			dist = abs(new_pos[0] - old_pos[0]) + abs(new_pos[1] - old_pos[1])
			if dist > best_dist:
				best_dist = dist
				best_card = card
				best_start = old_pos
				best_end = new_pos

		return best_card, best_start, best_end

	def _start_transition(self, board: BoardRenderer) -> None:
		prev_state = self._solution_path[self._index]
		next_state = self._solution_path[self._index + 1]

		card, start_pos, end_pos = self._find_moved_card(board, prev_state, next_state)

		if card is None or start_pos is None or end_pos is None:
			board.apply_state(next_state)
			self._index += 1
			self.status.applied_moves = self._index
			self._last_step_tick = pygame.time.get_ticks()
			return

		widget = board.get_widget(card)
		if widget is None:
			self.status.active = False
			self.status.finished = True
			self.status.failed = True
			return

		self._moving_card = card
		self._start_pos = start_pos
		self._end_pos = end_pos
		self._pending_state = next_state
		self._transition_frame = 0
		self._in_transition = True
		widget.move_to(start_pos[0], start_pos[1])

	def _update_transition(self, board: BoardRenderer) -> None:
		if self._moving_card is None or self._start_pos is None or self._end_pos is None:
			self.status.active = False
			self.status.finished = True
			self.status.failed = True
			return

		widget = board.get_widget(self._moving_card)
		if widget is None:
			self.status.active = False
			self.status.finished = True
			self.status.failed = True
			return

		t = (self._transition_frame + 1) / float(self.transition_frames)
		x = int(self._start_pos[0] + (self._end_pos[0] - self._start_pos[0]) * t)
		y = int(self._start_pos[1] + (self._end_pos[1] - self._start_pos[1]) * t)
		widget.move_to(x, y)
		self._transition_frame += 1
		self._clock.tick(60)

		if self._transition_frame >= self.transition_frames:
			if self._pending_state is not None:
				board.apply_state(self._pending_state)
			self._pending_state = None
			self._in_transition = False
			self._moving_card = None
			self._start_pos = None
			self._end_pos = None
			self._index += 1
			self.status.applied_moves = self._index
			self._last_step_tick = pygame.time.get_ticks()

	def update(self, board: BoardRenderer) -> None:
		if not self.status.active:
			return

		if self._index >= len(self._solution_path) - 1:
			self.status.active = False
			self.status.finished = True
			return

		if self._in_transition:
			self._update_transition(board)
			return

		now = pygame.time.get_ticks()
		if (now - self._last_step_tick) < self.step_delay_ms:
			return

		self._start_transition(board)
