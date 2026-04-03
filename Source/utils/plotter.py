import csv
import math
import textwrap
import matplotlib.pyplot as plt
from collections import defaultdict


SINGLE_BAR_COLOR = "#1f4e9a"

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
    fig, ax = plt.subplots(figsize=(10, 6), dpi=160)

    bars = ax.bar(labels, values, color=SINGLE_BAR_COLOR, edgecolor="#15396e", linewidth=0.9)

    ax.set_title(title, fontsize=15, weight="bold", pad=12)
    ax.set_xlabel("Algorithm", fontsize=11)
    ax.set_ylabel(ylabel, fontsize=11)
    ax.grid(axis="y", linestyle="--", linewidth=0.7, alpha=0.35)
    ax.set_axisbelow(True)

    # Keep percent chart in [0, 100]; for others, add headroom for labels.
    if ylabel == "%":
        ax.set_ylim(0, 100)
    else:
        max_val = max(values) if values else 0
        ax.set_ylim(0, max_val * 1.18 if max_val > 0 else 1)

    # Hide top/right spines to reduce visual clutter.
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Value labels with metric-aware formatting.
    for bar, value in zip(bars, values):
        if ylabel == "%":
            text = f"{value:.1f}%"
        elif ylabel == "Seconds":
            text = f"{value:.2f}s"
        elif ylabel == "MB":
            text = f"{value:.1f}"
        elif ylabel == "Nodes":
            text = f"{value:,.0f}"
        elif ylabel == "Steps":
            text = f"{value:.1f}"
        else:
            text = f"{value:.2f}"

        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            text,
            ha="center",
            va="bottom",
            fontsize=9,
            color="#111111",
        )

    fig.tight_layout()
    fig.savefig(output_file)
    plt.close(fig)


def _normalize_values(values, higher_is_better):
    min_val = min(values)
    max_val = max(values)
    if max_val == min_val:
        return [1.0 for _ in values]

    if higher_is_better:
        return [(v - min_val) / (max_val - min_val) for v in values]
    return [(max_val - v) / (max_val - min_val) for v in values]


def plot_overview_radar(summary, output_file):
    if not summary:
        return

    algorithms = list(summary.keys())
    metric_specs = [
        ("Success Rate", "success_rate", True),
        ("Few Nodes", "avg_expanded_nodes", False),
        ("Speed", "avg_time", False),
        ("Low Memory", "avg_memory_mb", False),
        ("Few Steps", "avg_solution_steps", False),
    ]

    normalized = {algo: {} for algo in algorithms}
    for label, key, higher_is_better in metric_specs:
        raw_values = [summary[algo][key] for algo in algorithms]
        scaled = _normalize_values(raw_values, higher_is_better)
        for algo, value in zip(algorithms, scaled):
            normalized[algo][label] = value

    metric_labels = [item[0] for item in metric_specs]
    axis_count = len(metric_labels)
    base_angles = [n / float(axis_count) * 2 * math.pi for n in range(axis_count)]
    angles = base_angles + base_angles[:1]

    fig = plt.figure(figsize=(8.0, 6.4), dpi=180)
    fig.patch.set_facecolor("#ffffff")
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor("#ffffff")

    ax.set_theta_offset(math.pi / 2)
    ax.set_theta_direction(-1)
    ax.set_xticks(base_angles)
    ax.set_xticklabels(metric_labels, color="#1f2937", fontsize=11)

    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["", "", "", "", ""])
    ax.grid(color="#d1d5db", alpha=0.9, linewidth=0.8)
    ax.spines["polar"].set_color("#9ca3af")
    ax.spines["polar"].set_alpha(0.8)

    palette = ["#46a0ff", "#d89b2b", "#70c24a", "#6f5be3", "#f87171", "#14b8a6"]

    for idx, algo in enumerate(algorithms):
        values = [normalized[algo][metric] for metric in metric_labels]
        values = values + values[:1]
        color = palette[idx % len(palette)]
        ax.plot(
            angles,
            values,
            color=color,
            linewidth=2.2,
            marker="o",
            markersize=4.5,
            label=algo.upper(),
        )
        ax.fill(angles, values, color=color, alpha=0.07)

    ax.set_title("Overview Performance Radar", color="#111827", fontsize=14, pad=18, weight="bold")

    legend = ax.legend(
        loc="lower center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=min(4, len(algorithms)),
        frameon=False,
        fontsize=10,
        handlelength=1.8,
        handletextpad=0.5,
        columnspacing=1.3,
    )
    for text in legend.get_texts():
        text.set_color("#1f2937")

    fig.tight_layout()
    fig.savefig(output_file, facecolor=fig.get_facecolor())
    plt.close(fig)


def _hex_to_rgb01(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def _mix_colors(c1, c2, t):
    return tuple((1 - t) * a + t * b for a, b in zip(c1, c2))


def _normalize_linear(values, higher_is_better):
    v_min = min(values)
    v_max = max(values)
    if v_max == v_min:
        return [0.5 for _ in values]
    if higher_is_better:
        return [(v - v_min) / (v_max - v_min) for v in values]
    return [(v_max - v) / (v_max - v_min) for v in values]


def plot_summary_table(summary, output_file):
    if not summary:
        return

    algo_order = ["bfs", "dfs", "ucs", "a_star"]
    algorithms = [a for a in algo_order if a in summary] + [a for a in summary if a not in algo_order]
    algo_labels = [a.upper() if a != "a_star" else "A*" for a in algorithms]

    metric_specs = [
        ("Peak Memory (avg)", "avg_memory_mb", False, lambda v: f"{v:.1f} MB"),
        ("Expanded Nodes\n(avg)", "avg_expanded_nodes", False, lambda v: f"{v:,.0f}"),
        ("Runtime (avg)", "avg_time", False, lambda v: f"{v:.2f} s"),
        ("Solution Steps (avg)", "avg_solution_steps", False, lambda v: f"{v:.1f}"),
        ("Success Rate", "success_rate", True, lambda v: f"{v * 100:.0f}%"),
    ]

    # Base palette close to requested style.
    header_blue = _hex_to_rgb01("#1f4e79")
    metric_gray = _hex_to_rgb01("#d9d9d9")
    best_green = _hex_to_rgb01("#d9ead3")
    worst_red = _hex_to_rgb01("#f4d6d2")

    cell_text = [["Metric", *algo_labels]]
    cell_colors = [[header_blue for _ in range(len(algo_labels) + 1)]]

    for metric_label, key, higher_is_better, formatter in metric_specs:
        values = [summary[a][key] for a in algorithms]
        scores = _normalize_linear(values, higher_is_better)

        row_text = [metric_label]
        row_colors = [metric_gray]
        for val, score in zip(values, scores):
            row_text.append(formatter(val))
            # score 0 -> worst_red, score 1 -> best_green
            row_colors.append(_mix_colors(worst_red, best_green, score))

        cell_text.append(row_text)
        cell_colors.append(row_colors)

    fig, ax = plt.subplots(figsize=(10.2, 3.6), dpi=170)
    ax.axis("off")

    table = ax.table(
        cellText=cell_text,
        cellColours=cell_colors,
        cellLoc="center",
        colLoc="center",
        loc="center",
        bbox=[0.03, 0.16, 0.94, 0.80],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    # Style cells.
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#b7b7b7")
        cell.set_linewidth(0.4)
        if row == 0:
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
            cell.get_text().set_fontsize(10)
        elif col == 0:
            cell.get_text().set_weight("bold")
            cell.get_text().set_ha("left")

    fig.tight_layout()
    fig.savefig(output_file, facecolor="white")
    plt.close(fig)


def _rank_map(summary, key, higher_is_better):
    items = [(algo, summary[algo][key]) for algo in summary]
    items.sort(key=lambda x: x[1], reverse=higher_is_better)
    return {algo: idx + 1 for idx, (algo, _) in enumerate(items)}


def _algo_display_name(algo):
    return "A*" if algo == "a_star" else algo.upper()


def _build_strengths_and_weaknesses(summary, algo):
    rank_time = _rank_map(summary, "avg_time", higher_is_better=False)
    rank_memory = _rank_map(summary, "avg_memory_mb", higher_is_better=False)
    rank_nodes = _rank_map(summary, "avg_expanded_nodes", higher_is_better=False)
    rank_steps = _rank_map(summary, "avg_solution_steps", higher_is_better=False)
    rank_success = _rank_map(summary, "success_rate", higher_is_better=True)

    candidates_good = [
        (rank_success[algo], f"High success ({summary[algo]['success_rate'] * 100:.0f}%)"),
        (rank_time[algo], f"Fast runtime ({summary[algo]['avg_time']:.2f}s)"),
        (rank_memory[algo], f"Low memory ({summary[algo]['avg_memory_mb']:.1f} MB)"),
        (rank_nodes[algo], f"Few nodes ({summary[algo]['avg_expanded_nodes']:,.0f})"),
        (rank_steps[algo], f"Short solutions ({summary[algo]['avg_solution_steps']:.1f})"),
    ]
    candidates_bad = [
        (-rank_success[algo], f"Low success ({summary[algo]['success_rate'] * 100:.0f}%)"),
        (-rank_time[algo], f"Slow runtime ({summary[algo]['avg_time']:.2f}s)"),
        (-rank_memory[algo], f"High memory ({summary[algo]['avg_memory_mb']:.1f} MB)"),
        (-rank_nodes[algo], f"Many nodes ({summary[algo]['avg_expanded_nodes']:,.0f})"),
        (-rank_steps[algo], f"Long solutions ({summary[algo]['avg_solution_steps']:.1f})"),
    ]

    candidates_good.sort(key=lambda x: x[0])
    candidates_bad.sort(key=lambda x: x[0])

    strength_text = ", ".join([candidates_good[0][1], candidates_good[1][1]])
    weakness_text = ", ".join([candidates_bad[0][1], candidates_bad[1][1]])
    return strength_text, weakness_text


def plot_algorithm_guidance_table(summary, output_file):
    if not summary:
        return

    algo_order = ["bfs", "dfs", "ucs", "a_star"]
    algorithms = [a for a in algo_order if a in summary] + [a for a in summary if a not in algo_order]

    best_when = {
        "bfs": "Step-optimal path needed;\nresources are sufficient",
        "dfs": "Memory is limited;\nflexible on runtime",
        "ucs": "Cost-sensitive search\nwithout heuristic",
        "a_star": "General purpose;\nbalanced speed and quality",
    }

    header = ["Algo", "Strengths", "Weaknesses", "Best Used When"]
    rows = [header]
    for algo in algorithms:
        strengths, weaknesses = _build_strengths_and_weaknesses(summary, algo)
        strengths = textwrap.fill(strengths, width=30)
        weaknesses = textwrap.fill(weaknesses, width=30)
        usage_text = textwrap.fill(best_when.get(algo, "Depends on constraints"), width=28)
        rows.append(
            [
                _algo_display_name(algo),
                strengths,
                weaknesses,
                usage_text,
            ]
        )

    # Table palette close to the sample style.
    header_blue = "#1f4e79"
    default_bg = "#f5f5f5"
    algo_bg = {
        "BFS": "#d6e3f3",
        "DFS": "#efe4bf",
        "UCS": "#e4e4e4",
        "A*": "#dce9d5",
    }

    colors = [[header_blue, header_blue, header_blue, header_blue]]
    for row in rows[1:]:
        colors.append([algo_bg.get(row[0], "#e8eef5"), default_bg, default_bg, default_bg])

    fig, ax = plt.subplots(figsize=(12.6, 4.8), dpi=190)
    ax.axis("off")

    table = ax.table(
        cellText=rows,
        cellColours=colors,
        colWidths=[0.13, 0.29, 0.29, 0.29],
        cellLoc="left",
        colLoc="center",
        loc="center",
        bbox=[0.02, 0.08, 0.96, 0.86],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10.4)

    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#b2b9c2")
        cell.set_linewidth(0.55)
        cell.PAD = 0.085

        if r == 0:
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
            cell.get_text().set_ha("center")
            cell.get_text().set_fontsize(11.2)
            cell.get_text().set_va("center")
        else:
            if c == 0:
                cell.get_text().set_weight("bold")
                cell.get_text().set_ha("center")
                cell.get_text().set_va("center")
                cell.get_text().set_fontsize(11)
            elif c == 1:
                cell.get_text().set_color("#244f11")
                cell.get_text().set_ha("left")
                cell.get_text().set_va("center")
            elif c == 2:
                cell.get_text().set_color("#8f1f1f")
                cell.get_text().set_ha("left")
                cell.get_text().set_va("center")
            elif c == 3:
                cell.get_text().set_style("italic")
                cell.get_text().set_ha("left")
                cell.get_text().set_va("center")

    # Increase row height for readability with wrapped text.
    table.scale(1.0, 1.45)

    fig.tight_layout()
    fig.savefig(output_file, facecolor="white")
    plt.close(fig)