from Source.core.state import Card, State
from Source.solvers.dfs import solve_dfs


def test_dfs_solves_last_card_to_win():
    """Chỉ còn 1 lá cuối — DFS phải giải được và solved=True."""
    state = State(
        cascades=[[Card(13, 'H')], [], [], [], [], [], [], []],
        foundations={'H': 12, 'D': 13, 'C': 13, 'S': 13},
    )

    result = solve_dfs(state, max_nodes=1000, max_time_seconds=5.0)

    assert result.solved is True
    assert len(result.moves) == 1


def test_dfs_returns_result_even_if_unsolved():
    """Ván phức tạp có thể không giải được trong giới hạn — nhưng không crash."""
    state = State.microsoft_shuffle(1)

    result = solve_dfs(state, max_nodes=5000, max_time_seconds=3.0)

    assert result is not None
    assert isinstance(result.solved, bool)
    assert isinstance(result.moves, list)


def test_dfs_state_path_consistent():
    """state_path phải có độ dài = số moves + 1."""
    state = State([[Card(1, 'H')], [], [], [], [], [], [], []])

    result = solve_dfs(state, max_nodes=1000, max_time_seconds=5.0)

    assert len(result.state_path) == len(result.moves) + 1


def test_dfs_respects_max_nodes():
    """DFS không vượt quá max_nodes."""
    state = State.microsoft_shuffle(2)

    result = solve_dfs(state, max_nodes=100, max_time_seconds=10.0)

    assert result.metrics.expanded_nodes <= 110