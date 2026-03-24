from __future__ import annotations

import os
import re
import sys
import threading
import math
from gui.howto import HowToScreen
from typing import Dict, List

import pygame

GOLD   = (212, 175, 55)
GOLD_L = (255, 223, 100)
WHITE  = (255, 255, 255)

try:
    from moviepy.editor import VideoFileClip
except ImportError:
    VideoFileClip = None

from config import CARD_IMAGE_DIR, SOLUTION_DIR
from core import FreeCellGame, rules
from core.loader import load_game_from_json
from gui.animation import SolverAnimator
from gui.hud import draw_solver_stats, draw_win_or_lose_overlay
from gui.interface import BoardRenderer, CardImageLoader
from gui.menu import MenuScreen
from solvers.ucs import Move as HintMove, UCSSearchResult, get_hint, solve_ucs
from solvers.a_star import AStarResult, AStarSearchSession, solve_a_star
try:
    from solvers.bfs import solve_bfs
except ImportError:
    solve_bfs = None
try:
    from solvers.dfs import solve_dfs
except ImportError:
    solve_dfs = None

SolverResult = UCSSearchResult | AStarResult


class FreeCellApp:
    """Main application controller for FreeCell (scene management + game loop)."""

    _GAME_SIZE = (1366, 990)  

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
        y = 40
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
            new_rect = pygame.Rect(0, 0, *self._GAME_SIZE)
            self.board.rebuild_for_screen(new_rect)

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

    def _scene_transition(self, target_setup_func, target_scene_name: str) -> None:
        """Hiệu ứng Fade Out / Fade In mượt mà giữa các cảnh."""
        # 1. FADE OUT (Tối dần màn hình hiện tại)
        w, h = self.screen.get_size()
        fade_surf = pygame.Surface((w, h))
        fade_surf.fill((0, 0, 0)) # Dùng màn đen làm nền chuyển cảnh
        
        for alpha in range(0, 260, 25): # Tốc độ mờ (tăng mỗi 25)
            fade_surf.set_alpha(min(alpha, 255))
            self._draw() # Vẽ lại cảnh cũ
            self.screen.blit(fade_surf, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)
            pygame.event.pump() # Ngăn game bị Not Responding trong lúc chuyển cảnh

        # 2. THAY ĐỔI SCENE VÀ CHẠY SETUP (Resize màn hình, nạp ảnh...)
        self.scene = target_scene_name
        if target_setup_func:
            target_setup_func()

        # 3. FADE IN (Sáng dần lên cảnh mới)
        w, h = self.screen.get_size() # Lấy kích thước màn hình MỚI
        fade_surf = pygame.Surface((w, h))
        fade_surf.fill((0, 0, 0))
        
        for alpha in range(255, -25, -25):
            fade_surf.set_alpha(max(alpha, 0))
            self._draw() # Vẽ cảnh mới (Lúc này bài bắt đầu bay xuống)
            self.screen.blit(fade_surf, (0, 0))
            pygame.display.flip()
            self.clock.tick(60)
            pygame.event.pump()

    def _go_menu(self) -> None:
        self._play_click_sound()
        self._scene_transition(self._switch_to_menu_screen, "menu")

    def _go_easy_select(self) -> None:
        self._play_click_sound()
        self._scene_transition(self._switch_to_selector_screen, "easy_select")

    def _go_howto(self) -> None:
        self._play_click_sound()
        self._scene_transition(self._switch_to_howto_screen, "howto")

    def _go_ai_select(self) -> None:
        self._play_click_sound()
        self._scene_transition(self._switch_to_menu_screen, "ai_select")

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("FreeCell Solver")
        self._bg_size = self._GAME_SIZE  # fallback
        self._set_screen(self._GAME_SIZE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.scene = "menu"
        self.selected_easy_game_index = 0
        self.selected_manual_difficulty = "easy"
        self.victory_timer = 0
        self.particles = []
        self.lose_particles = []

        self.title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self.menu_font = pygame.font.SysFont("georgia", 36, bold=True)
        self.hint_font = pygame.font.SysFont("georgia", 24, bold=True)
        self.body_font = pygame.font.SysFont("georgia", 28)
        self.victory_title_font = pygame.font.SysFont("arialblack", 120)

        self.click_sound = None
        click_path = os.path.join(os.path.dirname(__file__), "..", "..", "btn_click.mp3")
        if os.path.exists(click_path):
            try:
                self.click_sound = pygame.mixer.Sound(click_path)
                self.click_sound.set_volume(0.6) # Âm lượng to, rõ ràng
            except Exception as e:
                print(f"Lỗi nạp âm thanh click: {e}")

        # 1. Background Image setup cho Menu
        bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "background.jpg")
        bg_image = None
        if os.path.exists(bg_path):
            try:
                bg_image = pygame.image.load(bg_path).convert()
            except Exception as e:
                print(f"Error loading background image: {e}")
        self.bg_image = bg_image

        self.page0_bg = None
        p0_path = os.path.join(os.path.dirname(__file__), "..", "..", "howto_p0_bg.png")
        if os.path.exists(p0_path):
            self.page0_bg = pygame.image.load(p0_path).convert()
        
        # 2. Background cho HowToPlay - dùng để xác định kích thước chuẩn của cửa sổ
        howto_bg = None
        howto_bg_path = os.path.join(os.path.dirname(__file__), "..", "..", "howto_bg.png")
        if os.path.exists(howto_bg_path):
            try:
                howto_bg = pygame.image.load(howto_bg_path).convert()
                self._howto_size = (820, 990)
            except Exception as e:
                print(f"Error loading howto background: {e}")
        
        if not hasattr(self, "_howto_size"):
            self._howto_size = (820, 990)

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

        # Khởi tạo mixer nếu chưa có (thường đã có ở phần Video)
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        # Nạp hiệu ứng âm thanh Jackpot
        self.jackpot_sound = None
        sound_path = os.path.join(os.path.dirname(__file__), "..", "..", "jackpot.wav")
        if os.path.exists(sound_path):
            try:
                self.jackpot_sound = pygame.mixer.Sound(sound_path)
                # Bạn có thể chỉnh âm lượng (0.0 đến 1.0)
                self.jackpot_sound.set_volume(0.7)
            except Exception as e:
                print(f"Error loading jackpot sound: {e}")

        self.bg_music_path = os.path.join(os.path.dirname(__file__), "..", "..", "bg_jazz.mp3")

        if self.scene != "intro":
            self._play_bg_music()

        self.hover_sound = None
        self._last_hovered_item = None

        hover_path = os.path.join(os.path.dirname(__file__), "..", "..", "chip_hover.mp3")
        if os.path.exists(hover_path):
            try:
                self.hover_sound = pygame.mixer.Sound(hover_path)
                self.hover_sound.set_volume(0.4) 
            except Exception as e:
                print(f"Error loading hover sound: {e}")

        self._board_bgs = {
            "manual": _load_bg("board_bg_manual.jpg"),
            "ucs":    _load_bg("board_bg_ucs.jpg"),
            "a_star": _load_bg("board_bg_astar.jpg"),
            "bfs":    _load_bg("board_bg_bfs.jpg"),
            "dfs":    _load_bg("board_bg_dfs.jpg"),
        }
        ai_bg = _load_bg("ai_bg.jpg")  
        self._ai_bg = ai_bg

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

        self._sample_game_files = self._discover_sample_games()
        self._sample_games_by_difficulty = self._discover_sample_games_by_difficulty() 
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
        self._ai_seen_states: set[tuple] = set()
        self._hint_thread: threading.Thread | None = None
        self._hint_job_id = 0
        self._hint_pending = False
        self._hint_async_result = None
        self._hint_async_error = None
        self.current_hint = None
        self._a_star_session: AStarSearchSession | None = None

    def _spawn_lose_particles(self):
        """Tạo ra các hạt sương khói mờ ảo trôi ngang màn hình."""
        import random
        w, h = self.screen.get_size()
        # Chỉ tạo hạt nếu đang bị kẹt (Stuck)
        if len(self.lose_particles) < 50: # Giới hạn 50 hạt để không lag
            self.lose_particles.append({
                "pos": [random.randint(-50, w), random.randint(0, h)],
                "vel": [random.uniform(0.2, 0.8), random.uniform(-0.2, 0.2)], # Trôi rất chậm
                "size": random.randint(40, 100), # Hạt to mờ
                "alpha": random.randint(20, 60), # Rất trong suốt
                "life": random.randint(100, 200) # Tuổi thọ hạt
            })

    def _spawn_lose_particles(self):
        """Tạo ra các hạt sương khói mờ ảo trôi ngang màn hình."""
        import random
        w, h = self.screen.get_size()
        # Chỉ tạo hạt nếu đang bị kẹt (Stuck)
        if len(self.lose_particles) < 50: # Giới hạn 50 hạt để không lag
            self.lose_particles.append({
                "pos": [random.randint(-50, w), random.randint(0, h)],
                "vel": [random.uniform(0.2, 0.8), random.uniform(-0.2, 0.2)], # Trôi rất chậm
                "size": random.randint(40, 100), # Hạt to mờ
                "alpha": random.randint(20, 60), # Rất trong suốt
                "life": random.randint(100, 200) # Tuổi thọ hạt
            })


    def _draw_poker_chip(self, name: str, center: tuple, radius: int, color: tuple, is_hover: bool):
        """Vẽ một con chip Poker 3D với họa tiết viền."""
        GOLD = (212, 175, 55)
        WHITE = (255, 255, 255)
        
        # 1. Vẽ bóng đổ (Shadow) để tạo độ nổi
        pygame.draw.circle(self.screen, (20, 20, 20), (center[0] + 4, center[1] + 4), radius)
        
        # 2. Vẽ thân chip (Base) - Sáng hơn nếu đang di chuột (hover)
        base_color = tuple(min(255, c + 40) for c in color) if is_hover else color
        pygame.draw.circle(self.screen, base_color, center, radius)
        
        # 3. Vẽ 6 họa tiết vạch trắng đặc trưng quanh viền (Dashes)
        import math
        for i in range(6):
            angle = math.radians(i * 60 + (pygame.time.get_ticks() * 0.05 if is_hover else 0))
            # Vẽ vạch trắng nhỏ sát mép
            for offset in [-0.1, 0.1]: # Tạo độ dày cho vạch
                p1 = (center[0] + (radius - 12) * math.cos(angle + offset), 
                      center[1] + (radius - 12) * math.sin(angle + offset))
                p2 = (center[0] + radius * math.cos(angle + offset), 
                      center[1] + radius * math.sin(angle + offset))
                pygame.draw.line(self.screen, WHITE, p1, p2, width=8)

        # 4. Vẽ vòng nhẫn Gold bên trong (Inlay)
        pygame.draw.circle(self.screen, GOLD, center, radius, width=3)
        pygame.draw.circle(self.screen, GOLD, center, int(radius * 0.75), width=2)

        # 5. Vẽ tên thuật toán (Sử dụng font Palatino đã nạp)
        # Chữ sẽ có bóng đổ nhẹ để dễ đọc
        lbl_shad = self.menu_font.render(name, True, (0, 0, 0))
        lbl      = self.menu_font.render(name, True, WHITE)
        
        lx = center[0] - lbl.get_width() // 2
        ly = center[1] - lbl.get_height() // 2
        self.screen.blit(lbl_shad, (lx + 2, ly + 2))
        self.screen.blit(lbl, (lx, ly))

    def _draw_ai_selector(self) -> None:
        w, h = self.screen.get_width(), self.screen.get_height()

        # Vẽ nền (Background bài lá của bạn)
        if self._ai_bg:
            bg = pygame.transform.scale(self._ai_bg, (w, h))
            self.screen.blit(bg, (0, 0))
        
        algos = [
            ("UCS", (190, 80, 30)),   # Cam
            ("A*",  (140, 20, 20)),   # Đỏ đô
            ("BFS", (10, 10, 15)),    # Đen/Xanh đậm
            ("DFS", (80, 40, 130)),   # Tím
        ]
        
        radius = 90  # Bán kính con chip
        gap = 25    # Khoảng cách giữa các chip
        mp = pygame.mouse.get_pos()

        # Tính toán để căn giữa cụm chip theo chiều dọc
        total_h = len(algos) * (radius * 2) + (len(algos) - 1) * gap
        start_y = h // 2 - total_h // 2 + radius

        current_hover = None

        for i, (name, color) in enumerate(algos):
            # Bạn có thể cho các chip hơi so le (zig-zag) cho tự nhiên
            offset_x = 40 if i % 2 == 0 else -40 
            center = (w // 2 + offset_x, start_y + i * (radius * 2 + gap))
            
            # Kiểm tra va chạm hình tròn (Dùng công thức khoảng cách)
            dist = math.hypot(mp[0] - center[0], mp[1] - center[1])
            is_hover = dist < radius
            
            if is_hover:
                current_hover = i

            self._draw_poker_chip(name, center, radius, color, is_hover)

        # Back button
        back_rect = pygame.Rect(24, h - 70, 140, 46)
        fill = (175,40,40) if back_rect.collidepoint(mp) else (140,25,25)
        pygame.draw.rect(self.screen, fill, back_rect, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, back_rect, width=2, border_radius=10)
        lbl = self.hint_font.render("Back", True, GOLD_L)
        self.screen.blit(lbl, (back_rect.centerx - lbl.get_width()//2,
                                back_rect.centery - lbl.get_height()//2))

        if current_hover != getattr(self, "_last_hovered_item", None):
            if current_hover is not None and getattr(self, "hover_sound", None):
                self.hover_sound.play() # Cạch!
            # Cập nhật lại bộ nhớ
            self._last_hovered_item = current_hover

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
        if self.scene == "intro" and self.video_clip is not None:
            self._play_custom_video(self.video_clip, allow_skip=True)
            self._end_intro()
            self._switch_to_menu_screen()

        while self.running:
            if self.scene == "outro":
                if self.outro_clip is not None:
                    self._switch_to_menu_screen()
                    self.screen.fill((0, 0, 0))        # ← xóa sạch board cũ
                    pygame.display.flip()              # ← hiện màn đen ngay lập tức
                    self._play_custom_video(self.outro_clip, allow_skip=False)
                self.running = False
                break

            if not self.running or self.scene == "outro":
                continue

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

            self._update_victory_logic()
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
                    on_ai_select=self._go_ai_select,   # ← thêm
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
            elif self.scene == "ai_select":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    w, h = self.screen.get_width(), self.screen.get_height()
                    back_rect = pygame.Rect(24, h - 70, 140, 46)
                    
                    # 2. Kiểm tra nếu nhấn vào nút Back
                    if back_rect.collidepoint(event.pos):
                        # Sử dụng hiệu ứng chuyển cảnh để quay về Menu cho chuyên nghiệp
                        self._go_menu()
                        return

                    radius = 90
                    gap = 25
                    total_h = 4 * (radius * 2) + 3 * gap
                    start_y = h // 2 - total_h // 2 + radius
                    
                    algos = ["ucs", "a_star", "bfs", "dfs"]
                    for i, algo in enumerate(algos):
                        offset_x = 40 if i % 2 == 0 else -40
                        center = (w // 2 + offset_x, start_y + i * (radius * 2 + gap))
                        
                        # Sử dụng công thức khoảng cách Euclide: distance <= radius
                        if math.hypot(event.pos[0] - center[0], event.pos[1] - center[1]) <= radius:
                            self._start_solver_game(algo)
                            return
            else:
                self._on_game_event(event)

    def _on_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._play_click_sound()
                self._reset_victory_state()
                self._cancel_pending_solver()
                self.animator.clear()
                self.is_animating = False
                self.ai_solver_mode = False
                self._ai_total_applied_moves = 0
                self._ai_seen_states.clear()
                self._go_menu()
            elif event.key == pygame.K_h and not self.ai_solver_mode and not self.animator.status.active:
                self._play_click_sound()
                self._request_hint()
            elif event.key == pygame.K_v: 
                self._debug_set_instant_win()
            elif event.key == pygame.K_l:
                self.is_stuck = True
                self.solver_message = "DEBUG: You pressed 'L' to trigger Lose screen."
                self._play_lose_music()
            elif event.key == pygame.K_r:
                self._play_click_sound()
                self._reset_victory_state()
                self._cancel_pending_solver()
                self.game.new_game()
                self.board.state = self.game.get_state().clone()
                # self.board.on_reset()
                self.board.start_deal_animation(self.game.get_state())
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
        self._play_click_sound()
        self._reset_victory_state()
        self._cancel_pending_solver()
        self.animator.clear()
        self.is_animating = False
        self.ai_solver_mode = False
        self._ai_total_applied_moves = 0
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
            # self.board.on_reset()
            self.board.start_deal_animation(self.game.get_state())
            self._refresh_game_flags()
            self.solver_message = "No Easy sample deals found. Started a random shuffle."
            self.board.set_board_bg(self._board_bgs.get("manual"))
            self._scene_transition(self._switch_to_game_screen, "game")
            return
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

        self.board.set_board_bg(self._board_bgs.get("manual"))
        self._scene_transition(self._switch_to_game_screen, "game")

    def _set_selected_easy_game_index(self, index: int) -> None:
        easy_games = self._sample_games_by_difficulty.get("easy", [])
        if not easy_games:
            self.selected_easy_game_index = 0
            return
        self.selected_easy_game_index = max(0, min(index, len(easy_games) - 1))

    def _start_selected_easy_game(self, selected_index: int) -> None:
        easy_games = self._sample_games_by_difficulty.get("easy", [])
        if not easy_games:
            self._play_click_sound()
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.start_deal_animation(self.game.get_state())
            self._refresh_game_flags()
            self.solver_message = "No Easy sample deals found. Started a random shuffle."
            self.board.set_board_bg(self._board_bgs.get("manual"))
            self._switch_to_game_screen()
            self.scene = "game"
            self.board.start_deal_animation(self.game.get_state())
            return

        selected_index = max(0, min(selected_index, len(easy_games) - 1))
        self.selected_easy_game_index = selected_index
        loaded = self._load_sample_game_by_index("easy", selected_index)
        self._play_click_sound()

        if loaded:
            self.solver_message = f"Loaded Easy sample: {self.last_loaded_sample}"
            self.board.start_deal_animation(self.game.get_state())
        else:
            self.game.new_game(seed=None)
            self._update_game_from_state()
            self.board.start_deal_animation(self.game.get_state())
            self._refresh_game_flags()
            self.solver_message = "Failed to load selected Easy deal. Started a random shuffle."

        self.board.set_board_bg(self._board_bgs.get("manual"))
        self._switch_to_game_screen()
        self.scene = "game"

    def _start_solver_game(self, algorithm: str = "ucs") -> None:
        self._play_click_sound()
        self._reset_victory_state()
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
        self._a_star_session = None
        self.solver_algorithm = algorithm
        self.solver_label = "A*" if algorithm == "a_star" else algorithm.upper()

        loaded = self._load_next_sample_game("easy")
        if not loaded:
            loaded = self._load_next_sample_game()
        if not loaded:
            self.game.new_game()
            self.board.state = self.game.get_state().clone()
            # self.board.on_reset()
            self.board.start_deal_animation(self.game.get_state())
            self._refresh_game_flags()
            self.solver_message = f"AI Solver ({algorithm.upper()}) sample not found. Started a random shuffle."
        else:
            self.solver_message = f"AI Solver ({algorithm.upper()}): loaded {self.last_loaded_sample}, searching..."

        
        self.board.set_board_bg(self._board_bgs.get(algorithm))
        self._scene_transition(self._switch_to_game_screen, "game")
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
                algo = getattr(self, "solver_algorithm", "ucs")
                if algo == "a_star":
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
                elif algo == "bfs" and solve_bfs:
                    result = solve_bfs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                elif algo == "dfs" and solve_dfs:
                    result = solve_dfs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                else:
                    result = solve_ucs(snapshot, max_nodes=max_nodes, max_time_seconds=max_time_seconds)
                if self._solver_job_id == job_id:
                    if algo == "a_star":
                        self._a_star_session = session
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

    def _cancel_pending_hint(self) -> None:
        self._hint_job_id += 1
        self._hint_pending = False
        self._hint_async_result = None
        self._hint_async_error = None

    def _clear_hint(self) -> None:
        self.current_hint = None
        self.board.set_highlighted_card(None)

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

    def _discover_sample_games_by_difficulty(self) -> dict:
        result = {}
        for file_path in self._sample_game_files:
            difficulty = os.path.basename(os.path.dirname(file_path)).lower()
            result.setdefault(difficulty, []).append(file_path)
        for key in result:
            result[key].sort()
        return result

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
            self.board.start_deal_animation(self.game.get_state())
            self.last_loaded_sample = os.path.relpath(file_path, SOLUTION_DIR)
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
            self.board.start_deal_animation(self.game.get_state())
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
        pygame.mixer.music.fadeout(500)

        if self.outro_clip is not None:
            self.scene = "outro"
        else:
            self.running = False

    def _play_bg_music(self) -> None:
        """Phát nhạc nền Jazz lặp vô tận, âm lượng nhỏ để không lấn át tiếng Jackpot."""
        if hasattr(self, 'bg_music_path') and os.path.exists(self.bg_music_path):
            try:
                pygame.mixer.music.load(self.bg_music_path)
                pygame.mixer.music.set_volume(0.8) # Âm lượng 30% để làm nền (Background)
                pygame.mixer.music.play(-1) # -1 nghĩa là lặp lại vô tận
            except Exception as e:
                print(f"Lỗi khi nạp nhạc nền: {e}")

    def _play_click_sound(self) -> None:
        """Phát tiếng click mượt mà khi nhấn nút."""
        if getattr(self, "click_sound", None):
            self.click_sound.play()

    def _play_lose_music(self) -> None:
        """Làm mờ nhạc Jazz và phát nhạc nền buồn khi thua cuộc."""
        if not getattr(self, "_is_lose_music_playing", False):
            lose_path = os.path.join(os.path.dirname(__file__), "..", "..", "lose_bgm.mp3")
            if os.path.exists(lose_path):
                try:
                    pygame.mixer.music.fadeout(500) # Từ từ tắt nhạc Jazz
                    pygame.mixer.music.load(lose_path)
                    pygame.mixer.music.set_volume(0.5)
                    pygame.mixer.music.play(-1) # Lặp vô tận
                    self._is_lose_music_playing = True
                except Exception as e:
                    print(f"Lỗi nạp nhạc thua: {e}")

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

        self._play_bg_music()

    def _update_game_from_state(self) -> None:
        self.board.state = self.game.get_state().clone()
        self.board.on_reset()


    def _debug_set_instant_win(self) -> None:
        """Hàm 'hack' game: Đưa về trạng thái chỉ còn 1 bước là thắng để test hiệu ứng."""
        from core.state import Card, State
        
        # SỬA TẠI ĐÂY: Tạo 8 cột Tableau trống để thỏa mãn yêu cầu của State
        # Dòng này tạo ra một list chứa 8 list con trống: [[], [], ..., []]
        cheat_state = State(cascades=[[] for _ in range(8)])
        
        # Lấp đầy Foundation (Chuồn, Rô, Cơ mỗi bộ 13 lá)
        # Lưu ý: Nếu code báo lỗi 'foundations' chưa có, bạn hãy kiểm tra core/state.py
        cheat_state.foundations['C'] = 13
        cheat_state.foundations['D'] = 13
        cheat_state.foundations['H'] = 13
        
        # Bộ Bích (Spades) để 12 lá (thiếu con Già - King)
        cheat_state.foundations['S'] = 12
        
        # Đặt con Già Bích (King of Spades) vào ô Free Cell đầu tiên
        cheat_state.free_cells[0] = Card(rank=13, suit='S')
        
        # Cập nhật trạng thái này lên màn hình
        self.game.set_state(cheat_state)
        self.board.apply_state(cheat_state)
        self._refresh_game_flags()
        self.solver_message = "DEBUG: Move the King of Spades to Foundation to win!"

    # Thêm vào Source/gui/app.py

    def _reset_victory_state(self):
        """Dọn dẹp sạch sẽ hiệu ứng ăn mừng để không bị lây sang ván sau."""
        self.victory_timer = 0
        self.particles = []
        self.lose_particles = []

        if hasattr(self, 'jackpot_sound') and self.jackpot_sound:
            self.jackpot_sound.stop() # Dừng tiếng tiền đổ nếu đang kêu

        if getattr(self, "_is_lose_music_playing", False):
            self._is_lose_music_playing = False
            self._play_bg_music()

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
            self._draw_ai_thinking_cocktail()
            self._draw_lose_celebration()
            self._draw_victory_celebration()
        elif self.scene == "ai_select":
            self._draw_ai_selector()

    def _draw_game_hud(self) -> None:
        h = self.screen.get_height()
        
        hint = self.hint_font.render("ESC: Menu   |   R: New Shuffle", True, (255, 250, 205))
        # Luôn cách đáy màn hình 14px
        self.screen.blit(hint, (18, h - hint.get_height() - 14))

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

        if self.is_stuck:
            w, h = self.screen.get_size()
        

        # if self.ai_solver_mode and not self.is_animating and not rules.is_goal(self.game.get_state()):
        #    lock = self.hint_font.render("AI Solver mode: manual card movement is disabled.", True, (255, 236, 170))
        #    self.screen.blit(lock, (18, 48))

    def _draw_ai_thinking_cocktail(self):
        """Vẽ icon ly cocktail thu nhỏ, thẳng hàng và rực rỡ (Nâng cấp Pro)."""
        # Chỉ sủi bọt khi AI thực sự đang tìm kiếm
        if not self._solver_pending: 
            if hasattr(self, "is_solving_indicator_particles"):
                self.is_solving_indicator_particles = []
            return

        import math, random
        # 1. Tọa độ MINI: gx=520, gy=15. Nằm sau text "searching..."
        gx, gy = 780, 15 
        gw, gh = 25, 32 # Tăng kích thước nhẹ 25x32px để nổi bật hơn
        
        if not hasattr(self, "is_solving_indicator_particles"):
            self.is_solving_indicator_particles = []

        # 2. HIỆU ỨNG: Sinh bọt khí rực rỡ (GOLD_L)
        if len(self.is_solving_indicator_particles) < 20 and random.random() < 0.2:
            self.is_solving_indicator_particles.append({
                "x_base": random.uniform(gx + 5, gx + gw - 5),
                "y": gy + gh - 5,
                "speed": random.uniform(0.4, 0.9),
                "offset": random.uniform(0, math.pi * 2),
                "size": random.randint(1, 3), # Hạt li ti
                "alpha": random.randint(180, 255)
            })

        # 3. NÂNG CẤP NỔI BẬT: Nước màu Hổ pháchGlowing Amber
        wave = math.sin(pygame.time.get_ticks() * 0.01) * 2.5
        # Mực nước cao hơn (gy + 10)
        liquid_rect = [
            (gx + 4, gy + 10 + wave), (gx + gw - 4, gy + 10 + wave),
            (gx + gw - 8, gy + gh - 2), (gx + 8, gy + gh - 2)
        ]
        liquid_surf = pygame.Surface((gw, gh + 10), pygame.SRCALPHA)
        # SỬA: Chuyển sang màu Hổ phách Glowing Amber rực rỡ
        pygame.draw.polygon(liquid_surf, (255, 191, 0, 220), [(p[0]-gx, p[1]-gy) for p in liquid_rect])
        self.screen.blit(liquid_surf, (gx, gy))

        # 4. Cập nhật và vẽ bọt khí (Màu Gold rực rỡ)
        for p in self.is_solving_indicator_particles[:]:
            p["y"] -= p["speed"]
            drift = math.sin(p["y"] * 0.3 + p["offset"]) * 2.5
            if p["y"] < gy + 10 + wave:
                self.is_solving_indicator_particles.remove(p)
                continue
            # (255, 223, 100) là GOLD_L của bạn
            pygame.draw.circle(self.screen, (255, 223, 100, p["alpha"]), (int(p["x_base"] + drift), int(p["y"])), p["size"])

        # 5. NÂNG CẤP NỔI BẬT: KHUNG LY METALLIC GOLD (Rực Rỡ)
        glass_points = [(gx, gy), (gx + gw, gy), (gx + gw - 8, gy + gh), (gx + 8, gy + gh)]
        
        # Thêm một viền Gold mảnh phía trước để tạo độ nổi (Metallic edge)
        # (255, 215, 0) là màu Vàng Bright Gold
        pygame.draw.lines(self.screen, (255, 215, 0, 200), False, glass_points, 1) # Gold rực rỡ
        
        # Chân ly đơn giản nhưng rực rỡ
        pygame.draw.line(self.screen, (255, 215, 0, 200), (gx + gw//2, gy + gh), (gx + gw//2, gy + gh + 12), 1)
        pygame.draw.line(self.screen, (255, 215, 0, 200), (gx + 6, gy + gh + 12), (gx + gw - 6, gy + gh + 12), 1)

    #def _refresh_game_flags(self) -> None:
    #    self.view_model = self.game.get_view_model()
    #    is_won = self.view_model["is_goal"]
    #    has_moves = len(self.view_model.get("legal_moves", [])) > 0
    #    self.is_stuck = (not is_won) and (not has_moves)

    def _refresh_game_flags(self) -> None:
        # Nếu đang trong chế độ test phím 'L', không cho phép tự động tính toán lại
        # (Để hiệu ứng thua không bị mất ngay lập tức)
        if self.solver_message.startswith("DEBUG: You pressed 'L'"):
            return

        self.view_model = self.game.get_view_model()
        is_won = self.view_model["is_goal"]
        has_moves = len(self.view_model.get("legal_moves", [])) > 0
        was_stuck = getattr(self, "is_stuck", False)
        self.is_stuck = (not is_won) and (not has_moves)

        if self.is_stuck and not was_stuck:
            self._play_lose_music()

    def _spawn_victory_particles(self):
        """Tạo ra các đồng xu vàng ngẫu nhiên ở cạnh trên màn hình."""
        import random
        w = self.screen.get_width()
        for _ in range(5): # Mỗi frame tạo 5 đồng xu
            self.particles.append({
                "pos": [random.randint(0, w), -20],
                "vel": [random.uniform(-2, 2), random.uniform(5, 12)],
                "color": random.choice([(212, 175, 55), (255, 223, 100)]), # GOLD và GOLD_L
                "size": random.randint(6, 12)
            })

    def _update_victory_logic(self):
        """Cập nhật vị trí tiền rơi và kiểm tra thời gian quay về menu."""
        # --- THÊM ĐIỀU KIỆN CHẶN TẠI ĐÂY ---
        # 1. Chỉ chạy khi đang ở màn hình Game
        # 2. Không chạy khi AI đang di chuyển bài (is_animating)
        if self.scene != "game" or self.is_animating:
            return
        # ----------------------------------

        # Nếu chưa thắng thì thoát luôn
        if not rules.is_goal(self.game.get_state()):
            return

        # Khi victory_timer bắt đầu từ 0 sang 1, phát âm thanh
        if self.victory_timer == 0 and self.jackpot_sound:
            self.jackpot_sound.play() 

        self.victory_timer += 1
        self._spawn_victory_particles()

        # Cập nhật tọa độ tiền rơi
        for p in self.particles[:]:
            p["pos"][0] += p["vel"][0]
            p["pos"][1] += p["vel"][1]
            if p["pos"][1] > self.screen.get_height():
                self.particles.remove(p)

        # Sau khoảng 5 giây, tự động về menu
        if self.victory_timer > 300:
            self.victory_timer = 0
            self.particles = []
            self.ai_solver_mode = False
            self._go_menu()

    def _draw_victory_celebration(self):
        """Vẽ VICTORY 3D với viền Burnt Coffee và hiệu ứng vệt sáng kim loại (Glint)."""
        if self.victory_timer <= 0 or not rules.is_goal(self.game.get_state()):
            return

        w, h = self.screen.get_size()
        import math

        # 1. Làm mờ nền màu Burnt Coffee (52, 21, 15)
        dim_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        dim_surf.fill((52, 21, 15, 180)) 
        self.screen.blit(dim_surf, (0, 0))

        # Vẽ mưa tiền/chip (Particles)
        for p in self.particles:
            pygame.draw.circle(self.screen, p["color"], (int(p["pos"][0]), int(p["pos"][1])), p["size"])

        # 2. Chuẩn bị các lớp chữ
        text = "VICTORY"
        shadow_surf = self.victory_title_font.render(text, True, (20, 10, 0)) # Bóng đổ sâu
        body_surf = self.victory_title_font.render(text, True, (212, 175, 55)) # Vàng đồng
        outline_surf = self.victory_title_font.render(text, True, (52, 21, 15)) # Viền Burnt Coffee

        tx = w // 2 - body_surf.get_width() // 2
        ty = h // 2 - body_surf.get_height() // 2 - 50

        # 3. Vẽ độ dày 3D (Vẽ từ xa đến gần)
        depth = 8
        self.screen.blit(shadow_surf, (tx + depth + 5, ty + depth + 5))
        for i in range(depth, 0, -1):
            self.screen.blit(body_surf, (tx + i, ty + i))

        # 4. Vẽ VIỀN để tách biệt chữ với nền
        edge_thickness = 3 
        for dx in range(-edge_thickness, edge_thickness + 1):
            for dy in range(-edge_thickness, edge_thickness + 1):
                if dx != 0 or dy != 0:
                    self.screen.blit(outline_surf, (tx + dx, ty + dy))

        # 5. Vẽ mặt chữ phát sáng nhịp thở (Pulse)
        pulse = math.sin(self.victory_timer * 0.15) * 25
        glow_color = (min(255, 255 + pulse), min(255, 230 + pulse), min(255, 100 + pulse))
        top_surf = self.victory_title_font.render(text, True, glow_color)
        self.screen.blit(top_surf, (tx, ty))

        # --- 6. HIỆU ỨNG MỚI: VỆT SÁNG KIM LOẠI (GLINT) ---
        # Tính toán vị trí vệt sáng chạy từ trái sang phải dựa trên timer
        glint_speed = 12
        text_w, text_h = top_surf.get_size()
        # Vệt sáng sẽ chạy lại sau mỗi chu kỳ
        glint_x = (self.victory_timer * glint_speed) % (text_w * 3) - text_w
        
        # Tạo vệt sáng trắng mờ hình chữ nhật nghiêng
        glint_width = 50
        glint_surf = pygame.Surface((glint_width, text_h), pygame.SRCALPHA)
        for i in range(glint_width):
            # Tạo hiệu ứng gradient cho vệt sáng (sáng ở giữa, mờ ở rìa)
            alpha = int(100 * (1 - abs(i - glint_width/2) / (glint_width/2)))
            pygame.draw.line(glint_surf, (255, 255, 255, alpha), (i, 0), (i, text_h))
        
        # Nghiêng vệt sáng 25 độ cho "nghệ"
        glint_surf = pygame.transform.rotate(glint_surf, 25)
        
        # Thiết lập vùng cắt (Clip) để vệt sáng chỉ hiện trên phạm vi chữ VICTORY
        old_clip = self.screen.get_clip()
        self.screen.set_clip(pygame.Rect(tx, ty, text_w, text_h))
        self.screen.blit(glint_surf, (tx + glint_x, ty - 20))
        self.screen.set_clip(old_clip)

        # 7. Chữ phụ trắng tinh khôi
        sub_msg = self.menu_font.render("YOU CLEARED THE BOARD", True, (255, 255, 255))
        self.screen.blit(sub_msg, (w // 2 - sub_msg.get_width() // 2, ty + text_h + 20))

        if self.ai_solver_mode and self.solver_result:
            # Chỉ cần truyền tham số cơ bản, việc căn giữa và làm đẹp sẽ xử lý ở hud.py
            draw_solver_stats(self.screen, self.hint_font, self.body_font, self.solver_result)


    def _draw_lose_celebration(self):
        """Vẽ màn hình thua cuộc với hiệu ứng sương khói mờ ảo."""
        if not self.is_stuck:
            self.lose_particles = []
            return

        w, h = self.screen.get_size()
        self._spawn_lose_particles() # Sinh thêm khói

        # 1. Overlay Burnt Coffee thẫm hơn một chút (Alpha 220)
        lose_overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        lose_overlay.fill((14, 20, 28, 210)) 
        self.screen.blit(lose_overlay, (0, 0))

        # 2. Vẽ các hạt sương khói (Mist)
        for p in self.lose_particles[:]:
            # Tạo surface riêng cho từng hạt để dùng độ trong suốt (Alpha)
            mist_surf = pygame.Surface((p["size"]*2, p["size"]*2), pygame.SRCALPHA)
            # Vẽ vòng tròn mờ màu Xám nhạt
            pygame.draw.circle(mist_surf, (150, 150, 160, p["alpha"]), (p["size"], p["size"]), p["size"])
            self.screen.blit(mist_surf, (p["pos"][0] - p["size"], p["pos"][1] - p["size"]))
            
            # Cập nhật vị trí và giảm tuổi thọ
            p["pos"][0] += p["vel"][0]
            p["pos"][1] += p["vel"][1]
            p["life"] -= 1
            if p["life"] <= 0 or p["pos"][0] > w + 100:
                self.lose_particles.remove(p)

        # 3. Vẽ chữ GAME OVER màu Bạc Lạnh (Giữ nguyên logic cũ của Quan)
        msg_surf = self.victory_title_font.render("GAME OVER", True, (170, 170, 180))
        tx = w // 2 - msg_surf.get_width() // 2
        ty = h // 2 - 120
        self.screen.blit(msg_surf, (tx, ty))

        sub_msg = self.menu_font.render("So close! Press 'R' to try again", True, (180, 180, 180))
        self.screen.blit(sub_msg, (w // 2 - sub_msg.get_width() // 2, ty + msg_surf.get_height() + 20))