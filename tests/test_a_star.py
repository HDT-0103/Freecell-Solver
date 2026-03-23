import pytest
from Source.core.rules import LOCATION_FOUNDATION
from Source.core.state import Card, State
from Source.solvers.a_star import (
    HEURISTICS,
    get_heuristic,
    heuristic_blocking,
    heuristic_foundation_gap,
    solve_a_star,
)


def test_builtin_heuristics_return_expected_values():
    state = State(
        cascades=[
            [Card(4, 'S'), Card(1, 'H')],
            [],
            [],
            [],
            [],
            [],
            [],
            [],
        ],
        free_cells=[Card(13, 'C'), None, None, None],
        foundations={'H': 0, 'D': 0, 'C': 0, 'S': 0},
    )

    assert heuristic_foundation_gap(state) == 52
    assert heuristic_blocking(state) == 52


def test_builtin_heuristics_registry_only_exposes_supported_options():
    assert set(HEURISTICS) == {'foundation_gap', 'blocking'}


def test_get_heuristic_supports_names_and_callables():
    name, fn = get_heuristic('blocking')
    custom_name, custom_fn = get_heuristic(lambda state: 7)

    assert name == 'blocking'
    assert fn is HEURISTICS['blocking']
    assert custom_name == '<lambda>'
    assert custom_fn(State([[] for _ in range(8)])) == 7


def test_get_heuristic_rejects_unknown_name():
    with pytest.raises(ValueError):
        get_heuristic('not_registered')


@pytest.mark.parametrize('heuristic_name', ['foundation_gap', 'blocking'])
def test_solve_a_star_finds_single_foundation_move(heuristic_name):
    initial_state = State(
        cascades=[[Card(13, 'S')], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 12},
    )

    result = solve_a_star(initial_state, heuristic=heuristic_name)

    assert result.solved is True
    assert result.heuristic_name == heuristic_name
    assert len(result.moves) == 1
    assert result.moves[0].dst_type == LOCATION_FOUNDATION
    assert result.state_path[-1].foundations['S'] == 13


@pytest.mark.parametrize('heuristic_name', ['foundation_gap', 'blocking'])
def test_solve_a_star_reconstructs_two_step_solution(heuristic_name):
    initial_state = State(
        cascades=[[Card(12, 'S')], [Card(13, 'S')], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 11},
    )

    result = solve_a_star(initial_state, heuristic=heuristic_name)

    assert result.solved is True
    assert len(result.moves) == 2
    assert [move.dst_type for move in result.moves] == [LOCATION_FOUNDATION, LOCATION_FOUNDATION]
    assert result.state_path[0] == initial_state
    assert result.state_path[-1].foundations['S'] == 13


def test_solve_a_star_supports_custom_callable_heuristic():
    initial_state = State(
        cascades=[[Card(13, 'S')], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 12},
    )

    result = solve_a_star(initial_state, heuristic=lambda state: 0)

    assert result.solved is True
    assert result.heuristic_name == '<lambda>'


def test_solve_a_star_reports_unsolved_when_node_budget_is_zero():
    initial_state = State(
        cascades=[[Card(12, 'S')], [Card(13, 'S')], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 11},
    )

    result = solve_a_star(initial_state, heuristic='foundation_gap', max_nodes=0)

    assert result.solved is False
    assert result.moves == []
    assert len(result.state_path) == 1


def test_solve_a_star_returns_best_progress_path_when_budget_is_tight():
    initial_state = State(
        cascades=[
            [Card(11, 'S')],
            [Card(13, 'S'), Card(12, 'H'), Card(12, 'S')],
            [],
            [],
            [],
            [],
            [],
            [],
        ],
        free_cells=[Card(13, 'H'), None, None, None],
        foundations={'H': 11, 'D': 13, 'C': 13, 'S': 10},
    )

    result = solve_a_star(initial_state, heuristic='blocking', max_nodes=1, heuristic_weight=2.0)

    assert result.solved is False
    assert len(result.moves) >= 1
    assert len(result.state_path) == len(result.moves) + 1
    assert result.state_path[0] == initial_state


def test_solve_a_star_rejects_non_positive_heuristic_weight():
    initial_state = State(
        cascades=[[Card(13, 'S')], [], [], [], [], [], [], []],
        free_cells=[None, None, None, None],
        foundations={'H': 13, 'D': 13, 'C': 13, 'S': 12},
    )

    with pytest.raises(ValueError):
        solve_a_star(initial_state, heuristic='foundation_gap', heuristic_weight=0)


def test_solver_handles_multi_step_blocked_endgame():
    initial_state = State(
        cascades=[
            [Card(11, 'S')],
            [Card(13, 'S'), Card(12, 'H'), Card(12, 'S')],
            [],
            [],
            [],
            [],
            [],
            [],
        ],
        free_cells=[Card(13, 'H'), None, None, None],
        foundations={'H': 11, 'D': 13, 'C': 13, 'S': 10},
    )

    result = solve_a_star(initial_state, heuristic='blocking')

    assert result.solved is True
    assert len(result.moves) == 5
    assert all(move.dst_type == LOCATION_FOUNDATION for move in result.moves)
    assert result.state_path[-1].foundations['S'] == 13
    assert result.state_path[-1].foundations['H'] == 13


def test_solve_a_star_accepts_state_loaded_from_gui_json_sample():
    import os
    import sys
    import importlib

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Source"))

    from config import SOLUTION_DIR
    from core import FreeCellGame
    from core.loader import load_game_from_json
    solver_module = importlib.import_module("solvers.a_star")

    game = FreeCellGame(seed=1)
    ok = load_game_from_json(f"{SOLUTION_DIR}/easy/game_01.json", game)

    assert ok is True

    result = solver_module.solve_a_star(game.get_state(), heuristic='foundation_gap', max_nodes=10)

    assert result.heuristic_name == 'foundation_gap'
    assert result.state_path[0] == game.get_state()
