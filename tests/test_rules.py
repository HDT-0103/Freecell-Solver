import pytest

from Source.core import rules
from Source.core.rules import LOCATION_CASCADE, LOCATION_FOUNDATION, LOCATION_FREE_CELL, Move
from Source.core.state import Card, State


def test_is_valid_sequence_checks_alternating_descending_cards():
    assert rules.is_valid_sequence([Card(8, 'H'), Card(7, 'S'), Card(6, 'D')])
    assert not rules.is_valid_sequence([Card(8, 'H'), Card(7, 'D')])
    assert not rules.is_valid_sequence([Card(8, 'H'), Card(8, 'S')])


def test_get_max_move_size_uses_empty_spaces():
    cascades_not_empty = [[Card(13, 'S')] for _ in range(8)]
    state_full = State(cascades_not_empty, free_cells=[Card(1, 'H')] * 4)
    state_empty_fc = State(cascades_not_empty, free_cells=[None] * 4)

    assert rules.get_max_move_size(state_full) == 1
    assert rules.get_max_move_size(state_empty_fc) == 5


def test_can_move_card_to_foundation():
    foundations = {'H': 0, 'D': 0, 'C': 0, 'S': 0}

    assert rules.can_move_to_foundation(Card(1, 'H'), foundations)
    assert not rules.can_move_to_foundation(Card(2, 'H'), foundations)


def test_enumerate_legal_moves_includes_foundation_and_free_cell_moves():
    state = State([[Card(1, 'H')], [Card(13, 'S')], [], [], [], [], [], []])

    moves = rules.enumerate_legal_moves(state)

    assert Move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, 'H') in moves
    assert Move(LOCATION_CASCADE, 0, LOCATION_FREE_CELL, 0) in moves


def test_enumerate_legal_moves_includes_free_cell_to_cascade_move():
    state = State(
        cascades=[[Card(9, 'S')], [], [], [], [], [], [], []],
        free_cells=[Card(8, 'H'), None, None, None],
    )

    moves = rules.enumerate_legal_moves(state)

    assert Move(LOCATION_FREE_CELL, 0, LOCATION_CASCADE, 0) in moves


def test_apply_move_moves_card_to_foundation():
    state = State([[Card(1, 'H')], [], [], [], [], [], [], []])
    move = Move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, 'H')

    new_state = rules.apply_move(state, move)

    assert new_state.foundations['H'] == 1
    assert new_state.cascades[0] == []
    assert new_state.parent == state
    assert new_state.move == move


def test_apply_move_moves_sequence_between_cascades():
    state = State(
        cascades=[
            [Card(10, 'C'), Card(9, 'H'), Card(8, 'S')],
            [Card(10, 'S')],
            [],
            [],
            [],
            [],
            [],
            [],
        ]
    )
    move = Move(LOCATION_CASCADE, 0, LOCATION_CASCADE, 1, count=2)

    new_state = rules.apply_move(state, move)

    assert new_state.cascades[0] == [Card(10, 'C')]
    assert new_state.cascades[1] == [Card(10, 'S'), Card(9, 'H'), Card(8, 'S')]


def test_apply_move_rejects_illegal_move():
    state = State([[Card(8, 'H')], [Card(9, 'H')], [], [], [], [], [], []])
    illegal_move = Move(LOCATION_CASCADE, 0, LOCATION_CASCADE, 1)

    with pytest.raises(ValueError):
        rules.apply_move(state, illegal_move)


def test_is_legal_move_rejects_wrong_foundation_target():
    state = State([[Card(1, 'H')], [], [], [], [], [], [], []])
    move = Move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, 'D')

    assert not rules.is_legal_move(state, move)


def test_get_next_states_returns_applied_legal_moves():
    state = State(
        cascades=[[Card(1, 'H')], [Card(9, 'S')], [], [], [], [], [], []],
        free_cells=[Card(8, 'H'), None, None, None],
    )

    next_states = rules.get_next_states(state)

    assert any(next_state.foundations['H'] == 1 for next_state in next_states)
    assert any(next_state.cascades[1] == [Card(9, 'S'), Card(8, 'H')] for next_state in next_states)


def test_is_goal_uses_foundations():
    winning_state = State(
        cascades=[[] for _ in range(8)],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 13},
    )

    assert rules.is_goal(winning_state)
