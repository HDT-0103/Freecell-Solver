from dataclasses import dataclass


SUITS = ('H', 'D', 'C', 'S')
CASCADE_COUNT = 8
FREE_CELL_COUNT = 4


@dataclass(frozen=True)
class Card:
    rank: int
    suit: str

    def __post_init__(self):
        if self.rank < 1 or self.rank > 13:
            raise ValueError(f"Invalid card rank: {self.rank}")
        if self.suit not in SUITS:
            raise ValueError(f"Invalid card suit: {self.suit}")

    @property
    def color(self):
        return 'red' if self.suit in ('H', 'D') else 'black'

    def __repr__(self):
        ranks = {1: 'A', 11: 'J', 12: 'Q', 13: 'K'}
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

    def _validate_structure(self):
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

    def __repr__(self):
        lines = [f"FreeCells: {self.free_cells} | Foundations: {self.foundations}", "Cascades:"]
        lines.extend(f" {index}: {cascade}" for index, cascade in enumerate(self.cascades))
        return "\n".join(lines)

    def __eq__(self, other):
        if not isinstance(other, State):
            return False
        return self.as_key() == other.as_key()

    def __lt__(self, other):
        return (self.g + self.h) < (other.g + other.h)

    @staticmethod
    def build_standard_deck():
        return [Card(rank, suit) for suit in ('C', 'D', 'H', 'S') for rank in range(1, 14)]

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
