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
        self.page0_bg = None 
        
        # 2. Định nghĩa đường dẫn và nạp ảnh
        # Giả sử ảnh nằm cùng cấp với background.jpg (thư mục cha của thư mục Source)
        p0_path = os.path.join(os.path.dirname(__file__), "..", "..", "howto_p0_bg.jpg")
        
        if os.path.exists(p0_path):
            try:
                self.page0_bg = pygame.image.load(p0_path).convert()
                # Bạn có thể scale luôn ở đây để đảm bảo nó khớp với màn hình
                self.page0_bg = pygame.transform.scale(self.page0_bg, self.screen.get_size())
            except Exception as e:
                print(f"Error loading page 0 background: {e}")
        # ------------------------------

        self._build_buttons()

    # ── public ─────────────────────────────────────────────────────────────────

    def rebuild_for_screen(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self._build_buttons()

    # ── button layout ───────────────────────────────────────────────────────────

    def _build_buttons(self) -> None:
        w, h   = self.screen.get_width(), self.screen.get_height()
        pr = self._paper_rect()
        bw, bh = 150, 48
        # buttons sit BOTTOM_RESERVED px from the bottom, page indicator below them
        by = h - BOTTOM_RESERVED + 4

        btn_y = pr.bottom - bh - 30 
        
        self.btn_prev = Button(text="Prev", 
                               rect=pygame.Rect(pr.x + 20, btn_y, bw, bh),
                               base_color=EMERALD, hover_color=EMERALD_HOV, text_color=GOLD)
        
        self.btn_next = Button(text="Next", 
                               rect=pygame.Rect(pr.right - bw - 20, btn_y, bw, bh),
                               base_color=EMERALD, hover_color=EMERALD_HOV, text_color=GOLD)

        # Nút Back hình tròn nên ta định nghĩa rect vuông ở giữa dưới
        self.btn_back = Button(text="", 
                               rect=pygame.Rect(w // 2 - 40, h - 90, 80, 80),
                               base_color=EMERALD, hover_color=EMERALD_HOV, text_color=GOLD)

    # ── paper rect (tờ giấy trong background) ─────────────────────────────────

    def _paper_rect(self) -> pygame.Rect:
        """Trả về vùng tờ giấy tính theo tỉ lệ màn hình."""
        w, h = self.screen.get_width(), self.screen.get_height()
        x  = int(w * 0.11)
        y  = int(h * 0.15)
        pw = int(w * 0.78)
        ph = int(h * 0.64)
        return pygame.Rect(x, y, pw, ph)

    # ── content area (excludes bottom reserved zone) ────────────────────────────

    def _content_h(self) -> int:
        """Usable height for page content (excludes title and bottom area)."""
        return self._paper_rect().bottom - BOTTOM_RESERVED

    # ── internal draw helpers ───────────────────────────────────────────────────

    def _draw_bg(self) -> None:
            w, h = self.screen.get_width(), self.screen.get_height()
        
            if self.page == 0 and self.page0_bg:
                bg = pygame.transform.scale(self.page0_bg, (w, h))
                self.screen.blit(bg, (0, 0))
        
            elif self.bg_image:
                bg = pygame.transform.scale(self.bg_image, (w, h))
                self.screen.blit(bg, (0, 0))
            
            else:
                self.screen.fill((10, 60, 35))

    def _draw_btn(self, btn: Button, visible: bool = True) -> None:
        if not visible:
            return
        mp = pygame.mouse.get_pos()
        btn.draw(self.screen, self.hint_font, mp)
        pygame.draw.rect(self.screen, GOLD, btn.rect, width=2, border_radius=10)

    def _draw_back_btn(self, btn: Button, visible: bool = True) -> None:
            if not visible: return
            mp = pygame.mouse.get_pos()
            is_hover = btn.rect.collidepoint(mp)
            center = btn.rect.center
            radius = btn.rect.width // 2

            # 1. Vẽ nền tròn đỏ đô
            color = (180, 0, 40) if is_hover else (144, 0, 32)
            pygame.draw.circle(self.screen, color, center, radius)
            # 2. Vẽ viền vàng
            pygame.draw.circle(self.screen, GOLD, center, radius, width=4)

            pygame.draw.circle(self.screen, GOLD, center, radius, width=3)

            # 3. Vẽ icon ngôi nhà màu Gold (CHỈNH SỬA: NGẮN HƠN)
            # 3.1 Vẽ Mái nhà (Hạ thấp đỉnh mái xuống 2px)
            # Cũ: Đỉnh mái center[1]-10 -> NHÔ CAO QUÁ (kệch cỡm)
            # Mới: Đỉnh mái center[1]-8  -> NGẮN HƠN, bớt awkward
            pygame.draw.polygon(self.screen, GOLD, [
                (center[0], center[1] - 8),       # Đỉnh mái lowered (less nhọn)
                (center[0] - 16, center[1] + 2),  # Chân trái rộng hơn
                (center[0] + 16, center[1] + 2)   # Chân phải rộng hơn
            ])
        
            # 3.2 Vẽ Thân nhà (Thấp hơn: cao 9px thay vì 11px)
            # Rect = (center[0]-12, center[1]+2, 24, 9)
            # Thấp hơn: cao 9px, không còn cảm giác bị "vươn" lên.
            pygame.draw.rect(self.screen, GOLD, (center[0] - 12, center[1] + 2, 24, 9))

            # 3.3 Vẽ cửa sổ nhỏ (O-ho)
            pygame.draw.rect(self.screen, color, (center[0] - 4, center[1] + 4, 8, 7))

    def _title(self, text: str, y: int = None) -> int:
        """Draw page title inside paper; return y just below it."""
        pr   = self._paper_rect()
        w    = self.screen.get_width()
        y    = y if y is not None else pr.y + 14
        font = self.title_font
        surf = font.render(text, True, GOLD)
        if surf.get_width() > pr.width - 24:
            font = pygame.font.SysFont("georgia", 34, bold=True)
            surf = font.render(text, True, GOLD)
        shad = font.render(text, True, (40, 20, 0))
        x = pr.centerx - surf.get_width() // 2
        self.screen.blit(shad, (x + 2, y + 2))
        self.screen.blit(surf,  (x,     y))
        return y + surf.get_height() + 8

    def _text(self, text: str, y: int, color=WHITE, center: bool = True,
              font: pygame.font.Font = None) -> int:
        """Render one line inside paper; return y for the next line."""
        f  = font or self.body_font
        pr = self._paper_rect()
        s  = f.render(text, True, color)
        x  = pr.centerx - s.get_width() // 2 if center else pr.x + 16
        self.screen.blit(s, (x, y))
        return y + s.get_height() + 8

    def _text_wrapped(self, text: str, y: int, color=WHITE,
                      font: pygame.font.Font = None,
                      max_width: int = None) -> int:
        """Render text wrapped inside paper. Returns next y."""
        f  = font or self.body_font
        pr = self._paper_rect()
        mw = max_width or (pr.width - 32)

        surf = f.render(text, True, color)
        if surf.get_width() <= mw:
            x = pr.centerx - surf.get_width() // 2
            self.screen.blit(surf, (x, y))
            return y + surf.get_height() + 8

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
            x = pr.centerx - s.get_width() // 2
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
        """Render 'HOW TO PLAY' centred within paper with a gold shimmer effect."""
        pr = self._paper_rect()
        self._shimmer = (self._shimmer + 0.018) % 1.0
        t = self._shimmer
        bright_alpha = int(180 * abs(math.sin(t * math.pi)))
        bright_col   = (
            min(255, GOLD[0] + 43),
            min(255, GOLD[1] + 70),
            min(255, GOLD[2] + 105),
        )
        font = self.title_font
        font = pygame.font.SysFont("georgia", 34, bold=True)
        base_surf = font.render(text, True, GOLD)
        tw = base_surf.get_width() - 10
        ty = pr.centery - base_surf.get_height() // 2 + 190
        tx = pr.centerx - tw // 2

        layers = [((50, 25, 0), (2, 2)), (GOLD, (0, 0))]
        for color, (ox, oy) in layers:
            s = font.render(text, True, color)
            self.screen.blit(s, (tx + ox, ty + oy))

        hi_surf = font.render(text, True, bright_col)
        hi_surf.set_alpha(bright_alpha)
        self.screen.blit(hi_surf, (tx, ty))

    # ── page renderers ─────────────────────────────────────────────────────────

    def _page0(self) -> None:
            if self.page0_bg:
                bg = pygame.transform.scale(self.page0_bg, self.screen.get_size())
                self.screen.blit(bg, (0, 0))
            self._shimmer_title("INSTRUCTION")

    def _get_title_rect(self) -> pygame.Rect:
            pr = self._paper_rect()
       
            width, height = 300, 60
        
            return pygame.Rect(
                pr.centerx - width // 2, 
                pr.centery - height // 2 + 180, 
                width, 
                height
            )

    def _page1(self) -> None:
        """Board layout — inside paper."""
        pr = self._paper_rect()
        w  = self.screen.get_width()

        title_bot = self._title("The Board Layout")

        BLUE_C   = ( 40, 100, 220)
        YELLOW_C = (218, 180,   0)
        GREEN_C  = ( 30, 160,  80)

        cw, ch = 62, 82
        gap    = 6
        row1_y = title_bot + 12

        # Free Cells — left half of paper
        fc_total = 4 * cw + 3 * gap
        fc_x0    = pr.x + pr.width // 4 - fc_total // 2
        for i in range(4):
            self._empty_cell(fc_x0 + i * (cw + gap), row1_y, cw, ch, BLUE_C)
        lfc = self.hint_font.render("Free Cells (4)", True, BLUE_C)
        self.screen.blit(lfc, (fc_x0, row1_y + ch + 4))

        # Foundations — right half of paper
        fd_x0 = pr.x + pr.width * 3 // 4 - fc_total // 2
        for i, (suit, red) in enumerate([("S", False), ("H", True), ("C", False), ("D", True)]):
            x = fd_x0 + i * (cw + gap)
            self._empty_cell(x, row1_y, cw, ch, YELLOW_C)
            self._suit_symbol(x + cw // 2, row1_y + ch // 2, 14, suit, YELLOW_C)
        lfd = self.hint_font.render("Foundations (4)", True, YELLOW_C)
        self.screen.blit(lfd, (fd_x0, row1_y + ch + 4))

        # Tableau
        tab_y  = row1_y + ch + 44
        tcw    = max(36, (pr.width - 40) // 9)
        tab_tot = 8 * tcw + 7 * 6
        tab_x0 = pr.centerx - tab_tot // 2
        for i in range(8):
            self._empty_cell(tab_x0 + i * (tcw + 6), tab_y, tcw, ch, GREEN_C)
        ltab = self.hint_font.render("Tableau  -  8 columns (52 cards dealt here)", True, GREEN_C)
        self.screen.blit(ltab, (pr.centerx - ltab.get_width() // 2, tab_y + ch + 6))

        # Notes
        notes = [
            ("Free Cells",  "Temp storage - park a card", BLUE_C),
            ("Foundations", "Goal piles - build A to K by suit",            YELLOW_C),
            ("Tableau",     "8 columns - main play area",                   GREEN_C),
        ]
        ny = tab_y + ch + 80
        for name, desc, c in notes:
            s = self.hint_font.render(f"  {name}:  {desc}", True, c)
            self.screen.blit(s, (pr.centerx - s.get_width() // 2, ny))
            ny += 28

    def _page2(self) -> None:
        pr = self._paper_rect()

        title_bot = self._title("Movement Rules")
        card_y    = title_bot + 50        

        cw, ch = 88, 122

        self._card(pr.centerx - cw + 10, card_y, cw, ch, "10", "S", red=False)
        self._card(pr.centerx - cw + 50, card_y + 30, cw, ch, "9", "H", red=True)

        y = card_y + ch + 50            

        rules = [
            ("1.  The card ON TOP must be a DIFFERENT colour.", (20, 20, 20)),
            ("2.  The card ON TOP must be ONE rank LOWER.",     (20, 20, 20)),
            ("",                                                 WHITE),
            ("e.g.   9-Hearts (Red)  on  10-Spades (Black)  +", (180, 60, 60)),  
            ("       9-Spades (Black) on  10-Hearts (Red)   +",  (180, 60, 60)),
        ]
        for line, color in rules:
            if not line:
                y += 8
                continue
            y = self._text_wrapped(line, y, color, font=self.body_font)

    def _page3(self) -> None:
        """Free Cell strategy — inside paper."""
        pr = self._paper_rect()

        title_bot = self._title("Free Cell Strategy")
        start_y   = title_bot + 18

        cw, ch = 76, 105
        pile_x = pr.x + pr.width // 4 - cw // 2

        for i, (rank, suit, red) in enumerate([("K","S",False), ("5","D",True), ("J","C",False)]):
            self._card(pile_x, start_y + i * 24, cw, ch, rank, suit, red)

        fc_x = pr.x + pr.width * 2 // 3
        fc_y = start_y + 10
        self._empty_cell(fc_x, fc_y, cw, ch, ( 40, 100, 220))
        lfc = self.hint_font.render("Free Cell", True, ( 40, 100, 220))
        self.screen.blit(lfc, (fc_x + cw // 2 - lfc.get_width() // 2, fc_y + ch + 4))

        self._arrow(
            (pile_x + cw,  start_y + 48 + 24),
            (fc_x,         fc_y + ch // 2),
        )

        freed_y = start_y + 48 + ch
        self._card(pile_x, freed_y, cw, ch, "5", "D", red=True)
        lf = self.hint_font.render("Now free to move!", True, (80, 220, 120))
        self.screen.blit(lf, (pile_x, freed_y + ch + 4))

        tips = [
            "Park a blocking card in a Free Cell to unblock others.",
            "Retrieve it later when needed.",
            "Warning: only 4 slots  -  use them wisely!",
        ]
        ty = freed_y + ch + 30
        for tip in tips:
            ty = self._text_wrapped(tip, ty, (20, 20, 20))

    def _page4(self) -> None:
        """Goal and winning — inside paper."""
        pr = self._paper_rect()

        title_bot = self._title("The Goal  -  Win!")
        card_y    = title_bot + 30

        cw, ch = 90, 125
        cx     = pr.centerx - 20

        self._empty_cell(cx - cw // 2, card_y, cw, ch, (218, 180, 0))
        self._card(cx - cw // 2 + 4, card_y + 4, cw - 8, ch - 8, "A", "H", red=True)

        c2x = cx + cw + 30
        c2y = card_y - 10
        self._card(c2x, c2y, cw, ch, "2", "H", red=True)
        self._arrow((c2x, c2y + ch // 2), (cx + cw // 2, card_y + ch // 2))

        y = card_y + ch + 30
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
            color = (144, 0, 32) if g.startswith("A  2") else (30, 30, 30)
            y = self._text_wrapped(g, y, color)

    # ── main draw & event ──────────────────────────────────────────────────────

    def draw(self) -> None:
            # 1. Vẽ hình nền (Tự động chọn nền Page 0 hoặc nền chung)
            self._draw_bg()

            # 2. Vẽ nội dung trang hiện tại
            pages = {
                0: self._page0, 1: self._page1, 2: self._page2,
                3: self._page3, 4: self._page4
            }
            pages[self.page]()

            # Các biến kiểm soát trạng thái trang
            is_p0 = (self.page == 0)
            is_last = (self.page == TOTAL_PAGES - 1)
            w, h = self.screen.get_width(), self.screen.get_height()

            # 3. Vẽ Page Indicator (Chỉ hiện từ trang 1 trở đi để trang 0 sạch đẹp)
            if not is_p0:
                pf = self.hint_font.render(f"{self.page} / {TOTAL_PAGES - 1}", True, GOLD)
                # Đặt số trang nằm ngay trên nút Back một chút
                self.screen.blit(pf, (w // 2 - pf.get_width() // 2, h - BOTTOM_RESERVED - 10))

            # 4. Điều khiển hiển thị các nút điều hướng
            # Trang 0: Không hiện nút nào (người dùng click vào tiêu đề để bắt đầu)
            # Trang 1-4: Hiện Prev, Next (nếu không phải trang cuối), và nút Home
            if not is_p0:
                # Vẽ nút Next (ẩn ở trang cuối cùng)
                self._draw_btn(self.btn_next, visible=not is_last)
            
                # Vẽ nút Prev (luôn hiện từ trang 1)
                self._draw_btn(self.btn_prev, visible=True)
            
                # Vẽ nút Back hình tròn (ngôi nhà) ở giữa dưới
                self._draw_back_btn(self.btn_back, visible=True)

    def handle_event(self, event, on_back) -> None:
            # 1. XỬ LÝ PHÍM ESC (Bổ sung mới)
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.page = 0  # Reset về trang đầu để lần sau mở lại đúng trang bìa
                    on_back()      # Quay về Menu
                    return

            # 2. XỬ LÝ CHUỘT (Giữ nguyên hoặc chỉnh sửa logic cũ)
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.page == 0:
                    # Nhấn vào chữ Instruction để vào trang 1
                    if self._get_title_rect().collidepoint(event.pos):
                        self.page = 1 
                    return 

                # Các nút điều hướng ở trang 1-4
                if self.btn_next.rect.collidepoint(event.pos) and self.page < TOTAL_PAGES - 1:
                    self.page += 1
                elif self.btn_prev.rect.collidepoint(event.pos) and self.page > 0:
                    self.page -= 1
                elif self.btn_back.rect.collidepoint(event.pos):
                    self.page = 0
                    on_back()