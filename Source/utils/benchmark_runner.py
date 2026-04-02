"""Benchmark mode runner.

Contains the benchmark + chart pipeline used by main entrypoint.
"""
from __future__ import annotations

import os

from Source.utils.benchmark import benchmark_one_board, collect_board_path, write_csv
from Source.utils.plotter import (
    compute_summary,
    convert_types,
    group_by_algorithm,
    load_csv_data,
    plot_bar_chart,
)

DEFAULT_BOARD_DIR = "Source/assets/solution/easy"
BENCHMARK_ASSET_DIR = "Source/assets/benchmark"
DEFAULT_BENCHMARK_CSV = os.path.join(BENCHMARK_ASSET_DIR, "benchmark_result.csv")


def _print_summary(summary: dict) -> None:
    print("\n=== SUMMARY ===")
    for algo, stats in summary.items():
        print(algo, stats)


def _plot_summary(summary: dict) -> None:
    labels = list(summary.keys())

    # 1. Runtime
    plot_bar_chart(
        labels,
        [summary[a]["avg_time"] for a in labels],
        "Average Runtime by Algorithm",
        "Seconds",
        os.path.join(BENCHMARK_ASSET_DIR, "runtime.png"),
    )

    # 2. Memory
    plot_bar_chart(
        labels,
        [summary[a]["avg_memory_mb"] for a in labels],
        "Average Memory Usage",
        "MB",
        os.path.join(BENCHMARK_ASSET_DIR, "memory.png"),
    )

    # 3. Expanded nodes
    plot_bar_chart(
        labels,
        [summary[a]["avg_expanded_nodes"] for a in labels],
        "Average Expanded Nodes",
        "Nodes",
        os.path.join(BENCHMARK_ASSET_DIR, "nodes.png"),
    )

    # 4. Success rate
    plot_bar_chart(
        labels,
        [summary[a]["success_rate"] * 100 for a in labels],
        "Success Rate",
        "%",
        os.path.join(BENCHMARK_ASSET_DIR, "success.png"),
    )


def run_benchmark_mode() -> None:
    os.makedirs(BENCHMARK_ASSET_DIR, exist_ok=True)

    board_paths = collect_board_path(DEFAULT_BOARD_DIR)
    all_rows = []

    for path in board_paths:
        print(f"Benchmarking {path}")
        row = benchmark_one_board(path)
        all_rows.extend(row)

    write_csv(all_rows, DEFAULT_BENCHMARK_CSV)

    rows = load_csv_data(DEFAULT_BENCHMARK_CSV)
    rows = convert_types(rows)
    grouped = group_by_algorithm(rows)

    for algo, data in grouped.items():
        print(f"{algo}: {len(data)} samples")

    summary = compute_summary(grouped)
    _print_summary(summary)
    _plot_summary(summary)
