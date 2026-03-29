import csv
import os

from Source.core.game_service import FreeCellGame
from Source.core.loader import load_game_from_json
from Source.solvers.a_star import solve_a_star
from Source.solvers.bfs import solve_bfs
from Source.solvers.dfs import solve_dfs
from Source.solvers.ucs import solve_ucs


def collect_board_path(base_dir):
    board_names = ["game_00.json", "game_01.json", "game_02.json"]
    board_paths = [os.path.join(base_dir, board_name) for board_name in board_names]

    missing_paths = [path for path in board_paths if not os.path.exists(path)]
    if missing_paths:
        missing = ", ".join(missing_paths)
        raise FileNotFoundError(f"Missing benchmark boards: {missing}")

    return board_paths


def load_state(board_path):
    game = FreeCellGame()
    success = load_game_from_json(board_path, game)

    if not success:
        raise ValueError(f"Load failed for {board_path}")

    return game.get_state()


def run_algorithm(state, algorithm_name, max_nodes=30000, max_time_seconds=15):
    algorithm_name = algorithm_name.lower()
    if algorithm_name == "bfs":
        return solve_bfs(state, max_nodes, max_time_seconds)
    elif algorithm_name == "dfs":
        return solve_dfs(state, max_nodes, max_time_seconds)
    elif algorithm_name == "ucs":
        return solve_ucs(state, max_nodes, max_time_seconds)
    elif algorithm_name == "a_star":
        return solve_a_star(state, "foundation_gap", max_nodes, max_time_seconds)
    else:
        raise ValueError(f"Unknown algorithm: {algorithm_name}")


def extract_row(board_id, algorithm_name, result):
    return {
        "board_id": board_id,
        "algorithm": algorithm_name,
        "solved": result.solved,
        "elapsed_seconds": result.metrics.elapsed_seconds,
        "peak_memory_bytes": result.metrics.peak_memory_bytes,
        "expanded_nodes": result.metrics.expanded_nodes,
        "solution_steps": result.metrics.solution_steps,
    }


def benchmark_one_board(board_path):
    algorithms = ["bfs", "dfs", "ucs", "a_star"]
    rows = []
    board_id = os.path.basename(board_path).replace(".json", "")
    for algorithm in algorithms:
        state = load_state(board_path)
        result = run_algorithm(state, algorithm)
        row = extract_row(board_id, algorithm, result)
        rows.append(row)
    return rows


def write_csv(rows, output_path):
    if not rows:
        print("No data to write.")
        return

    fields_name = [
        "board_id",
        "algorithm",
        "solved",
        "elapsed_seconds",
        "peak_memory_bytes",
        "expanded_nodes",
        "solution_steps",
    ]
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields_name)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Save result to {output_path}")
