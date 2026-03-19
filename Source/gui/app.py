from __future__ import annotations

import os
import re
import sys
import threading
from typing import Dict, List

import pygame

from config import CARD_IMAGE_DIR, SOLUTION_DIR
from core import FreeCellGame, rules
from core.loader import load_game_from_json
from core.state import State
from gui.animation import SolverAnimator
from gui.hud import draw_solver_stats, draw_win_or_lose_overlay
from gui.interface import BoardRenderer, CardImageLoader
from gui.menu import MenuScreen
from solvers.ucs import Move as HintMove, UCSSearchResult, get_hint, solve_ucs


class FreeCellApp:
    """Main application controller for FreeCell (scene management + game loop)."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("FreeCell Solver")
        self.screen = pygame.display.set_mode((1366, 768))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "menu"  # menu | easy_select | game | howto

        self.title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self.menu_font = pygame.font.SysFont("georgia", 36, bold=True)
        self.hint_font = pygame.font.SysFont("georgia", 24, bold=True)
        self.body_font = pygame.font.SysFont("georgia", 28)

        self.menu = MenuScreen(
            screen=self.screen,
            title_font=self.title_font,
            menu_font=self.menu_font,
            hint_font=self.hint_font,
        )

        loader = CardImageLoader(base_dir=CARD_IMAGE_DIR, card_size=(110, 154))
        self.game = FreeCellGame(seed=1)
        self.view_model = self.game.get_view_model()
        self.board = BoardRenderer(self.screen.get_rect(), loader, self.game.get_state(), self.game, self.view_model)
        self.is_stuck = False

        self.animator = SolverAnimator(step_delay_ms=500)
        self.is_animating = False
        self.ai_solver_mode = False

        self._ai_seen_states: set[tuple] = set()
        self._sample_games_by_difficulty = self._discover_sample_games_by_difficulty()
        self._sample_game_indices = {
            difficulty: 0 for difficulty in self._sample_games_by_difficulty
        }
        self.selected_easy_game_index = 0
        self.selected_manual_difficulty = "easy"
        self._ai_game_path = self._discover_ai_game()
        self.last_loaded_sample: str | None = None

        self.solver_result: UCSSearchResult | None = None
        self.solver_message = ""
        self.current_hint: HintMove | None = None

        self._solver_thread: threading.Thread | None = None
        self._solver_job_id = 0
        self._solver_pending = False
        self._solver_async_result: UCSSearchResult | None = None
        self._solver_async_error: str | None = None
        self._solver_stages = [
            (120_000, 6.0),
            (250_000, 10.0),
            (500_000, 18.0),
            (900_000, 28.0),
        ]
        self._solver_stage_idx = 0
        self._hint_thread: threading.Thread | None = None
        self._hint_job_id = 0
        self._hint_pending = False
        self._hint_async_result: HintMove | None = None
        self._hint_async_error: str | None = None

        self.howto_lines: List[str] = [
            "Goal: move all 52 cards to the 4 Foundations by suit, from Ace to King.",
            "The board has 8 Tableau columns, 4 Free Cells, and 4 Foundations.",
            "You can move only the top card of a Tableau column or a card in a Free Cell.",
            "Place a card on another Tableau card if colors alternate and rank is one lower.",
            "Move cards to Foundation only when suit matches and rank is the next needed card.",
            "Use Free Cells as temporary storage to unlock difficult positions.",
            "Shortcuts: ESC to return to menu, H to request a hint.",
        ]

    def run(self) -> None:
        while self.running:
            if self.scene == "menu":
                self.menu.update_dropdown_animation()

            self._handle_events()
            self._poll_solver_result()
            self._poll_hint_result()

            if self.scene == "game":
                was_active = self.animator.status.active
                self.animator.update(self.board)
                self.is_animating = self.animator.is_animating
                if was_active and not self.animator.status.active and self.animator.status.finished:
                    # Keep core state in sync with the board after auto-play animation.
                    # Without this, UCS restarts from a stale snapshot and loops forever.
                    self.game.set_state(self.board.state.clone())
                    self.view_model = self.game.get_view_model()
                    if self.animator.status.failed:
                        self.solver_message = "Animation failed due to an invalid transition."
                    elif self.view_model.get("is_goal", False):
                        self.solver_message = "AI Solver completed: you win!"
                    else:
                        if self.ai_solver_mode:
                            if not self._solver_pending:
                                self.solver_message = "AI Solver: continuing search..."
                                self._launch_solver_async()
                        elif self._start_next_ai_local_step():
                            self.solver_message = "AI Solver auto-playing..."
                        else:
                            self.solver_message = "AI Solver: replay finished."

            if self.scene == "game":
                self._refresh_game_flags()

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        sys.exit(0)

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            if self.scene == "menu":
                self.menu.handle_menu_event(
                    event,
                    on_start_game=self._start_manual_game,
                    on_start_solver=self._start_solver_game,
                    on_howto=lambda: setattr(self, "scene", "howto"),
                    on_exit=lambda: setattr(self, "running", False),
                )
            elif self.scene == "easy_select":
                easy_games = self._sample_games_by_difficulty.get("easy", [])
                self.menu.handle_easy_selector_event(
                    event,
                    easy_games=easy_games,
                    selected_index=self.selected_easy_game_index,
                    on_select=self._set_selected_easy_game_index,
                    on_start=self._start_selected_easy_game,
                    on_back=lambda: setattr(self, "scene", "menu"),
                )
            elif self.scene == "howto":
                self.menu.handle_howto_event(event, on_back=lambda: setattr(self, "scene", "menu"))
            else:
                self._on_game_event(event)

    def _on_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._cancel_pending_solver()
                self._cancel_pending_hint()
                self.animator.clear()
                self.is_animating = False
                self.ai_solver_mode = False
                self._ai_seen_states.clear()
                self.scene = "menu"
            elif event.key == pygame.K_h and not self.ai_solver_mode and not self.animator.status.active:
                self._request_hint()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.ai_solver_mode and not self.is_stuck and not self.animator.status.active:
                self._cancel_pending_hint()
                self._clear_hint()
                self.board.on_mouse_down(event.pos)

        if event.type == pygame.MOUSEMOTION and (not self.ai_solver_mode) and (not self.animator.status.active):
            self.board.on_mouse_motion(event.pos)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # Always allow releasing a dragged card, even if a temporary "stuck"
            # flag was raised while the card is in hand.
            if not self.ai_solver_mode and not self.animator.status.active:
                moved = self.board.on_mouse_up(event.pos)
                if moved:
                    self._cancel_pending_hint()
                    self._clear_hint()
                    self._update_game_from_state()
                    self._refresh_game_flags()

    def _start_manual_game(self, difficulty: str) -> None:
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_seen_states.clear()
        self.solver_result = None
        self.solver_message = ""
        self._cancel_pending_hint()
        self._clear_hint()
        self.selected_manual_difficulty = difficulty

        if difficulty == "easy":
            easy_games = self._sample_games_by_difficulty.get("easy", [])
            if easy_games:
                self.selected_easy_game_index = min(self.selected_easy_game_index, len(easy_games) - 1)
                self.solver_message = "Manual Easy: choose a deal from the list."
                self.scene = "easy_select"
                return

            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "No Easy sample deals found. Started a random shuffle."
            self.scene = "game"
            return

        loaded = self._load_next_sample_game(difficulty)
        if loaded:
            self.solver_message = f"Loaded {difficulty.title()} sample: {self.last_loaded_sample}"
        else:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = f"No {difficulty.title()} sample deals found. Started a random shuffle."

        self.scene = "game"

    def _set_selected_easy_game_index(self, index: int) -> None:
        easy_games = self._sample_games_by_difficulty.get("easy", [])
        if not easy_games:
            self.selected_easy_game_index = 0
            return
        self.selected_easy_game_index = max(0, min(index, len(easy_games) - 1))

    def _start_selected_easy_game(self, selected_index: int) -> None:
        easy_games = self._sample_games_by_difficulty.get("easy", [])
        if not easy_games:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "No Easy sample deals found. Started a random shuffle."
            self.scene = "game"
            return

        selected_index = max(0, min(selected_index, len(easy_games) - 1))
        self.selected_easy_game_index = selected_index
        loaded = self._load_sample_game_by_index("easy", selected_index)

        if loaded:
            self.solver_message = f"Loaded Easy sample: {self.last_loaded_sample}"
        else:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "Failed to load selected Easy deal. Started a random shuffle."

        self.scene = "game"

    def _start_solver_game(self) -> None:
        self._cancel_pending_solver()
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = True
        self.solver_result = None
        self._solver_async_result = None
        self._solver_async_error = None
        self._solver_stage_idx = 0
        self._ai_seen_states.clear()
        self._cancel_pending_hint()
        self._clear_hint()

        loaded = self._load_ai_game()
        if not loaded:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "AI Solver sample game_01.json not found. Started a random shuffle."
        else:
            self.solver_message = f"AI Solver: loaded {self.last_loaded_sample} and searching for solution..."

        self.scene = "game"
        self._launch_solver_async()

    def _launch_solver_async(self) -> None:
        if self._solver_pending:
            return

        snapshot = self.game.get_state().clone()
        stage_idx = min(self._solver_stage_idx, len(self._solver_stages) - 1)
        max_nodes, max_time_seconds = self._solver_stages[stage_idx]
        self._solver_job_id += 1
        job_id = self._solver_job_id
        self._solver_pending = True

        def worker() -> None:
            try:
                result = solve_ucs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                if self._solver_job_id == job_id:
                    self._solver_async_result = result
            except Exception as exc:
                if self._solver_job_id == job_id:
                    self._solver_async_error = str(exc)

        self._solver_thread = threading.Thread(target=worker, daemon=True)
        self._solver_thread.start()

    def _cancel_pending_solver(self) -> None:
        self._solver_job_id += 1
        self._solver_pending = False
        self._solver_async_result = None
        self._solver_async_error = None

    def _request_hint(self) -> None:
        if self._hint_pending:
            self.solver_message = "Hint: still analyzing current position..."
            return

        self._clear_hint()
        snapshot = self.game.get_state().clone()
        self._hint_job_id += 1
        job_id = self._hint_job_id
        self._hint_pending = True
        self.solver_message = "Hint: analyzing current position..."

        def worker() -> None:
            try:
                result = get_hint(snapshot, max_depth=5, max_nodes=8_000, max_time_seconds=0.25)
                if self._hint_job_id == job_id:
                    self._hint_async_result = result
            except Exception as exc:
                if self._hint_job_id == job_id:
                    self._hint_async_error = str(exc)

        self._hint_thread = threading.Thread(target=worker, daemon=True)
        self._hint_thread.start()

    def _cancel_pending_hint(self) -> None:
        self._hint_job_id += 1
        self._hint_pending = False
        self._hint_async_result = None
        self._hint_async_error = None

    def _update_game_from_state(self) -> None:
        """Update renderer state from FreeCellGame state."""
        self.board.update_state(self.game.get_state())

    def _poll_hint_result(self) -> None:
        if not self._hint_pending:
            return

        if self._hint_async_error:
            self._hint_pending = False
            self.solver_message = f"Hint error: {self._hint_async_error}"
            self._hint_async_error = None
            return

        if self._hint_async_result is None and self._hint_thread is not None and self._hint_thread.is_alive():
            return

        hint = self._hint_async_result
        self._hint_async_result = None
        self._hint_pending = False
        self._show_hint(hint)

    def _poll_solver_result(self) -> None:
        if not self._solver_pending:
            return

        if self._solver_async_error:
            self._solver_pending = False
            self.solver_message = f"AI Solver error: {self._solver_async_error}"
            self._solver_async_error = None
            return

        if self._solver_async_result is None:
            return

        result = self._solver_async_result
        self._solver_async_result = None
        self._solver_pending = False
        self.solver_result = result

        if result.solved:
            self._solver_stage_idx = 0
            name = self.last_loaded_sample or "random shuffle"
            self.solver_message = (
                f"AI Solver: {name} - "
                f"{result.metrics.solution_steps} steps, "
                f"{result.metrics.elapsed_seconds:.2f}s"
            )
            self.animator.animate_solution(result.state_path)
            self.is_animating = True
            return

        self._solver_stage_idx = min(self._solver_stage_idx + 1, len(self._solver_stages) - 1)
        if len(result.state_path) > 1:
            self._solver_stage_idx = 0
            self.animator.animate_solution(result.state_path)
            self.is_animating = True
            self.solver_message = f"AI Solver: advanced {len(result.state_path) - 1} moves - continuing..."
            return

        self.solver_message = (
            f"AI Solver: searching deeper "
            f"({result.metrics.expanded_nodes} nodes, {result.metrics.elapsed_seconds:.1f}s)..."
        )
        self._launch_solver_async()

    def _discover_sample_games_by_difficulty(self) -> Dict[str, List[str]]:
        return {
            difficulty: self._discover_games_for_difficulty(difficulty)
            for difficulty in ("easy", "medium", "hard")
        }

    def _discover_games_for_difficulty(self, difficulty: str) -> List[str]:
        difficulty_dir = os.path.join(SOLUTION_DIR, difficulty)
        if not os.path.isdir(difficulty_dir):
            return []

        pattern = re.compile(r"^game_\d+\.json$", re.IGNORECASE)
        files: List[str] = []
        for name in os.listdir(difficulty_dir):
            if pattern.match(name):
                files.append(os.path.join(difficulty_dir, name))
        files.sort()
        return files

    def _discover_ai_game(self) -> str | None:
        ai_game_path = os.path.join(SOLUTION_DIR, "easy", "game_01.json")
        if os.path.isfile(ai_game_path):
            return ai_game_path
        return None

    def _load_next_sample_game(self, difficulty: str) -> bool:
        files = self._sample_games_by_difficulty.get(difficulty, [])
        if not files:
            return False

        sample_idx = self._sample_game_indices.get(difficulty, 0)
        file_path = files[sample_idx % len(files)]
        self._sample_game_indices[difficulty] = (sample_idx + 1) % len(files)
        ok = load_game_from_json(file_path, self.game)
        if ok:
            self.last_loaded_sample = os.path.join(difficulty, os.path.basename(file_path))
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
        return ok

    def _load_sample_game_by_index(self, difficulty: str, index: int) -> bool:
        files = self._sample_games_by_difficulty.get(difficulty, [])
        if not files:
            return False

        index = max(0, min(index, len(files) - 1))
        file_path = files[index]
        ok = load_game_from_json(file_path, self.game)
        if ok:
            self._sample_game_indices[difficulty] = (index + 1) % len(files)
            self.last_loaded_sample = os.path.join(difficulty, os.path.basename(file_path))
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
        return ok

    def _load_ai_game(self) -> bool:
        if self._ai_game_path is None:
            return False

        ok = load_game_from_json(self._ai_game_path, self.game)
        if ok:
            self.last_loaded_sample = os.path.join("easy", os.path.basename(self._ai_game_path))
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
        return ok

    def _start_next_ai_local_step(self) -> bool:
        path = self._build_immediate_step_path()
        if path is None:
            self.animator.clear()
            self.is_animating = False
            return False

        self.animator.animate_solution(path)
        self.is_animating = True
        self._ai_seen_states.add(path[-1].as_key())
        return True

    def _clear_hint(self) -> None:
        self.current_hint = None
        self.board.set_highlighted_card(None)

    def _format_location(self, location: tuple[str, int] | tuple[str, int, int]) -> str:
        zone = location[0]
        index = location[1]
        if zone == "cascade":
            return f"Tableau {index + 1}"
        if zone == "freecell":
            return f"Free Cell {index + 1}"
        if isinstance(index, str):
            suit_names = {"C": "Clubs", "D": "Diamonds", "H": "Hearts", "S": "Spades"}
            return f"Foundation {suit_names.get(index, index)}"
        suit_names = ["Clubs", "Diamonds", "Hearts", "Spades"]
        return f"Foundation {suit_names[index]}"

    def _format_card(self, card) -> str:
        ranks = {1: "A", 11: "J", 12: "Q", 13: "K"}
        rank_label = ranks.get(card.rank, str(card.rank))
        suit_label = {"C": "Clubs", "D": "Diamonds", "H": "Hearts", "S": "Spades"}.get(card.suit, str(card.suit).title())
        return f"{rank_label} of {suit_label}"

    def _show_hint(self, hint: HintMove | None) -> None:
        if hint is None:
            self._clear_hint()
            self.solver_message = "Hint: no strong move found from the current position."
            return

        self.current_hint = hint
        self.board.set_highlighted_card(hint.card)
        self.solver_message = (
            f"Hint: move {self._format_card(hint.card)} from {self._format_location(hint.source)} "
            f"to {self._format_location(hint.target)}."
        )

    def _build_immediate_step_path(self) -> List[State] | None:
        cur = self.game.get_state()
        preferred_next: State | None = None
        fallback_next: State | None = None

        legal_moves = rules.enumerate_legal_moves(cur)

        def move_matches_priority(move: rules.Move, priority: int) -> bool:
            if priority == 0:
                return move.src_type == rules.LOCATION_FREE_CELL and move.dst_type == rules.LOCATION_FOUNDATION
            if priority == 1:
                return move.src_type == rules.LOCATION_CASCADE and move.dst_type == rules.LOCATION_FOUNDATION
            if priority == 2:
                return move.src_type == rules.LOCATION_CASCADE and move.dst_type == rules.LOCATION_FREE_CELL
            return move.src_type == rules.LOCATION_CASCADE and move.dst_type == rules.LOCATION_CASCADE

        def consider(nxt: State) -> bool:
            nonlocal preferred_next, fallback_next
            if fallback_next is None:
                fallback_next = nxt
            if nxt.as_key() not in self._ai_seen_states:
                preferred_next = nxt
                return True
            return False

        for priority in range(4):
            for move in legal_moves:
                if not move_matches_priority(move, priority):
                    continue
                nxt = rules.apply_move(cur, move)
                if consider(nxt):
                    return [cur, preferred_next]

        if preferred_next is not None:
            return [cur, preferred_next]
        if fallback_next is not None:
            return [cur, fallback_next]
        return None

    def _draw(self) -> None:
        if self.scene == "menu":
            self.menu.draw_menu()
        elif self.scene == "easy_select":
            self.menu.draw_easy_selector(
                self._sample_games_by_difficulty.get("easy", []),
                self.selected_easy_game_index,
            )
        elif self.scene == "howto":
            self.menu.draw_howto(self.body_font, self.howto_lines)
        else:
            self.board.draw(self.screen)
            self._draw_game_hud()

    def _draw_game_hud(self) -> None:
        if self.ai_solver_mode:
            hint_text = "ESC: Menu"
        else:
            hint_text = "ESC: Menu   |   H: Hint"
            
        hint = self.hint_font.render(hint_text, True, (255, 250, 205))
        self.screen.blit(hint, (18, self.screen.get_height() - hint.get_height() - 14))

        if self.is_animating:
            progress = self.hint_font.render(
                f"AI Auto-play: {self.animator.status.applied_moves}/{self.animator.status.total_moves}",
                True,
                (255, 250, 180),
            )
            self.screen.blit(progress, (18, 16))
        elif self.solver_message:
            msg = self.hint_font.render(self.solver_message, True, (255, 245, 180))
            self.screen.blit(msg, (18, 16))

        is_won = self.view_model.get("is_goal", False)

        if self.solver_result and (
            is_won and (self.animator.status.finished or self.solver_result.metrics.solution_steps == 0)
        ):
            draw_solver_stats(self.screen, self.hint_font, self.body_font, self.solver_result)

        draw_win_or_lose_overlay(
            self.screen,
            self.title_font,
            self.hint_font,
            is_won,
            self.is_stuck,
        )

    def _refresh_game_flags(self) -> None:
        self.view_model = self.game.get_view_model()
        is_won = self.view_model["is_goal"]
        has_moves = len(self.view_model.get("legal_moves", [])) > 0
        self.is_stuck = (not is_won) and (not has_moves)
