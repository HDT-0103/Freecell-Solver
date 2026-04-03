import csv
import os
import glob
import time
from dataclasses import dataclass

from Source.core.game_service import FreeCellGame
from Source.core.loader import load_game_from_json
from Source.solvers.a_star import AStarSearchSession, solve_a_star
from Source.solvers.bfs import solve_bfs
from Source.solvers.dfs import solve_dfs
from Source.solvers.ucs import solve_ucs
from Source.utils.metrics import SearchMetrics


DEFAULT_SOLVER_STAGES = [
    (120_000, 6.0),
    (250_000, 10.0),
    (500_000, 18.0),
    (900_000, 28.0),
]

A_STAR_STAGES = [
    (250_000, 10.0),
    (500_000, 20.0),
    (1_000_000, 35.0),
    (2_000_000, 50.0),
]

MAX_STAGE_RETRIES = 40


@dataclass
class BenchmarkSearchResult:
    solved: bool
    moves: list
    state_path: list
    metrics: SearchMetrics


def collect_board_path(base_dir):
    board_paths = sorted(glob.glob(os.path.join(base_dir, "game_*.json")))
    if not board_paths:
        raise FileNotFoundError(f"No game files found in {base_dir}")
    return board_paths


def load_state(board_path):
    game = FreeCellGame()
    success = load_game_from_json(board_path, game)

    if not success:
        raise ValueError(f"Load failed for {board_path}")

    return game.get_state()


def run_algorithm(state, algorithm_name, max_nodes=300000, max_time_seconds=30):
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


def _run_a_star_staged(state):
    print("  [a_star] start staged search", flush=True)
    session = AStarSearchSession(
        state,
        heuristic="blocking",
        heuristic_weight=3.0,
    )
    result = None
    for stage_no, (max_nodes, max_time_seconds) in enumerate(A_STAR_STAGES, start=1):
        print(
            f"  [a_star] stage {stage_no}/{len(A_STAR_STAGES)} "
            f"(max_nodes={max_nodes}, max_time={max_time_seconds}s)",
            flush=True,
        )
        result = session.advance(max_nodes=max_nodes, max_time_seconds=max_time_seconds)
        print(
            f"  [a_star] stage {stage_no} done: solved={result.solved}, "
            f"expanded={result.metrics.expanded_nodes}, elapsed={result.metrics.elapsed_seconds:.2f}s",
            flush=True,
        )
        if result.solved or session.exhausted:
            break

    if result is None:
        return solve_a_star(state, "blocking", 250_000, 10.0, 3.0)
    return result


def _run_graph_solver_staged(initial_state, algorithm_name):
    print(f"  [{algorithm_name}] start staged search", flush=True)
    current_state = initial_state.clone()
    stage_idx = 0
    retries = 0

    total_elapsed = 0.0
    total_expanded = 0
    peak_memory_bytes = 0

    state_path = [current_state.clone()]
    solved = False

    while stage_idx < len(DEFAULT_SOLVER_STAGES) and retries < MAX_STAGE_RETRIES:
        max_nodes, max_time_seconds = DEFAULT_SOLVER_STAGES[stage_idx]
        stage_no = stage_idx + 1
        print(
            f"  [{algorithm_name}] stage {stage_no}/{len(DEFAULT_SOLVER_STAGES)} "
            f"retry={retries + 1}/{MAX_STAGE_RETRIES} "
            f"(max_nodes={max_nodes}, max_time={max_time_seconds}s)",
            flush=True,
        )

        result = run_algorithm(
            current_state,
            algorithm_name,
            max_nodes=max_nodes,
            max_time_seconds=max_time_seconds,
        )

        print(
            f"  [{algorithm_name}] stage {stage_no} done: solved={result.solved}, "
            f"expanded={result.metrics.expanded_nodes}, elapsed={result.metrics.elapsed_seconds:.2f}s, "
            f"steps={result.metrics.solution_steps}",
            flush=True,
        )

        total_elapsed += result.metrics.elapsed_seconds
        total_expanded += result.metrics.expanded_nodes
        peak_memory_bytes = max(peak_memory_bytes, result.metrics.peak_memory_bytes)

        if result.solved:
            solved = True
            if len(result.state_path) > 1:
                state_path.extend(result.state_path[1:])
            break

        progressed = len(result.state_path) > 1
        if progressed:
            state_path.extend(result.state_path[1:])
            current_state = result.state_path[-1].clone()
            # Match UI behavior: if we made progress, restart at the first stage.
            stage_idx = 0
        else:
            stage_idx += 1

        retries += 1

    print(
        f"  [{algorithm_name}] finished: solved={solved}, total_elapsed={total_elapsed:.2f}s, "
        f"total_expanded={total_expanded}, total_steps={max(0, len(state_path) - 1)}",
        flush=True,
    )

    metrics = SearchMetrics(
        elapsed_seconds=total_elapsed,
        peak_memory_bytes=peak_memory_bytes,
        expanded_nodes=total_expanded,
        solution_steps=max(0, len(state_path) - 1),
    )
    return BenchmarkSearchResult(
        solved=solved,
        moves=[],
        state_path=state_path,
        metrics=metrics,
    )


def run_algorithm_benchmark_mode(state, algorithm_name):
    algorithm_name = algorithm_name.lower()
    if algorithm_name == "a_star":
        return _run_a_star_staged(state)
    return _run_graph_solver_staged(state, algorithm_name)


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
    print(f"\n=== Benchmark board: {board_id} ===", flush=True)
    for algorithm in algorithms:
        started = time.perf_counter()
        print(f"\n-> Running algorithm: {algorithm}", flush=True)
        state = load_state(board_path)
        result = run_algorithm_benchmark_mode(state, algorithm)
        wall_time = time.perf_counter() - started
        row = extract_row(board_id, algorithm, result)
        rows.append(row)
        print(
            f"<- Done {algorithm}: solved={result.solved}, wall_time={wall_time:.2f}s, "
            f"measured_elapsed={result.metrics.elapsed_seconds:.2f}s",
            flush=True,
        )
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
