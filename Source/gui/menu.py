from __future__ import annotations

import os
import re
from typing import Callable

import pygame

from gui.interface import Button


class MenuScreen:
    """Render and handle events for the menu scene, including solver dropdown."""

    def __init__(
        self,
        screen: pygame.Surface,
        title_font: pygame.font.Font,
        menu_font: pygame.font.Font,
        hint_font: pygame.font.Font,
        bg_image: pygame.Surface = None,
        selector_bg: pygame.Surface = None,
    ) -> None:
        self.screen = screen
        self.title_font = title_font
        self.menu_font = menu_font
        self.hint_font = hint_font
        self.bg_image = bg_image
        self.selector_bg = selector_bg

        self.manual_dropdown_open = False
        self.manual_dropdown_progress = 0.0
        self.solver_dropdown_open = False
        self.solver_dropdown_progress = 0.0
        self.dropdown_anim_speed = 0.18

        self.easy_page_size = 5
        self.easy_list_rects = [pygame.Rect(0, 0, 0, 0) for _ in range(self.easy_page_size)]
        self.easy_visible_indices: list[int] = []
        self.easy_page_start = 0

        self._rebuild_layout()

    def _rebuild_layout(self) -> None:
        """Tính lại toàn bộ vị trí button dựa trên screen hiện tại."""
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        cx = sw // 2
        bw, bh = 300, 70

        # --- Nút trung tâm: Manual & AI Solver ---
        center_y_start = sh // 2 - 250
        self.start_button = Button(
            text="Manual",
            rect=pygame.Rect(cx - bw // 2, center_y_start, bw, bh),
            base_color=(24, 128, 49),
            hover_color=(38, 156, 62),
            text_color=(255, 250, 210),
        )
        self.solver_button = Button(
            text="AI Solver",
            rect=pygame.Rect(cx - bw // 2, center_y_start + 100, bw, bh),
            base_color=(25, 86, 130),
            hover_color=(34, 109, 162),
            text_color=(245, 248, 214),
        )

        # --- Nút góc: How To Play (trên trái) & Exit (trên phải) ---
        cs = 90   # kích thước ô vuông góc
        cm = 16   # margin từ cạnh màn hình
        self.howto_button = Button(
            text="📖",
            rect=pygame.Rect(cm, cm, cs, cs),
            base_color=(132, 95, 20),
            hover_color=(160, 115, 25),
            text_color=(255, 247, 214),
        )
        self.exit_button = Button(
            text="✕",
            rect=pygame.Rect(sw - cm - cs, cm, cs, cs),
            base_color=(130, 42, 38),
            hover_color=(162, 56, 52),
            text_color=(255, 244, 210),
        )

        # --- Back button (dùng ở howto / easy_select) ---
        self.back_button = Button(
            text="Back",
            rect=pygame.Rect(28, sh - 78, 150, 48),
            base_color=(22, 96, 120),
            hover_color=(29, 118, 148),
            text_color=(245, 250, 215),
        )

        # Base Y cho dropdown animation (chỉ Manual & AI Solver bị đẩy)
        self.base_start_y = center_y_start
        self.base_solver_y = center_y_start + 100
        self.base_howto_y = cm   # cố định
        self.base_exit_y = cm    # cố định

        # Dropdown options cho Manual
        self.manual_option_buttons = [
            Button(
                text="Easy",
                rect=pygame.Rect(cx - bw // 2, self.start_button.rect.bottom + 6, bw, 50),
                base_color=(28, 120, 64),
                hover_color=(39, 145, 78),
                text_color=(251, 250, 219),
            ),
            Button(
                text="Hard",
                rect=pygame.Rect(cx - bw // 2, self.start_button.rect.bottom + 64, bw, 50),
                base_color=(134, 60, 30),
                hover_color=(164, 75, 38),
                text_color=(255, 244, 210),
            ),
        ]
        self.manual_dropdown_max_h = (
            len(self.manual_option_buttons) * 50
            + (len(self.manual_option_buttons) - 1) * 8
        )

        # Dropdown option cho AI Solver — 4 thuật toán, màu chip casino
        _ALGO_CONFIGS = [
            # (text,  base_color,          hover_color,         label = chip color name)
            ("UCS",   (190, 80, 30), (232, 110, 48),   ),  # xanh bạc hà
            ("A*",    (140,  20,  20),     (175,  35,  35),   ),  # đỏ         – $5  chip
            ("BFS",   (10, 10, 15),     (25, 25, 35),   ),  # xanh lá    – $25 chip
            ("DFS",   ( 80,  40, 130),     (105,  58, 165),   ),  # tím        – $500 chip
        ]
        algo_h   = 48
        algo_gap = 6
        self.solver_dropdown_max_h = len(_ALGO_CONFIGS) * algo_h + (len(_ALGO_CONFIGS) - 1) * algo_gap

        self.solver_option_buttons = []
        for i, (text, base, hover) in enumerate(_ALGO_CONFIGS):
            self.solver_option_buttons.append(Button(
                text=text,
                rect=pygame.Rect(
                    self.solver_button.rect.left,
                    self.solver_button.rect.bottom + 6 + i * (algo_h + algo_gap),
                    self.solver_button.rect.width,
                    algo_h,
                ),
                base_color=base,
                hover_color=hover,
                text_color=(255, 245, 200),
            ))
        # keep legacy reference for compatibility
        self.ucs_option_button = self.solver_option_buttons[0]

        # Easy selector buttons
        self.easy_prev_button = Button(
            text="Prev",
            rect=pygame.Rect(0, 0, 140, 46),
            base_color=(190, 80, 15),   
            hover_color=(220, 105, 30),
            text_color=(251, 248, 218),
        )
        self.easy_next_button = Button(
            text="Next",
            rect=pygame.Rect(0, 0, 140, 46),
            base_color=(190, 80, 15),   
            hover_color=(220, 105, 30),
            text_color=(251, 248, 218),
        )
        self.easy_start_button = Button(
            text="Start Deal",
            rect=pygame.Rect(0, 0, 200, 52),
            base_color=(24, 128, 49),
            hover_color=(38, 156, 62),
            text_color=(255, 250, 210),
        )

    def rebuild_for_screen(self, screen: pygame.Surface) -> None:
        """Gọi sau khi screen được resize để cập nhật layout button."""
        self.screen = screen
        self._rebuild_layout()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _draw_button_state(
        self,
        button: Button,
        font: pygame.font.Font,
        mouse_pos: tuple[int, int],
        enabled: bool,
    ) -> None:
        if enabled:
            button.draw(self.screen, font, mouse_pos)
            return

        pygame.draw.rect(self.screen, (82, 98, 90), button.rect, border_radius=10)
        pygame.draw.rect(self.screen, (168, 176, 164), button.rect, width=2, border_radius=10)
        label = font.render(button.text, True, (210, 216, 202))
        self.screen.blit(
            label,
            (button.rect.centerx - label.get_width() // 2, button.rect.centery - label.get_height() // 2),
        )

    def _layout_easy_selector(self, total_games: int, selected_index: int) -> pygame.Rect:
        w, h = self.screen.get_width(), self.screen.get_height()
        pw, ph = min(660, w - 40), 550
        panel = pygame.Rect(w // 2 - pw // 2, h // 2 - ph // 2 - 30, pw, ph)

        if total_games > 0:
            selected_index = max(0, min(selected_index, total_games - 1))
            self.easy_page_start = (selected_index // self.easy_page_size) * self.easy_page_size
        else:
            self.easy_page_start = 0

        list_x = panel.x + 32
        list_y = panel.y + 115
        list_w = panel.width - 64
        row_h  = 52
        gap    = 14

        self.easy_visible_indices.clear()
        for row_idx in range(self.easy_page_size):
            row_rect = pygame.Rect(list_x, list_y + row_idx * (row_h + gap), list_w, row_h)
            self.easy_list_rects[row_idx] = row_rect

            absolute_idx = self.easy_page_start + row_idx
            if absolute_idx < total_games:
                self.easy_visible_indices.append(absolute_idx)

        self.easy_prev_button.rect.topleft  = (panel.x + 32,      panel.bottom - 60)
        self.easy_next_button.rect.topright = (panel.right - 32,   panel.bottom - 60)
        self.easy_start_button.rect.midbottom = (w // 2, h - 22)

        self.back_button.rect.topleft = (24, h - 70)
        return panel

    def _easy_deal_label(self, file_path: str, index: int) -> str:
        stem = os.path.splitext(os.path.basename(file_path))[0]
        matched = re.search(r"(\d+)", stem)
        if matched:
            return f"Deal {int(matched.group(1)):02d}"
        return f"Deal {index + 1:02d}"

    def _draw_icon_book(self, cx: int, cy: int, size: int, color: tuple) -> None:
        """Vẽ icon cuốn sách mở bằng pygame primitives."""
        s = size // 2
        # Trang trái
        left = pygame.Rect(cx - s, cy - s, s - 1, s * 2)
        pygame.draw.rect(self.screen, color, left, border_radius=2)
        # Trang phải
        right = pygame.Rect(cx + 1, cy - s, s - 1, s * 2)
        pygame.draw.rect(self.screen, color, right, border_radius=2)
        # Gáy sách (đường giữa)
        pygame.draw.line(self.screen, (0, 0, 0, 80), (cx, cy - s), (cx, cy + s), 2)
        # Đường kẻ dòng trang trái
        line_color = tuple(max(0, c - 60) for c in color)
        for i in range(1, 4):
            ly = cy - s + i * (s * 2 // 4)
            pygame.draw.line(self.screen, line_color, (cx - s + 4, ly), (cx - 4, ly), 1)
        # Đường kẻ dòng trang phải
        for i in range(1, 4):
            ly = cy - s + i * (s * 2 // 4)
            pygame.draw.line(self.screen, line_color, (cx + 4, ly), (cx + s - 4, ly), 1)

    def _draw_icon_x(self, cx: int, cy: int, size: int, color: tuple) -> None:
        """Vẽ icon X (close) bằng pygame primitives."""
        half = size // 2
        thick = max(3, size // 6)
        pygame.draw.line(self.screen, color, (cx - half, cy - half), (cx + half, cy + half), thick)
        pygame.draw.line(self.screen, color, (cx + half, cy - half), (cx - half, cy + half), thick)

    def _draw_corner_icon_button(
        self,
        button: Button,
        icon_type: str,
        label: str,
        mouse_pos: tuple[int, int],
    ) -> None:
        """Vẽ nút góc vuông với icon vẽ bằng primitives + label tuỳ chọn.
        icon_type: 'book' | 'x'
        """
        is_hover = button.rect.collidepoint(mouse_pos)
        color = button.hover_color if is_hover else button.base_color

        pygame.draw.rect(self.screen, color, button.rect, border_radius=14)
        pygame.draw.rect(self.screen, (255, 230, 160), button.rect, width=2, border_radius=14)

        ic = button.text_color
        icon_size = 28

        if label:
            # Có label → icon lệch lên trên một chút
            icon_cy = button.rect.y + button.rect.height // 2 - 8
        else:
            icon_cy = button.rect.centery

        icon_cx = button.rect.centerx

        if icon_type == "book":
            self._draw_icon_book(icon_cx, icon_cy, icon_size, ic)
        elif icon_type == "x":
            self._draw_icon_x(icon_cx, icon_cy, icon_size, ic)

        # Label nhỏ bên dưới — chỉ vẽ nếu có nội dung
        if label:
            label_surf = self.hint_font.render(label, True, button.text_color)
            lx = button.rect.centerx - label_surf.get_width() // 2
            ly = button.rect.bottom - label_surf.get_height() - 6
            self.screen.blit(label_surf, (lx, ly))

    # ------------------------------------------------------------------
    # Animation
    # ------------------------------------------------------------------

    def update_dropdown_animation(self) -> None:
        manual_target = 1.0 if self.manual_dropdown_open else 0.0
        solver_target = 1.0 if self.solver_dropdown_open else 0.0

        if self.manual_dropdown_progress < manual_target:
            self.manual_dropdown_progress = min(manual_target, self.manual_dropdown_progress + self.dropdown_anim_speed)
        elif self.manual_dropdown_progress > manual_target:
            self.manual_dropdown_progress = max(manual_target, self.manual_dropdown_progress - self.dropdown_anim_speed)

        if self.solver_dropdown_progress < solver_target:
            self.solver_dropdown_progress = min(solver_target, self.solver_dropdown_progress + self.dropdown_anim_speed)
        elif self.solver_dropdown_progress > solver_target:
            self.solver_dropdown_progress = max(solver_target, self.solver_dropdown_progress - self.dropdown_anim_speed)

        manual_push = int((self.manual_dropdown_max_h + 14) * self.manual_dropdown_progress)
        solver_push = int((self.solver_dropdown_max_h + 14) * self.solver_dropdown_progress)

        self.start_button.rect.y = self.base_start_y
        self.solver_button.rect.y = self.base_solver_y + manual_push
        # howto & exit là góc cố định — không bị đẩy bởi dropdown
        self.howto_button.rect.y = self.base_howto_y
        self.exit_button.rect.y = self.base_exit_y

        for idx, button in enumerate(self.manual_option_buttons):
            button.rect.x = self.start_button.rect.x
            button.rect.width = self.start_button.rect.width
            button.rect.y = self.start_button.rect.bottom + 6 + idx * (button.rect.height + 8)

        for i, btn in enumerate(self.solver_option_buttons):
            btn.rect.x = self.solver_button.rect.x
            btn.rect.width = self.solver_button.rect.width
            algo_h   = btn.rect.height
            algo_gap = 6
            btn.rect.y = self.solver_button.rect.bottom + 6 + i * (algo_h + algo_gap)
        # legacy compat
        self.ucs_option_button = self.solver_option_buttons[0]

    # ------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------

    def draw_menu(self) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()

        # --- Background ---
        if self.bg_image is not None:
            bg = pygame.transform.scale(self.bg_image, (w, h))
            self.screen.blit(bg, (0, 0))
        else:
            for y in range(h):
                shade = 70 + int(36 * (y / h))
                pygame.draw.line(self.screen, (5, shade, 24), (0, y), (w, y))

        # --- Overlay tối sau các nút trung tâm ---
        overlay_w, overlay_h = 340, 260
        overlay_surf = pygame.Surface((overlay_w, overlay_h), pygame.SRCALPHA)
        overlay_surf.fill((10, 10, 10, 150))
        self.screen.blit(overlay_surf, (w // 2 - overlay_w // 2, self.start_button.rect.top - 24))

        mp = pygame.mouse.get_pos()

        # --- Manual button + dropdown ---
        self.start_button.draw(self.screen, self.menu_font, mp)
        if self.manual_dropdown_progress > 0:
            current_h = max(1, int(self.manual_dropdown_max_h * self.manual_dropdown_progress))
            visible_rect = pygame.Rect(
                self.manual_option_buttons[0].rect.x,
                self.manual_option_buttons[0].rect.y,
                self.manual_option_buttons[0].rect.width,
                current_h,
            )
            drop_bg = visible_rect.inflate(10, 10)
            pygame.draw.rect(self.screen, (16, 74, 44), drop_bg, border_radius=12)
            pygame.draw.rect(self.screen, (248, 238, 170), drop_bg, width=2, border_radius=12)
            clip_before = self.screen.get_clip()
            self.screen.set_clip(visible_rect)
            for button in self.manual_option_buttons:
                button.draw(self.screen, self.hint_font, mp)
            self.screen.set_clip(clip_before)

        # --- AI Solver button + dropdown ---
        self.solver_button.draw(self.screen, self.menu_font, mp)
        if self.solver_dropdown_progress > 0:
            # Tính vùng hiển thị theo progress
            total_h = self.solver_dropdown_max_h
            current_h = max(1, int(total_h * self.solver_dropdown_progress))
            first = self.solver_option_buttons[0]
            visible_rect = pygame.Rect(first.rect.x, first.rect.y, first.rect.width, current_h)
            drop_bg = visible_rect.inflate(10, 10)
            pygame.draw.rect(self.screen, (20, 20, 30), drop_bg, border_radius=12)
            pygame.draw.rect(self.screen, (248, 238, 170), drop_bg, width=2, border_radius=12)
            clip_before = self.screen.get_clip()
            self.screen.set_clip(visible_rect)
            for btn in self.solver_option_buttons:
                btn.draw(self.screen, self.hint_font, mp)
                # Gold border on each algo button
                pygame.draw.rect(self.screen, (212, 175, 55), btn.rect, width=1, border_radius=8)
            self.screen.set_clip(clip_before)

        # --- Nút góc ---
        # How To Play: icon sách mở + label "How To Play"
        self._draw_corner_icon_button(self.howto_button, "book", "", mp)
        # Exit: chỉ icon X, không có label
        self._draw_corner_icon_button(self.exit_button, "x", "", mp)

        # --- FREECELL title dưới đáy ---
        shadow = self.title_font.render("FREECELL", True, (80, 45, 8))
        title  = self.title_font.render("FREECELL", True, (250, 236, 150))
        tx = w // 2 - title.get_width() // 2
        ty = h - title.get_height() - 24
        self.screen.blit(shadow, (tx + 3, ty + 3))
        self.screen.blit(title,  (tx, ty))

    def _draw_back_door_button(self, button: Button, mouse_pos: tuple) -> None:
        """Nút back: nền đỏ nhung, viền gold, chữ Back căn giữa."""
        VELVET_RED = (140,  25,  25)
        VELVET_HOV = (175,  40,  40)
        GOLD       = (212, 175,  55)
        GOLD_LIGHT = (255, 223, 100)
        is_hover   = button.rect.collidepoint(mouse_pos)
        fill = VELVET_HOV if is_hover else VELVET_RED
        pygame.draw.rect(self.screen, fill, button.rect, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, button.rect, width=2, border_radius=10)

        lbl  = self.hint_font.render("Back", True, GOLD_LIGHT)
        shad = self.hint_font.render("Back", True, (0, 0, 0))
        lx = button.rect.centerx - lbl.get_width() // 2
        ly = button.rect.centery - lbl.get_height() // 2
        self.screen.blit(shad, (lx + 1, ly + 1))
        self.screen.blit(lbl,  (lx,     ly))

    def draw_howto(self, body_font: pygame.font.Font, howto_lines: list[str]) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()
        for y in range(h):
            shade = 36 + int(28 * (y / h))
            pygame.draw.line(self.screen, (6, 60 + shade, 38), (0, y), (w, y))

        title = self.title_font.render("HOW TO PLAY", True, (250, 236, 150))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 86))

        line_y = 210
        for line in howto_lines:
            text = body_font.render(f"- {line}", True, (248, 240, 203))
            self.screen.blit(text, (90, line_y))
            line_y += 56

        hint = self.hint_font.render("Press ESC/B or click Back to return to menu", True, (248, 230, 168))
        self.screen.blit(hint, (90, self.screen.get_height() - 120))
        self._draw_back_door_button(self.back_button, pygame.mouse.get_pos())

    def draw_easy_selector(self, easy_games: list[str], selected_index: int, difficulty: str = "easy") -> None:   
        
        h, w = self.screen.get_height(), self.screen.get_width()

        # --- Background ---
        if self.selector_bg is not None:
            bg = pygame.transform.scale(self.selector_bg, (w, h))
            self.screen.blit(bg, (0, 0))
            ov = pygame.Surface((w, h), pygame.SRCALPHA)
            ov.fill((0, 0, 0, 80))
            self.screen.blit(ov, (0, 0))
        else:
            for y in range(h):
                shade = 22 + int(40 * (y / h))
                pygame.draw.line(self.screen, (4, 62 + shade, 31), (0, y), (w, y))

        GOLD        = (212, 175,  55)
        GOLD_LIGHT  = (255, 223, 100)
        EMERALD_ROW = ( 18,  92,  54)
        ORANGE_SEL  = (200,  90,  20)
        ORANGE_HOV  = (160,  70,  15)

        panel = self._layout_easy_selector(len(easy_games), selected_index)

        ps = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        ps.fill((10, 10, 10, 160))
        self.screen.blit(ps, (panel.x, panel.y))
        pygame.draw.rect(self.screen, GOLD, panel, width=2, border_radius=16)

        title = self.title_font.render("SELECT A DEAL", True, GOLD_LIGHT)
        shad  = self.title_font.render("SELECT A DEAL", True, (40, 20, 0))
        tx = w // 2 - title.get_width() // 2
        self.screen.blit(shad,  (tx + 2, panel.y + 14))
        self.screen.blit(title, (tx,     panel.y + 12))

        total    = len(easy_games)
        page     = (self.easy_page_start // self.easy_page_size) + 1 if total else 0
        max_page = ((total - 1) // self.easy_page_size + 1) if total else 0
        summary  = self.hint_font.render(
            f"{total} deals   —   Page {page} / {max_page}", True, GOLD_LIGHT)
        self.screen.blit(summary, (w // 2 - summary.get_width() // 2, panel.y + 72))

        mp = pygame.mouse.get_pos()
        if not self.easy_visible_indices:
            empty = self.menu_font.render("No Easy deals found.", True, GOLD_LIGHT)
            self.screen.blit(empty, (w // 2 - empty.get_width() // 2,
                                     panel.centery - empty.get_height() // 2))
        else:
            for row, absolute_idx in enumerate(self.easy_visible_indices):
                row_rect    = self.easy_list_rects[row]
                is_hover    = row_rect.collidepoint(mp)
                is_selected = absolute_idx == selected_index

                if is_selected:
                    fill, border = ORANGE_SEL, GOLD
                elif is_hover:
                    fill, border = ORANGE_HOV, GOLD_LIGHT
                else:
                    fill, border = EMERALD_ROW, (177, 191, 159)

                pygame.draw.rect(self.screen, fill,   row_rect, border_radius=10)
                pygame.draw.rect(self.screen, border, row_rect, width=2, border_radius=10)

                label_text = self._easy_deal_label(easy_games[absolute_idx], absolute_idx)
                label = self.menu_font.render(label_text, True, (252, 248, 218))
                self.screen.blit(label, (row_rect.x + 16,
                                         row_rect.centery - label.get_height() // 2))

        can_prev      = self.easy_page_start > 0
        can_next      = self.easy_page_start + self.easy_page_size < len(easy_games)
        has_selection = bool(easy_games)

        self._draw_button_state(self.easy_prev_button,  self.hint_font, mp, can_prev)
        pygame.draw.rect(self.screen, GOLD, self.easy_prev_button.rect,  width=2, border_radius=10)
        self._draw_button_state(self.easy_next_button,  self.hint_font, mp, can_next)
        pygame.draw.rect(self.screen, GOLD, self.easy_next_button.rect,  width=2, border_radius=10)
        self._draw_button_state(self.easy_start_button, self.hint_font, mp, has_selection)
        pygame.draw.rect(self.screen, GOLD, self.easy_start_button.rect, width=2, border_radius=10)
        self._draw_back_door_button(self.back_button, mp)

        diff_text = difficulty.upper()
        
        # Dùng menu_font (size to) và màu GOLD_LIGHT cho đồng bộ với tiêu đề
        text_surf = self.menu_font.render(diff_text, True, GOLD_LIGHT)
        shad_surf = self.menu_font.render(diff_text, True, (40, 20, 0)) # Bóng đổ cho nổi bật
        
        # Căn giữa hoàn hảo dựa trên khung panel
        center_x = panel.centerx
        center_y = self.easy_prev_button.rect.centery
        text_rect = text_surf.get_rect(center=(center_x, center_y))
        
        # In bóng đổ trước, in chữ thật đè lên sau
        self.screen.blit(shad_surf, (text_rect.x + 2, text_rect.y + 2))
        self.screen.blit(text_surf, text_rect)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def handle_menu_event(self, event, on_start_game, on_start_solver,
                          on_ai_select, on_howto, on_exit) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        if self.start_button.rect.collidepoint(event.pos):
            self.manual_dropdown_open = not self.manual_dropdown_open
            self.solver_dropdown_open = False
            return

        if self.solver_button.rect.collidepoint(event.pos):
            self.manual_dropdown_open = False
            on_ai_select()
            return

        if self.manual_dropdown_progress >= 0.95:
            selected_difficulty = None
            for button in self.manual_option_buttons:
                if button.rect.collidepoint(event.pos):
                    selected_difficulty = button.text.lower()
                    break

            if selected_difficulty is not None:
                self.manual_dropdown_open = False
                on_start_game(selected_difficulty)
                return

        if self.solver_dropdown_progress >= 0.95:
            algos = ["ucs", "a_star", "bfs", "dfs"]
            for btn, algo in zip(self.solver_option_buttons, algos):
                if btn.rect.collidepoint(event.pos):
                    self.solver_dropdown_open = False
                    on_start_solver(algo)
                    return

        if self.howto_button.rect.collidepoint(event.pos):
            self.manual_dropdown_open = False
            self.solver_dropdown_open = False
            on_howto()
            return

        if self.exit_button.rect.collidepoint(event.pos):
            on_exit()
            return

        self.manual_dropdown_open = False
        self.solver_dropdown_open = False

    def handle_howto_event(self, event: pygame.event.Event, on_back: Callable[[], None]) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
            on_back()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_button.rect.collidepoint(event.pos):
                on_back()

    def handle_easy_selector_event(
        self,
        event: pygame.event.Event,
        easy_games: list[str],
        selected_index: int,
        on_select: Callable[[int], None],
        on_start: Callable[[int], None],
        on_back: Callable[[], None],
    ) -> None:
        total = len(easy_games)
        self._layout_easy_selector(total, selected_index)

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_b):
                on_back()
                return

            if not total:
                return

            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                on_start(selected_index)
                return

            if event.key == pygame.K_UP:
                on_select((selected_index - 1) % total)
                return
            if event.key == pygame.K_DOWN:
                on_select((selected_index + 1) % total)
                return

            if event.key == pygame.K_LEFT:
                on_select(max(0, selected_index - self.easy_page_size))
                return
            if event.key == pygame.K_RIGHT:
                on_select(min(total - 1, selected_index + self.easy_page_size))
                return

        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        if self.back_button.rect.collidepoint(event.pos):
            on_back()
            return

        if total:
            if self.easy_start_button.rect.collidepoint(event.pos):
                on_start(selected_index)
                return

            if self.easy_prev_button.rect.collidepoint(event.pos) and self.easy_page_start > 0:
                on_select(max(0, self.easy_page_start - self.easy_page_size))
                return

            if self.easy_next_button.rect.collidepoint(event.pos) and (
                self.easy_page_start + self.easy_page_size < total
            ):
                on_select(min(total - 1, self.easy_page_start + self.easy_page_size))
                return

            for row_idx, absolute_idx in enumerate(self.easy_visible_indices):
                if self.easy_list_rects[row_idx].collidepoint(event.pos):
                    on_select(absolute_idx)
                    return