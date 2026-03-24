from Source.core.rules import LOCATION_CASCADE, LOCATION_FOUNDATION, LOCATION_FREE_CELL, Move
from Source.core.state import Card, State
from Source.solvers import bfs as bfs_module
from Source.solvers.bfs import (
    _core_move_to_refs,
    _generate_moves,
    _is_inverse_move,
    _refs_to_core_move,
    solve_bfs,
)


def test_core_move_to_refs_maps_cascade_move_with_correct_start_index():
    state = State(
        cascades=[[Card(10, "C"), Card(9, "H"), Card(8, "S")], [Card(10, "S")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )
    move = Move(LOCATION_CASCADE, 0, LOCATION_CASCADE, 1, count=2)

    source, target = _core_move_to_refs(state, move)

    assert source == ("cascade", 0, 1)
    assert target == ("cascade", 1)


def test_refs_to_core_move_returns_none_for_invalid_refs_or_illegal_move():
    state = State(
        cascades=[[Card(8, "H")], [Card(9, "H")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    assert _refs_to_core_move(state, ("unknown", 0, 0), ("cascade", 1)) is None
    assert _refs_to_core_move(state, ("cascade", 99, 0), ("cascade", 1)) is None
    assert _refs_to_core_move(state, ("cascade", 0, 0), ("invalid", 0)) is None
    # Same-color stack (8H onto 9H) is illegal in FreeCell.
    assert _refs_to_core_move(state, ("cascade", 0, 0), ("cascade", 1)) is None


def test_refs_to_core_move_builds_valid_foundation_move():
    state = State(
        cascades=[[Card(1, "H")], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    move = _refs_to_core_move(state, ("cascade", 0, 0), ("foundation", "H"))

    assert move == Move(LOCATION_CASCADE, 0, LOCATION_FOUNDATION, "H", count=1)


def test_is_inverse_move_detects_direct_reverse_only():
    previous = Move(LOCATION_CASCADE, 0, LOCATION_FREE_CELL, 2, count=1)
    inverse = Move(LOCATION_FREE_CELL, 2, LOCATION_CASCADE, 0, count=1)
    different_count = Move(LOCATION_FREE_CELL, 2, LOCATION_CASCADE, 0, count=2)

    assert _is_inverse_move(inverse, previous) is True
    assert _is_inverse_move(different_count, previous) is False
    assert _is_inverse_move(inverse, None) is False


def test_generate_moves_prioritizes_foundation_before_other_moves():
    state = State(
        cascades=[[Card(1, "H")], [Card(9, "S")], [], [], [], [], [], []],
        free_cells=[Card(8, "H"), None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    successors = _generate_moves(state)

    assert len(successors) > 0
    # Foundation move must come first by BFS move priority.
    first_core_move, first_refs_move, first_state = successors[0]
    assert first_core_move.dst_type == LOCATION_FOUNDATION
    assert first_refs_move[1][0] == "foundation"
    assert first_state.foundations["H"] == 1


def test_bfs_handles_already_solved_state_without_expanding_nodes():
    initial_state = State(
        cascades=[[] for _ in range(8)],
        free_cells=[None, None, None, None],
        foundations={"H": 13, "D": 13, "C": 13, "S": 13},
    )

    result = solve_bfs(initial_state, max_nodes=1_000, max_time_seconds=5.0)

    assert result.solved is True
    assert result.moves == []
    assert len(result.state_path) == 1
    assert result.state_path[0] == initial_state
    assert result.metrics.expanded_nodes == 0
    assert result.metrics.solution_steps == 0


def test_bfs_solves_single_foundation_move():
    initial_state = State(
        cascades=[[Card(13, "S")], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 13, "D": 13, "C": 13, "S": 12},
    )

    result = solve_bfs(initial_state, max_nodes=1_000, max_time_seconds=5.0)

    assert result.solved is True
    assert len(result.moves) == 1
    assert result.moves[0][1][0] == "foundation"
    assert result.state_path[-1].foundations["S"] == 13


def test_bfs_solves_two_step_foundation_sequence():
    initial_state = State(
        cascades=[[Card(12, "S")], [Card(13, "S")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 13, "D": 13, "C": 13, "S": 11},
    )

    result = solve_bfs(initial_state, max_nodes=1_000, max_time_seconds=5.0)

    assert result.solved is True
    assert len(result.moves) == 2
    assert all(target[0] == "foundation" for _, target in result.moves)
    assert len(result.state_path) == 3
    assert result.state_path[-1].foundations["S"] == 13
    assert result.metrics.solution_steps == 2


def test_bfs_returns_unsolved_when_node_budget_is_zero():
    initial_state = State(
        cascades=[[Card(12, "S")], [Card(13, "S")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 13, "D": 13, "C": 13, "S": 11},
    )

    result = solve_bfs(initial_state, max_nodes=0, max_time_seconds=5.0)

    assert result.solved is False
    assert result.moves == []
    assert len(result.state_path) == 1
    assert result.metrics.expanded_nodes == 0


def test_bfs_returns_unsolved_when_time_budget_is_zero():
    initial_state = State(
        cascades=[[Card(12, "S")], [Card(13, "S")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 13, "D": 13, "C": 13, "S": 11},
    )

    result = solve_bfs(initial_state, max_nodes=1_000, max_time_seconds=0.0)

    assert result.solved is False
    assert result.moves == []
    assert len(result.state_path) == 1
    assert result.metrics.expanded_nodes == 0


def test_bfs_returns_best_partial_progress_path_when_budget_is_tight():
    initial_state = State(
        cascades=[[Card(11, "H")], [Card(12, "H")], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 10, "D": 13, "C": 13, "S": 13},
    )

    result = solve_bfs(initial_state, max_nodes=1, max_time_seconds=5.0)

    assert result.solved is False
    # BFS should still return the best discovered progress path (JH -> foundation).
    assert len(result.moves) >= 1
    assert result.moves[0][1] == ("foundation", "H")
    assert len(result.state_path) == len(result.moves) + 1


def test_bfs_state_path_matches_move_count():
    state = State(
        cascades=[[Card(1, "H")], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    result = solve_bfs(state, max_nodes=1_000, max_time_seconds=5.0)

    assert len(result.state_path) == len(result.moves) + 1


def test_bfs_does_not_reenqueue_state_once_reached(monkeypatch):
    start = State(
        cascades=[[Card(7, "H")], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )
    next_state = State(
        cascades=[[], [], [], [], [], [], [], []],
        free_cells=[Card(7, "H"), None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    move_a = Move(LOCATION_CASCADE, 0, LOCATION_FREE_CELL, 0, 1)
    move_b = Move(LOCATION_CASCADE, 0, LOCATION_FREE_CELL, 1, 1)

    def fake_enumerate_legal_moves(_state):
        return [move_a, move_b]

    def fake_apply_move(_state, _move):
        return next_state.clone()

    monkeypatch.setattr(bfs_module.rules, "enumerate_legal_moves", fake_enumerate_legal_moves)
    monkeypatch.setattr(bfs_module.rules, "apply_move", fake_apply_move)
    monkeypatch.setattr(bfs_module.rules, "is_goal", lambda _state: False)

    result = solve_bfs(start, max_nodes=10, max_time_seconds=5.0)

    # Expected expansion sequence: start -> next_state (once).
    # If duplicate enqueue were allowed, expanded_nodes would be larger.
    assert result.solved is False
    assert result.metrics.expanded_nodes == 2


def test_bfs_prunes_immediate_inverse_move(monkeypatch):
    start = State(
        cascades=[[Card(7, "H")], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )
    after_forward = State(
        cascades=[[], [], [], [], [], [], [], []],
        free_cells=[Card(7, "H"), None, None, None],
        foundations={"H": 0, "D": 0, "C": 0, "S": 0},
    )

    forward = Move(LOCATION_CASCADE, 0, LOCATION_FREE_CELL, 0, 1)
    backward = Move(LOCATION_FREE_CELL, 0, LOCATION_CASCADE, 0, 1)

    calls = {"enumerate": 0, "apply": 0, "inverse": 0}

    original_is_inverse_move = bfs_module._is_inverse_move

    def fake_enumerate_legal_moves(state):
        calls["enumerate"] += 1
        if state == start:
            return [forward]
        return [backward]

    def fake_apply_move(state, move):
        calls["apply"] += 1
        if state == start and move == forward:
            return after_forward.clone()
        if state == after_forward and move == backward:
            return start.clone()
        raise AssertionError("Unexpected move application in test")

    def tracked_inverse(move, previous_move):
        calls["inverse"] += 1
        return original_is_inverse_move(move, previous_move)

    monkeypatch.setattr(bfs_module.rules, "enumerate_legal_moves", fake_enumerate_legal_moves)
    monkeypatch.setattr(bfs_module.rules, "apply_move", fake_apply_move)
    monkeypatch.setattr(bfs_module.rules, "is_goal", lambda _state: False)
    monkeypatch.setattr(bfs_module, "_is_inverse_move", tracked_inverse)

    result = solve_bfs(start, max_nodes=10, max_time_seconds=5.0)

    # Backward move is generated but must be pruned before enqueue/expansion.
    assert result.solved is False
    assert calls["enumerate"] == 2
    assert calls["apply"] == 2
    assert calls["inverse"] >= 1
    assert result.metrics.expanded_nodes == 2
