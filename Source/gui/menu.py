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
    ) -> None:
        self.screen = screen
        self.title_font = title_font
        self.menu_font = menu_font
        self.hint_font = hint_font

        cx, bw, bh = self.screen.get_rect().centerx, 300, 70
        self.start_button = Button(
            text="Manual",
            rect=pygame.Rect(cx - bw // 2, 290, bw, bh),
            base_color=(24, 128, 49),
            hover_color=(38, 156, 62),
            text_color=(255, 250, 210),
        )
        self.solver_button = Button(
            text="AI Solver",
            rect=pygame.Rect(cx - bw // 2, 380, bw, bh),
            base_color=(25, 86, 130),
            hover_color=(34, 109, 162),
            text_color=(245, 248, 214),
        )
        self.howto_button = Button(
            text="How To Play",
            rect=pygame.Rect(cx - bw // 2, 470, bw, bh),
            base_color=(132, 95, 20),
            hover_color=(160, 115, 25),
            text_color=(255, 247, 214),
        )
        self.exit_button = Button(
            text="Exit",
            rect=pygame.Rect(cx - bw // 2, 560, bw, bh),
            base_color=(130, 42, 38),
            hover_color=(162, 56, 52),
            text_color=(255, 244, 210),
        )

        self.back_button = Button(
            text="Back",
            rect=pygame.Rect(28, self.screen.get_height() - 78, 150, 48),
            base_color=(22, 96, 120),
            hover_color=(29, 118, 148),
            text_color=(245, 250, 215),
        )

        self.base_start_y = 290
        self.base_solver_y = 380
        self.base_howto_y = 470
        self.base_exit_y = 560

        self.manual_dropdown_open = False
        self.manual_dropdown_progress = 0.0
        self.solver_dropdown_open = False
        self.solver_dropdown_progress = 0.0
        self.dropdown_anim_speed = 0.18

        self.manual_option_buttons = [
            Button(
                text="Easy",
                rect=pygame.Rect(self.start_button.rect.left, self.start_button.rect.bottom + 6, bw, 50),
                base_color=(28, 120, 64),
                hover_color=(39, 145, 78),
                text_color=(251, 250, 219),
            ),
            Button(
                text="Hard",
                rect=pygame.Rect(self.start_button.rect.left, self.start_button.rect.bottom + 64, bw, 50),
                base_color=(134, 60, 30),
                hover_color=(164, 75, 38),
                text_color=(255, 244, 210),
            ),
        ]
        self.manual_dropdown_max_h = len(self.manual_option_buttons) * 50 + (len(self.manual_option_buttons) - 1) * 8

        self.solver_option_buttons = [
            Button(
                text="UCS",
                rect=pygame.Rect(
                    self.solver_button.rect.left,
                    self.solver_button.rect.bottom + 6,
                    self.solver_button.rect.width,
                    54,
                ),
                base_color=(34, 121, 73),
                hover_color=(45, 147, 88),
                text_color=(251, 250, 219),
            ),
            Button(
                text="A*",
                rect=pygame.Rect(
                    self.solver_button.rect.left,
                    self.solver_button.rect.bottom + 68,
                    self.solver_button.rect.width,
                    54,
                ),
                base_color=(46, 98, 162),
                hover_color=(61, 119, 191),
                text_color=(248, 250, 221),
            ),
        ]
        self.solver_dropdown_max_h = (
            len(self.solver_option_buttons) * 54 + (len(self.solver_option_buttons) - 1) * 8
        )

        self.easy_page_size = 6
        self.easy_list_rects = [
            pygame.Rect(0, 0, 0, 0)
            for _ in range(self.easy_page_size)
        ]
        self.easy_visible_indices: list[int] = []
        self.easy_page_start = 0

        self.easy_prev_button = Button(
            text="Prev",
            rect=pygame.Rect(0, 0, 140, 46),
            base_color=(28, 114, 74),
            hover_color=(39, 140, 90),
            text_color=(251, 248, 218),
        )
        self.easy_next_button = Button(
            text="Next",
            rect=pygame.Rect(0, 0, 140, 46),
            base_color=(28, 114, 74),
            hover_color=(39, 140, 90),
            text_color=(251, 248, 218),
        )
        self.easy_start_button = Button(
            text="Start Deal",
            rect=pygame.Rect(0, 0, 200, 52),
            base_color=(24, 128, 49),
            hover_color=(38, 156, 62),
            text_color=(255, 250, 210),
        )

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
        panel = pygame.Rect(w // 2 - 360, 130, 720, 520)

        if total_games > 0:
            selected_index = max(0, min(selected_index, total_games - 1))
            self.easy_page_start = (selected_index // self.easy_page_size) * self.easy_page_size
        else:
            self.easy_page_start = 0

        list_x = panel.x + 38
        list_y = panel.y + 120
        list_w = panel.width - 76
        row_h = 48
        gap = 10

        self.easy_visible_indices.clear()
        for row_idx in range(self.easy_page_size):
            row_rect = pygame.Rect(list_x, list_y + row_idx * (row_h + gap), list_w, row_h)
            self.easy_list_rects[row_idx] = row_rect

            absolute_idx = self.easy_page_start + row_idx
            if absolute_idx < total_games:
                self.easy_visible_indices.append(absolute_idx)

        self.easy_prev_button.rect.topleft = (panel.x + 38, panel.bottom - 72)
        self.easy_next_button.rect.topright = (panel.right - 38, panel.bottom - 72)
        self.easy_start_button.rect.midbottom = (w // 2, h - 24)

        self.back_button.rect.topleft = (32, h - 76)
        return panel

    def _easy_deal_label(self, file_path: str, index: int) -> str:
        stem = os.path.splitext(os.path.basename(file_path))[0]
        matched = re.search(r"(\d+)", stem)
        if matched:
            return f"Deal {int(matched.group(1)):02d}"
        return f"Deal {index + 1:02d}"

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
        self.howto_button.rect.y = self.base_howto_y + manual_push + solver_push
        self.exit_button.rect.y = self.base_exit_y + manual_push + solver_push

        for idx, button in enumerate(self.manual_option_buttons):
            button.rect.x = self.start_button.rect.x
            button.rect.width = self.start_button.rect.width
            button.rect.y = self.start_button.rect.bottom + 6 + idx * (button.rect.height + 8)

        for idx, button in enumerate(self.solver_option_buttons):
            button.rect.x = self.solver_button.rect.x
            button.rect.width = self.solver_button.rect.width
            button.rect.y = self.solver_button.rect.bottom + 6 + idx * (button.rect.height + 8)

    def draw_menu(self) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()
        for y in range(h):
            shade = 70 + int(36 * (y / h))
            pygame.draw.line(self.screen, (5, shade, 24), (0, y), (w, y))

        title = self.title_font.render("FREECELL", True, (250, 236, 150))
        sub = self.hint_font.render("Choose manual difficulty or watch AI solver replay", True, (245, 235, 185))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 180))
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, 255))

        mp = pygame.mouse.get_pos()
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

        self.solver_button.draw(self.screen, self.menu_font, mp)

        if self.solver_dropdown_progress > 0:
            current_h = max(1, int(self.solver_dropdown_max_h * self.solver_dropdown_progress))
            visible_rect = pygame.Rect(
                self.solver_option_buttons[0].rect.x,
                self.solver_option_buttons[0].rect.y,
                self.solver_option_buttons[0].rect.width,
                current_h,
            )
            drop_bg = visible_rect.inflate(10, 10)
            pygame.draw.rect(self.screen, (17, 64, 38), drop_bg, border_radius=12)
            pygame.draw.rect(self.screen, (248, 238, 170), drop_bg, width=2, border_radius=12)
            clip_before = self.screen.get_clip()
            self.screen.set_clip(visible_rect)
            for button in self.solver_option_buttons:
                button.draw(self.screen, self.hint_font, mp)
            self.screen.set_clip(clip_before)

        self.howto_button.draw(self.screen, self.menu_font, mp)
        self.exit_button.draw(self.screen, self.menu_font, mp)

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
        self.back_button.draw(self.screen, self.hint_font, pygame.mouse.get_pos())

    def draw_easy_selector(self, easy_games: list[str], selected_index: int) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()
        for y in range(h):
            shade = 22 + int(40 * (y / h))
            pygame.draw.line(self.screen, (4, 62 + shade, 31), (0, y), (w, y))

        panel = self._layout_easy_selector(len(easy_games), selected_index)
        pygame.draw.rect(self.screen, (13, 75, 43), panel, border_radius=16)
        pygame.draw.rect(self.screen, (249, 238, 170), panel, width=2, border_radius=16)

        title = self.title_font.render("MANUAL EASY DEALS", True, (250, 236, 150))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, panel.y + 20))

        total = len(easy_games)
        page = (self.easy_page_start // self.easy_page_size) + 1 if total else 0
        max_page = ((total - 1) // self.easy_page_size + 1) if total else 0
        summary = self.hint_font.render(
            f"Choose one available deal ({total} total)   Page {page}/{max_page}",
            True,
            (247, 240, 201),
        )
        self.screen.blit(summary, (w // 2 - summary.get_width() // 2, panel.y + 82))

        mp = pygame.mouse.get_pos()
        if not self.easy_visible_indices:
            empty = self.menu_font.render("No Easy deals found.", True, (248, 240, 202))
            self.screen.blit(empty, (w // 2 - empty.get_width() // 2, panel.centery - empty.get_height() // 2))
        else:
            for row, absolute_idx in enumerate(self.easy_visible_indices):
                row_rect = self.easy_list_rects[row]
                is_hover = row_rect.collidepoint(mp)
                is_selected = absolute_idx == selected_index

                if is_selected:
                    fill = (38, 140, 86)
                    border = (252, 242, 173)
                elif is_hover:
                    fill = (24, 110, 66)
                    border = (228, 234, 188)
                else:
                    fill = (18, 92, 54)
                    border = (177, 191, 159)

                pygame.draw.rect(self.screen, fill, row_rect, border_radius=10)
                pygame.draw.rect(self.screen, border, row_rect, width=2, border_radius=10)

                label_text = self._easy_deal_label(easy_games[absolute_idx], absolute_idx)
                label = self.menu_font.render(label_text, True, (252, 248, 218))
                self.screen.blit(label, (row_rect.x + 16, row_rect.centery - label.get_height() // 2))

        can_prev = self.easy_page_start > 0
        can_next = self.easy_page_start + self.easy_page_size < len(easy_games)
        has_selection = bool(easy_games)

        self._draw_button_state(self.easy_prev_button, self.hint_font, mp, can_prev)
        self._draw_button_state(self.easy_next_button, self.hint_font, mp, can_next)
        self._draw_button_state(self.easy_start_button, self.hint_font, mp, has_selection)
        self.back_button.draw(self.screen, self.hint_font, mp)

    def handle_menu_event(
        self,
        event: pygame.event.Event,
        on_start_game: Callable[[str], None],
        on_start_solver: Callable[[str], None],
        on_howto: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        if self.start_button.rect.collidepoint(event.pos):
            self.manual_dropdown_open = not self.manual_dropdown_open
            self.solver_dropdown_open = False
            return

        if self.solver_button.rect.collidepoint(event.pos):
            self.solver_dropdown_open = not self.solver_dropdown_open
            self.manual_dropdown_open = False
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
            selected_solver = None
            for button in self.solver_option_buttons:
                if button.rect.collidepoint(event.pos):
                    selected_solver = "a_star" if button.text == "A*" else button.text.lower()
                    break

            if selected_solver is not None:
                self.solver_dropdown_open = False
                on_start_solver(selected_solver)
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
