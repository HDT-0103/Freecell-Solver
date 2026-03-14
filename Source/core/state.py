"""
state.py
--------
Trang thai ban FreeCell thuan tuy (khong phu thuoc pygame).
Duoc su dung boi ca GUI (gui/interface.py) va cac thuat toan AI (solvers/).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from core.rules import (
    SUITS,
    RANKS,
    FOUNDATION_SUITS,
    is_red,
    can_place_on,
    can_place_on_foundation,
    is_valid_sequence,
    max_movable_cards,
)


# ---------------------------------------------------------------------------
# Du lieu la bai (khong co pygame)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CardData:
    """Du lieu thuan tui cua mot la bai.
    Frozen dataclass -> hashable, dung lam key trong dict cua BoardRenderer.
    Moi cap (rank, suit) la duy nhat trong bo bai 52 la.
    """
    rank: int
    suit: str

    @property
    def is_red(self) -> bool:
        """La bai mau do (hearts/diamonds) hay den (spades/clubs)."""
        return is_red(self.suit)

    def can_stack_on(self, other: "CardData") -> bool:
        """Kiem tra la bai nay co the dat len 'other' trong cascade."""
        return can_place_on(self.rank, self.is_red, other.rank, other.is_red)


# ---------------------------------------------------------------------------
# Tham chieu nguon / dich
# ---------------------------------------------------------------------------

# (loai: "freecell"/"cascade", idx, depth_trong_cascade)
SourceRef = Tuple[str, int, int]
# (loai: "freecell"/"foundation"/"cascade", idx)
TargetRef = Tuple[str, int]


@dataclass
class DragInfo:
    """Thong tin ve nhom bai dang duoc nguoi choi keo."""
    cards: List[CardData]
    source: SourceRef


# ---------------------------------------------------------------------------
# Trang thai ban FreeCell
# ---------------------------------------------------------------------------

class GameState:
    """Quan ly toan bo trang thai ban FreeCell.

    Khong chua bat ky logic hien thi (pygame) nao.
    Co the serialise/copy de dung cho thuat toan tim kiem (BFS/A*/DFS).
    """

    def __init__(self) -> None:
        self.free_cells:  List[Optional[CardData]] = [None] * 4
        self.foundations: List[List[CardData]]      = [[] for _ in range(4)]
        self.cascades:    List[List[CardData]]      = [[] for _ in range(8)]
        self.move_count:  int                       = 0
        # Luu lich su de ho tro Undo
        self._history: List[tuple]                  = []

    # ------------------------------------------------------------------
    # Khoi tao / reset
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Tao lai bo bai 52 la, tron ngau nhien va chia vao 8 cascade."""
        self.free_cells  = [None] * 4
        self.foundations = [[] for _ in range(4)]
        self.cascades    = [[] for _ in range(8)]
        self.move_count  = 0
        self._history.clear()

        deck = [CardData(rank, suit) for suit in SUITS for rank in RANKS]
        random.shuffle(deck)
        for idx, card in enumerate(deck):
            self.cascades[idx % 8].append(card)

    def _push_history(self) -> None:
        """Luu snapshot truoc khi ap dung 1 nuoc di hop le."""
        self._history.append(
            (
                list(self.free_cells),
                [list(pile) for pile in self.foundations],
                [list(col) for col in self.cascades],
                self.move_count,
            )
        )

    def undo(self) -> bool:
        """Quay lai trang thai truoc do. Tra ve False neu khong co lich su."""
        if not self._history:
            return False

        free_cells, foundations, cascades, move_count = self._history.pop()
        self.free_cells = list(free_cells)
        self.foundations = [list(pile) for pile in foundations]
        self.cascades = [list(col) for col in cascades]
        self.move_count = move_count
        return True

    # ------------------------------------------------------------------
    # Trang thai thang / thua
    # ------------------------------------------------------------------

    def is_won(self) -> bool:
        """Tra ve True khi ca 52 la bai da duoc xep het len Foundation."""
        return sum(len(pile) for pile in self.foundations) == 52

    # ------------------------------------------------------------------
    # Ham noi bo
    # ------------------------------------------------------------------

    def _seq_repr(self, cards: Sequence[CardData]) -> List[Tuple[int, bool]]:
        """Chuyen danh sach CardData thanh list (rank, is_red) cho rules.py."""
        return [(c.rank, c.is_red) for c in cards]

    def _count_empty_free(self) -> int:
        return sum(1 for c in self.free_cells if c is None)

    def _count_empty_cascades(self) -> int:
        return sum(1 for pile in self.cascades if not pile)

    def _max_movable(self, target_idx: int) -> int:
        """So la toi da co the di chuyen sang cascade tai target_idx."""
        target_is_empty = not self.cascades[target_idx]
        return max_movable_cards(
            self._count_empty_free(),
            self._count_empty_cascades(),
            target_is_empty,
        )

    # ------------------------------------------------------------------
    # Thao tac pick / drop / cancel
    # ------------------------------------------------------------------

    def pick_cards(self, source: SourceRef) -> Optional[DragInfo]:
        """Lay nhom bai ra khoi vi tri nguon.

        Tra ve DragInfo neu hop le, None neu khong the lay.
        Bai da duoc xoa khoi state sau khi goi ham nay.
        """
        src_type, src_idx, src_depth = source

        if src_type == "freecell":
            card = self.free_cells[src_idx]
            if card is None:
                return None
            self.free_cells[src_idx] = None
            return DragInfo(cards=[card], source=source)

        if src_type == "cascade":
            cascade = self.cascades[src_idx]
            if src_depth >= len(cascade):
                return None
            moving = list(cascade[src_depth:])
            # Kiem tra day bai duoc chon co la chuoi hop le khong
            if not is_valid_sequence(self._seq_repr(moving)):
                return None
            del cascade[src_depth:]
            return DragInfo(cards=moving, source=source)

        return None

    def cancel_drag(self, drag: DragInfo) -> None:
        """Tra bai ve dung vi tri nguon (khi drop khong hop le)."""
        src_type, src_idx, _ = drag.source
        if src_type == "freecell":
            self.free_cells[src_idx] = drag.cards[0]
        else:
            self.cascades[src_idx].extend(drag.cards)

    def can_drop(self, drag: DragInfo, target: TargetRef) -> bool:
        """Kiem tra co the tha nhom bai vao vi tri dich khong (khong thay doi state)."""
        target_type, idx = target
        cards = drag.cards

        if target_type == "freecell":
            return len(cards) == 1 and self.free_cells[idx] is None

        if target_type == "foundation":
            if len(cards) != 1:
                return False
            card = cards[0]
            return can_place_on_foundation(
                card.rank, card.suit,
                FOUNDATION_SUITS[idx], len(self.foundations[idx]),
            )

        if target_type == "cascade":
            if not is_valid_sequence(self._seq_repr(cards)):
                return False
            if len(cards) > self._max_movable(idx):
                return False
            cascade = self.cascades[idx]
            if not cascade:
                return True
            return can_place_on(
                cards[0].rank, cards[0].is_red,
                cascade[-1].rank, cascade[-1].is_red,
            )

        return False

    def apply_drop(self, drag: DragInfo, target: TargetRef) -> bool:
        """Tha bai vao vi tri dich neu hop le.

        Tra ve True neu thanh cong.
        Khong tu dong cancel_drag khi that bai — caller phai goi cancel_drag.
        """
        if not self.can_drop(drag, target):
            return False

        target_type, idx = target
        if target_type == "freecell":
            self.free_cells[idx] = drag.cards[0]
        elif target_type == "foundation":
            self.foundations[idx].append(drag.cards[0])
        else:
            self.cascades[idx].extend(drag.cards)

        self.move_count += 1
        return True

    def _can_drop_with_source_effect(self, drag: DragInfo, target: TargetRef) -> bool:
        """Ban mo rong cua can_drop co tinh den trang thai sau khi pick.

        Ham nay dung de check deadlock chinh xac hon cho move nhom.
        """
        target_type, idx = target
        cards = drag.cards
        src_type, src_idx, src_depth = drag.source

        if target_type == "freecell":
            return len(cards) == 1 and self.free_cells[idx] is None

        if target_type == "foundation":
            if len(cards) != 1:
                return False
            card = cards[0]
            return can_place_on_foundation(
                card.rank, card.suit,
                FOUNDATION_SUITS[idx], len(self.foundations[idx]),
            )

        if target_type != "cascade":
            return False

        if not is_valid_sequence(self._seq_repr(cards)):
            return False

        empty_free = self._count_empty_free()
        if src_type == "freecell":
            empty_free += 1

        empty_cascades = self._count_empty_cascades()
        if src_type == "cascade" and src_depth == 0 and len(self.cascades[src_idx]) > 0:
            empty_cascades += 1

        target_is_empty = not self.cascades[idx]
        max_len = max_movable_cards(empty_free, empty_cascades, target_is_empty)
        if len(cards) > max_len:
            return False

        cascade = self.cascades[idx]
        if not cascade:
            return True

        return can_place_on(
            cards[0].rank, cards[0].is_red,
            cascade[-1].rank, cascade[-1].is_red,
        )

    def has_any_legal_move(self) -> bool:
        """Kiem tra con nuoc di hop le nao khong.

        Dung de xac dinh trang thai bi ket (khong con move).
        """
        drags: List[DragInfo] = []

        for i, card in enumerate(self.free_cells):
            if card is not None:
                drags.append(DragInfo(cards=[card], source=("freecell", i, 0)))

        for col_idx, cascade in enumerate(self.cascades):
            for start in range(len(cascade)):
                moving = cascade[start:]
                if is_valid_sequence(self._seq_repr(moving)):
                    drags.append(DragInfo(cards=list(moving), source=("cascade", col_idx, start)))

        for drag in drags:
            src_type, src_idx, _ = drag.source

            for i in range(4):
                if src_type == "freecell" and src_idx == i:
                    continue
                if self._can_drop_with_source_effect(drag, ("freecell", i)):
                    return True

            for i in range(4):
                if self._can_drop_with_source_effect(drag, ("foundation", i)):
                    return True

            for i in range(8):
                if src_type == "cascade" and src_idx == i:
                    continue
                if self._can_drop_with_source_effect(drag, ("cascade", i)):
                    return True

        return False

    # ------------------------------------------------------------------
    # Tien ich cho Solver (su dung sau)
    # ------------------------------------------------------------------

    def clone(self) -> "GameState":
        """Tao ban sao sau cua trang thai hien tai (dung cho thuat toan AI)."""
        new = GameState()
        new.free_cells  = list(self.free_cells)
        new.foundations = [list(pile) for pile in self.foundations]
        new.cascades    = [list(col)  for col  in self.cascades]
        new.move_count  = self.move_count
        return new

    def to_hashable(self) -> tuple:
        """Chuyen trang thai thanh tuple bat bien de dung lam key trong BFS/A*."""
        return (
            tuple(self.free_cells),
            tuple(tuple(pile) for pile in self.foundations),
            tuple(tuple(col)  for col  in self.cascades),
        )
