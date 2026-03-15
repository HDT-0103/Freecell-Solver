from __future__ import annotations

import time
import tracemalloc
from dataclasses import dataclass
from typing import Callable, List, Tuple, TypeVar


T = TypeVar("T")


@dataclass
class SearchMetrics:
	elapsed_seconds: float
	peak_memory_bytes: int
	expanded_nodes: int = 0
	solution_steps: int = 0

	@property
	def peak_memory_mb(self) -> float:
		return self.peak_memory_bytes / (1024.0 * 1024.0)


def measure_search(search_fn: Callable[[], Tuple[bool, List[T], int]]) -> Tuple[bool, List[T], int, SearchMetrics]:
	"""Measure runtime and peak memory for a search routine."""
	tracemalloc.start()
	t0 = time.perf_counter()
	solved, moves, expanded_nodes = search_fn()
	elapsed = time.perf_counter() - t0
	_, peak = tracemalloc.get_traced_memory()
	tracemalloc.stop()

	metrics = SearchMetrics(
		elapsed_seconds=elapsed,
		peak_memory_bytes=peak,
		expanded_nodes=expanded_nodes,
		solution_steps=len(moves),
	)
	return solved, moves, expanded_nodes, metrics
