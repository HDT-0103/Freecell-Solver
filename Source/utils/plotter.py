import csv
import matplotlib.pyplot as plt
from collections import defaultdict

def load_csv_data(csv_path):
    rows = []
    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def convert_types(rows):
    for row in rows:
        row["elapsed_seconds"] = float(row["elapsed_seconds"]) if row["elapsed_seconds"] else 0.0
        row["peak_memory_bytes"] = float(row["peak_memory_bytes"]) if row["peak_memory_bytes"] else 0.0
        row["peak_memory_mb"] = row["peak_memory_bytes"] / (1024 * 1024)
        row["expanded_nodes"] = int(row["expanded_nodes"]) if row["expanded_nodes"] else 0
        row["solution_steps"] = int(row["solution_steps"]) if row["solution_steps"] else 0
        row["solved"] = True if str(row["solved"]).lower() == "true" else False
    return rows

def group_by_algorithm(rows):
    grouped = defaultdict(list)
    for row in rows:
        algo = row["algorithm"]
        grouped[algo].append(row)
    return grouped

def compute_summary(grouped_data):
    summary = {}
    for algo, rows in grouped_data.items():
        n = len(rows)
        avg_time = sum(r["elapsed_seconds"] for r in rows) / n
        avg_memory = sum(r["peak_memory_mb"] for r in rows) / n
        avg_nodes = sum(r["expanded_nodes"] for r in rows) / n
        avg_steps = sum(r["solution_steps"] for r in rows) / n

        success_count = sum(1 for r in rows if r["solved"])
        success_rate = success_count / n

        summary[algo] = {
            "avg_time": avg_time,
            "avg_memory_mb": avg_memory,
            "avg_expanded_nodes": avg_nodes,
            "avg_solution_steps": avg_steps,
            "success_rate": success_rate
        }
    return summary

def plot_bar_chart(labels, values, title, ylabel, output_file):
    plt.figure()
    plt.bar(labels, values)
    plt.title(title)
    plt.xlabel("Algorithm")
    plt.ylabel(ylabel)
    if ylabel == "%":
        plt.ylim(0, 100)

    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()