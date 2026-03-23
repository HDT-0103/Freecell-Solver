from __future__ import annotations

import os
import re
import sys
import threading
from typing import List

import pygame

from config import CARD_IMAGE_DIR, SOLUTION_DIR
from core import FreeCellGame, rules
from core.loader import load_game_from_json
from gui.animation import SolverAnimator
from gui.hud import draw_solver_stats, draw_win_or_lose_overlay
from gui.interface import BoardRenderer, CardImageLoader
from gui.menu import MenuScreen
from solvers.a_star import AStarResult, AStarSearchSession, solve_a_star
from solvers.ucs import UCSSearchResult, solve_ucs


SolverResult = UCSSearchResult | AStarResult


class FreeCellApp:
    """Main application controller for FreeCell (scene management + game loop)."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("FreeCell Solver")
        self.screen = pygame.display.set_mode((1366, 768))
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "menu"  # menu | game | howto

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
        self.board = BoardRenderer(self.screen.get_rect(), loader, self.game.get_state().clone(), self.game)
        self.board.on_reset()
        self.is_stuck = False

        self.animator = SolverAnimator(step_delay_ms=500)
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_total_applied_moves = 0

        self._sample_game_files = self._discover_sample_games()
        self._sample_game_indices = {"all": 0, "easy": 0, "hard": 0}
        self.last_loaded_sample: str | None = None

        self.solver_result: SolverResult | None = None
        self.solver_message = ""
        self.solver_algorithm = "ucs"
        self.solver_label = "UCS"

        self._solver_thread: threading.Thread | None = None
        self._solver_job_id = 0
        self._solver_pending = False
        self._solver_async_result: SolverResult | None = None
        self._solver_async_error: str | None = None
        self._solver_stages = [
            (120_000, 6.0),
            (250_000, 10.0),
            (500_000, 18.0),
            (900_000, 28.0),
        ]
        self._solver_stage_idx = 0
        self._a_star_session: AStarSearchSession | None = None

        self.howto_lines: List[str] = [
            "Goal: move all 52 cards to the 4 Foundations by suit, from Ace to King.",
            "The board has 8 Tableau columns, 4 Free Cells, and 4 Foundations.",
            "You can move only the top card of a Tableau column or a card in a Free Cell.",
            "Place a card on another Tableau card if colors alternate and rank is one lower.",
            "Move cards to Foundation only when suit matches and rank is the next needed card.",
            "Use Free Cells as temporary storage to unlock difficult positions.",
            "Shortcuts: ESC to return to menu, R to start a new shuffled game.",
        ]

    def _solver_renders_partial_progress(self) -> bool:
        return self.solver_algorithm != "a_star"

    def _current_solver_stage(self) -> tuple[int, float]:
        if self.solver_algorithm == "a_star":
            a_star_stages = [
                (250_000, 10.0),
                (500_000, 20.0),
                (1_000_000, 35.0),
                (2_000_000, 50.0),
            ]
            stage_idx = min(self._solver_stage_idx, len(a_star_stages) - 1)
            return a_star_stages[stage_idx]

        stage_idx = min(self._solver_stage_idx, len(self._solver_stages) - 1)
        return self._solver_stages[stage_idx]

    def run(self) -> None:
        while self.running:
            if self.scene == "menu":
                self.menu.update_dropdown_animation()

            self._handle_events()
            self._poll_solver_result()

            if self.scene == "game":
                was_active = self.animator.status.active
                self.animator.update(self.board)
                self.is_animating = self.animator.is_animating
                if was_active and not self.animator.status.active and self.animator.status.finished:
                    self.game.set_state(self.board.state.clone())
                    if self.ai_solver_mode:
                        self._ai_total_applied_moves += self.animator.status.applied_moves

                    if self.animator.status.failed:
                        self.solver_message = "Animation failed due to an invalid transition."
                    elif rules.is_goal(self.game.get_state()):
                        self.solver_message = f"{self.solver_label} completed: you win!"
                    elif self.ai_solver_mode and not self._solver_pending:
                        self.solver_message = f"{self.solver_label}: continuing search..."
                        self._launch_solver_async()
                    else:
                        self.solver_message = f"{self.solver_label}: replay finished."

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
            elif self.scene == "howto":
                self.menu.handle_howto_event(event, on_back=lambda: setattr(self, "scene", "menu"))
            else:
                self._on_game_event(event)

    def _on_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._cancel_pending_solver()
                self.animator.clear()
                self.is_animating = False
                self.ai_solver_mode = False
                self._ai_total_applied_moves = 0
                self.scene = "menu"
            elif event.key == pygame.K_r:
                self._cancel_pending_solver()
                self.game.new_game()
                self.board.state = self.game.get_state().clone()
                self.board.on_reset()
                self.animator.clear()
                self.is_animating = False
                self.ai_solver_mode = False
                self._ai_total_applied_moves = 0
                self.solver_result = None
                self.solver_message = ""
                self._refresh_game_flags()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self.ai_solver_mode and not self.is_stuck and not self.animator.status.active:
                self.board.on_mouse_down(event.pos)

        if event.type == pygame.MOUSEMOTION and (not self.ai_solver_mode) and (not self.animator.status.active):
            self.board.on_mouse_motion(event.pos)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not self.ai_solver_mode and not self.is_stuck and not self.animator.status.active:
                moved = self.board.on_mouse_up(event.pos)
                if moved:
                    self._refresh_game_flags()

    def _start_manual_game(self, difficulty: str) -> None:
        self._cancel_pending_solver()
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_total_applied_moves = 0
        self.solver_result = None
        self.solver_message = ""
        self.solver_algorithm = "ucs"
        self.solver_label = "UCS"

        loaded = self._load_next_sample_game(difficulty)
        if loaded:
            self.solver_message = f"Loaded {difficulty.title()} sample: {self.last_loaded_sample}"
        else:
            self.game.new_game()
            self.board.state = self.game.get_state().clone()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = f"No {difficulty.title()} sample deals found. Started a random shuffle."

        self.scene = "game"

    def _start_solver_game(self, solver_algorithm: str) -> None:
        self._cancel_pending_solver()
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = True
        self._ai_total_applied_moves = 0
        self.solver_result = None
        self._solver_async_result = None
        self._solver_async_error = None
        self._solver_stage_idx = 0
        self._a_star_session = None
        self.solver_algorithm = solver_algorithm
        self.solver_label = "A*" if solver_algorithm == "a_star" else "UCS"

        loaded = self._load_next_sample_game("easy")
        if not loaded:
            loaded = self._load_next_sample_game()
        if not loaded:
            self.game.new_game()
            self.board.state = self.game.get_state().clone()
            self.board.on_reset()
            self._refresh_game_flags()

        self.solver_message = f"{self.solver_label}: searching for solution..."
        self.scene = "game"
        self._launch_solver_async()

    def _launch_solver_async(self) -> None:
        if self._solver_pending:
            return

        snapshot = self.game.get_state().clone()
        max_nodes, max_time_seconds = self._current_solver_stage()
        self._solver_job_id += 1
        job_id = self._solver_job_id
        self._solver_pending = True

        def worker() -> None:
            try:
                if self.solver_algorithm == "a_star":
                    session = self._a_star_session
                    if session is None:
                        session = AStarSearchSession(
                            snapshot,
                            heuristic="blocking",
                            heuristic_weight=3.0,
                        )
                    result = session.advance(
                        max_nodes=max_nodes,
                        max_time_seconds=max_time_seconds,
                    )
                else:
                    result = solve_ucs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)

                if self._solver_job_id == job_id:
                    if self.solver_algorithm == "a_star":
                        self._a_star_session = session
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
        self._a_star_session = None

    def _poll_solver_result(self) -> None:
        if not self._solver_pending:
            return

        if self._solver_async_error:
            self._solver_pending = False
            self.solver_message = f"{self.solver_label} error: {self._solver_async_error}"
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
            if isinstance(result, UCSSearchResult):
                total_steps = self._ai_total_applied_moves + result.metrics.solution_steps
                result.metrics.solution_steps = total_steps
                self.solver_message = (
                    f"{self.solver_label}: {name} - "
                    f"{total_steps} steps, "
                    f"{result.metrics.elapsed_seconds:.2f}s"
                )
            else:
                total_steps = self._ai_total_applied_moves + len(result.moves)
                self.solver_message = (
                    f"{self.solver_label}: {name} - "
                    f"{total_steps} steps, "
                    f"{result.expanded_nodes} expanded"
                )
            self.animator.animate_solution(result.state_path)
            self.is_animating = True
            return

        self._solver_stage_idx = min(self._solver_stage_idx + 1, len(self._solver_stages) - 1)
        if self._solver_renders_partial_progress() and len(result.state_path) > 1:
            self._solver_stage_idx = 0
            self.animator.animate_solution(result.state_path)
            self.is_animating = True
            self.solver_message = (
                f"{self.solver_label}: advanced {len(result.state_path) - 1} moves - continuing..."
            )
            return

        if isinstance(result, UCSSearchResult):
            self.solver_message = (
                f"{self.solver_label}: searching deeper "
                f"({result.metrics.expanded_nodes} nodes, {result.metrics.elapsed_seconds:.1f}s)..."
            )
        else:
            if self._a_star_session is not None and self._a_star_session.exhausted:
                self.solver_message = f"{self.solver_label}: no solution found from this state."
                return
            self.solver_message = (
                f"{self.solver_label}: still searching for full solution "
                f"({result.expanded_nodes} expanded, {result.generated_nodes} generated)..."
            )
        self._launch_solver_async()

    def _discover_sample_games(self) -> List[str]:
        if not os.path.isdir(SOLUTION_DIR):
            return []

        pattern = re.compile(r"^game_\d+\.json$", re.IGNORECASE)
        files: List[str] = []
        for root, _, names in os.walk(SOLUTION_DIR):
            for name in names:
                if pattern.match(name):
                    files.append(os.path.join(root, name))
        files.sort()
        return files

    def _load_next_sample_game(self, difficulty: str | None = None) -> bool:
        if difficulty is None:
            files = self._sample_game_files
            key = "all"
        else:
            key = difficulty.lower()
            files = [
                file_path
                for file_path in self._sample_game_files
                if os.path.basename(os.path.dirname(file_path)).lower() == key
            ]

        if not files:
            return False

        sample_idx = self._sample_game_indices.get(key, 0)
        file_path = files[sample_idx % len(files)]
        self._sample_game_indices[key] = (sample_idx + 1) % len(files)

        ok = load_game_from_json(file_path, self.game)
        if ok:
            self.board.state = self.game.get_state().clone()
            self.board.on_reset()
            self.last_loaded_sample = os.path.relpath(file_path, SOLUTION_DIR)
            self._refresh_game_flags()
        return ok

    def _draw(self) -> None:
        if self.scene == "menu":
            self.menu.draw_menu()
        elif self.scene == "howto":
            self.menu.draw_howto(self.body_font, self.howto_lines)
        else:
            self.board.draw(self.screen)
            self._draw_game_hud()

    def _draw_game_hud(self) -> None:
        hint = self.hint_font.render("ESC: Menu   |   R: New Shuffle", True, (255, 250, 205))
        self.screen.blit(hint, (18, self.screen.get_height() - hint.get_height() - 14))

        if self.is_animating:
            progress = self.hint_font.render(
                f"{self.solver_label} Auto-play: {self.animator.status.applied_moves}/{self.animator.status.total_moves}",
                True,
                (255, 250, 180),
            )
            self.screen.blit(progress, (18, 16))
        elif self.solver_message:
            msg = self.hint_font.render(self.solver_message, True, (255, 245, 180))
            self.screen.blit(msg, (18, 16))

        if self.ai_solver_mode and not self.is_animating and not rules.is_goal(self.game.get_state()):
            lock = self.hint_font.render("AI Solver mode: manual card movement is disabled.", True, (255, 236, 170))
            self.screen.blit(lock, (18, 48))

        if isinstance(self.solver_result, UCSSearchResult) and (
            rules.is_goal(self.game.get_state())
            and (self.animator.status.finished or self.solver_result.metrics.solution_steps == 0)
        ):
            draw_solver_stats(self.screen, self.hint_font, self.body_font, self.solver_result)

        draw_win_or_lose_overlay(
            self.screen,
            self.title_font,
            self.hint_font,
            self.game.get_state(),
            self.is_stuck,
        )

    def _refresh_game_flags(self) -> None:
        state = self.game.get_state()
        self.is_stuck = (not rules.is_goal(state)) and (not self.game.get_legal_moves())
