"""
main.py
-------
Diem vao duy nhat cua game FreeCell.
Chi giu vong lap chinh va chuyen tiep su kien — moi logic o Source/.
"""
from __future__ import annotations

import os
import sys

# Them Source/ vao sys.path de co the import: core.* va gui.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "Source"))

import pygame

from core.state import GameState
from gui.interface import BoardRenderer, Button, CardImageLoader


# Duong dan den thu muc chua anh la bai (chinh lai neu can)
CARD_IMAGE_DIR = (
    r"C:\Users\LENOVO\Downloads\2025-26\HỌC KÌ 2"
    r"\CƠ SỞ TRÍ TUỆ NHÂN TẠO\Project1"
    r"\Freecell-Solver\Source\assets\images\cards"
)


class FreeCellApp:
    """Lop ung dung chinh: khoi tao pygame, quan ly scene va vong lap."""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("FreeCell - Manual Play")
        self.screen  = pygame.display.set_mode((1366, 768))
        self.clock   = pygame.time.Clock()
        self.running = True
        self.scene   = "menu"   # "menu" hoac "game"

        # Font
        self.title_font = pygame.font.SysFont("georgia", 64, bold=True)
        self.menu_font  = pygame.font.SysFont("georgia", 36, bold=True)
        self.hint_font  = pygame.font.SysFont("georgia", 24, bold=True)

        # Nut menu
        cx, bw, bh = self.screen.get_rect().centerx, 270, 74
        self.start_button = Button(
            text="Start Game",
            rect=pygame.Rect(cx - bw // 2, 350, bw, bh),
            base_color=(24, 128, 49), hover_color=(38, 156, 62),
            text_color=(255, 250, 210),
        )
        self.exit_button = Button(
            text="Exit",
            rect=pygame.Rect(cx - bw // 2, 350 + 96, bw, bh),
            base_color=(130, 42, 38), hover_color=(162, 56, 52),
            text_color=(255, 244, 210),
        )

        # Khoi tao state va renderer
        loader          = CardImageLoader(base_dir=CARD_IMAGE_DIR, card_size=(110, 154))
        self.game_state = GameState()
        self.board      = BoardRenderer(self.screen.get_rect(), loader, self.game_state)

    # ------------------------------------------------------------------
    # Vong lap chinh
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            self._handle_events()
            self._draw()
            pygame.display.flip()
            self.clock.tick(60)
        pygame.quit()
        sys.exit(0)

    # ------------------------------------------------------------------
    # Xu ly su kien
    # ------------------------------------------------------------------

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if self.scene == "menu":
                self._on_menu_event(event)
            else:
                self._on_game_event(event)

    def _on_menu_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.start_button.rect.collidepoint(event.pos):
                self.game_state.reset()
                self.board.on_reset()
                self.scene = "game"
            elif self.exit_button.rect.collidepoint(event.pos):
                self.running = False

    def _on_game_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.scene = "menu"
            elif event.key == pygame.K_r:
                self.game_state.reset()
                self.board.on_reset()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.board.on_mouse_down(event.pos)

        if event.type == pygame.MOUSEMOTION:
            self.board.on_mouse_motion(event.pos)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.board.on_mouse_up(event.pos)

    # ------------------------------------------------------------------
    # Ve
    # ------------------------------------------------------------------

    def _draw(self) -> None:
        if self.scene == "menu":
            self._draw_menu()
        else:
            self.board.draw(self.screen)
            self._draw_game_hud()

    def _draw_menu(self) -> None:
        h, w = self.screen.get_height(), self.screen.get_width()
        for y in range(h):
            shade = 70 + int(36 * (y / h))
            pygame.draw.line(self.screen, (5, shade, 24), (0, y), (w, y))

        title = self.title_font.render("FREECELL",        True, (250, 236, 150))
        sub   = self.hint_font.render("Manual Play Mode", True, (245, 235, 185))
        self.screen.blit(title, (w // 2 - title.get_width() // 2, 180))
        self.screen.blit(sub,   (w // 2 - sub.get_width()   // 2, 255))

        mp = pygame.mouse.get_pos()
        self.start_button.draw(self.screen, self.menu_font, mp)
        self.exit_button.draw(self.screen,  self.menu_font, mp)

    def _draw_game_hud(self) -> None:
        # Goi y phim tat (goc duoi trai)
        hint = self.hint_font.render("ESC: Menu   |   R: New Shuffle", True, (255, 250, 205))
        self.screen.blit(hint, (18, self.screen.get_height() - hint.get_height() - 14))

        # Man hinh thang
        if self.game_state.is_won():
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 95))
            self.screen.blit(overlay, (0, 0))
            win = self.title_font.render("YOU WIN!", True, (255, 245, 160))
            cx  = self.screen.get_rect().centerx
            cy  = self.screen.get_rect().centery
            self.screen.blit(win, (cx - win.get_width() // 2, cy - win.get_height() // 2))


if __name__ == "__main__":
    FreeCellApp().run()
