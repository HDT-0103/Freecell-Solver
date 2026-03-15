"""
rules.py
--------
Cac quy tac thuan tuy cua FreeCell. Khong phu thuoc pygame.
Duoc dung boi state.py va co the tai su dung cho cac thuat toan AI (BFS, A*, ...).
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

# ---------------------------------------------------------------------------
# Hang so bo bai
# ---------------------------------------------------------------------------

SUITS = ("spades", "hearts", "clubs", "diamonds")
RANKS = tuple(range(1, 14))               # 1 = Ace, 13 = King

# Thu tu chuan cho 4 o Foundation (co the chinh lai trong state.py neu muon)
FOUNDATION_SUITS = ["spades", "hearts", "clubs", "diamonds"]


# ---------------------------------------------------------------------------
# Cac ham kiem tra luat
# ---------------------------------------------------------------------------

def is_red(suit: str) -> bool:
    """Kiem tra la bai co phai mau do khong (hearts hoac diamonds)."""
    return suit in ("hearts", "diamonds")


def can_place_on(
    child_rank: int,
    child_is_red: bool,
    parent_rank: int,
    parent_is_red: bool,
) -> bool:
    """Quy tac xep bai tren cascade:
    - la con phai khac mau voi la cha
    - rank cua la con phai bang rank la cha tru 1
    Vi du: 9 do co the dat len 10 den.
    """
    return child_is_red != parent_is_red and child_rank + 1 == parent_rank


def is_valid_sequence(seq: Sequence[Tuple[int, bool]]) -> bool:
    """Kiem tra day bai (rank, is_red) co phai la chuoi hop le de keo nhom.

    seq[0] la la duoi cung cua nhom (rank cao nhat),
    seq[-1] la la tren cung (rank thap nhat).
    Moi phan tu seq[i+1] phai co the dat len seq[i].
    """
    for i in range(len(seq) - 1):
        rank_cur,  red_cur  = seq[i]
        rank_next, red_next = seq[i + 1]
        if not can_place_on(rank_next, red_next, rank_cur, red_cur):
            return False
    return True


def max_movable_cards(
    empty_free: int,
    empty_cascades: int,
    target_is_empty: bool,
) -> int:
    """Tinh so la bai toi da co the keo cung 1 lan (supermove rule).

    Cong thuc: (so_o_freecell_trong + 1) * 2^(so_cascade_trong)
    Neu dat vao cascade trong thi cascade do khong duoc dem la "trong" them.
    """
    adjusted_empty = max(0, empty_cascades - (1 if target_is_empty else 0))
    return (empty_free + 1) * (2 ** adjusted_empty)


def can_place_on_foundation(
    card_rank: int,
    card_suit: str,
    pile_suit: str,
    pile_size: int,
) -> bool:
    """Kiem tra co the dat la bai len foundation hay khong.
    - Phai dung chat (suit) voi o foundation
    - Rank phai tuong ung voi vi tri tiep theo (pile_size + 1)
    """
    return card_suit == pile_suit and card_rank == pile_size + 1
