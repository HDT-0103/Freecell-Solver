from __future__ import annotations

import math
import os

import pygame

from gui.interface import Button

# ── Colour palette ─────────────────────────────────────────────────────────────
GOLD        = (212, 175,  55)
GOLD_LIGHT  = (255, 223, 100)
GOLD_BRIGHT = (255, 245, 160)
EMERALD     = (  4,  98,  56)
EMERALD_HOV = (  6, 130,  74)
WHITE       = (255, 255, 255)
RED_CARD    = (190,  25,  25)
BLACK_CARD  = ( 18,  18,  18)
GRAY_BORDER = (180, 180, 180)

TOTAL_PAGES = 5   # pages 0 – 4

# Bottom area reserved for buttons + page indicator (px)
BOTTOM_RESERVED = 90


class HowToScreen:
    """5-page How To Play screen with Prev / Next / Back navigation."""

    def __init__(
        self,
        screen:     pygame.Surface,
        title_font: pygame.font.Font,
        body_font:  pygame.font.Font,
        hint_font:  pygame.font.Font,
        bg_image:   pygame.Surface = None,
    ) -> None:
        self.screen     = screen
        self.title_font = title_font
        self.body_font  = body_font
        self.hint_font  = hint_font
        self.bg_image   = bg_image
        self.page       = 0
        self._shimmer   = 0.0   # 0..1 phase for gold shimmer on page 0
        self._build_buttons()

    # ── public ─────────────────────────────────────────────────────────────────

    def rebuild_for_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self._build_buttons()

    # ── button layout ───────────────────────────────────────────────────────────

    def _build_buttons(self) -> None:
        w, h   = self.screen.get_width(), self.screen.get_height()
        bw, bh = 150, 48
        # buttons sit BOTTOM_RESERVED px from the bottom, page indicator below them
        by = h - BOTTOM_RESERVED + 4

        kw = {"base_color": EMERALD, "hover_color": EMERALD_HOV, "text_color": GOLD}

        self.btn_back = Button(text="Back",
                               rect=pygame.Rect(24, by, bw, bh), **kw)
        self.btn_prev = Button(text="Prev",
                               rect=pygame.Rect(w // 2 - bw - 8, by, bw, bh), **kw)
        self.btn_next = Button(text="Next",
                               rect=pygame.Rect(w // 2 + 8, by, bw, bh), **kw)

    # ── content area (excludes bottom reserved zone) ────────────────────────────

    def _content_h(self) -> int:
        """Usable height for page content (excludes title and bottom area)."""
        return self.screen.get_height() - BOTTOM_RESERVED

    # ── internal draw helpers ───────────────────────────────────────────────────

    def _draw_bg(self) -> None:
        w, h = self.screen.get_width(), self.screen.get_height()
        if self.bg_image:
            bg = pygame.transform.scale(self.bg_image, (w, h))
            self.screen.blit(bg, (0, 0))
            # FIX 1: no dark overlay — show background as-is
        else:
            self.screen.fill((10, 60, 35))

    def _draw_btn(self, btn: Button, visible: bool = True) -> None:
        if not visible:
            return
        mp = pygame.mouse.get_pos()
        btn.draw(self.screen, self.hint_font, mp)
        pygame.draw.rect(self.screen, GOLD, btn.rect, width=2, border_radius=10)

    def _draw_back_door_btn(self, btn: Button, visible: bool = True) -> None:
        """Nút back: nền đỏ nhung, viền gold, icon người đi ra cửa."""
        if not visible:
            return
        VELVET_RED = (140,  25,  25)
        VELVET_HOV = (175,  40,  40)
        mp = pygame.mouse.get_pos()
        is_hover = btn.rect.collidepoint(mp)
        fill = VELVET_HOV if is_hover else VELVET_RED
        pygame.draw.rect(self.screen, fill, btn.rect, border_radius=10)
        pygame.draw.rect(self.screen, GOLD, btn.rect, width=2, border_radius=10)

        lbl  = self.hint_font.render("Back", True, GOLD)
        shad = self.hint_font.render("Back", True, (0, 0, 0))
        lx = btn.rect.centerx - lbl.get_width() // 2
        ly = btn.rect.centery - lbl.get_height() // 2
        self.screen.blit(shad, (lx + 1, ly + 1))
        self.screen.blit(lbl,  (lx,     ly))

    def _title(self, text: str, y: int = 14) -> int:
        """Draw page title; return y just below it."""
        w    = self.screen.get_width()
        font = self.title_font
        surf = font.render(text, True, GOLD)
        if surf.get_width() > w - 24:
            font = pygame.font.SysFont("georgia", 34, bold=True)
            surf = font.render(text, True, GOLD)
        shad = font.render(text, True, (40, 20, 0))
        x = w // 2 - surf.get_width() // 2
        self.screen.blit(shad, (x + 2, y + 2))
        self.screen.blit(surf,  (x,     y))
        return y + surf.get_height() + 8

    def _text(self, text: str, y: int, color=WHITE, center: bool = True,
              font: pygame.font.Font = None) -> int:
        """Render one line; return y for the next line."""
        f = font or self.body_font
        s = f.render(text, True, color)
        w = self.screen.get_width()
        x = w // 2 - s.get_width() // 2 if center else 30
        self.screen.blit(s, (x, y))
        return y + s.get_height() + 8

    def _text_wrapped(self, text: str, y: int, color=WHITE,
                      font: pygame.font.Font = None,
                      max_width: int = None) -> int:
        """Render text, auto-wrapping if wider than max_width. Returns next y."""
        f   = font or self.body_font
        w   = self.screen.get_width()
        mw  = (max_width or w) - 40   # 20px padding each side

        # try single line first
        surf = f.render(text, True, color)
        if surf.get_width() <= mw:
            x = w // 2 - surf.get_width() // 2
            self.screen.blit(surf, (x, y))
            return y + surf.get_height() + 8

        # wrap by words
        words = text.split()
        lines, cur = [], ""
        for word in words:
            test = (cur + " " + word).strip()
            if f.render(test, True, color).get_width() <= mw:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = word
        if cur:
            lines.append(cur)

        for line in lines:
            s = f.render(line, True, color)
            x = w // 2 - s.get_width() // 2
            self.screen.blit(s, (x, y))
            y += s.get_height() + 6
        return y + 4

    def _info_overlay(self, y_start: int, y_end: int,
                      alpha: int = 130, padding: int = 10) -> None:
        """Draw a semi-transparent dark strip ONLY behind the text info area,
        leaving the title and illustration untouched."""
        w = self.screen.get_width()
        rect_y = max(0, y_start - padding)
        rect_h = (y_end + padding) - rect_y
        surf = pygame.Surface((w, rect_h), pygame.SRCALPHA)
        surf.fill((0, 0, 0, alpha))
        self.screen.blit(surf, (0, rect_y))

    def _card(self, x: int, y: int, cw: int, ch: int,
              rank: str, suit: str, red: bool) -> None:
        pygame.draw.rect(self.screen, WHITE,       (x, y, cw, ch), border_radius=6)
        pygame.draw.rect(self.screen, GRAY_BORDER, (x, y, cw, ch), width=2, border_radius=6)
        color = RED_CARD if red else BLACK_CARD
        rf = pygame.font.SysFont("georgia", 16, bold=True)
        rs = rf.render(rank, True, color)
        self.screen.blit(rs, (x + 5, y + 4))
        self._suit_symbol(x + cw // 2, y + ch // 2, 18, suit, color)

    def _suit_symbol(self, cx, cy, r, suit, color) -> None:
        if suit == "H":
            self._draw_heart(cx, cy, r, color)
        elif suit == "D":
            pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            pygame.draw.polygon(self.screen, color, pts)
        elif suit == "S":
            self._draw_spade(cx, cy, r, color)
        else:
            self._draw_club(cx, cy, r, color)

    def _draw_heart(self, cx, cy, r, color) -> None:
        pygame.draw.circle(self.screen, color, (cx - r // 2, cy - r // 3), r // 2)
        pygame.draw.circle(self.screen, color, (cx + r // 2, cy - r // 3), r // 2)
        pts = [(cx - r, cy - r // 4), (cx, cy + r), (cx + r, cy - r // 4)]
        pygame.draw.polygon(self.screen, color, pts)

    def _draw_spade(self, cx, cy, r, color) -> None:
        pygame.draw.circle(self.screen, color, (cx - r // 2, cy + r // 3), r // 2)
        pygame.draw.circle(self.screen, color, (cx + r // 2, cy + r // 3), r // 2)
        pts = [(cx - r, cy + r // 4), (cx, cy - r), (cx + r, cy + r // 4)]
        pygame.draw.polygon(self.screen, color, pts)
        pygame.draw.rect(self.screen, color, (cx - r // 4, cy + r // 2, r // 2, r // 2))

    def _draw_club(self, cx, cy, r, color) -> None:
        for dx, dy in [(-r // 2, r // 3), (r // 2, r // 3), (0, -r // 2)]:
            pygame.draw.circle(self.screen, color, (cx + dx, cy + dy), r // 2)
        pygame.draw.rect(self.screen, color, (cx - r // 4, cy + r // 2, r // 2, r // 2))

    def _empty_cell(self, x, y, w, h, border_color) -> None:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((255, 255, 255, 30))
        self.screen.blit(surf, (x, y))
        pygame.draw.rect(self.screen, border_color, (x, y, w, h), width=2, border_radius=8)

    def _arrow(self, start, end, color=GOLD, width=3) -> None:
        pygame.draw.line(self.screen, color, start, end, width)
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        for da in (0.4, -0.4):
            ex = end[0] - 16 * math.cos(angle - da)
            ey = end[1] - 16 * math.sin(angle - da)
            pygame.draw.line(self.screen, color, end, (int(ex), int(ey)), width)

    # ── FIX 2: shimmering gold title for page 0 ────────────────────────────────

    def _shimmer_title(self, text: str) -> None:
        """Render 'HOW TO PLAY' centred vertically with a gold shimmer effect."""
        w, h = self.screen.get_width(), self.screen.get_height()

        # advance shimmer phase
        self._shimmer = (self._shimmer + 0.018) % 1.0
        t = self._shimmer

        # three layers: dark shadow, base gold, bright highlight strip
        layers = [
            ((50, 25, 0),    (2,  2)),   # shadow
            (GOLD,           (0,  0)),   # base
        ]

        # interpolate a bright sweep colour across the text
        bright_alpha = int(180 * abs(math.sin(t * math.pi)))
        bright_col   = (
            min(255, GOLD[0] + 43),
            min(255, GOLD[1] + 70),
            min(255, GOLD[2] + 105),
        )

        font = self.title_font
        base_surf = font.render(text, True, GOLD)
        tw = base_surf.get_width()
        ty = h // 2 - base_surf.get_height() // 2

        for color, (ox, oy) in layers:
            s = font.render(text, True, color)
            self.screen.blit(s, (w // 2 - tw // 2 + ox, ty + oy))

        # bright shimmer strip overlay
        hi_surf = font.render(text, True, bright_col)
        hi_surf.set_alpha(bright_alpha)
        self.screen.blit(hi_surf, (w // 2 - tw // 2, ty))

    # ── page renderers ─────────────────────────────────────────────────────────

    def _page0(self) -> None:
        """FIX 2: Title only, centred, with shimmer."""
        self._shimmer_title("HOW TO PLAY")

    def _page1(self) -> None:
        """Board layout — proportional spacing."""
        w, h  = self.screen.get_width(), self.screen.get_height()
        ch_   = self._content_h()

        title_bot = self._title("The Board Layout")

        BLUE_C   = ( 40, 100, 220)   # deep blue for Free Cells (was red)
        YELLOW_C = (218, 180,   0)
        GREEN_C  = ( 30, 160,  80)

        # Row 1: Free Cells + Foundations — pushed down more
        cw, ch = 68, 90
        gap     = 8
        row1_y  = title_bot + int(ch_ * 0.14)   # was 0.04 → pushed down

        fc_total = 4 * cw + 3 * gap
        fc_x0    = w // 4 - fc_total // 2
        for i in range(4):
            self._empty_cell(fc_x0 + i * (cw + gap), row1_y, cw, ch, BLUE_C)
        lfc = self.hint_font.render("Free Cells (4)", True, BLUE_C)
        self.screen.blit(lfc, (fc_x0, row1_y + ch + 4))

        fd_x0 = w * 3 // 4 - fc_total // 2
        for i, (suit, red) in enumerate([("S", False), ("H", True), ("C", False), ("D", True)]):
            x = fd_x0 + i * (cw + gap)
            self._empty_cell(x, row1_y, cw, ch, YELLOW_C)
            self._suit_symbol(x + cw // 2, row1_y + ch // 2, 15, suit, YELLOW_C)
        lfd = self.hint_font.render("Foundations (4)", True, YELLOW_C)
        self.screen.blit(lfd, (fd_x0, row1_y + ch + 4))

        # Row 2: Tableau
        tab_y   = row1_y + ch + int(ch_ * 0.09)
        tcw     = max(38, (w - 60) // 9)
        tab_tot = 8 * tcw + 7 * 8
        tab_x0  = w // 2 - tab_tot // 2
        for i in range(8):
            self._empty_cell(tab_x0 + i * (tcw + 8), tab_y, tcw, ch + 10, GREEN_C)
        ltab = self.hint_font.render("Tableau  -  8 columns (52 cards dealt here)", True, GREEN_C)
        self.screen.blit(ltab, (w // 2 - ltab.get_width() // 2, tab_y + ch + 16))

        # Notes — no overlay, just text
        notes = [
            ("Free Cells",  "Temp storage  -  park a card to unblock others", BLUE_C),
            ("Foundations", "Goal piles  -  build A to K by suit",            YELLOW_C),
            ("Tableau",     "8 columns  -  main play area",                   GREEN_C),
        ]
        ny = tab_y + ch + int(ch_ * 0.13)
        for name, desc, c in notes:
            s = self.hint_font.render(f"  {name}:  {desc}", True, c)
            self.screen.blit(s, (w // 2 - s.get_width() // 2, ny))
            ny += 28

    def _page2(self) -> None:
        """Movement rules."""
        w, h  = self.screen.get_width(), self.screen.get_height()
        ch_   = self._content_h()

        title_bot = self._title("Movement Rules")
        card_y    = title_bot + int(ch_ * 0.05)

        cw, ch = 88, 122

        # 10 of Spades (black)
        self._card(w // 2 - cw // 2 - 30, card_y, cw, ch, "10", "S", red=False)
        # 9 of Hearts (red) on top
        self._card(w // 2 - cw // 2 + 30, card_y + 30, cw, ch, "9", "H", red=True)

        # Green tick
        tx, ty = w // 2 + cw + 24, card_y + 16
        pygame.draw.line(self.screen, (50, 210, 70), (tx,      ty + 28), (tx + 16, ty + 50), 7)
        pygame.draw.line(self.screen, (50, 210, 70), (tx + 16, ty + 50), (tx + 44, ty),       7)

        y = card_y + ch + int(ch_ * 0.1)
        rules = [
            ("1.  The card ON TOP must be a DIFFERENT colour.", WHITE),
            ("2.  The card ON TOP must be ONE rank LOWER.",     WHITE),
            ("",                                                 WHITE),
            ("e.g.   9-Hearts (Red)  on  10-Spades (Black)  +", GOLD_LIGHT),
            ("       9-Spades (Black) on  10-Hearts (Red)   +",  GOLD_LIGHT),
        ]
        for line, color in rules:
            if not line:
                y += 8
                continue
            y = self._text_wrapped(line, y, color)

    def _page3(self) -> None:
        """Free Cell strategy."""
        w, h  = self.screen.get_width(), self.screen.get_height()
        ch_   = self._content_h()

        title_bot = self._title("Free Cell Strategy")
        start_y   = title_bot + int(ch_ * 0.04)

        cw, ch = 76, 105
        pile_x = w // 4 - cw // 2

        # Messy pile
        for i, (rank, suit, red) in enumerate([("K","S",False), ("5","D",True), ("J","C",False)]):
            self._card(pile_x, start_y + i * 24, cw, ch, rank, suit, red)

        # Empty Free Cell — cyan/teal instead of red (avoids blending with background)
        fc_x = w * 2 // 3
        fc_y = start_y + 16
        FC_COLOR = (0, 200, 210)
        self._empty_cell(fc_x, fc_y, cw, ch, FC_COLOR)
        lfc = self.hint_font.render("Free Cell", True, FC_COLOR)
        self.screen.blit(lfc, (fc_x + cw // 2 - lfc.get_width() // 2, fc_y + ch + 4))

        # Arrow
        self._arrow(
            (pile_x + cw,  start_y + 48 + 24),
            (fc_x,         fc_y + ch // 2),
        )

        # Freed card
        freed_y = start_y + 48 + ch
        self._card(pile_x, freed_y, cw, ch, "5", "D", red=True)
        lf = self.hint_font.render("Now free to move!", True, (80, 220, 120))
        self.screen.blit(lf, (pile_x, freed_y + ch + 4))

        # Tips — no overlay
        tips = [
            "Park a blocking card in a Free Cell to unblock others.",
            "Retrieve it later when needed.",
            "Warning: only 4 slots  -  use them wisely!",
        ]
        ty = freed_y + ch + int(ch_ * 0.1)
        for tip in tips:
            ty = self._text_wrapped(tip, ty, GOLD_LIGHT)

    def _page4(self) -> None:
        """Goal and winning."""
        w, h  = self.screen.get_width(), self.screen.get_height()
        ch_   = self._content_h()

        title_bot = self._title("The Goal  -  Win!")
        card_y    = title_bot + int(ch_ * 0.04)

        cw, ch = 90, 125
        cx     = w // 2 - 50

        # Foundation cell with Ace inside
        self._empty_cell(cx - cw // 2, card_y, cw, ch, (218, 180, 0))
        self._card(cx - cw // 2 + 4, card_y + 4, cw - 8, ch - 8, "A", "H", red=True)

        # 2 of Hearts flying in
        c2x = cx + cw + 50
        c2y = card_y - 20
        self._card(c2x, c2y, cw, ch, "2", "H", red=True)
        self._arrow((c2x, c2y + ch // 2), (cx + cw // 2, card_y + ch // 2))

        y = card_y + ch + int(ch_ * 0.08)
        goals = [
            "A  2  3  4  5  6  7  8  9  10  J  Q  K",
            "",
            "Build all 4 suits (Spades, Hearts, Clubs, Diamonds) Ace to King.",
            "Fill all 4 Foundations  -  YOU WIN!",
        ]
        for g in goals:
            if not g:
                y += 8
                continue
            color = GOLD_LIGHT if g.startswith("A  2") else WHITE
            y = self._text_wrapped(g, y, color)

    # ── main draw & event ──────────────────────────────────────────────────────

    def draw(self) -> None:
        self._draw_bg()

        {0: self._page0, 1: self._page1, 2: self._page2,
         3: self._page3, 4: self._page4}[self.page]()

        w, h = self.screen.get_width(), self.screen.get_height()

        # FIX 3: page indicator sits below the buttons, well above screen edge
        pf = self.hint_font.render(f"{self.page + 1} / {TOTAL_PAGES}", True, GOLD)
        self.screen.blit(pf, (w // 2 - pf.get_width() // 2,
                               h - BOTTOM_RESERVED + 58))

        is_first = self.page == 0
        is_last  = self.page == TOTAL_PAGES - 1

        self._draw_btn(self.btn_next, visible=not is_last)
        self._draw_btn(self.btn_prev, visible=not is_first)
        self._draw_back_door_btn(self.btn_back, visible=not is_first)

    def handle_event(self, event: pygame.event.Event, on_back) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_b):
                self.page = 0
                on_back()
            elif event.key == pygame.K_RIGHT and self.page < TOTAL_PAGES - 1:
                self.page += 1
            elif event.key == pygame.K_LEFT and self.page > 0:
                self.page -= 1

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if self.btn_next.rect.collidepoint(pos) and self.page < TOTAL_PAGES - 1:
                self.page += 1
            elif self.btn_prev.rect.collidepoint(pos) and self.page > 0:
                self.page -= 1
            elif self.btn_back.rect.collidepoint(pos) and self.page > 0:
                self.page = 0
                on_back()