import pytest

from Source.core.state import Card, State


def serialize_state(state):
    return [[(card.rank, card.suit) for card in cascade] for cascade in state.cascades]


def test_microsoft_shuffle_is_deterministic_and_deals_all_cards():
    first = State.microsoft_shuffle(1)
    second = State.microsoft_shuffle(1)

    assert serialize_state(first) == serialize_state(second)
    assert [len(cascade) for cascade in first.cascades] == [7, 7, 7, 7, 6, 6, 6, 6]

    cards = list(first.iter_cards())
    assert len(cards) == 52
    assert len(set(cards)) == 52


def test_state_uses_value_semantics_for_cards():
    first = State([[] for _ in range(8)], [None] * 4, {'H': 0, 'D': 0, 'C': 0, 'S': 0})
    second = State([[] for _ in range(8)], [None] * 4, {'H': 0, 'D': 0, 'C': 0, 'S': 0})

    assert first == second
    assert first.get_hash() == second.get_hash()


def test_state_copies_input_containers():
    cascades = [[Card(1, 'S')], [], [], [], [], [], [], []]
    free_cells = [Card(13, 'H'), None, None, None]
    foundations = {'H': 1, 'D': 0, 'C': 0, 'S': 0}

    state = State(cascades, free_cells, foundations)

    cascades[0].append(Card(2, 'S'))
    free_cells[0] = None
    foundations['H'] = 5

    assert serialize_state(state) == [[(1, 'S')], [], [], [], [], [], [], []]
    assert state.free_cells[0] == Card(13, 'H')
    assert state.foundations['H'] == 1


def test_clone_returns_independent_copy():
    state = State([[Card(5, 'C')], [], [], [], [], [], [], []])
    cloned = state.clone()

    cloned.cascades[0].append(Card(4, 'H'))

    assert len(state.cascades[0]) == 1
    assert len(cloned.cascades[0]) == 2


def test_state_validates_structure():
    with pytest.raises(ValueError):
        State([[] for _ in range(7)])

    with pytest.raises(ValueError):
        State([[] for _ in range(8)], free_cells=[None] * 3)

    with pytest.raises(ValueError):
        State([[] for _ in range(8)], foundations={'H': 0, 'D': 0, 'C': 0})
