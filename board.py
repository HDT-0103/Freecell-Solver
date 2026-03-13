# FILE NAY DA DUOC CHUYEN SANG:
#   Logic trang thai -> Source/core/state.py  (class GameState)
#   Hien thi ban bai -> Source/gui/interface.py (class BoardRenderer)
#
# File nay khong duoc import nua. Co the xoa an toan.

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import pygame

from card import Card, CardImageLoader, RANKS, SUITS


SourceRef = Tuple[str, int, int]
TargetRef = Tuple[str, int]


@dataclass
class DragState:
    cards: List[Card]
    source: SourceRef


class Board:
    """Quan ly ban FreeCell, trang thai va luat di chuyen."""

    BG_COLOR = (7, 109, 27)
    SLOT_COLOR = (230, 210, 90)
    SLOT_BORDER = (250, 240, 130)
    LABEL_COLOR = (255, 244, 170)

    def __init__(self, screen_rect: pygame.Rect, image_loader: CardImageLoader) -> None:
        self.screen_rect = screen_rect
        self.image_loader = image_loader

        sample = self.image_loader.get_image(1, "spades")
        self.card_w, self.card_h = sample.get_size()

        self.margin_x = 26
        self.top_y = 80  # Tang len de label co khoang trong phia tren
        self.cascades_y = self.top_y + self.card_h + 72
        self.card_overlap_y = max(26, self.card_h // 4)

        self.slot_gap = (self.screen_rect.width - 2 * self.margin_x - 8 * self.card_w) // 7
        self.slot_gap = max(14, self.slot_gap)

        self.font_label = pygame.font.SysFont("georgia", 24, bold=True)
        self.font_info = pygame.font.SysFont("georgia", 22, bold=True)

        self.free_cell_rects: List[pygame.Rect] = []
        self.foundation_rects: List[pygame.Rect] = []
        self.cascade_rects: List[pygame.Rect] = []
        self._build_layout()

        self.foundation_suits = ["spades", "hearts", "clubs", "diamonds"]

        self.free_cells: List[Optional[Card]] = [None] * 4
        self.foundations: List[List[Card]] = [[] for _ in range(4)]
        self.cascades: List[List[Card]] = [[] for _ in range(8)]

        self.move_count = 0
        self._static_surface = pygame.Surface(self.screen_rect.size)
        self._rebuild_static_surface()

        self.reset()

    def _build_layout(self) -> None:
        self.free_cell_rects.clear()
        self.foundation_rects.clear()
        self.cascade_rects.clear()

        for i in range(4):
            x = self.margin_x + i * (self.card_w + self.slot_gap)
            self.free_cell_rects.append(pygame.Rect(x, self.top_y, self.card_w, self.card_h))

        start_foundation_x = self.margin_x + 4 * (self.card_w + self.slot_gap)
        for i in range(4):
            x = start_foundation_x + i * (self.card_w + self.slot_gap)
            self.foundation_rects.append(pygame.Rect(x, self.top_y, self.card_w, self.card_h))

        cascade_height = self.screen_rect.height - self.cascades_y - 24
        for i in range(8):
            x = self.margin_x + i * (self.card_w + self.slot_gap)
            self.cascade_rects.append(pygame.Rect(x, self.cascades_y, self.card_w, cascade_height))

    def _rebuild_static_surface(self) -> None:
        self._static_surface.fill(self.BG_COLOR)

        # Tao van nen nhe de giao dien co cam giac mat ni.
        for y in range(0, self.screen_rect.height, 6):
            shade = 100 + (y % 18)
            pygame.draw.line(self._static_surface, (5, shade, 22), (0, y), (self.screen_rect.width, y))

        self._draw_slot_group(self.free_cell_rects, "Free Cells")
        self._draw_slot_group(self.foundation_rects, "Foundation")
        self._draw_slot_group(self.cascade_rects, "Tableau")

    def _draw_slot_group(self, rects: Sequence[pygame.Rect], title: str) -> None:
        for rect in rects:
            pygame.draw.rect(self._static_surface, self.SLOT_COLOR, rect, width=2, border_radius=8)
            pygame.draw.rect(self._static_surface, self.SLOT_BORDER, rect.inflate(-6, -6), width=1, border_radius=7)

        first = rects[0]
        last = rects[-1]
        title_surface = self.font_label.render(title, True, self.LABEL_COLOR)
        title_x = (first.left + last.right - title_surface.get_width()) // 2
        title_y = first.top - title_surface.get_height() - 8
        self._static_surface.blit(title_surface, (title_x, title_y))

    def reset(self) -> None:
        self.free_cells = [None] * 4
        self.foundations = [[] for _ in range(4)]
        self.cascades = [[] for _ in range(8)]
        self.move_count = 0

        deck = [Card(rank, suit, self.image_loader) for suit in SUITS for rank in RANKS]
        random.shuffle(deck)

        for idx, card in enumerate(deck):
            self.cascades[idx % 8].append(card)

        self._sync_card_positions()

    def _sync_card_positions(self) -> None:
        for i, card in enumerate(self.free_cells):
            if card:
                card.move_to(self.free_cell_rects[i].x, self.free_cell_rects[i].y)

        for i, pile in enumerate(self.foundations):
            for card in pile:
                card.move_to(self.foundation_rects[i].x, self.foundation_rects[i].y)

        for i, cascade in enumerate(self.cascades):
            base_x = self.cascade_rects[i].x
            base_y = self.cascade_rects[i].y
            for depth, card in enumerate(cascade):
                card.move_to(base_x, base_y + depth * self.card_overlap_y)

    def is_won(self) -> bool:
        return sum(len(pile) for pile in self.foundations) == 52

    def _is_valid_cascade_sequence(self, cards: Sequence[Card]) -> bool:
        for i in range(len(cards) - 1):
            if not cards[i + 1].can_stack_on(cards[i]):
                return False
        return True

    def _max_movable_cards(self, target: TargetRef) -> int:
        empty_free = sum(1 for c in self.free_cells if c is None)
        empty_cascades = sum(1 for pile in self.cascades if not pile)

        target_type, target_idx = target
        if target_type == "cascade" and not self.cascades[target_idx]:
            empty_cascades = max(0, empty_cascades - 1)

        return (empty_free + 1) * (2 ** empty_cascades)

    def pick_cards(self, mouse_pos: Tuple[int, int]) -> Optional[DragState]:
        for idx, rect in enumerate(self.free_cell_rects):
            card = self.free_cells[idx]
            if card and card.rect.collidepoint(mouse_pos):
                self.free_cells[idx] = None
                return DragState(cards=[card], source=("freecell", idx, 0))

        for col_idx, cascade in enumerate(self.cascades):
            for start in range(len(cascade) - 1, -1, -1):
                card = cascade[start]
                if card.rect.collidepoint(mouse_pos):
                    moving = cascade[start:]
                    if not self._is_valid_cascade_sequence(moving):
                        return None
                    del cascade[start:]
                    return DragState(cards=moving, source=("cascade", col_idx, start))

        return None

    def cancel_drag(self, drag: DragState) -> None:
        src_type, src_idx, _ = drag.source
        if src_type == "freecell":
            self.free_cells[src_idx] = drag.cards[0]
        else:
            self.cascades[src_idx].extend(drag.cards)
        self._sync_card_positions()

    def _can_drop_on_freecell(self, cards: Sequence[Card], idx: int) -> bool:
        return len(cards) == 1 and self.free_cells[idx] is None

    def _can_drop_on_foundation(self, cards: Sequence[Card], idx: int) -> bool:
        if len(cards) != 1:
            return False
        card = cards[0]
        if card.suit != self.foundation_suits[idx]:
            return False
        expected_rank = len(self.foundations[idx]) + 1
        return card.rank == expected_rank

    def _can_drop_on_cascade(self, cards: Sequence[Card], idx: int) -> bool:
        if not self._is_valid_cascade_sequence(cards):
            return False

        if len(cards) > self._max_movable_cards(("cascade", idx)):
            return False

        cascade = self.cascades[idx]
        if not cascade:
            return True

        top = cascade[-1]
        return cards[0].can_stack_on(top)

    def _apply_drop(self, cards: Sequence[Card], target: TargetRef) -> None:
        target_type, idx = target

        if target_type == "freecell":
            self.free_cells[idx] = cards[0]
        elif target_type == "foundation":
            self.foundations[idx].append(cards[0])
        else:
            self.cascades[idx].extend(cards)

        self.move_count += 1
        self._sync_card_positions()

    def drop_cards(self, drag: DragState, target: Optional[TargetRef]) -> bool:
        if target is None:
            return False

        target_type, idx = target
        cards = drag.cards

        is_valid = False
        if target_type == "freecell":
            is_valid = self._can_drop_on_freecell(cards, idx)
        elif target_type == "foundation":
            is_valid = self._can_drop_on_foundation(cards, idx)
        elif target_type == "cascade":
            is_valid = self._can_drop_on_cascade(cards, idx)

        if not is_valid:
            return False

        self._apply_drop(cards, target)
        return True

    def find_drop_target(self, mouse_pos: Tuple[int, int]) -> Optional[TargetRef]:
        for idx, rect in enumerate(self.free_cell_rects):
            if rect.collidepoint(mouse_pos):
                return ("freecell", idx)

        for idx, rect in enumerate(self.foundation_rects):
            if rect.collidepoint(mouse_pos):
                return ("foundation", idx)

        for idx, rect in enumerate(self.cascade_rects):
            if rect.collidepoint(mouse_pos):
                return ("cascade", idx)

        return None

    def draw(
        self,
        surface: pygame.Surface,
        drag_cards: Optional[Sequence[Card]] = None,
        drag_anchor: Optional[Tuple[int, int]] = None,
    ) -> None:
        surface.blit(self._static_surface, (0, 0))

        for card in self.free_cells:
            if card:
                surface.blit(card.image, card.rect)

        for pile in self.foundations:
            if pile:
                top = pile[-1]
                surface.blit(top.image, top.rect)

        for cascade in self.cascades:
            for card in cascade:
                surface.blit(card.image, card.rect)

        if drag_cards and drag_anchor:
            x, y = drag_anchor
            for i, card in enumerate(drag_cards):
                card.move_to(x, y + i * self.card_overlap_y)
                surface.blit(card.image, card.rect)

        info = self.font_info.render(f"Moves: {self.move_count}", True, (255, 250, 190))
        # Dat o cuoi man hinh de khong de len label Foundation phia tren
        surface.blit(info, (self.screen_rect.width - info.get_width() - 18, self.screen_rect.height - info.get_height() - 14))
