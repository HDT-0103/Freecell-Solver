# tests/test_dfs.py
import pytest
from Source.core.state import Card, State
from Source.solvers.dfs import solve_dfs

def test_dfs_solves_last_card_to_win():
    """Test ván bài chỉ còn 1 lá — IDS phải giải được ngay lập tức."""
    # Trạng thái gần thắng: 3 bộ đầy, bộ Cơ (H) có 12 lá, lá 13 nằm trong Cascade
    state = State(
        cascades=[[Card(13, 'H')], [], [], [], [], [], [], []],
        foundations={'H': 12, 'D': 13, 'C': 13, 'S': 13},
    )

    result = solve_dfs(state, max_nodes=1000, max_time_seconds=5.0)

    assert result.solved is True
    assert len(result.moves) == 1

def test_dfs_returns_result_even_if_unsolved():
    """Kiểm tra nếu ván quá khó, thuật toán không được crash mà phải trả về kết quả tốt nhất."""
    state = State.microsoft_shuffle(1) # Ván bài ngẫu nhiên

    result = solve_dfs(state, max_nodes=1000, max_time_seconds=1.0)

    assert result is not None
    assert isinstance(result.solved, bool)
    assert isinstance(result.moves, list)

def test_dfs_state_path_consistent():
    """Kiểm tra tính logic: state_path phải dài hơn số moves đúng 1 đơn vị (bao gồm cả state gốc)."""
    state = State([[Card(1, 'H')], [], [], [], [], [], [], []])
    result = solve_dfs(state, max_nodes=500)

    # Nếu giải được, đường đi trạng thái phải khớp với số nước đi
    assert len(result.state_path) == len(result.moves) + 1

def test_dfs_respects_max_nodes():
    """Kiểm tra xem IDS có tuân thủ giới hạn duyệt node (max_nodes) không."""
    state = State.microsoft_shuffle(1)
    limit = 100
    result = solve_dfs(state, max_nodes=limit)

    # Số node đã duyệt có thể nhỉnh hơn limit một chút do IDS duyệt nốt tầng hiện tại
    assert result.metrics.expanded_nodes <= limit + 50