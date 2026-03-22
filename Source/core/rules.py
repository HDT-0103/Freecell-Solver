from dataclasses import dataclass

from .state import FREE_CELL_COUNT, State


FOUNDATION_SUITS = ("clubs", "diamonds", "hearts", "spades")


LOCATION_CASCADE = 'cascade'
LOCATION_FREE_CELL = 'free_cell'
LOCATION_FOUNDATION = 'foundation'


@dataclass(frozen=True)
class Move:
    src_type: str
    src_index: int
    dst_type: str
    dst_index: int | str
    count: int = 1


def _is_valid_cascade_index(state, index):
    return 0 <= index < len(state.cascades)


def _is_valid_free_cell_index(index):
    return 0 <= index < FREE_CELL_COUNT


def _is_valid_foundation_index(index):
    return index in ('H', 'D', 'C', 'S')


def is_goal(state):
    return sum(state.foundations.values()) == 52


def get_max_move_size(state, moving_to_empty_stack=False):
    empty_free_cells = state.free_cells.count(None)
    empty_cascades = sum(1 for cascade in state.cascades if not cascade)
    if moving_to_empty_stack:
        empty_cascades -= 1
    return (1 + empty_free_cells) * (2 ** max(0, empty_cascades))


def can_move_to_foundation(card, foundations):
    return foundations[card.suit] + 1 == card.rank


def can_place_on_cascade(card, cascade):
    if not cascade:
        return True
    top_card = cascade[-1]
    return card.color != top_card.color and card.rank == top_card.rank - 1


def is_valid_sequence(cards):
    if not cards:
        return False
    for index in range(len(cards) - 1):
        current_card = cards[index]
        next_card = cards[index + 1]
        if current_card.color == next_card.color:
            return False
        if current_card.rank != next_card.rank + 1:
            return False
    return True


def get_movable_sequence_lengths(cascade):
    lengths = []
    for length in range(1, len(cascade) + 1):
        if is_valid_sequence(cascade[-length:]):
            lengths.append(length)
    return lengths


def _first_empty_free_cell(state):
    return next((index for index, card in enumerate(state.free_cells) if card is None), None)


def is_legal_move(state, move):
    if move.count < 1:
        return False

    if move.src_type == LOCATION_CASCADE:
        if not _is_valid_cascade_index(state, move.src_index):
            return False
        src_cascade = state.cascades[move.src_index]
        if len(src_cascade) < move.count:
            return False
        moving_cards = src_cascade[-move.count:]
    elif move.src_type == LOCATION_FREE_CELL:
        if not _is_valid_free_cell_index(move.src_index):
            return False
        if move.count != 1:
            return False
        card = state.free_cells[move.src_index]
        if card is None:
            return False
        moving_cards = [card]
    else:
        return False

    if not is_valid_sequence(moving_cards):
        return False

    if move.dst_type == LOCATION_FOUNDATION:
        if move.count != 1:
            return False
        if not _is_valid_foundation_index(move.dst_index):
            return False
        if moving_cards[0].suit != move.dst_index:
            return False
        return can_move_to_foundation(moving_cards[0], state.foundations)

    if move.dst_type == LOCATION_FREE_CELL:
        if move.count != 1:
            return False
        if not _is_valid_free_cell_index(move.dst_index):
            return False
        return state.free_cells[move.dst_index] is None

    if move.dst_type == LOCATION_CASCADE:
        if not _is_valid_cascade_index(state, move.dst_index):
            return False
        destination = state.cascades[move.dst_index]
        if not can_place_on_cascade(moving_cards[0], destination):
            return False
        return move.count <= get_max_move_size(state, moving_to_empty_stack=(not destination))

    return False


def enumerate_legal_moves(state):
    moves = []

    for cascade_index, cascade in enumerate(state.cascades):
        if cascade:
            top_card = cascade[-1]
            if can_move_to_foundation(top_card, state.foundations):
                moves.append(Move(LOCATION_CASCADE, cascade_index, LOCATION_FOUNDATION, top_card.suit))

    for free_cell_index, card in enumerate(state.free_cells):
        if card and can_move_to_foundation(card, state.foundations):
            moves.append(Move(LOCATION_FREE_CELL, free_cell_index, LOCATION_FOUNDATION, card.suit))

    empty_free_cell_index = _first_empty_free_cell(state)
    if empty_free_cell_index is not None:
        for cascade_index, cascade in enumerate(state.cascades):
            if cascade:
                moves.append(Move(LOCATION_CASCADE, cascade_index, LOCATION_FREE_CELL, empty_free_cell_index))

    for free_cell_index, card in enumerate(state.free_cells):
        if card is None:
            continue
        for cascade_index, cascade in enumerate(state.cascades):
            if can_place_on_cascade(card, cascade):
                moves.append(Move(LOCATION_FREE_CELL, free_cell_index, LOCATION_CASCADE, cascade_index))

    for src_index, src_cascade in enumerate(state.cascades):
        if not src_cascade:
            continue

        for count in get_movable_sequence_lengths(src_cascade):
            moving_cards = src_cascade[-count:]
            for dst_index, dst_cascade in enumerate(state.cascades):
                if src_index == dst_index:
                    continue
                if not can_place_on_cascade(moving_cards[0], dst_cascade):
                    continue
                if count > get_max_move_size(state, moving_to_empty_stack=(not dst_cascade)):
                    continue
                moves.append(Move(LOCATION_CASCADE, src_index, LOCATION_CASCADE, dst_index, count=count))

    return moves


def apply_move(state, move):
    if not is_legal_move(state, move):
        raise ValueError(f"Illegal move: {move}")

    new_state = State(
        cascades=[cascade[:] for cascade in state.cascades],
        free_cells=state.free_cells[:],
        foundations=state.foundations.copy(),
        parent=state,
        move=move,
    )

    if move.src_type == LOCATION_CASCADE:
        moving_cards = new_state.cascades[move.src_index][-move.count:]
        new_state.cascades[move.src_index] = new_state.cascades[move.src_index][:-move.count]
    else:
        moving_cards = [new_state.free_cells[move.src_index]]
        new_state.free_cells[move.src_index] = None

    if move.dst_type == LOCATION_FOUNDATION:
        new_state.foundations[move.dst_index] += 1
    elif move.dst_type == LOCATION_FREE_CELL:
        new_state.free_cells[move.dst_index] = moving_cards[0]
    elif move.dst_type == LOCATION_CASCADE:
        new_state.cascades[move.dst_index].extend(moving_cards)

    return new_state


def get_next_states(state):
    return [apply_move(state, move) for move in enumerate_legal_moves(state)]
