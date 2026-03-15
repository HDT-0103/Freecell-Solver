from __future__ import annotations

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
            text="Start Game",
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

        self.dropdown_open = False
        self.dropdown_progress = 0.0
        self.dropdown_max_h = 54
        self.dropdown_anim_speed = 0.18
        self.ucs_option_button = Button(
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
        )

    def update_dropdown_animation(self) -> None:
        target = 1.0 if self.dropdown_open else 0.0
        if self.dropdown_progress < target:
            self.dropdown_progress = min(target, self.dropdown_progress + self.dropdown_anim_speed)
        elif self.dropdown_progress > target:
            self.dropdown_progress = max(target, self.dropdown_progress - self.dropdown_anim_speed)

        push_down = int((self.dropdown_max_h + 14) * self.dropdown_progress)
        self.howto_button.rect.y = 470 + push_down
        self.exit_button.rect.y = 560 + push_down

        self.ucs_option_button.rect.x = self.solver_button.rect.x
        self.ucs_option_button.rect.width = self.solver_button.rect.width
        self.ucs_option_button.rect.y = self.solver_button.rect.bottom + 6

    def draw_menu(self) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()
        for y in range(h):
            shade = 70 + int(36 * (y / h))
            pygame.draw.line(self.screen, (5, shade, 24), (0, y), (w, y))

        title = self.title_font.render("FREECELL", True, (250, 236, 150))
        sub = self.hint_font.render("Play manually or watch AI solver replay", True, (245, 235, 185))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 180))
        self.screen.blit(sub, (w // 2 - sub.get_width() // 2, 255))

        mp = pygame.mouse.get_pos()
        self.start_button.draw(self.screen, self.menu_font, mp)
        self.solver_button.draw(self.screen, self.menu_font, mp)

        if self.dropdown_progress > 0:
            current_h = max(1, int(self.dropdown_max_h * self.dropdown_progress))
            visible_rect = pygame.Rect(
                self.ucs_option_button.rect.x,
                self.ucs_option_button.rect.y,
                self.ucs_option_button.rect.width,
                current_h,
            )
            drop_bg = visible_rect.inflate(10, 10)
            pygame.draw.rect(self.screen, (17, 64, 38), drop_bg, border_radius=12)
            pygame.draw.rect(self.screen, (248, 238, 170), drop_bg, width=2, border_radius=12)
            clip_before = self.screen.get_clip()
            self.screen.set_clip(visible_rect)
            self.ucs_option_button.draw(self.screen, self.hint_font, mp)
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

    def handle_menu_event(
        self,
        event: pygame.event.Event,
        on_start_game: Callable[[], None],
        on_start_solver: Callable[[], None],
        on_howto: Callable[[], None],
        on_exit: Callable[[], None],
    ) -> None:
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return

        if self.start_button.rect.collidepoint(event.pos):
            on_start_game()
            self.dropdown_open = False
        elif self.solver_button.rect.collidepoint(event.pos):
            self.dropdown_open = not self.dropdown_open
        elif self.dropdown_progress >= 0.95 and self.ucs_option_button.rect.collidepoint(event.pos):
            self.dropdown_open = False
            on_start_solver()
        elif self.howto_button.rect.collidepoint(event.pos):
            self.dropdown_open = False
            on_howto()
        elif self.exit_button.rect.collidepoint(event.pos):
            on_exit()
        else:
            self.dropdown_open = False

    def handle_howto_event(self, event: pygame.event.Event, on_back: Callable[[], None]) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_b):
            on_back()
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_button.rect.collidepoint(event.pos):
                on_back()
