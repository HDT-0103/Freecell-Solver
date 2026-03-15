from Source.core.game_service import FreeCellGame, serialize_card, serialize_move, serialize_state
from Source.core.rules import LOCATION_CASCADE, LOCATION_FOUNDATION, LOCATION_FREE_CELL, Move
from Source.core.state import Card, State


def test_serialize_helpers_return_frontend_friendly_payloads():
    card_payload = serialize_card(Card(1, 'H'))
    move_payload = serialize_move(Move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, 'H'))

    assert card_payload == {'rank': 1, 'suit': 'H', 'color': 'red', 'label': 'AH'}
    assert move_payload == {
        'src_type': 'cascade',
        'src_index': 0,
        'dst_type': 'foundation',
        'dst_index': 'H',
        'count': 1,
    }


def test_get_view_model_contains_board_and_legal_moves():
    game = FreeCellGame(state=State([[Card(1, 'H')], [], [], [], [], [], [], []]))

    payload = game.get_view_model()

    assert payload['cascades'][0][0]['label'] == 'AH'
    assert payload['foundations']['H'] == 0
    assert any(move['dst_type'] == 'foundation' for move in payload['legal_moves'])


def test_try_move_updates_state_for_legal_move():
    game = FreeCellGame(state=State([[Card(1, 'H')], [], [], [], [], [], [], []]))

    result = game.try_move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, 'H')

    assert result.ok is True
    assert result.state.foundations['H'] == 1
    assert result.message == 'Move applied'


def test_try_move_rejects_illegal_move_without_mutating_state():
    state = State([[Card(8, 'H')], [Card(9, 'H')], [], [], [], [], [], []])
    game = FreeCellGame(state=state)

    result = game.try_move(LOCATION_CASCADE, 0, LOCATION_CASCADE, 1)

    assert result.ok is False
    assert result.message == 'Illegal move'
    assert game.get_state() == state


def test_auto_move_to_foundation_uses_available_move():
    game = FreeCellGame(state=State([[Card(1, 'H')], [], [], [], [], [], [], []]))

    result = game.auto_move_to_foundation()

    assert result.ok is True
    assert result.state.foundations['H'] == 1


def test_serialize_state_marks_goal():
    state = State(
        cascades=[[] for _ in range(8)],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 13},
    )

    payload = serialize_state(state)

    assert payload['is_goal'] is True


def test_new_game_replaces_current_state():
    game = FreeCellGame(seed=1)
    initial = game.get_state()

    game.new_game(2)

    assert game.get_state() != initial


def test_get_legal_move_payloads_returns_serialized_moves():
    game = FreeCellGame(
        state=State(
            cascades=[[Card(9, 'S')], [], [], [], [], [], [], []],
            free_cells=[Card(8, 'H'), None, None, None],
        )
    )

    payloads = game.get_legal_move_payloads()

    assert {
        'src_type': 'free_cell',
        'src_index': 0,
        'dst_type': 'cascade',
        'dst_index': 0,
        'count': 1,
    } in payloads
