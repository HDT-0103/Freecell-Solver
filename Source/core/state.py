from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Literal, Optional, TypeAlias


SUITS = ("H", "D", "C", "S")
CASCADE_COUNT = 8
FREE_CELL_COUNT = 4


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank < 1 or self.rank > 13:
            raise ValueError(f"Invalid card rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid card suit: {self.suit}")

    @property
    def color(self) -> str:
        return "red" if self.suit in ("H", "D") else "black"

    def __repr__(self) -> str:
        ranks = {1: "A", 11: "J", 12: "Q", 13: "K"}
        rank_label = ranks.get(self.rank, str(self.rank))
        return f"{rank_label}{self.suit}"


class State:
    def __init__(self, cascades, free_cells=None, foundations=None, parent=None, move=None, g=None, h=0):
        self.cascades = [list(cascade) for cascade in cascades]
        self.free_cells = list(free_cells) if free_cells is not None else [None] * FREE_CELL_COUNT
        self.foundations = foundations.copy() if foundations is not None else {suit: 0 for suit in SUITS}

        self._validate_structure()

        self.parent = parent
        self.move = move
        self.g = parent.g + 1 if g is None and parent else (0 if g is None else g)
        self.h = h

    def _validate_structure(self) -> None:
        if len(self.cascades) != CASCADE_COUNT:
            raise ValueError(f"State must contain exactly {CASCADE_COUNT} cascades")
        if len(self.free_cells) != FREE_CELL_COUNT:
            raise ValueError(f"State must contain exactly {FREE_CELL_COUNT} free cells")
        if set(self.foundations.keys()) != set(SUITS):
            raise ValueError(f"Foundations must contain exactly these suits: {SUITS}")

        for cascade in self.cascades:
            for card in cascade:
                if not isinstance(card, Card):
                    raise TypeError("Each cascade entry must be a Card")

        for card in self.free_cells:
            if card is not None and not isinstance(card, Card):
                raise TypeError("Each free cell must be a Card or None")

        for suit, rank in self.foundations.items():
            if not isinstance(rank, int) or rank < 0 or rank > 13:
                raise ValueError(f"Invalid foundation rank for {suit}: {rank}")

    def clone(self, *, parent=None, move=None, g=None, h=None):
        return State(
            cascades=[cascade[:] for cascade in self.cascades],
            free_cells=self.free_cells[:],
            foundations=self.foundations.copy(),
            parent=self.parent if parent is None else parent,
            move=self.move if move is None else move,
            g=self.g if g is None else g,
            h=self.h if h is None else h,
        )

    def iter_cards(self):
        for cascade in self.cascades:
            for card in cascade:
                yield card
        for card in self.free_cells:
            if card is not None:
                yield card

    def as_key(self):
        return (
            tuple(tuple(cascade) for cascade in self.cascades),
            tuple(self.free_cells),
            tuple((suit, self.foundations[suit]) for suit in SUITS),
        )

    def get_hash(self):
        return hash(self.as_key())

    def __repr__(self) -> str:
        lines = [f"FreeCells: {self.free_cells} | Foundations: {self.foundations}", "Cascades:"]
        lines.extend(f" {index}: {cascade}" for index, cascade in enumerate(self.cascades))
        return "\n".join(lines)

    def __eq__(self, other) -> bool:
        if not isinstance(other, State):
            return False
        return self.as_key() == other.as_key()

    def __lt__(self, other) -> bool:
        return (self.g + self.h) < (other.g + other.h)

    @staticmethod
    def build_standard_deck():
        return [Card(rank, suit) for suit in ("C", "D", "H", "S") for rank in range(1, 14)]

    @staticmethod
    def microsoft_shuffle(seed):
        cards = State.build_standard_deck()
        shuffled_cards = []
        random_state = seed

        def ms_rand():
            nonlocal random_state
            random_state = (random_state * 214013 + 2531011) & 0x7FFFFFFF
            return (random_state >> 16) & 0x7FFF

        cards_left = len(cards)
        while cards_left > 0:
            index = ms_rand() % cards_left
            shuffled_cards.append(cards.pop(index))
            cards_left -= 1

        shuffled_cards.reverse()
        cascades = [[] for _ in range(CASCADE_COUNT)]
        for index, card in enumerate(shuffled_cards):
            cascades[index % CASCADE_COUNT].append(card)
        return State(cascades)


CARD_SUITS = ("clubs", "diamonds", "hearts", "spades")
FOUNDATION_INDEX_TO_SUIT = CARD_SUITS
_SUIT_COLORS = {
    "clubs": "black",
    "spades": "black",
    "diamonds": "red",
    "hearts": "red",
}

LocationName: TypeAlias = Literal["cascade", "freecell", "foundation"]
SourceRef: TypeAlias = tuple[Literal["cascade", "freecell", "foundation"], int, int]
TargetRef: TypeAlias = tuple[LocationName, int]


@dataclass(frozen=True)
class CardData:
    rank: int
    suit: str

    def __post_init__(self) -> None:
        if self.rank < 1 or self.rank > 13:
            raise ValueError(f"Invalid card rank: {self.rank}")
        if self.suit not in CARD_SUITS:
            raise ValueError(f"Invalid card suit: {self.suit}")

    @property
    def color(self) -> str:
        return _SUIT_COLORS[self.suit]

    def can_stack_on(self, other: "CardData") -> bool:
        return self.color != other.color and self.rank == other.rank - 1


@dataclass(frozen=True)
class DragInfo:
    cards: list[CardData]
    source: SourceRef


class GameState:
    def __init__(
        self,
        cascades: Optional[list[list[CardData]]] = None,
        free_cells: Optional[list[CardData | None]] = None,
        foundations: Optional[list[list[CardData]]] = None,
        move_count: int = 0,
        *,
        seed: int | None = None,
    ) -> None:
        self._history: list[tuple[SourceRef, TargetRef, list[CardData]]] = []
        if cascades is None:
            self.cascades = [[] for _ in range(CASCADE_COUNT)]
            self.free_cells = [None] * FREE_CELL_COUNT
            self.foundations = [[] for _ in range(4)]
            self.move_count = 0
            self.reset(seed)
            return

        self.cascades = [list(cascade) for cascade in cascades]
        self.free_cells = list(free_cells) if free_cells is not None else [None] * FREE_CELL_COUNT
        self.foundations = [list(pile) for pile in foundations] if foundations is not None else [[] for _ in range(4)]
        self.move_count = move_count
        self._validate()

    def _validate(self) -> None:
        if len(self.cascades) != CASCADE_COUNT:
            raise ValueError("GameState must contain 8 cascades")
        if len(self.free_cells) != FREE_CELL_COUNT:
            raise ValueError("GameState must contain 4 free cells")
        if len(self.foundations) != 4:
            raise ValueError("GameState must contain 4 foundation piles")

    def clone(self) -> "GameState":
        clone = GameState(
            cascades=[cascade[:] for cascade in self.cascades],
            free_cells=self.free_cells[:],
            foundations=[pile[:] for pile in self.foundations],
            move_count=self.move_count,
        )
        clone._history = list(self._history)
        return clone

    def reset(self, seed: int | None = None) -> None:
        rng = random.Random(seed)
        deck = [CardData(rank=rank, suit=suit) for suit in CARD_SUITS for rank in range(1, 14)]
        rng.shuffle(deck)

        self.cascades = [[] for _ in range(CASCADE_COUNT)]
        for index, card in enumerate(deck):
            self.cascades[index % CASCADE_COUNT].append(card)

        self.free_cells = [None] * FREE_CELL_COUNT
        self.foundations = [[] for _ in range(4)]
        self.move_count = 0
        self._history.clear()

    def to_hashable(self) -> tuple:
        return (
            tuple(tuple(cascade) for cascade in self.cascades),
            tuple(self.free_cells),
            tuple(tuple(pile) for pile in self.foundations),
        )

    def is_won(self) -> bool:
        return sum(len(pile) for pile in self.foundations) == 52

    def _is_valid_sequence(self, cards: list[CardData]) -> bool:
        if not cards:
            return False
        for index in range(len(cards) - 1):
            if not cards[index + 1].can_stack_on(cards[index]):
                return False
        return True

    def _max_movable(self, destination_index: int | None = None) -> int:
        empty_free_cells = sum(1 for card in self.free_cells if card is None)
        empty_cascades = sum(1 for cascade in self.cascades if not cascade)
        if destination_index is not None and 0 <= destination_index < CASCADE_COUNT and not self.cascades[destination_index]:
            empty_cascades -= 1
        return (1 + empty_free_cells) * (2 ** max(0, empty_cascades))

    def pick_cards(self, source: SourceRef) -> DragInfo | None:
        location, index, start = source

        if location == "freecell":
            if not (0 <= index < FREE_CELL_COUNT) or start != 0:
                return None
            card = self.free_cells[index]
            if card is None:
                return None
            self.free_cells[index] = None
            return DragInfo(cards=[card], source=source)

        if location == "foundation":
            if not (0 <= index < 4):
                return None
            pile = self.foundations[index]
            if not pile or start != len(pile) - 1:
                return None
            card = pile.pop()
            return DragInfo(cards=[card], source=source)

        if location != "cascade" or not (0 <= index < CASCADE_COUNT):
            return None

        cascade = self.cascades[index]
        if not (0 <= start < len(cascade)):
            return None

        cards = cascade[start:]
        if not self._is_valid_sequence(cards):
            return None
        if len(cards) > self._max_movable():
            return None

        self.cascades[index] = cascade[:start]
        return DragInfo(cards=cards, source=source)

    def can_drop(self, drag: DragInfo, target: TargetRef) -> bool:
        location, index = target
        if location == drag.source[0] and index == drag.source[1]:
            return False

        cards = drag.cards
        if not cards or not self._is_valid_sequence(cards):
            return False

        if drag.source[0] == "foundation" and location != "cascade":
            return False

        if location == "freecell":
            return len(cards) == 1 and 0 <= index < FREE_CELL_COUNT and self.free_cells[index] is None

        if location == "foundation":
            if len(cards) != 1 or not (0 <= index < 4):
                return False
            card = cards[0]
            expected_suit = FOUNDATION_INDEX_TO_SUIT[index]
            return card.suit == expected_suit and card.rank == len(self.foundations[index]) + 1

        if location == "cascade":
            if not (0 <= index < CASCADE_COUNT):
                return False
            if len(cards) > self._max_movable(index):
                return False
            destination = self.cascades[index]
            return not destination or cards[0].can_stack_on(destination[-1])

        return False

    def apply_drop(self, drag: DragInfo, target: TargetRef) -> bool:
        if not self.can_drop(drag, target):
            return False

        location, index = target
        if location == "freecell":
            self.free_cells[index] = drag.cards[0]
        elif location == "foundation":
            self.foundations[index].append(drag.cards[0])
        else:
            self.cascades[index].extend(drag.cards)

        self.move_count += 1
        self._history.append((drag.source, target, list(drag.cards)))
        return True

    def cancel_drag(self, drag: DragInfo) -> None:
        location, index, start = drag.source
        if location == "freecell":
            self.free_cells[index] = drag.cards[0]
            return

        if location == "foundation":
            self.foundations[index].append(drag.cards[0])
            return

        cascade = self.cascades[index]
        self.cascades[index] = cascade[:start] + list(drag.cards) + cascade[start:]

    def has_any_legal_move(self) -> bool:
        for src_idx, card in enumerate(self.free_cells):
            if card is None:
                continue
            drag = DragInfo(cards=[card], source=("freecell", src_idx, 0))
            for foundation_idx in range(4):
                if self.can_drop(drag, ("foundation", foundation_idx)):
                    return True
            for cascade_idx in range(CASCADE_COUNT):
                if self.can_drop(drag, ("cascade", cascade_idx)):
                    return True

        for src_idx, cascade in enumerate(self.cascades):
            if not cascade:
                continue

            top_drag = DragInfo(cards=[cascade[-1]], source=("cascade", src_idx, len(cascade) - 1))
            for free_cell_idx in range(FREE_CELL_COUNT):
                if self.can_drop(top_drag, ("freecell", free_cell_idx)):
                    return True
            for foundation_idx in range(4):
                if self.can_drop(top_drag, ("foundation", foundation_idx)):
                    return True
            for dst_idx in range(CASCADE_COUNT):
                if dst_idx != src_idx and self.can_drop(top_drag, ("cascade", dst_idx)):
                    return True

            max_tail = 1
            for pos in range(len(cascade) - 2, -1, -1):
                if cascade[pos + 1].can_stack_on(cascade[pos]):
                    max_tail += 1
                else:
                    break

            for length in range(2, max_tail + 1):
                drag = DragInfo(cards=cascade[-length:], source=("cascade", src_idx, len(cascade) - length))
                for dst_idx in range(CASCADE_COUNT):
                    if dst_idx != src_idx and self.can_drop(drag, ("cascade", dst_idx)):
                        return True

        for foundation_idx, pile in enumerate(self.foundations):
            if not pile:
                continue
            top_card = pile[-1]
            if top_card.rank > 3:
                continue
            drag = DragInfo(cards=[top_card], source=("foundation", foundation_idx, len(pile) - 1))
            for cascade_idx in range(CASCADE_COUNT):
                if self.can_drop(drag, ("cascade", cascade_idx)):
                    return True

        return False
