"""
Trade-off Plot & Pareto Analysis Generator (Phase 17)

Produces publication-quality Pareto optimality trade-off plots,
deadline adherence comparisons, and online learning convergence curves:
- logs/benchmark_results/pareto_tradeoff.png
- logs/benchmark_results/energy_latency_tradeoff.png
- logs/benchmark_results/bandit_convergence.png
"""

import os
import sys
import csv
import json
from typing import Dict, Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import matplotlib
    matplotlib.use("Agg")  # Headless backend
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from benchmarks.run_benchmarks import BenchmarkHarness


def load_or_run_benchmarks(data_dir: str = "logs/benchmark_results") -> List[Dict[str, Any]]:
    """Loads benchmark CSV records or runs harness if missing."""
    csv_path = os.path.join(data_dir, "benchmark_runs.csv")
    if not os.path.exists(csv_path):
        print("Benchmark records not found. Running benchmark harness...")
        harness = BenchmarkHarness(output_dir=data_dir)
        harness.run_benchmark(num_windows=50)

    records = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            records.append({
                "window_id": int(r["window_id"]),
                "strategy": r["strategy"],
                "codec": r["codec"],
                "ratio": float(r["ratio"]),
                "energy_uj": float(r["energy_uj"]),
                "energy_per_raw_byte": float(r["energy_per_raw_byte"]),
                "exec_time_ms": float(r["exec_time_ms"]),
                "total_latency_ms": float(r["total_latency_ms"]),
                "deadline_met": int(r["deadline_met"])
            })
    return records


def generate_pareto_plot(records: List[Dict[str, Any]], output_path: str) -> None:
    """Generates Compression Ratio vs. Energy per Byte Pareto plot."""
    if not HAS_MATPLOTLIB:
        print("matplotlib not available; skipping graphical plot generation.")
        return

    # Group by strategy
    strategies = {}
    for r in records:
        s = r["strategy"]
        if s not in strategies:
            strategies[s] = {"ratios": [], "energies": []}
        strategies[s]["ratios"].append(r["ratio"])
        strategies[s]["energies"].append(r["energy_per_raw_byte"])

    plt.figure(figsize=(9, 6), dpi=150)
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    colors = {
        "static_raw": "#888888",
        "static_fast": "#3498db",
        "static_high_ratio": "#e67e22",
        "static_heuristic": "#9b59b6",
        "adaptive_bandit": "#2ecc71"
    }
    markers = {
        "static_raw": "x",
        "static_fast": "s",
        "static_high_ratio": "^",
        "static_heuristic": "d",
        "adaptive_bandit": "o"
    }

    for strat, data in strategies.items():
        mean_ratio = sum(data["ratios"]) / len(data["ratios"])
        mean_energy = sum(data["energies"]) / len(data["energies"])
        marker = markers.get(strat, "o")
        scatter_kwargs = {
            "color": colors.get(strat, "#333333"),
            "marker": marker,
            "s": 160,
            "label": f"{strat.replace('_', ' ').title()} ({mean_ratio:.2f}x, {mean_energy:.4f} uJ/B)",
            "linewidth": 1.2,
            "zorder": 4
        }
        if marker != "x":
            scatter_kwargs["edgecolors"] = "black"
        plt.scatter(mean_energy, mean_ratio, **scatter_kwargs)

    plt.title("Multi-Objective Pareto Trade-off: Compression Ratio vs. Energy per Byte", fontsize=13, fontweight="bold", pad=12)
    plt.xlabel("Energy Consumed per Raw Byte (uJ / byte) [Lower is Better]", fontsize=11)
    plt.ylabel("Compression Ratio (x) [Higher is Better]", fontsize=11)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(frameon=True, facecolor="white", edgecolor="#cccccc", fontsize=9, loc="best")
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Pareto plot: {output_path}")


def generate_deadline_and_latency_plot(records: List[Dict[str, Any]], output_path: str) -> None:
    """Generates bar chart comparing Deadline Adherence Rate & Mean Total Latency."""
    if not HAS_MATPLOTLIB:
        return

    strategies = {}
    for r in records:
        s = r["strategy"]
        if s not in strategies:
            strategies[s] = {"latencies": [], "deadlines": []}
        strategies[s]["latencies"].append(r["total_latency_ms"])
        strategies[s]["deadlines"].append(r["deadline_met"])

    strats = list(strategies.keys())
    deadline_pcts = [sum(strategies[s]["deadlines"]) / len(strategies[s]["deadlines"]) * 100.0 for s in strats]
    mean_latencies = [sum(strategies[s]["latencies"]) / len(strategies[s]["latencies"]) for s in strats]

    fig, ax1 = plt.subplots(figsize=(10, 5.5), dpi=150)
    x = range(len(strats))

    color = "#2980b9"
    bars = ax1.bar(x, deadline_pcts, width=0.45, color=color, alpha=0.85, label="Deadline Met (%)")
    ax1.set_ylabel("Deadline Adherence Rate (%)", color=color, fontsize=11, fontweight="bold")
    ax1.set_ylim(0, 110)
    ax1.set_xticks(x)
    ax1.set_xticklabels([s.replace("_", "\n").title() for s in strats], fontsize=10)
    ax1.tick_params(axis="y", labelcolor=color)

    for bar in bars:
        h = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2.0, h + 2.0, f"{h:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    ax2 = ax1.twinx()
    color2 = "#e74c3c"
    ax2.plot(x, mean_latencies, color=color2, marker="o", linewidth=2.5, markersize=8, label="Mean Total Latency (ms)")
    ax2.set_ylabel("Total Latency: Compute + Transfer (ms)", color=color2, fontsize=11, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.grid(False)

    plt.title("Deadline Adherence & Latency Comparison across Compression Strategies", fontsize=12, fontweight="bold", pad=12)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Deadline/Latency plot: {output_path}")


def generate_bandit_convergence_plot(records: List[Dict[str, Any]], output_path: str) -> None:
    """Generates rolling reward convergence plot for Adaptive Bandit."""
    if not HAS_MATPLOTLIB:
        return

    bandit_runs = [r for r in records if r["strategy"] == "adaptive_bandit"]
    if not bandit_runs:
        return

    # Calculate rolling reward
    rewards = []
    for r in bandit_runs:
        # Standard utility: 0.4*ratio - 0.3*energy_norm - 0.3*latency_norm
        reward = (0.4 * r["ratio"]) - (0.3 * (r["energy_uj"] / 5000.0)) - (0.3 * (r["total_latency_ms"] / 20.0))
        rewards.append(reward)

    window = 5
    rolling_avg = []
    for i in range(len(rewards)):
        start = max(0, i - window + 1)
        rolling_avg.append(sum(rewards[start:i + 1]) / (i - start + 1))

    plt.figure(figsize=(9, 4.5), dpi=150)
    plt.plot(range(1, len(rewards) + 1), rewards, color="#bdc3c7", alpha=0.6, label="Instantaneous Window Utility")
    plt.plot(range(1, len(rolling_avg) + 1), rolling_avg, color="#27ae60", linewidth=2.5, label=f"Rolling Average Utility (W={window})")

    plt.title("Online Contextual Bandit Learning Convergence & Regret Minimization", fontsize=12, fontweight="bold", pad=10)
    plt.xlabel("Transmission Cycle / Window ID", fontsize=10)
    plt.ylabel("Multi-Objective Utility Reward", fontsize=10)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(loc="lower right", frameon=True)
    plt.tight_layout()

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    plt.savefig(output_path)
    plt.close()
    print(f"Generated Bandit convergence plot: {output_path}")


def main():
    print("=== Generating Empirical Evaluation Trade-off Plots (Phase 17) ===")
    records = load_or_run_benchmarks()
    out_dir = "logs/benchmark_results"

    pareto_img = os.path.join(out_dir, "pareto_tradeoff.png")
    deadline_img = os.path.join(out_dir, "deadline_adherence.png")
    bandit_img = os.path.join(out_dir, "bandit_convergence.png")

    generate_pareto_plot(records, pareto_img)
    generate_deadline_and_latency_plot(records, deadline_img)
    generate_bandit_convergence_plot(records, bandit_img)
    print("Trade-off plot generation complete.")


if __name__ == "__main__":
    main()
