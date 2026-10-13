"""
Unit Tests for Phase 17: Benchmarking Harness & Trade-off Evaluation
"""

import os
import unittest
from benchmarks.run_benchmarks import BenchmarkHarness
from benchmarks.plot_tradeoffs import generate_pareto_plot, generate_deadline_and_latency_plot


class TestBenchmarks(unittest.TestCase):

    def setUp(self):
        self.test_dir = "logs/test_benchmark_results"
        self.harness = BenchmarkHarness(output_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_benchmark_execution_across_all_strategies(self):
        """Harness executes 5 candidate strategies and outputs summary dictionary."""
        summary = self.harness.run_benchmark(num_windows=5)

        for strat in BenchmarkHarness.STRATEGIES:
            self.assertIn(strat, summary)
            s = summary[strat]
            self.assertEqual(s["sample_count"], 5)
            self.assertGreater(s["total_raw_bytes"], 0)
            self.assertGreater(s["avg_compression_ratio"], 0.0)

        # Verify output files generated
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "benchmark_runs.csv")))
        self.assertTrue(os.path.exists(os.path.join(self.test_dir, "benchmark_summary.json")))

    def test_tradeoff_plot_generation(self):
        """Plotting routines generate valid image files without throwing exceptions."""
        summary = self.harness.run_benchmark(num_windows=3)
        csv_path = os.path.join(self.test_dir, "benchmark_runs.csv")

        import csv
        records = []
        with open(csv_path, "r", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                records.append({
                    "strategy": r["strategy"],
                    "ratio": float(r["ratio"]),
                    "energy_per_raw_byte": float(r["energy_per_raw_byte"]),
                    "total_latency_ms": float(r["total_latency_ms"]),
                    "deadline_met": int(r["deadline_met"])
                })

        pareto_path = os.path.join(self.test_dir, "pareto.png")
        generate_pareto_plot(records, pareto_path)
        self.assertTrue(os.path.exists(pareto_path))


if __name__ == "__main__":
    unittest.main()
