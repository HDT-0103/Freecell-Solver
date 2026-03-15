from __future__ import annotations

import json
from typing import Callable, List

from core.state import CardData, GameState


def parse_card_token(token: str) -> CardData:
    token = token.strip().upper()
    if len(token) < 2:
        raise ValueError(f"Invalid card token: {token}")

    rank_part = token[:-1]
    suit_part = token[-1]

    rank_map = {
        "A": 1,
        "T": 10,
        "J": 11,
        "Q": 12,
        "K": 13,
    }
    if rank_part in rank_map:
        rank = rank_map[rank_part]
    else:
        rank = int(rank_part)
        if rank < 2 or rank > 9:
            raise ValueError(f"Invalid rank in token: {token}")

    suit_map = {
        "C": "clubs",
        "D": "diamonds",
        "H": "hearts",
        "S": "spades",
    }
    if suit_part not in suit_map:
        raise ValueError(f"Invalid suit in token: {token}")

    return CardData(rank=rank, suit=suit_map[suit_part])


def load_game_from_json(
    file_path: str,
    game_state: GameState,
    on_reset: Callable[[], None] | None = None,
) -> bool:
    """Load game state from JSON file into the provided GameState instance."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        cascades_raw = payload.get("cascades", [])
        if not isinstance(cascades_raw, list) or len(cascades_raw) != 8:
            raise ValueError("JSON must contain 8 cascades")

        new_cascades: List[List[CardData]] = [[] for _ in range(8)]
        new_free_cells: List[CardData | None] = [None] * 4
        new_foundations: List[List[CardData]] = [[] for _ in range(4)]
        used_cards: set[CardData] = set()

        for i, column in enumerate(cascades_raw):
            if not isinstance(column, list):
                raise ValueError("Each cascade must be a list")

            for token in column:
                card = parse_card_token(str(token))
                if card in used_cards:
                    raise ValueError(f"Duplicate card found: {token}")
                used_cards.add(card)
                new_cascades[i].append(card)

        free_cells_raw = payload.get("free_cells", [None, None, None, None])
        for i, token in enumerate(free_cells_raw):
            if i >= 4:
                break
            if token is None:
                new_free_cells[i] = None
            else:
                card = parse_card_token(str(token))
                if card in used_cards:
                    raise ValueError(f"Duplicate card found: {token}")
                used_cards.add(card)
                new_free_cells[i] = card

        foundations_raw = payload.get("foundations", {"C": 0, "D": 0, "H": 0, "S": 0})
        suit_map = {"C": 0, "D": 1, "H": 2, "S": 3}
        suit_names = {"C": "clubs", "D": "diamonds", "H": "hearts", "S": "spades"}

        for suit_abbr, count in foundations_raw.items():
            if suit_abbr in suit_map:
                idx = suit_map[suit_abbr]
                for rank in range(1, int(count) + 1):
                    card = CardData(rank=rank, suit=suit_names[suit_abbr])
                    if card in used_cards:
                        raise ValueError(f"Duplicate foundation card: {suit_abbr}{rank}")
                    used_cards.add(card)
                    new_foundations[idx].append(card)

        game_state.free_cells = new_free_cells
        game_state.foundations = new_foundations
        game_state.cascades = new_cascades
        game_state.move_count = 0
        if hasattr(game_state, "_history"):
            game_state._history.clear()

        if on_reset is not None:
            on_reset()

        return True
    except Exception as exc:
        print(f"Error loading JSON: {exc}")
        return False
