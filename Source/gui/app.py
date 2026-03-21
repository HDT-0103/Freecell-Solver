from __future__ import annotations

import os
import re
import sys
import threading
from gui.howto import HowToScreen
from typing import Dict, List

import pygame

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None

from config import CARD_IMAGE_DIR, SOLUTION_DIR
from core import FreeCellGame, rules
from core.loader import load_game_from_json
from core.state import State
from gui.animation import SolverAnimator
from gui.hud import draw_solver_stats, draw_win_or_lose_overlay
from gui.interface import BoardRenderer, CardImageLoader
from gui.menu import MenuScreen
from solvers.ucs import Move as HintMove, UCSSearchResult, get_hint, solve_ucs
try:
    from solvers.a_star import solve_a_star
except ImportError:
    solve_a_star = None
try:
    from solvers.bfs import solve_bfs
except ImportError:
    solve_bfs = None
try:
    from solvers.dfs import solve_dfs
except ImportError:
    solve_dfs = None


class FreeCellApp:
    """Main application controller for FreeCell (scene management + game loop)."""

    _GAME_SIZE = (1366, 768)  # kích thước cố định cho game/easy_select/howto

    @staticmethod
    def _center_window(win_w: int, win_h: int) -> None:
        """Di chuyển cửa sổ SDL về đúng trung tâm màn hình."""
        try:
            import ctypes
            user32 = ctypes.windll.user32
            user32.SetProcessDPIAware()
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
        except Exception:
            info = pygame.display.Info()
            screen_w, screen_h = info.current_w, info.current_h
        x = (screen_w - win_w) // 2
        y = (screen_h - win_h) // 2
        os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

    def _set_screen(self, size: tuple, flags: int = 0) -> None:
        """Căn giữa rồi set_mode."""
        self._center_window(*size)
        self.screen = pygame.display.set_mode(size, flags)

    def _switch_to_game_screen(self) -> None:
        """Resize về 1366×768 cho game/easy_select/howto và cập nhật board + menu."""
        self._set_screen(self._GAME_SIZE)
        if hasattr(self, "menu"):
            self.menu.rebuild_for_screen(self.screen)
            self.howto_screen.rebuild_for_screen(self.screen)
        if hasattr(self, "board"):
            self.board.rect = pygame.Rect(0, 0, *self._GAME_SIZE)

    def _switch_to_menu_screen(self) -> None:
        """Resize về kích thước background/menu và cập nhật menu."""
        self._set_screen(self._bg_size)
        if hasattr(self, "menu"):
            self.menu.rebuild_for_screen(self.screen)

    def _switch_to_howto_screen(self) -> None:        
        self._set_screen(self._howto_size)
        if hasattr(self, "howto_screen"):
            self.howto_screen.rebuild_for_screen(self.screen)

    def _switch_to_selector_screen(self) -> None:
        self._set_screen(self._selector_size)
        self.menu.rebuild_for_screen(self.screen)

    def _go_menu(self) -> None:
        self.scene = "menu"
        self._switch_to_menu_screen()

    def _go_easy_select(self) -> None:
        self.scene = "easy_select"
        self._switch_to_selector_screen()

    def _go_howto(self) -> None:
        self.scene = "howto"
        self._switch_to_howto_screen()

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("FreeCell Solver")
        self._bg_size = self._GAME_SIZE  # fallback
        self._set_screen(self._GAME_SIZE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "menu"

        self.title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self.menu_font = pygame.font.SysFont("georgia", 36, bold=True)
        self.hint_font = pygame.font.SysFont("georgia", 24, bold=True)
        self.body_font = pygame.font.SysFont("georgia", 28)

        # 1. Background Image setup cho Menu
        bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "background.jpg")
        bg_image = None
        if os.path.exists(bg_path):
            try:
                bg_image = pygame.image.load(bg_path).convert()
            except Exception as e:
                print(f"Error loading background image: {e}")

        # 2. Background cho HowToPlay - dùng để xác định kích thước chuẩn của cửa sổ
        howto_bg = None
        howto_bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "howto_bg.png")
        if os.path.exists(howto_bg_path):
            try:
                howto_bg = pygame.image.load(howto_bg_path).convert()
                self._howto_size = howto_bg.get_size()
            except Exception as e:
                print(f"Error loading howto background: {e}")
        
        if not hasattr(self, "_howto_size"):
            self._howto_size = (820, 1024)

        # 3. Đồng bộ kích thước chuẩn cho các màn hình phụ
        self._bg_size       = self._howto_size
        self._selector_size = self._howto_size

        # QUAN TRỌNG: Set màn hình về kích thước chuẩn TRƯỚC khi xử lý ảnh video_bg
        self._set_screen(self._howto_size)

        # 4. Tải ảnh nền cho video - ÉP VÀO KÍCH THƯỚC CỬA SỔ
        self.video_bg_image = None
        v_bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "video_bg.jpg")
        if os.path.exists(v_bg_path):
            try:
                loaded_v_bg = pygame.image.load(v_bg_path).convert()
                # Sử dụng self._howto_size để ép ảnh nền vừa khít cửa sổ, tránh bị lệch hay hở nền đen
                self.video_bg_image = pygame.transform.scale(loaded_v_bg, self._howto_size)
            except Exception as e:
                print(f"Error loading video background image: {e}")

        # 5. Intro Video setup
        self.scene = "intro" if VideoFileClip is not None else "menu"
        self.video_clip = None
        self.outro_clip = None

        video_path = os.path.join(os.path.dirname(__file__), "..", "..", "intro.mp4")
        outro_path = os.path.join(os.path.dirname(__file__), "..", "..", "outro.mp4")

        if self.scene == "intro":
            if os.path.exists(video_path):
                try:
                    self.video_clip = VideoFileClip(video_path)
                except Exception as e:
                    print(f"Error loading video: {e}")
                    self.scene = "menu"
            else:
                self.scene = "menu"

        if VideoFileClip is not None and os.path.exists(outro_path):
            try:
                self.outro_clip = VideoFileClip(outro_path)
            except Exception as e:
                print(f"Error loading outro video: {e}")

        # 6. Background cho selector
        selector_bg = None
        selector_bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "selector_bg.jpg")
        if os.path.exists(selector_bg_path):
            try:
                selector_bg = pygame.image.load(selector_bg_path).convert()
            except Exception as e:
                print(f"Error loading selector background: {e}")

        # Load ảnh nền cho từng mode game
        def _load_bg(filename):
            path = os.path.join(os.path.dirname(__file__), "..", "..", filename)
            try:
                return pygame.image.load(path).convert() if os.path.exists(path) else None
            except Exception as e:
                print(f"Error loading {filename}: {e}")
                return None

        self._board_bgs = {
            "manual": _load_bg("board_bg_manual.jpg"),
            "ucs":    _load_bg("board_bg_ucs.jpg"),
            "a_star": _load_bg("board_bg_astar.jpg"),
            "bfs":    _load_bg("board_bg_bfs.jpg"),
            "dfs":    _load_bg("board_bg_dfs.jpg"),
        }

        # Khởi tạo các màn hình với dữ liệu đã nạp
        self.menu = MenuScreen(
            screen=self.screen,
            title_font=self.title_font,
            menu_font=self.menu_font,
            hint_font=self.hint_font,
            bg_image=bg_image,
            selector_bg=selector_bg,
        )

        self.howto_screen = HowToScreen(
            screen=self.screen,
            title_font=self.title_font,
            body_font=self.body_font,
            hint_font=self.hint_font,
            bg_image=howto_bg,      
        )

        # Thiết lập bàn chơi
        loader = CardImageLoader(base_dir=CARD_IMAGE_DIR, card_size=(110, 154))
        self.game = FreeCellGame(seed=1)
        self.view_model = self.game.get_view_model()
        game_rect = pygame.Rect(0, 0, 1366, 768)
        self.board = BoardRenderer(game_rect, loader, self.game.get_state(), self.game, self.view_model)
        self.is_stuck = False

        self.animator = SolverAnimator(step_delay_ms=500)
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_total_applied_moves = 0

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


    def run(self) -> None:
        if self.scene == "intro" and self.video_clip is not None:
            self._play_custom_video(self.video_clip, allow_skip=True)
            self._end_intro()
            self._switch_to_menu_screen()

        while self.running:
            if self.scene == "outro":
                if self.outro_clip is not None:
                    # KHÔNG resize — giữ kích thước chuẩn, letterbox
                    self._play_custom_video(self.outro_clip, allow_skip=False)
                self.running = False
                break

            if not self.running or self.scene == "outro":
                continue

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
                    if self.ai_solver_mode:
                        self._ai_total_applied_moves += self.animator.status.applied_moves
                    # Keep core state in sync with the board after auto-play animation.
                    # Without this, UCS restarts from a stale snapshot and loops forever.
                    self.game.set_state(self.board.state.clone())
                    self.view_model = self.game.get_view_model()
                    if self.solver_result and self.ai_solver_mode:
                        # Metrics should show the full auto-play sequence, not only the last UCS stage.
                        self.solver_result.metrics.solution_steps = self._ai_total_applied_moves
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
                self._trigger_exit()
                return

            if self.scene == "intro":
                if event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self._end_intro()
                    self._switch_to_menu_screen()
                continue

            if self.scene == "menu":
                self.menu.handle_menu_event(
                    event,
                    on_start_game=self._start_manual_game,
                    on_start_solver=lambda algo="ucs": self._start_solver_game(algo),
                    on_howto=self._go_howto,
                    on_exit=self._trigger_exit,
                )
            elif self.scene == "easy_select":
                easy_games = self._sample_games_by_difficulty.get("easy", [])
                self.menu.handle_easy_selector_event(
                    event,
                    easy_games=easy_games,
                    selected_index=self.selected_easy_game_index,
                    on_select=self._set_selected_easy_game_index,
                    on_start=self._start_selected_easy_game,
                    on_back=self._go_menu,
                )
            elif self.scene == "howto":
                self.howto_screen.handle_event(event, on_back=self._go_menu)
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
                self._ai_total_applied_moves = 0
                self._ai_seen_states.clear()
                self._go_menu()
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
        self._ai_total_applied_moves = 0
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
                self._go_easy_select()
                return

            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = "No Easy sample deals found. Started a random shuffle."
            self.board.set_board_bg(self._board_bgs.get("manual"))
            self._switch_to_game_screen()
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

        self.board.set_board_bg(self._board_bgs.get("manual"))
        self._switch_to_game_screen()
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
            self.board.set_board_bg(self._board_bgs.get("manual"))
            self._switch_to_game_screen()
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

        self.board.set_board_bg(self._board_bgs.get("manual"))
        self._switch_to_game_screen()
        self.scene = "game"

    def _start_solver_game(self, algorithm: str = "ucs") -> None:
        self._cancel_pending_solver()
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = True
        self._ai_total_applied_moves = 0
        self.solver_result = None
        self._solver_async_result = None
        self._solver_async_error = None
        self._solver_stage_idx = 0
        self._ai_seen_states.clear()
        self._cancel_pending_hint()
        self._clear_hint()
        self._solver_algorithm = algorithm  # lưu lại để _launch_solver_async dùng

        loaded = self._load_ai_game()
        if not loaded:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.on_reset()
            self._refresh_game_flags()
            self.solver_message = f"AI Solver ({algorithm.upper()}) sample not found. Started a random shuffle."
        else:
            self.solver_message = f"AI Solver ({algorithm.upper()}): loaded {self.last_loaded_sample}, searching..."

        self.board.set_board_bg(self._board_bgs.get(algorithm))
        self._switch_to_game_screen()
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
                algo = getattr(self, "_solver_algorithm", "ucs")
                if algo == "a_star" and solve_a_star:
                    result = solve_a_star(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                elif algo == "bfs" and solve_bfs:
                    result = solve_bfs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                elif algo == "dfs" and solve_dfs:
                    result = solve_dfs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                else:
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
            total_steps = self._ai_total_applied_moves + result.metrics.solution_steps
            result.metrics.solution_steps = total_steps
            self.solver_message = (
                f"AI Solver: {name} - "
                f"{total_steps} steps, "
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

    def _trigger_exit(self) -> None:
        """Trigger safe exit (plays Outro video if exists)."""
        if self.outro_clip is not None:
            self.scene = "outro"
        else:
            self.running = False

    def _play_custom_video(self, clip, allow_skip: bool = True) -> None:
        base_path = os.path.splitext(clip.filename)[0]
        audio_path = base_path + "_audio.mp3"

        # --- Phần xử lý âm thanh (Giữ nguyên của bạn) ---
        if getattr(clip, 'audio', None) is not None and not os.path.exists(audio_path):
            self.screen.fill((16, 20, 24))
            msg_font = pygame.font.SysFont("georgia", 24)
            text = msg_font.render("Preparing video audio... Please wait.", True, (200, 200, 200))
            self.screen.blit(text, (self.screen.get_width() // 2 - text.get_width() // 2, self.screen.get_height() // 2))
            pygame.display.flip()
            try:
                clip.audio.write_audiofile(audio_path, logger=None)
            except Exception as e:
                print(f"Warning: Audio extraction failed: {e}")

        if os.path.exists(audio_path):
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

        # --- TÍNH TOÁN CO GIÃN VÀ CĂN GIỮA ---
        fps = clip.fps or 30
        start_time = pygame.time.get_ticks()
    
        # 1. Lấy kích thước màn hình hiện tại
        scr_w, scr_h = self.screen.get_size()
        clip_w, clip_h = clip.size

        # 2. Tính tỷ lệ scale để video vừa khít màn hình mà không bị méo
        scale = min(scr_w / clip_w, scr_h / clip_h)
        new_w, new_h = int(clip_w * scale), int(clip_h * scale)

        # 3. Tính tọa độ để đưa vào chính giữa
        x_off = (scr_w - new_w) // 2
        y_off = (scr_h - new_h) // 2

        # Cập nhật vị trí nút Skip theo màn hình
        btn_font = pygame.font.SysFont("georgia", 18, bold=True)
        skip_text = btn_font.render("Skip >>", True, (255, 223, 100))
        skip_rect = skip_text.get_rect(topright=(scr_w - 20, 20))
        bg_rect = skip_rect.inflate(20, 12)

        for t, frame in clip.iter_frames(fps=fps, with_times=True, dtype='uint8'):
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.mixer.music.stop()
                    pygame.quit()
                    sys.exit(0)
                if allow_skip and event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_SPACE):
                        pygame.mixer.music.stop()
                        return
                    if event.type == pygame.MOUSEBUTTONDOWN and bg_rect.collidepoint(event.pos):
                        pygame.mixer.music.stop()
                        return

            # Đồng bộ hình/tiếng
            now = (pygame.time.get_ticks() - start_time) / 1000.0
            if t > now:
                pygame.time.wait(int((t - now) * 1000))
            elif now - t > 0.1:
                continue

            # 4. CHUYỂN ĐỔI VÀ VẼ
            # Tạo surface từ frame video
            frame_surf = pygame.image.frombuffer(frame.tobytes(), clip.size, "RGB")
            # Resize frame cho khớp với màn hình
            scaled_surf = pygame.transform.smoothscale(frame_surf, (new_w, new_h))
        
            if self.video_bg_image:
                # 1. Vẽ ảnh nền đã được ép size che kín toàn bộ màn hình
                self.screen.blit(self.video_bg_image, (0, 0))
            else:
                # Fallback nền đen nếu không có ảnh
                self.screen.fill((0, 0, 0))

            self.screen.blit(scaled_surf, (x_off, y_off))

            if allow_skip:
                pygame.draw.rect(self.screen, (4, 98, 56), bg_rect, border_radius=10)
                pygame.draw.rect(self.screen, (212, 175, 55), bg_rect, width=2, border_radius=10)
                self.screen.blit(skip_text, skip_rect)

            pygame.display.flip()

        pygame.mixer.music.stop()

    def _end_intro(self) -> None:
        self.scene = "menu"
        if self.video_clip:
            self.video_clip.close()
            self.video_clip = None

    def _draw(self) -> None:
        if self.scene in ("intro", "outro"):
            pass  # Do not draw game UI when playing video
        elif self.scene == "menu":
            self.menu.draw_menu()
        elif self.scene == "easy_select":
            self.menu.draw_easy_selector(
                self._sample_games_by_difficulty.get("easy", []),
                self.selected_easy_game_index,
            )
        elif self.scene == "howto":
            self.howto_screen.draw()
        elif self.scene == "game":
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