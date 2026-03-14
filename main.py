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

        # Nut Undo trong scene game
        self.undo_button = Button(
            text="Undo",
            rect=pygame.Rect(self.screen.get_width() // 2 - 70, self.screen.get_height() - 60, 140, 42),
            base_color=(27, 104, 132), hover_color=(38, 126, 160),
            text_color=(245, 250, 215),
        )

        # Khoi tao state va renderer
        loader          = CardImageLoader(base_dir=CARD_IMAGE_DIR, card_size=(110, 154))
        self.game_state = GameState()
        self.board      = BoardRenderer(self.screen.get_rect(), loader, self.game_state)
        self.is_stuck = False

    # ------------------------------------------------------------------
    # Vong lap chinh
    # ------------------------------------------------------------------

    def run(self) -> None:
        while self.running:
            self._handle_events()
            # Cap nhat flag khi ket sau moi frame
            if self.scene == "game":
                self._refresh_game_flags()
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
                self._refresh_game_flags()
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
                self._refresh_game_flags()
            elif event.key == pygame.K_u:
                self._undo_action()

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.undo_button.rect.collidepoint(event.pos):
                self._undo_action()
                return
            if not self.is_stuck:
                self.game_state._push_history()
                self.board.on_mouse_down(event.pos)

        if event.type == pygame.MOUSEMOTION:
            self.board.on_mouse_motion(event.pos)

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if not self.is_stuck:
                moved = self.board.on_mouse_up(event.pos)
                if moved:
                    self._refresh_game_flags()

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
        hint = self.hint_font.render("ESC: Menu   |   R: New Shuffle   |   U: Undo", True, (255, 250, 205))
        self.screen.blit(hint, (18, self.screen.get_height() - hint.get_height() - 14))

        # Nut Undo (scene game)
        self.undo_button.draw(self.screen, self.hint_font, pygame.mouse.get_pos())

        # Man hinh thang
        if self.game_state.is_won():
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 95))
            self.screen.blit(overlay, (0, 0))
            win = self.title_font.render("YOU WIN!", True, (255, 245, 160))
            cx  = self.screen.get_rect().centerx
            cy  = self.screen.get_rect().centery
            self.screen.blit(win, (cx - win.get_width() // 2, cy - win.get_height() // 2))
        elif self.is_stuck:
            # Bao thua khi bi ket va khong con nuoc di
            overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 95))
            self.screen.blit(overlay, (0, 0))
            lose = self.title_font.render("NO MOVES LEFT", True, (255, 210, 150))
            tip = self.hint_font.render("Ban da bi ket. Nhan Undo hoac R de choi lai.", True, (255, 240, 200))
            cx = self.screen.get_rect().centerx
            cy = self.screen.get_rect().centery
            self.screen.blit(lose, (cx - lose.get_width() // 2, cy - lose.get_height() // 2 - 20))
            self.screen.blit(tip, (cx - tip.get_width() // 2, cy + 30))

    def _undo_action(self) -> None:
        """Thuc hien undo 1 nuoc, neu co lich su."""
        if self.game_state.undo():
            self.board.sync_positions()
            self._refresh_game_flags()

    def _refresh_game_flags(self) -> None:
        """Cap nhat trang thai ket/thang sau moi lan state thay doi."""
        self.is_stuck = (not self.game_state.is_won()) and (not self.game_state.has_any_legal_move())


if __name__ == "__main__":
    FreeCellApp().run()
