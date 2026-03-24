"""
interface.py
------------
Toan bo phan UI cua FreeCell dung Pygame:
  - CardImageLoader : nap va cache anh la bai
    - CardWidget      : sprite pygame bao boc Card
  - Button          : nut bam menu
  - BoardRenderer   : quan ly hien thi ban bai va keo-tha
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence, Tuple, TYPE_CHECKING

import pygame

from core import rules
from core.state import Card, State

SourceRef = tuple[str, int, int]
TargetRef = tuple[str, int]


@dataclass(frozen=True)
class DragInfo:
    cards: list[Card]
    source: SourceRef

if TYPE_CHECKING:
    from core import FreeCellGame


# ---------------------------------------------------------------------------
# Nap va cache anh la bai
# ---------------------------------------------------------------------------

def default_image_name(rank: int, suit: str) -> str:
    """Tra ve ten file anh mac dinh: rank_of_suit.png.
    Thay ham nay neu bo anh cua ban co ten file khac.
    """
    rank_map = {1: "ace", 11: "jack", 12: "queen", 13: "king"}
    return f"{rank_map.get(rank, str(rank))}_of_{suit}.png"


class CardImageLoader:
    """Nap anh tu dia va cache lai, tranh I/O lap lai moi frame."""

    def __init__(
        self,
        base_dir: str,
        naming_fn: Optional[Callable[[int, str], str]] = None,
        card_size: Optional[Tuple[int, int]] = None,
    ) -> None:
        self.base_dir  = base_dir
        self.naming_fn = naming_fn or default_image_name
        self.card_size = card_size
        self._playable_cards = set()
        self._cache: Dict[Tuple[int, str], pygame.Surface] = {}

    def build_card_path(self, rank: int, suit: str) -> str:
        """Tra ve duong dan day du den file anh. Ghi de ham nay neu can."""
        return os.path.join(self.base_dir, self.naming_fn(rank, suit))

    def _build_legacy_card_path(self, rank: int, suit: str) -> str:
        """Ho tro bo ten file cu theo dinh dang rank_of_suit.png."""
        rank_map = {1: "ace", 11: "jack", 12: "queen", 13: "king"}
        return os.path.join(self.base_dir, f"{rank_map.get(rank, str(rank))}_of_{suit}.png")

    def get_image(self, rank: int, suit: str) -> pygame.Surface:
        key = (rank, suit)
        if key in self._cache:
            return self._cache[key]

        path = self.build_card_path(rank, suit)
        if os.path.exists(path):
            img = pygame.image.load(path).convert_alpha()
            if self.card_size:
                img = pygame.transform.smoothscale(img, self.card_size)
        else:
            legacy_path = self._build_legacy_card_path(rank, suit)
            if os.path.exists(legacy_path):
                img = pygame.image.load(legacy_path).convert_alpha()
                if self.card_size:
                    img = pygame.transform.smoothscale(img, self.card_size)
            else:
                img = self._make_fallback(rank, suit)

        self._cache[key] = img
        return img

    def _make_fallback(self, rank: int, suit: str) -> pygame.Surface:
        """Ve la bai don gian bang hinh chu nhat khi khong co file anh."""
        size  = self.card_size or (100, 145)
        surf  = pygame.Surface(size, pygame.SRCALPHA)
        rect  = surf.get_rect()
        pygame.draw.rect(surf, (255, 255, 255), rect, border_radius=8)
        pygame.draw.rect(surf, (30, 30, 30),    rect, width=2, border_radius=8)
        rank_txt = {1: "A", 11: "J", 12: "Q", 13: "K"}.get(rank, str(rank))
        color    = (200, 0, 0) if suit in ("hearts", "diamonds") else (15, 15, 15)
        font     = pygame.font.SysFont("arial", 22, bold=True)
        surf.blit(font.render(f"{rank_txt} {suit[0].upper()}", True, color), (8, 8))
        return surf


# ---------------------------------------------------------------------------
# Widget la bai (Sprite pygame wrapping Card)
# ---------------------------------------------------------------------------

class CardWidget(pygame.sprite.Sprite):
    """Hien thi mot la bai: luu image va rect, tham chieu nguoc lai Card."""

    def __init__(self, data: Card, loader: CardImageLoader) -> None:
        super().__init__()
        self.data  = data
        self.image = loader.get_image(data.rank, _suit_short_to_long(data.suit))
        self.rect  = self.image.get_rect()

    def move_to(self, x: int, y: int) -> None:
        self.rect.topleft = (x, y)


# ---------------------------------------------------------------------------
# Nut bam cho menu
# ---------------------------------------------------------------------------

@dataclass
class Button:
    text:        str
    rect:        pygame.Rect
    base_color:  Tuple[int, int, int]
    hover_color: Tuple[int, int, int]
    text_color:  Tuple[int, int, int]

    def draw(
        self,
        surface:   pygame.Surface,
        font:      pygame.font.Font,
        mouse_pos: Tuple[int, int],
    ) -> None:
        color = self.hover_color if self.rect.collidepoint(mouse_pos) else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        pygame.draw.rect(surface, (240, 230, 150), self.rect, width=2, border_radius=12)
        label = font.render(self.text, True, self.text_color)
        surface.blit(
            label,
            (self.rect.centerx - label.get_width()  // 2,
             self.rect.centery - label.get_height() // 2),
        )


# ---------------------------------------------------------------------------
# Renderer ban bai (quan ly layout, widget, keo-tha, ve)
# ---------------------------------------------------------------------------

class BoardRenderer:
    """Phu trach moi thu lien quan den hien thi ban FreeCell.

    Tham chieu den core State de doc trang thai; khong tu thay doi luat.
    Quan ly toan bo vong doi CardWidget (tao moi sau moi reset).
    Xu ly keo-tha hoan toan ben trong (drag state noi bo).
    """

    BG_COLOR    = (7,  109, 27)
    SLOT_COLOR  = (230, 210, 90)
    SLOT_BORDER = (250, 240, 130)
    LABEL_COLOR = (255, 244, 170)

    def __init__(
        self,
        screen_rect:  pygame.Rect,
        image_loader: CardImageLoader,
        game_state:   State,
        game: Optional[FreeCellGame] = None,
        view_model: Optional[Dict] = None,
        board_bg: Optional[pygame.Surface] = None,
    ) -> None:
        self.screen_rect = screen_rect
        self.loader      = image_loader
        self.state       = game_state
        self.game        = game
        self.view_model  = view_model or {}
        self.board_bg    = board_bg

        # Lay kich thuoc la bai tu anh mau
        sample            = image_loader.get_image(1, "spades")
        self.card_w, self.card_h = sample.get_size()

        # Thong so layout
        self.margin_x      = 26
        self.top_y         = 95
        self.cascades_y    = self.top_y + self.card_h + 72
        self.card_overlap_y = max(26, self.card_h // 4)
        self.slot_gap       = max(
            14,
            (screen_rect.width - 2 * self.margin_x - 8 * self.card_w) // 7,
        )

        self.font_label = pygame.font.SysFont("georgia", 24, bold=True)
        self.font_info  = pygame.font.SysFont("georgia", 22, bold=True)

        self.free_cell_rects:  List[pygame.Rect] = []
        self.foundation_rects: List[pygame.Rect] = []
        self.cascade_rects:    List[pygame.Rect] = []
        self._build_layout()

        # Surface tinh (nen + khung o) — chi ve lai khi resize
        self._static_surface = pygame.Surface(screen_rect.size)
        self._rebuild_static_surface()

        # Map Card -> CardWidget, duoc tao lai sau moi reset()
        self._widgets: Dict[Card, CardWidget] = {}

        # Drag state noi bo
        self._drag_info:    Optional[DragInfo]        = None
        self._drag_widgets: List[CardWidget]           = []
        self._drag_offset:  Tuple[int, int]            = (0, 0)
        self._drag_anchor:  Optional[Tuple[int, int]]  = None
        self._highlighted_card: Optional[tuple[int, str]] = None
        self._hovered_card: Optional[Card] = None
        self.is_dealing = False
        self.deal_speed = 0.15 # Tốc độ bay (0.1 đến 0.3 là đẹp)
        self.animation_queue = [] # Danh sách các lá bài đang bay

    # ------------------------------------------------------------------
    # Xay dung layout va surface tinh
    # ------------------------------------------------------------------

    def _build_layout(self) -> None:
        self.free_cell_rects.clear()
        self.foundation_rects.clear()
        self.cascade_rects.clear()

        for i in range(4):
            x = self.margin_x + i * (self.card_w + self.slot_gap)
            self.free_cell_rects.append(
                pygame.Rect(x, self.top_y, self.card_w, self.card_h)
            )

        fc_start = self.margin_x + 4 * (self.card_w + self.slot_gap)
        for i in range(4):
            x = fc_start + i * (self.card_w + self.slot_gap)
            self.foundation_rects.append(
                pygame.Rect(x, self.top_y, self.card_w, self.card_h)
            )

        casc_h = self.screen_rect.height - self.cascades_y - 45
        for i in range(8):
            if i < 4:
                # 4 cột đầu lấy tọa độ X của Free Cells
                x = self.free_cell_rects[i].x
            else:
                # 4 cột sau lấy tọa độ X của Foundation
                x = self.foundation_rects[i-4].x
            
            self.cascade_rects.append(
                pygame.Rect(x, self.cascades_y, self.card_w, 500)
            )

    def set_board_bg(self, bg: Optional[pygame.Surface]) -> None:
        """Đổi ảnh nền board và rebuild static surface."""
        self.board_bg = bg
        self._rebuild_static_surface()

    def _rebuild_static_surface(self) -> None:
        """Ve nen + khung cac o bai len surface tinh."""
        EMERALD = (4, 98, 56)
        GOLD    = (212, 175, 55)

        if self.board_bg is not None:
            bg = pygame.transform.scale(self.board_bg, self.screen_rect.size)
            self._static_surface.blit(bg, (0, 0))
        else:
            self._static_surface.fill(self.BG_COLOR)
            for y in range(0, self.screen_rect.height, 6):
                shade = 100 + (y % 18)
                pygame.draw.line(
                    self._static_surface, (5, shade, 22),
                    (0, y), (self.screen_rect.width, y),
                )
        self._draw_slot_group(self.free_cell_rects,  "Free Cells", color=EMERALD)
        self._draw_slot_group(self.foundation_rects, "Foundation", color=GOLD)
        self._draw_slot_group(self.cascade_rects,    "Tableau")

        if self.free_cell_rects and self.foundation_rects:
            # 1. Tính toán vị trí chính giữa khoảng hở (Center Gap)
            mid_x = (self.free_cell_rects[-1].right + self.foundation_rects[0].left) // 2
            
            # 2. Xác định chiều cao của vách ngăn (nên cao hơn ô bài một chút)
            divider_top = self.top_y - 15
            divider_bottom = self.top_y + self.card_h + 15
            
            # 3. Vẽ bóng đổ nhẹ cho vách ngăn (tạo chiều sâu 3D)
            pygame.draw.line(self._static_surface, (14, 20, 28, 100), 
                             (mid_x + 2, divider_top + 2), (mid_x + 2, divider_bottom + 2), 3)
            
            # 4. Vẽ thanh ngăn chính màu Vàng Gold
            # (212, 175, 55) là màu GOLD bạn đã dùng cho Foundation
            pygame.draw.line(self._static_surface, (212, 175, 55), 
                             (mid_x, divider_top), (mid_x, divider_bottom), 2)
            
            # 5. Thêm hai điểm nhấn (Ornament) ở đầu vách ngăn cho sang trọng
            pygame.draw.circle(self._static_surface, (212, 175, 55), (mid_x, divider_top), 4)
            pygame.draw.circle(self._static_surface, (212, 175, 55), (mid_x, divider_bottom), 4)

    def _draw_slot_group(
        self, rects: Sequence[pygame.Rect], title: str, color: Optional[tuple] = None
    ) -> None:
        draw_color = color if color is not None else self.SLOT_COLOR
        for rect in rects:
            pygame.draw.rect(
                self._static_surface, draw_color,
                rect, width=2, border_radius=8,
            )
            pygame.draw.rect(
                self._static_surface, self.SLOT_BORDER,
                rect.inflate(-6, -6), width=1, border_radius=7,
            )
        label   = self.font_label.render(title, True, self.LABEL_COLOR)
        title_x = (rects[0].left + rects[-1].right - label.get_width()) // 2
        title_y = rects[0].top - label.get_height() - 8
        self._static_surface.blit(label, (title_x, title_y))

    # ------------------------------------------------------------------
    # Quan ly vong doi CardWidget
    # ------------------------------------------------------------------

    def on_reset(self) -> None:
        """Goi ngay sau khi thay state de tao lai toan bo CardWidget."""
        self._widgets.clear()
        self._drag_info    = None
        self._drag_widgets = []
        self._drag_anchor  = None
        self.apply_state(self.state)

    def _ensure_widget(self, data: Card) -> CardWidget:
        if data not in self._widgets:
            self._widgets[data] = CardWidget(data, self.loader)
        return self._widgets[data]

    def sync_positions(self) -> None:
        """Cap nhat toa do (rect.topleft) cua moi widget theo trang thai."""
        for i, card_data in enumerate(self.state.free_cells):
            if card_data:
                self._widgets[card_data].move_to(
                    self.free_cell_rects[i].x,
                    self.free_cell_rects[i].y,
                )

        for suit_idx, suit in enumerate(("C", "D", "H", "S")):
            top_rank = self.state.foundations[suit]
            if top_rank > 0:
                top_card = Card(rank=top_rank, suit=suit)
                self._ensure_widget(top_card).move_to(
                    self.foundation_rects[suit_idx].x,
                    self.foundation_rects[suit_idx].y,
                )

        for i, cascade in enumerate(self.state.cascades):
            bx = self.cascade_rects[i].x
            by = self.cascade_rects[i].y
            for depth, card_data in enumerate(cascade):
                self._widgets[card_data].move_to(
                    bx, by + depth * self.card_overlap_y
                )

    def apply_state(self, state: State) -> None:
        """Apply a full State snapshot to renderer and sync card positions."""
        self.state = state.clone()

        for card_data in self.state.free_cells:
            if card_data:
                self._ensure_widget(card_data)
        for suit in ("C", "D", "H", "S"):
            for rank in range(1, self.state.foundations[suit] + 1):
                self._ensure_widget(Card(rank=rank, suit=suit))
        for cascade in self.state.cascades:
            for card_data in cascade:
                self._ensure_widget(card_data)

        self.sync_positions()

    def get_widget(self, card: Card) -> Optional[CardWidget]:
        return self._widgets.get(card)

    def set_highlighted_card(self, card) -> None:
        self._highlighted_card = _normalize_card_identity(card)

    def update_state(self, state: State) -> None:
        """Update the internal state to a new State."""
        self.apply_state(state)

    def get_card_positions(self, state: State) -> Dict[Card, Tuple[int, int]]:
        """Return pixel positions for every card in a given snapshot state."""
        result: Dict[Card, Tuple[int, int]] = {}

        for i, card_data in enumerate(state.free_cells):
            if card_data:
                rect = self.free_cell_rects[i]
                result[card_data] = (rect.x, rect.y)

        for suit_idx, suit in enumerate(("C", "D", "H", "S")):
            rect = self.foundation_rects[suit_idx]
            for rank in range(1, state.foundations[suit] + 1):
                result[Card(rank=rank, suit=suit)] = (rect.x, rect.y)

        for i, cascade in enumerate(state.cascades):
            bx, by = self.cascade_rects[i].x, self.cascade_rects[i].y
            for depth, card_data in enumerate(cascade):
                result[card_data] = (bx, by + depth * self.card_overlap_y)

        return result

    def draw_board(self, surface: pygame.Surface, state: State) -> None:
        """Render a provided State snapshot on screen."""
        self.apply_state(state)
        self.draw(surface)

    # ------------------------------------------------------------------
    # Xu ly su kien chuot (goi tu main.py)
    # ------------------------------------------------------------------

    def on_mouse_down(self, pos: Tuple[int, int]) -> bool:
        """Bat dau keo bai tai vi tri pos. Tra ve True neu bat duoc bai."""
        if self._drag_info is not None:
            return False

        # Kiem tra o Free Cell
        for idx in range(4):
            card_data = self.state.free_cells[idx]
            if card_data:
                w = self._widgets[card_data]
                if w.rect.collidepoint(pos):
                    drag = self._pick_cards(("freecell", idx, 0))
                    if drag:
                        self._start_drag(drag, w, pos)
                        return True

        # Kiem tra Cascade (tu la cuoi len dau de lay la tren cung truoc)
        for col_idx, cascade in enumerate(self.state.cascades):
            for start in range(len(cascade) - 1, -1, -1):
                w = self._widgets[cascade[start]]
                if w.rect.collidepoint(pos):
                    drag = self._pick_cards(("cascade", col_idx, start))
                    if drag:
                        self._start_drag(drag, w, pos)
                        return True
                    # La nay khong the keo -> dung tim tiep
                    return False

        return False

    def _start_drag(
        self,
        drag:         DragInfo,
        first_widget: CardWidget,
        mouse_pos:    Tuple[int, int],
    ) -> None:
        self._drag_info    = drag
        self._drag_widgets = [self._widgets[c] for c in drag.cards]
        self._drag_offset  = (
            mouse_pos[0] - first_widget.rect.x,
            mouse_pos[1] - first_widget.rect.y,
        )
        self._drag_anchor  = (first_widget.rect.x, first_widget.rect.y)

    def on_mouse_motion(self, pos: Tuple[int, int]) -> None:
        """Cập nhật vị trí kéo bài và xác định lá bài đang hover."""
        self._hovered_card = None 
        
        if self._drag_info:
            self._drag_anchor = (pos[0] - self._drag_offset[0], pos[1] - self._drag_offset[1])
        else:
            for card, widget in self._widgets.items():
                if widget.rect.collidepoint(pos):
                    self._hovered_card = card

        self._playable_cards = set() 
        if self.game and not self._drag_info:
            moves = rules.enumerate_legal_moves(self.state)
            for m in moves:
                card = self._get_card_at_source(m.src_type, m.src_index)
                if card: self._playable_cards.add(card)

    def on_mouse_up(self, pos: Tuple[int, int]) -> bool:
        """Tha bai: kiem tra vi tri drop hop le, neu khong thi huy keo.

        Tra ve True neu vua thuc hien 1 nuoc di hop le.
        """
        if not self._drag_info:
            return False

        target  = self.find_drop_target(pos)
        success = False

        if target and self.game:
            # Translate GUI location names to core move names before submitting.
            src_type, src_idx, src_start = self._drag_info.source
            dst_type, dst_idx = target
            src_type_core = "free_cell" if src_type == "freecell" else src_type
            dst_type_core = "free_cell" if dst_type == "freecell" else dst_type
            if dst_type == "foundation":
                dst_idx_core = ["C", "D", "H", "S"][dst_idx]
            else:
                dst_idx_core = dst_idx

            count = len(self._drag_info.cards)
            if src_type == "freecell":
                count = 1

            result = self.game.try_move(src_type_core, src_idx, dst_type_core, dst_idx_core, count=count)
            success = result.ok

            if success:
                # Update renderer state from authoritative core state.
                self.state = result.state.clone()
        
        if not success and self._drag_info:
            self._cancel_drag(self._drag_info)

        self.sync_positions()
        self._drag_info    = None
        self._drag_widgets = []
        self._drag_anchor  = None
        return success

    def find_drop_target(self, pos: Tuple[int, int]) -> Optional[TargetRef]:
        """Xac dinh vung bai nao (neu co) chua con tro chuot."""
        for idx, rect in enumerate(self.free_cell_rects):
            if rect.collidepoint(pos):
                return ("freecell", idx)
        for idx, rect in enumerate(self.foundation_rects):
            if rect.collidepoint(pos):
                return ("foundation", idx)
        for idx, rect in enumerate(self.cascade_rects):
            if rect.collidepoint(pos):
                return ("cascade", idx)
        return None

    # ------------------------------------------------------------------
    # Ve (goi moi frame)
    # ------------------------------------------------------------------

    def draw(self, surface: pygame.Surface) -> None:
        """Vẽ tối ưu 3 lớp (Z-order chuẩn): Nền tĩnh -> Bài tĩnh -> Bài đang bay -> Bài đang kéo."""
        # 1. Vẽ nền
        surface.blit(self._static_surface, (0, 0))

        # 2. Xử lý Deal Animation
        if self.is_dealing:
            all_reached = True
            for item in self.animation_queue:
                if item["delay"] > 0:
                    item["delay"] -= 1
                    all_reached = False
                    continue
                w, tx, ty = item["widget"], item["target"][0], item["target"][1]
                curr_x, curr_y = w.rect.topleft
                w.move_to(int(curr_x + (tx - curr_x) * 0.1), int(curr_y + (ty - curr_y) * 0.1))
                if abs(tx - curr_x) > 1 or abs(ty - curr_y) > 1: all_reached = False
                else: w.move_to(tx, ty)
            if all_reached: self.is_dealing = False

        dragging_ids = {id(w) for w in self._drag_widgets}
        playable = getattr(self, "_playable_cards", set())

        # 3. TÁCH LỚP Z-ORDER: Tìm các lá bài đang bay (lệch khỏi vị trí gốc)
        expected_positions = self.get_card_positions(self.state)
        flying_cards = []

        def _render_card_item(card_data):
            if not card_data: return
            w = self._widgets.get(card_data)
            if not w or id(w) in dragging_ids: return
            
            # Nếu tọa độ hiện tại lệch với gốc -> bài đang bay -> Xếp vào danh sách vẽ sau
            exp_pos = expected_positions.get(card_data)
            if exp_pos and w.rect.topleft != exp_pos:
                flying_cards.append(card_data)
                return

            # Vẽ bài tĩnh (Có Glow nếu hợp lệ)
            if card_data == getattr(self, "_hovered_card", None) and card_data in playable:
                self._draw_glow(surface, w.rect)
            self.draw_card_with_shadow(surface, w.image, w.rect.topleft)

        # LỚP 1: BÀI TĨNH
        for card in self.state.free_cells: _render_card_item(card)
        for suit in ("C", "D", "H", "S"):
            rank = self.state.foundations[suit]
            if rank > 0: _render_card_item(Card(rank=rank, suit=suit))
        for cascade in self.state.cascades:
            for card in cascade: _render_card_item(card)

        # LỚP 2: BÀI ĐANG BAY (AI Animator & Deal Animation)
        # Vẽ sau bài tĩnh nên sẽ luôn nổi lên trên, không bị đè bóng đổ
        for card_data in flying_cards:
            w = self._widgets[card_data]
            self.draw_card_with_shadow(surface, w.image, w.rect.topleft)

        # LỚP 3: BÀI ĐANG KÉO CHUỘT (Cao nhất)
        if self._drag_widgets and self._drag_anchor:
            ax, ay = self._drag_anchor
            for i, w in enumerate(self._drag_widgets):
                new_pos = (ax, ay + i * self.card_overlap_y)
                self.draw_card_with_shadow(surface, w.image, new_pos)

    def _pick_cards(self, source: SourceRef) -> Optional[DragInfo]:
        location, index, start = source
        if location == "freecell":
            if not (0 <= index < 4) or start != 0:
                return None
            card = self.state.free_cells[index]
            if card is None:
                return None
            self.state.free_cells[index] = None
            return DragInfo(cards=[card], source=source)

        if location != "cascade" or not (0 <= index < len(self.state.cascades)):
            return None

        cascade = self.state.cascades[index]
        if not (0 <= start < len(cascade)):
            return None

        cards = cascade[start:]
        if not rules.is_valid_sequence(cards):
            return None

        max_movable = rules.get_max_move_size(self.state)
        if len(cards) > max_movable:
            return None

        self.state.cascades[index] = cascade[:start]
        return DragInfo(cards=cards, source=source)

    def _cancel_drag(self, drag: DragInfo) -> None:
        location, index, start = drag.source
        if location == "freecell":
            self.state.free_cells[index] = drag.cards[0]
            return

        cascade = self.state.cascades[index]
        self.state.cascades[index] = cascade[:start] + list(drag.cards) + cascade[start:]

    def _get_widget_by_identity(self, identity: tuple[int, str]) -> Optional[CardWidget]:
        for card, widget in self._widgets.items():
            if card.rank == identity[0] and card.suit == identity[1]:
                return widget
        return None
    
    def rebuild_for_screen(self, screen_rect: pygame.Rect) -> None:
        """Cập nhật kích thước mới và tạo lại toàn bộ bề mặt vẽ tĩnh."""
        self.screen_rect = screen_rect
        
        # QUAN TRỌNG: Tạo lại một surface mới với kích thước mới
        self._static_surface = pygame.Surface(self.screen_rect.size)
        
        # Tính toán lại vị trí các ô (slot_gap sẽ tự giãn ra)
        self._build_layout()
        
        # Vẽ lại hình nền và các khung ô lên tờ giấy mới
        self._rebuild_static_surface()

    def draw_card_with_shadow(self, surface, card_surf, pos):
        """Tối ưu: Vẽ shadow trực tiếp bằng cách fill vùng thay vì tạo Surface mới."""
        # Tạo bóng đổ lệch 4px màu tối
        shadow_rect = pygame.Rect(pos[0] + 4, pos[1] + 4, card_surf.get_width(), card_surf.get_height())
        # Vẽ một hình chữ nhật đen mờ nhanh (không cần tạo Surface phức tạp mỗi frame)
        s = pygame.Surface((card_surf.get_width(), card_surf.get_height()), pygame.SRCALPHA)
        s.fill((0, 0, 0, 80)) 
        surface.blit(s, shadow_rect.topleft)
        surface.blit(card_surf, pos)

    def _draw_glow(self, surface, rect):
        """Vẽ hào quang vàng tỏa ra từ phía sau lá bài."""
        # Tạo surface hào quang to hơn lá bài
        glow_surf = pygame.Surface((rect.width + 20, rect.height + 20), pygame.SRCALPHA)
        for i in range(8, 0, -1):
            alpha = 70 - (i * 8)
            # Màu Gold nhạt tỏa rộng dần
            pygame.draw.rect(glow_surf, (255, 223, 100, alpha), 
                             (10-i, 10-i, rect.width + i*2, rect.height + i*2), border_radius=12)
        surface.blit(glow_surf, (rect.x - 10, rect.y - 10))

    def _get_card_at_source(self, src_type, src_index): 
        """Hàm phụ trợ để lấy đối tượng Card từ tọa độ logic."""
        if src_type == rules.LOCATION_FREE_CELL:
            return self.state.free_cells[src_index]
        elif src_type == rules.LOCATION_CASCADE:
            if self.state.cascades[src_index]:
                return self.state.cascades[src_index][-1]
        return None

    def start_deal_animation(self, state: State):
        """Khởi tạo chia bài theo thứ tự (Sequential Deal)."""
        self.apply_state(state)
        self.is_dealing = True
        self.animation_queue = []
        
        center_x = self.screen_rect.width // 2
        center_y = -self.card_h # Bài bay từ cạnh trên màn hình xuống sẽ sinh động hơn
        
        final_positions = self.get_card_positions(state)
        
        # Sắp xếp bài theo thứ tự để chia từng cột từ trái sang phải
        for i, (card, target_pos) in enumerate(final_positions.items()):
            widget = self.get_widget(card)
            if widget:
                widget.rect.topleft = (center_x, center_y)
                self.animation_queue.append({
                    "widget": widget,
                    "target": target_pos,
                    "delay": i * 2 # Mỗi lá bài chờ 2 frame rồi mới bay
                })

def _suit_short_to_long(suit: str) -> str:
    return {"H": "hearts", "D": "diamonds", "C": "clubs", "S": "spades"}[suit]


def _normalize_card_identity(card) -> Optional[tuple[int, str]]:
    if card is None:
        return None

    suit = getattr(card, "suit", None)
    rank = getattr(card, "rank", None)
    if suit is None or rank is None:
        return None

    if suit in ("H", "D", "C", "S"):
        return (rank, suit)

    long_to_short = {"hearts": "H", "diamonds": "D", "clubs": "C", "spades": "S"}
    return (rank, long_to_short.get(suit, suit))

