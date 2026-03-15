from Source.core.state import Card, State


def serialize_state(state):
    return [[(card.rank, card.suit) for card in cascade] for cascade in state.cascades]


def test_microsoft_shuffle_is_deterministic_and_deals_all_cards():
    first = State.microsoft_shuffle(1)
    second = State.microsoft_shuffle(1)

    assert serialize_state(first) == serialize_state(second)
    assert [len(cascade) for cascade in first.cascades] == [7, 7, 7, 7, 6, 6, 6, 6]

    cards = [(card.rank, card.suit) for cascade in first.cascades for card in cascade]
    assert len(cards) == 52
    assert len(set(cards)) == 52


def test_state_uses_value_semantics_for_cards():
    first = State([[Card(1, 'C')]], [None] * 4, {'H': 0, 'D': 0, 'C': 0, 'S': 0})
    second = State([[Card(1, 'C')]], [None] * 4, {'H': 0, 'D': 0, 'C': 0, 'S': 0})

    assert first == second
    assert first.get_hash() == second.get_hash()


def test_state_copies_input_containers():
    cascades = [[Card(1, 'S')], []]
    free_cells = [Card(13, 'H'), None, None, None]
    foundations = {'H': 1, 'D': 0, 'C': 0, 'S': 0}

    state = State(cascades, free_cells, foundations)

    cascades[0].append(Card(2, 'S'))
    free_cells[0] = None
    foundations['H'] = 5

    assert serialize_state(state) == [[(1, 'S')], []]
    assert state.free_cells[0] == Card(13, 'H')
    assert state.foundations['H'] == 1

def test_get_next_states_foundation_move():
    # Setup: Có quân Át (Ace) ở đỉnh cột
    ace_hearts = Card(1, 'H')
    cascades = [[Card(13, 'S')], [ace_hearts], [], [], [], [], [], []]
    state = State(cascades)
    
    next_states = state.get_next_states()
    
    # Kiểm tra xem có trạng thái nào mà Foundation H đã lên 1 chưa [cite: 59]
    foundation_moves = [s for s in next_states if s.foundations['H'] == 1]
    assert len(foundation_moves) > 0

def test_get_next_states_sequence_move():
    # Setup: Cột 0 có chuỗi (8 Cơ - 7 Bích). Cột 1 có 9 Bích.
    # Theo luật: 8 Cơ có thể đặt lên 9 Bích [cite: 56]
    c0 = [Card(8, 'H'), Card(7, 'S')]
    c1 = [Card(9, 'S')]
    cascades = [c0, c1, [], [], [], [], [], []]
    state = State(cascades)
    
    next_states = state.get_next_states()
    
    # Kiểm tra xem có trạng thái nào mà cột 1 trở thành [9S, 8H, 7S] không
    moved = False
    for s in next_states:
        if len(s.cascades[1]) == 3 and s.cascades[1][-1].rank == 7:
            moved = True
            break
    assert moved, "Không tìm thấy nước đi di chuyển cả chuỗi bài hợp lệ"

def test_get_max_move_size_logic():
    # 1. Trường hợp: 0 ô trống, 0 cột trống -> chỉ di chuyển được 1 lá
    # Mỗi cột đều có 1 lá bài (ví dụ: King Spades) để không bị tính là cột trống
    dummy_card = Card(13, 'S')
    cascades_not_empty = [[dummy_card] for _ in range(8)] 
    
    # Các ô free cells đều đã có bài
    full_free_cells = [Card(1, 'H')] * 4
    
    state_full = State(cascades_not_empty, free_cells=full_free_cells)
    
    # Lúc này: empty_free_cells = 0, empty_cascades = 0
    # Công thức: (1 + 0) * (2 ** 0) = 1 * 1 = 1
    assert state_full.get_max_move_size() == 1

    # 2. Trường hợp: 4 ô trống, 0 cột trống -> di chuyển được 5 lá
    state_empty_fc = State(cascades_not_empty, free_cells=[None] * 4)
    # Công thức: (1 + 4) * (2 ** 0) = 5
    assert state_empty_fc.get_max_move_size() == 5