"""Performance regression tracking for Tree-sitter Chunker.

This module tracks performance metrics over time and detects regressions.
"""

import argparse
import json
import statistics
import subprocess
import sys
import warnings
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from benchmark import run_benchmarks


@dataclass
class PerformanceBaseline:
    """Performance baseline for a specific metric."""

    name: str
    mean: float
    std_dev: float
    min_val: float
    max_val: float
    samples: int
    timestamp: str
    commit_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RegressionResult:
    """Result of regression detection."""

    metric: str
    baseline_mean: float
    current_mean: float
    degradation_percent: float
    is_regression: bool
    confidence: float
    details: str


class PerformanceRegressionTracker:
    """Track performance over time and detect regressions."""

    def __init__(self, baseline_file: Path | None = None):
        """Initialize tracker with optional baseline file."""
        if baseline_file is None:
            baseline_file = Path(__file__).parent / "baselines.json"
        self.baseline_file = baseline_file
        self.baselines: dict[str, PerformanceBaseline] = {}
        self.load_baselines()

    def load_baselines(self):
        """Load performance baselines from file."""
        if self.baseline_file.exists():
            try:
                with Path(self.baseline_file).open(encoding="utf-8") as f:
                    data = json.load(f)
                    for key, value in data.items():
                        self.baselines[key] = PerformanceBaseline(**value)
            except (json.JSONDecodeError, ValueError) as e:
                warnings.warn(f"Failed to load baselines: {e}", stacklevel=2)

    def save_baselines(self):
        """Save performance baselines to file."""
        self.baseline_file.parent.mkdir(parents=True, exist_ok=True)
        data = {key: asdict(baseline) for key, baseline in self.baselines.items()}
        with Path(self.baseline_file).open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def record_baseline(
        self,
        name: str,
        measurements: list[float],
        commit_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PerformanceBaseline:
        """Record a new performance baseline.

        Args:
            name: Metric name
            measurements: List of performance measurements
            commit_hash: Optional git commit hash
            metadata: Additional metadata

        Returns:
            Created baseline
        """
        if not measurements:
            raise ValueError("No measurements provided")
        baseline = PerformanceBaseline(
            name=name,
            mean=statistics.mean(measurements),
            std_dev=statistics.stdev(measurements) if len(measurements) > 1 else 0.0,
            min_val=min(measurements),
            max_val=max(measurements),
            samples=len(measurements),
            timestamp=datetime.now().isoformat(),
            commit_hash=commit_hash or self._get_git_hash(),
            metadata=metadata or {},
        )
        self.baselines[name] = baseline
        self.save_baselines()
        return baseline

    def check_regression(
        self,
        name: str,
        current_measurements: list[float],
        threshold: float = 0.1,
        _confidence_level: float = 0.95,
    ) -> RegressionResult | None:
        """Check if current measurements indicate a performance regression.

        Args:
            name: Metric name
            current_measurements: Current performance measurements
            threshold: Regression threshold (default 10% degradation)
            confidence_level: Statistical confidence level

        Returns:
            RegressionResult if regression detected, None otherwise
        """
        if name not in self.baselines:
            return None
        if not current_measurements:
            return None
        baseline = self.baselines[name]
        current_mean = statistics.mean(current_measurements)
        degradation = (current_mean - baseline.mean) / baseline.mean
        is_regression = degradation > threshold
        if len(current_measurements) > 1:
            current_std = statistics.stdev(current_measurements)
            baseline_upper = baseline.mean + 2 * baseline.std_dev
            current_lower = current_mean - 2 * current_std
            overlap = max(0, baseline_upper - current_lower)
            confidence = 1.0 - overlap / (baseline_upper - baseline.mean)
        else:
            confidence = 0.5 if is_regression else 0.0
        details = []
        if is_regression:
            details.append(f"Performance degraded by {degradation * 100:.1f}%")
            details.append(f"Baseline: {baseline.mean:.3f}s (±{baseline.std_dev:.3f}s)")
            details.append(f"Current: {current_mean:.3f}s")
        return RegressionResult(
            metric=name,
            baseline_mean=baseline.mean,
            current_mean=current_mean,
            degradation_percent=degradation * 100,
            is_regression=is_regression,
            confidence=min(1.0, max(0.0, confidence)),
            details="\n".join(details),
        )

    def run_regression_tests(
        self,
        test_directory: Path,
        language: str = "python",
        iterations: int = 5,
    ) -> list[RegressionResult]:
        """Run benchmark suite and check for regressions.

        Args:
            test_directory: Directory containing test files
            language: Language to test
            iterations: Number of iterations per benchmark

        Returns:
            List of regression results
        """
        results = []
        all_measurements = {}
        for i in range(iterations):
            print(f"Running iteration {i + 1}/{iterations}...")
            suite = run_benchmarks(test_directory, language)
            for result in suite.results:
                if result.name not in all_measurements:
                    all_measurements[result.name] = []
                all_measurements[result.name].append(result.duration)
        for metric_name, measurements in all_measurements.items():
            regression = self.check_regression(metric_name, measurements)
            if regression and regression.is_regression:
                results.append(regression)
        return results

    def update_baseline(
        self,
        name: str,
        measurements: list[float],
        force: bool = False,
    ) -> bool:
        """Update baseline if performance improved or force=True.

        Args:
            name: Metric name
            measurements: New measurements
            force: Force update even if performance degraded

        Returns:
            True if baseline was updated
        """
        if not measurements:
            return False
        new_mean = statistics.mean(measurements)
        if name in self.baselines:
            old_baseline = self.baselines[name]
            if new_mean >= old_baseline.mean and not force:
                return False
        self.record_baseline(name, measurements)
        return True

    @staticmethod
    def _get_git_hash() -> str | None:
        """Get current git commit hash."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()[:8]
        except (subprocess.SubprocessError, OSError):
            return None

    def generate_report(self) -> str:
        """Generate a performance report."""
        lines = ["Performance Baseline Report", "=" * 50, ""]
        for name, baseline in sorted(self.baselines.items()):
            lines.append(f"{name}:")
            lines.append(f"  Mean: {baseline.mean:.3f}s (±{baseline.std_dev:.3f}s)")
            lines.append(f"  Range: {baseline.min_val:.3f}s - {baseline.max_val:.3f}s")
            lines.append(f"  Samples: {baseline.samples}")
            lines.append(f"  Updated: {baseline.timestamp}")
            if baseline.commit_hash:
                lines.append(f"  Commit: {baseline.commit_hash}")
            lines.append("")
        return "\n".join(lines)


def track_performance_history(
    history_file: Path | None = None,
) -> "PerformanceHistory":
    """Track performance metrics over time."""
    if history_file is None:
        history_file = Path(__file__).parent / "performance_history.json"
    return PerformanceHistory(history_file)


class PerformanceHistory:
    """Track performance metrics history over time."""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.history: dict[str, list[dict[str, Any]]] = {}
        self.load_history()

    def load_history(self):
        """Load performance history from file."""
        if self.history_file.exists():
            try:
                with Path(self.history_file).open(encoding="utf-8") as f:
                    self.history = json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                warnings.warn(f"Failed to load history: {e}", stacklevel=2)

    def save_history(self):
        """Save performance history to file."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with Path(self.history_file).open("w", encoding="utf-8") as f:
            json.dump(self.history, f, indent=2)

    def add_measurement(
        self,
        metric: str,
        value: float,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a measurement to history."""
        if metric not in self.history:
            self.history[metric] = []
        entry = {
            "value": value,
            "timestamp": timestamp or datetime.now().isoformat(),
            "metadata": metadata or {},
        }
        self.history[metric].append(entry)
        self.save_history()

    def get_trend(self, metric: str, window: int = 10) -> str | None:
        """Get performance trend for a metric.

        Returns: 'improving', 'degrading', 'stable', or None
        """
        if metric not in self.history or len(self.history[metric]) < 2:
            return None
        recent = self.history[metric][-window:]
        if len(recent) < 2:
            return None
        values = [entry["value"] for entry in recent]
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return "stable"
        slope = numerator / denominator
        if slope < -0.01:
            return "improving"
        if slope > 0.01:
            return "degrading"
        return "stable"

    def plot_history(self, metric: str, output_file: Path | None = None):
        """Plot performance history for a metric (requires matplotlib)."""
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            warnings.warn("matplotlib not installed, cannot plot history", stacklevel=2)
            return
        if metric not in self.history:
            return
        data = self.history[metric]
        if not data:
            return
        timestamps = [entry["timestamp"] for entry in data]
        values = [entry["value"] for entry in data]
        plt.figure(figsize=(10, 6))
        plt.plot(timestamps, values, marker="o")
        plt.title(f"Performance History: {metric}")
        plt.xlabel("Timestamp")
        plt.ylabel("Time (seconds)")
        plt.xticks(rotation=45)
        plt.tight_layout()
        if output_file:
            plt.savefig(output_file)
        else:
            plt.show()
        plt.close()


def check_for_regressions(
    test_dir: Path | None = None,
    _threshold: float = 0.1,
) -> bool:
    """Check for performance regressions and return True if any found."""
    if test_dir is None:
        test_dir = Path.cwd()
    tracker = PerformanceRegressionTracker()
    regressions = tracker.run_regression_tests(test_dir, iterations=3)
    if regressions:
        print("\n⚠️  Performance Regressions Detected:")
        for reg in regressions:
            print(f"\n{reg.metric}:")
            print(f"  Degradation: {reg.degradation_percent:.1f}%")
            print(f"  Confidence: {reg.confidence:.0%}")
            print(f"  {reg.details}")
        return True
    print("\n✅ No performance regressions detected")
    return False


def update_baselines(test_dir: Path | None = None, force: bool = False):
    """Update performance baselines."""
    if test_dir is None:
        test_dir = Path.cwd()
    tracker = PerformanceRegressionTracker()
    suite = run_benchmarks(test_dir, "python")
    updated = []
    for result in suite.results:
        measurements = [result.duration]
        for _ in range(4):
            suite = run_benchmarks(test_dir, "python")
            for r in suite.results:
                if r.name == result.name:
                    measurements.append(r.duration)
                    break
        if tracker.update_baseline(result.name, measurements, force=force):
            updated.append(result.name)
    if updated:
        print(f"\n✅ Updated baselines for: {', '.join(updated)}")
    else:
        print("\n✅ No baselines needed updating")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Performance regression tracking")
    parser.add_argument(
        "command",
        choices=["check", "update", "report", "history"],
        help="Command to run",
    )
    parser.add_argument(
        "--directory",
        type=Path,
        default=Path.cwd(),
        help="Test directory",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Regression threshold (default: 0.1 = 10%)",
    )
    parser.add_argument("--force", action="store_true", help="Force baseline update")
    parser.add_argument("--metric", help="Specific metric for history command")
    args = parser.parse_args()
    if args.command == "check":
        has_regressions = check_for_regressions(args.directory, args.threshold)
        sys.exit(1 if has_regressions else 0)
    elif args.command == "update":
        update_baselines(args.directory, args.force)
    elif args.command == "report":
        tracker = PerformanceRegressionTracker()
        print(tracker.generate_report())
    elif args.command == "history":
        history = track_performance_history()
        if args.metric:
            trend = history.get_trend(args.metric)
            print(f"Trend for {args.metric}: {trend or 'unknown'}")
            history.plot_history(args.metric)
        else:
            print("Available metrics:")
            for metric in history.history:
                trend = history.get_trend(metric)
                print(f"  {metric}: {trend or 'unknown'}")
