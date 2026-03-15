from __future__ import annotations

import os
import re
import sys
import threading
from typing import List

import pygame

from config import CARD_IMAGE_DIR, SOLUTION_DIR
from core.loader import load_game_from_json
from core.state import GameState
from gui.animation import SolverAnimator
from gui.hud import draw_solver_stats, draw_win_or_lose_overlay
from gui.interface import BoardRenderer, CardImageLoader
from gui.menu import MenuScreen
from solvers.ucs import UCSSearchResult, solve_ucs


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
        self.game_state = GameState()
        self.board = BoardRenderer(self.screen.get_rect(), loader, self.game_state)
        self.is_stuck = False

        self.animator = SolverAnimator(step_delay_ms=500)
        self.is_animating = False
        self.ai_solver_mode = False

        self._ai_seen_states: set[tuple] = set()
        self._sample_game_files = self._discover_sample_games()
        self._sample_game_idx = 0
        self.last_loaded_sample: str | None = None

        self.solver_result: UCSSearchResult | None = None
        self.solver_message = ""

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

        self.howto_lines: List[str] = [
            "Goal: move all 52 cards to the 4 Foundations by suit, from Ace to King.",
            "The board has 8 Tableau columns, 4 Free Cells, and 4 Foundations.",
            "You can move only the top card of a Tableau column or a card in a Free Cell.",
            "Place a card on another Tableau card if colors alternate and rank is one lower.",
            "Move cards to Foundation only when suit matches and rank is the next needed card.",
            "Use Free Cells as temporary storage to unlock difficult positions.",
            "Shortcuts: ESC to return to menu, R to start a new shuffled game.",
        ]

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
                    if self.animator.status.failed:
                        self.solver_message = "Animation failed due to an invalid transition."
                    elif self.game_state.is_won():
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
                self._ai_seen_states.clear()
                self.scene = "menu"
            elif event.key == pygame.K_r:
                self._cancel_pending_solver()
                self.game_state.reset()
                self.board.on_reset()
                self.animator.clear()
                self.is_animating = False
                self.ai_solver_mode = False
                self._ai_seen_states.clear()
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

    def _start_manual_game(self) -> None:
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_seen_states.clear()
        self.solver_result = None
        self.solver_message = ""

        loaded = self._load_next_sample_game()
        if loaded:
            self.solver_message = f"Loaded sample deal: {self.last_loaded_sample}"
        else:
            self.game_state.reset()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "Sample deals not found. Started a random shuffle."

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

        loaded = self._load_next_sample_game()
        if not loaded:
            self.game_state.reset()
            self.board.on_reset()
            self._refresh_game_flags()

        self.solver_message = "AI Solver: searching for solution..."
        self.scene = "game"
        self._launch_solver_async()

    def _launch_solver_async(self) -> None:
        if self._solver_pending:
            return

        snapshot = self.game_state.clone()
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

    def _discover_sample_games(self) -> List[str]:
        if not os.path.isdir(SOLUTION_DIR):
            return []

        pattern = re.compile(r"^game_\d+\.json$", re.IGNORECASE)
        files: List[str] = []
        for name in os.listdir(SOLUTION_DIR):
            if pattern.match(name):
                files.append(os.path.join(SOLUTION_DIR, name))
        files.sort()
        return files

    def _load_next_sample_game(self) -> bool:
        if not self._sample_game_files:
            return False

        file_path = self._sample_game_files[self._sample_game_idx % len(self._sample_game_files)]
        self._sample_game_idx = (self._sample_game_idx + 1) % len(self._sample_game_files)
        ok = load_game_from_json(file_path, self.game_state, on_reset=self.board.on_reset)
        if ok:
            self.last_loaded_sample = os.path.basename(file_path)
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
        self._ai_seen_states.add(path[-1].to_hashable())
        return True

    def _build_immediate_step_path(self) -> List[GameState] | None:
        cur = self.game_state.clone()
        preferred_next: GameState | None = None
        fallback_next: GameState | None = None

        def try_move(source, target) -> GameState | None:
            nxt = cur.clone()
            drag = nxt.pick_cards(source)
            if drag is None:
                return None
            if nxt.apply_drop(drag, target):
                return nxt
            nxt.cancel_drag(drag)
            return None

        def consider(nxt: GameState) -> bool:
            nonlocal preferred_next, fallback_next
            if fallback_next is None:
                fallback_next = nxt
            if nxt.to_hashable() not in self._ai_seen_states:
                preferred_next = nxt
                return True
            return False

        for fc_idx, card in enumerate(cur.free_cells):
            if card is None:
                continue
            for f_idx in range(4):
                nxt = try_move(("freecell", fc_idx, 0), ("foundation", f_idx))
                if nxt is not None and consider(nxt):
                    return [cur, preferred_next]

        for c_idx, cascade in enumerate(cur.cascades):
            if not cascade:
                continue
            src = ("cascade", c_idx, len(cascade) - 1)
            for f_idx in range(4):
                nxt = try_move(src, ("foundation", f_idx))
                if nxt is not None and consider(nxt):
                    return [cur, preferred_next]

        for c_idx, cascade in enumerate(cur.cascades):
            if not cascade:
                continue
            src = ("cascade", c_idx, len(cascade) - 1)
            for fc_idx in range(4):
                nxt = try_move(src, ("freecell", fc_idx))
                if nxt is not None and consider(nxt):
                    return [cur, preferred_next]

        for c_idx, cascade in enumerate(cur.cascades):
            if not cascade:
                continue
            src = ("cascade", c_idx, len(cascade) - 1)
            for dst in range(8):
                if dst == c_idx:
                    continue
                nxt = try_move(src, ("cascade", dst))
                if nxt is not None and consider(nxt):
                    return [cur, preferred_next]

        if preferred_next is not None:
            return [cur, preferred_next]
        if fallback_next is not None:
            return [cur, fallback_next]
        return None

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
                f"AI Auto-play: {self.animator.status.applied_moves}/{self.animator.status.total_moves}",
                True,
                (255, 250, 180),
            )
            self.screen.blit(progress, (18, 16))
        elif self.solver_message:
            msg = self.hint_font.render(self.solver_message, True, (255, 245, 180))
            self.screen.blit(msg, (18, 16))

        if self.ai_solver_mode and not self.is_animating and not self.game_state.is_won():
            lock = self.hint_font.render("AI Solver mode: manual card movement is disabled.", True, (255, 236, 170))
            self.screen.blit(lock, (18, 48))

        if self.solver_result and (
            self.game_state.is_won() and (self.animator.status.finished or self.solver_result.metrics.solution_steps == 0)
        ):
            draw_solver_stats(self.screen, self.hint_font, self.body_font, self.solver_result)

        draw_win_or_lose_overlay(
            self.screen,
            self.title_font,
            self.hint_font,
            self.game_state,
            self.is_stuck,
        )

    def _refresh_game_flags(self) -> None:
        self.is_stuck = (not self.game_state.is_won()) and (not self.game_state.has_any_legal_move())
