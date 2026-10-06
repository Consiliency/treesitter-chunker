"""
Integration and testing module for Phase 1.8 grammar management system.
"""

import contextlib
import ctypes
import io
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil

from .cli import ComprehensiveGrammarCLI
from .compatibility import (
    CompatibilityChecker,
    CompatibilityDatabase,
    GrammarTester,
    SmartSelector,
)
from .config import CacheManager, DirectoryManager, UserConfig

# Import from all other Phase 1.8 tasks
from .core import GrammarManager, GrammarValidator

logger = logging.getLogger(__name__)


class IntegrationTester:
    """Tests complete grammar management system integration."""

    def __init__(self, test_dir: Path | None = None):
        """Initialize integration tester."""
        self._owns_test_dir = test_dir is None
        if test_dir is None:
            temporary_parent = Path(tempfile.gettempdir()).resolve()
            home = Path.home().resolve()
            if temporary_parent.is_relative_to(home):
                temporary_parent = (
                    Path(os.environ.get("SYSTEMROOT", r"C:\Windows")) / "Temp"
                    if sys.platform == "win32"
                    else Path("/tmp")
                ).resolve()
            if temporary_parent.is_relative_to(home):
                raise ValueError(
                    "Grammar self-tests require a temporary parent outside home"
                )
            self.test_dir = Path(
                tempfile.mkdtemp(prefix="grammar_test_", dir=temporary_parent)
            )
        else:
            self.test_dir = test_dir
        self.test_results = {}
        self.performance_metrics = {}
        self.test_languages = ["python", "javascript", "rust", "go", "java"]
        try:
            self._setup_test_environment()
        except Exception:
            self.cleanup()
            raise

    def _setup_test_environment(self) -> None:
        """Set up test environment."""
        # Create test directories
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir = self.test_dir / "config"
        self.grammar_dir = self.test_dir / "grammars"
        self.cache_dir = self.test_dir / "cache"

        for dir_path in [self.config_dir, self.grammar_dir, self.cache_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.config = UserConfig(self.config_dir / "config.json")
        self.config.set("directories.base_dir", str(self.test_dir))
        self.dir_manager = DirectoryManager(self.config)
        self.cache_manager = CacheManager(self.config, self.dir_manager)
        self.grammar_manager = GrammarManager(
            user_dir=self.grammar_dir,
            package_dir=self.grammar_dir,
            cache_dir=self.cache_dir,
        )
        self.validator = GrammarValidator(self.cache_dir)
        self.compatibility_checker = CompatibilityChecker(
            self.grammar_manager, validator=self.validator
        )
        self.grammar_tester = GrammarTester(self.grammar_manager, self.validator)
        self.smart_selector = SmartSelector(
            self.grammar_manager,
            self.compatibility_checker,
        )

    def test_complete_workflow(
        self,
        sample_path: Path | None = None,
        language: str = "python",
        grammar_path: Path | None = None,
    ) -> dict[str, Any]:
        """Validate a caller-supplied fixture in a short-lived worker."""
        result = _run_test_worker(
            self.test_dir, "workflow", sample_path, language, grammar_path
        )
        self.test_results["complete_workflow"] = result
        return result

    def _test_complete_workflow_local(
        self,
        sample_path: Path | None = None,
        language: str = "python",
        grammar_path: Path | None = None,
    ) -> dict[str, Any]:
        """Run a bounded local grammar discovery and parse workflow."""
        results = {
            "status": "pass",
            "workflows_tested": [],
            "errors": [],
            "performance": {},
            "timestamp": datetime.now().isoformat(),
        }

        try:
            start = time.time()
            self.grammar_manager.discover_available_grammars()
            results["workflows_tested"].append("discovery")
            results["performance"]["discovery"] = time.time() - start

            if sample_path is None:
                raise ValueError("A local sample_path is required")
            if grammar_path is None:
                raise ValueError("A local grammar_path is required")
            source = sample_path.read_text(encoding="utf-8")
            start = time.time()
            valid, errors = GrammarValidator(self.cache_dir).test_parse_samples(
                language, [source], grammar_path
            )
            if valid:
                from .core import load_compiled_grammar

                if (
                    load_compiled_grammar(grammar_path, language)
                    .parse(source.encode("utf-8"))
                    .root_node.has_error
                ):
                    valid = False
                    errors.append("Sample contains parse errors")
            results["workflows_tested"].append("validation")
            results["performance"]["validation"] = time.time() - start
            if not valid:
                results["status"] = "fail"
                results["errors"].extend(errors)

        except Exception as e:
            results["status"] = "fail"
            results["errors"].append(str(e))
            logger.error(f"Complete workflow test failed: {e}")

        self.test_results["complete_workflow"] = results
        return results

    def _test_discovery_workflow(self) -> dict[str, Any]:
        """Test grammar discovery workflow."""
        start = time.time()
        grammars = self.grammar_manager.discover_available_grammars()
        duration = time.time() - start

        return {
            "grammars_found": len(grammars),
            "duration": duration,
            "status": "pass" if grammars else "fail",
        }

    def _test_installation_workflow(self) -> dict[str, Any]:
        """Test grammar installation workflow."""
        start = time.time()
        results = {"installed": [], "failed": []}

        for language in self.test_languages[:2]:  # Test first 2 languages
            try:
                success = self.grammar_manager.install_grammar(language)
                if success:
                    results["installed"].append(language)
                else:
                    results["failed"].append(language)
            except Exception as e:
                results["failed"].append(f"{language}: {e!s}")

        duration = time.time() - start
        return {
            "installed": results["installed"],
            "failed": results["failed"],
            "duration": duration,
            "status": "pass" if results["installed"] else "fail",
        }

    def _test_validation_workflow(self) -> dict[str, Any]:
        """Test grammar validation workflow."""
        start = time.time()
        results = {"validated": [], "invalid": []}

        for language in self.test_languages[:2]:
            validation = self.grammar_manager.validate_grammar(language)
            if validation and validation.get("valid"):
                results["validated"].append(language)
            else:
                results["invalid"].append(language)

        duration = time.time() - start
        return {
            "validated": results["validated"],
            "invalid": results["invalid"],
            "duration": duration,
            "status": "pass" if results["validated"] else "fail",
        }

    def _test_usage_workflow(self) -> dict[str, Any]:
        """Test grammar usage workflow."""
        start = time.time()
        results = {"successful_uses": 0, "failed_uses": 0}

        # Test getting grammar info
        for language in self.test_languages[:2]:
            info = self.grammar_manager.get_grammar_metadata(language)
            if info:
                results["successful_uses"] += 1
            else:
                results["failed_uses"] += 1

        duration = time.time() - start
        return {
            "successful": results["successful_uses"],
            "failed": results["failed_uses"],
            "duration": duration,
            "status": "pass" if results["successful_uses"] > 0 else "fail",
        }

    def _test_removal_workflow(self) -> dict[str, Any]:
        """Test grammar removal workflow."""
        start = time.time()
        results = {"removed": [], "failed": []}

        for language in self.test_languages[:2]:
            try:
                success = self.grammar_manager.remove_grammar(language)
                if success:
                    results["removed"].append(language)
                else:
                    results["failed"].append(language)
            except Exception as e:
                results["failed"].append(f"{language}: {e!s}")

        duration = time.time() - start
        return {
            "removed": results["removed"],
            "failed": results["failed"],
            "duration": duration,
            "status": "pass",
        }

    def test_cross_component_integration(self) -> dict[str, Any]:
        """Test integration between all components."""
        results = {
            "status": "pass",
            "components_tested": [],
            "integration_points": [],
            "errors": [],
        }

        try:
            # Test Core-Config integration
            self.config.set("grammars.auto_install", True)
            if self.config.get("grammars.auto_install"):
                results["integration_points"].append("core-config")

            # Test Core-Compatibility integration
            compat_result = self.compatibility_checker.check_compatibility(
                "python",
                "1.0.0",
                "3.9.0",
            )
            if compat_result:
                results["integration_points"].append("core-compatibility")

            # Test Config-Cache integration
            cache_size = self.cache_manager.get_cache_size()
            if cache_size["total_bytes"] >= 0 and self.cache_manager.cache_dir == (
                self.dir_manager.get_directory("cache")
            ):
                results["integration_points"].append("config-cache")

            # Test Compatibility-Selector integration
            selection = self.smart_selector.select_best_grammar("python")
            if selection:
                results["integration_points"].append("compatibility-selector")

            results["components_tested"] = [
                "core",
                "config",
                "compatibility",
                "cache",
                "selector",
            ]

        except Exception as e:
            results["status"] = "fail"
            results["errors"].append(str(e))
            logger.error(f"Cross-component integration test failed: {e}")

        self.test_results["cross_component"] = results
        return results

    def test_error_scenarios(self) -> dict[str, Any]:
        """Keep even corrupt-artifact loader checks in a short-lived worker."""
        result = _run_test_worker(
            self.test_dir, "error_scenarios", None, "python", None
        )
        self.test_results["error_scenarios"] = result
        return result

    def _test_error_scenarios_local(self) -> dict[str, Any]:
        """Observe local rejection; retire unimplemented simulations."""
        results = {
            "status": "unsupported",
            "scenarios_tested": [],
            "recovery_successful": [],
            "recovery_failed": [],
            "unsupported": {
                "network_failure": "No offline network fixture supplied",
                "disk_full": "Eviction does not demonstrate disk exhaustion",
                "permission_denied": "No portable recovery fixture supplied",
            },
        }
        for name, operation in (
            ("invalid_language", self._test_invalid_language_error),
            ("corrupt_grammar", self._test_corrupt_grammar_error),
        ):
            results["scenarios_tested"].append(name)
            try:
                results[
                    "recovery_successful" if operation() else "recovery_failed"
                ].append(name)
            except Exception as error:
                results["recovery_failed"].append(f"{name}: {error}")
        if results["recovery_failed"]:
            results["status"] = "fail"
        self.test_results["error_scenarios"] = results
        return results

    def _test_invalid_language_error(self) -> bool:
        """Reject a missing local artifact without installation."""
        from .core import ValidationLevel

        with tempfile.TemporaryDirectory(
            prefix="missing-fixture-", dir=self.test_dir
        ) as operation:
            missing = Path(operation) / "missing.so"
            result = GrammarValidator(Path(operation) / "cache").validate_grammar(
                missing, "nonexistent_language", ValidationLevel.BASIC
            )
            try:
                missing.stat()
            except FileNotFoundError as error:
                expected = f"Validation error: {error}"
            else:
                return False
            return not result.is_valid and result.errors == [expected]

    def _test_corrupt_grammar_error(self) -> bool:
        """Reject actual corrupt bytes through the current validator."""
        with tempfile.TemporaryDirectory(
            prefix="corrupt-fixture-", dir=self.test_dir
        ) as operation:
            corrupt_file = Path(operation) / "corrupt.so"
            corrupt_file.write_bytes(b"corrupt data")
            result = GrammarValidator(Path(operation) / "cache").validate_grammar(
                corrupt_file, "corrupt"
            )
            try:
                ctypes.CDLL(str(corrupt_file))
            except OSError as error:
                expected = (
                    f"ABI compatibility issue: ABI compatibility check failed: {error}"
                )
            else:
                return False
            return not result.is_valid and result.errors == [expected]

    def test_performance_under_load(self) -> dict[str, Any]:
        """Concurrent load claims need a controlled workload and join budget."""
        results = {
            "status": "unsupported",
            "concurrent_operations": 0,
            "errors": [],
            "reason": "No controlled concurrent workload fixture",
        }
        self.test_results["performance_load"] = results
        return results

    def cleanup(self) -> None:
        """Clean up test environment."""
        if self._owns_test_dir and self.test_dir.exists():
            shutil.rmtree(self.test_dir)


class CLIValidator:
    """Validates CLI functionality and user experience."""

    def __init__(self, *, test_dir: Path | None = None):
        """Initialize CLI validator."""
        self.test_results = {}
        self._environment = IntegrationTester(test_dir)
        self.test_dir = self._environment.test_dir
        self._cli_operation = None
        try:
            self._cli_operation = tempfile.TemporaryDirectory(
                prefix="cli-validator-", dir=self.test_dir
            )
            self.cli = ComprehensiveGrammarCLI(
                cache_dir=Path(self._cli_operation.name) / "cache"
            )
        except Exception:
            self.cleanup()
            raise

    def cleanup(self) -> None:
        try:
            if self._cli_operation is not None:
                self._cli_operation.cleanup()
        finally:
            self._environment.cleanup()

    def __enter__(self) -> "CLIValidator":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.cleanup()

    def test_all_commands(self) -> dict[str, Any]:
        """Check observed local exit codes; network/build work is unsupported."""
        results = {
            "status": "unsupported",
            "commands_tested": [],
            "passed": [],
            "failed": [],
            "observations": {},
            "unsupported": {
                "versions": "No offline version fixture",
                "fetch": "No offline download fixture",
                "build": "No local generation fixture",
            },
        }
        for name, operation, expected, diagnostic in (
            (
                "list",
                lambda: self.cli.list_grammars(output_format="json"),
                1,
                "No grammars found",
            ),
            (
                "info",
                lambda: self.cli.info_grammar("missing_grammar"),
                1,
                "Grammar for 'missing_grammar' not found",
            ),
            (
                "remove",
                lambda: self.cli.remove_grammar("missing_grammar", confirm=False),
                1,
                "No user-installed grammar found for 'missing_grammar'",
            ),
            (
                "test",
                lambda: self.cli.test_grammar(
                    "missing_grammar", str(self.test_dir / "missing.py")
                ),
                1,
                "Test file not found:",
            ),
            (
                "validate",
                lambda: self.cli.validate_grammar("missing_grammar"),
                1,
                "Grammar for 'missing_grammar' not found",
            ),
        ):
            results["commands_tested"].append(name)
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    code = operation()
                results["observations"][name] = {
                    "exit_code": code,
                    "output": output.getvalue(),
                }
                results[
                    (
                        "passed"
                        if code == expected and diagnostic in output.getvalue()
                        else "failed"
                    )
                ].append(name)
            except Exception as error:
                results["failed"].append(f"{name}: {error}")
        if results["failed"]:
            results["status"] = "fail"
        self.test_results["all_commands"] = results
        return results

    def test_user_experience(self) -> dict[str, Any]:
        """Observe actual help and formats without invented usability scores."""
        results = {
            "status": "unsupported",
            "help": self.test_help_and_documentation(),
            "formats": {},
            "unsupported": {"usability": "No user study fixture"},
        }
        for output_format in ("table", "json", "yaml"):
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    code = self.cli.list_grammars(output_format=output_format)
                results["formats"][output_format] = {
                    "exit_code": code,
                    "output": output.getvalue(),
                }
                if code != 1 or "No grammars found" not in output.getvalue():
                    results["status"] = "fail"
            except Exception as error:
                results["formats"][output_format] = {"error": str(error)}
                results["status"] = "fail"
        if results["help"]["status"] != "pass":
            results["status"] = "fail"
        self.test_results["user_experience"] = results
        return results

    def test_error_handling(self) -> dict[str, Any]:
        """Report observed missing-artifact outcomes, never stale-API success."""
        commands = self.test_all_commands()
        results = {
            "status": "fail" if commands["failed"] else "pass",
            "error_cases": ["info", "remove", "test", "validate"],
            "observations": {
                name: commands["observations"].get(name)
                for name in ("info", "remove", "test", "validate")
            },
            "errors": commands["failed"],
        }
        self.test_results["error_handling"] = results
        return results

    def test_help_and_documentation(self) -> dict[str, Any]:
        """Inspect actual Click help without asserting documentation quality."""
        from click.testing import CliRunner
        from .cli import grammar_cli

        observed = CliRunner().invoke(grammar_cli, ["--help"])
        available = observed.exit_code == 0 and "Commands:" in observed.output
        results = {
            "status": "pass" if available else "fail",
            "help_available": available,
            "exit_code": observed.exit_code,
            "output": observed.output,
        }
        self.test_results["help_documentation"] = results
        return results


class SystemValidator:
    """Validates system health and stability."""

    def __init__(
        self,
        grammar_manager: GrammarManager | None = None,
        config: UserConfig | None = None,
        *,
        test_dir: Path | None = None,
    ):
        """Initialize system validator."""
        self.health_metrics = {}
        self._environment = IntegrationTester(test_dir)
        self.test_dir = self._environment.test_dir
        self.grammar_manager = (
            grammar_manager
            if grammar_manager is not None
            else self._environment.grammar_manager
        )
        self.config = config if config is not None else self._environment.config

    def cleanup(self) -> None:
        self._environment.cleanup()

    def __enter__(self) -> "SystemValidator":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.cleanup()

    def check_system_health(self) -> dict[str, Any]:
        """Check overall system health."""
        results = {
            "status": "healthy",
            "components": {},
            "timestamp": datetime.now().isoformat(),
        }

        # Check core component
        try:
            self.grammar_manager.discover_available_grammars()
            results["components"]["core"] = "healthy"
        except Exception as e:
            logger.debug("Core component health check failed: %s", e)
            results["components"]["core"] = "unhealthy"
            results["status"] = "degraded"

        # Check configuration
        try:
            self.config.get("grammars.default_source")
            results["components"]["config"] = "healthy"
        except Exception as e:
            logger.debug("Config component health check failed: %s", e)
            results["components"]["config"] = "unhealthy"
            results["status"] = "degraded"

        # Check cache
        try:
            cache = CacheManager(self.config, DirectoryManager(self.config))
            cache.get_cache_size()
            results["components"]["cache"] = "healthy"
        except Exception as e:
            logger.debug("Cache component health check failed: %s", e)
            results["components"]["cache"] = "unhealthy"
            results["status"] = "degraded"

        # Check compatibility database
        try:
            CompatibilityDatabase(self.config.config_dir / "compatibility.db")
            results["components"]["compatibility_db"] = "healthy"
        except Exception as e:
            logger.debug("Compatibility DB health check failed: %s", e)
            results["components"]["compatibility_db"] = "unhealthy"
            results["status"] = "degraded"

        self.health_metrics["system_health"] = results
        return results

    def monitor_resource_usage(self) -> dict[str, Any]:
        """Monitor system resource usage."""
        process = psutil.Process()

        results = {
            "cpu_percent": process.cpu_percent(interval=1),
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "threads": process.num_threads(),
            "open_files": len(process.open_files()),
            "timestamp": datetime.now().isoformat(),
        }

        # Check for resource issues
        if results["memory_mb"] > 500:
            results["warnings"] = results.get("warnings", [])
            results["warnings"].append("High memory usage")

        if results["cpu_percent"] > 80:
            results["warnings"] = results.get("warnings", [])
            results["warnings"].append("High CPU usage")

        self.health_metrics["resource_usage"] = results
        return results

    def test_stability(self, duration_minutes: int = 1) -> dict[str, Any]:
        """Test system stability over time."""
        results = {
            "status": "stable",
            "duration_minutes": duration_minutes,
            "errors": [],
            "metrics": [],
        }

        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        while time.time() < end_time:
            try:
                # Perform operations
                self.grammar_manager.discover_available_grammars()

                # Collect metrics
                metrics = self.monitor_resource_usage()
                results["metrics"].append(metrics)

                # Short sleep
                time.sleep(5)

            except Exception as e:
                results["errors"].append(
                    {"error": str(e), "timestamp": datetime.now().isoformat()},
                )
                results["status"] = "unstable"

        # Analyze stability
        if len(results["errors"]) > duration_minutes:
            results["status"] = "unstable"

        self.health_metrics["stability"] = results
        return results

    def validate_configuration(self) -> dict[str, Any]:
        """Validate the actual supplied configuration with its current schema."""
        results = {"status": "valid", "config_items": {}, "errors": []}
        try:
            configured = self.config.get_all()
            self.config._validate_config(configured)
            results["config_items"] = configured
        except Exception as error:
            results["status"] = "invalid"
            results["errors"].append(str(error))
        self.health_metrics["configuration"] = results
        return results


class PerformanceBenchmark:
    """Benchmarks system performance and scalability."""

    def __init__(
        self,
        grammar_manager: GrammarManager | None = None,
        *,
        test_dir: Path | None = None,
    ):
        """Initialize performance benchmark."""
        self.benchmark_results = {}
        self._environment = IntegrationTester(test_dir)
        self.test_dir = self._environment.test_dir
        self.grammar_manager = (
            grammar_manager
            if grammar_manager is not None
            else self._environment.grammar_manager
        )

    def cleanup(self) -> None:
        self._environment.cleanup()

    def __enter__(self) -> "PerformanceBenchmark":
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.cleanup()

    def benchmark_grammar_operations(self) -> dict[str, Any]:
        """Measure current metadata APIs and report actual failures."""
        results = {
            "status": "unsupported",
            "operations": {},
            "errors": [],
            "timestamp": datetime.now().isoformat(),
            "unsupported": {"validate": "No explicit grammar fixture supplied"},
        }
        for name, operation in (
            ("discover", self.grammar_manager.discover_available_grammars),
            (
                "get_info",
                lambda: self.grammar_manager._registry.get_language_info("python"),
            ),
        ):
            times = []
            for _ in range(3):
                start = time.perf_counter()
                try:
                    operation()
                    times.append(time.perf_counter() - start)
                except Exception as error:
                    results["status"] = "fail"
                    results["errors"].append(f"{name}: {error}")
            if times:
                results["operations"][name] = {
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "samples": len(times),
                }
        self.benchmark_results["operations"] = results
        return results

    def test_scalability(self, max_grammars: int = 10) -> dict[str, Any]:
        """Do not claim scalability without distinct grammar populations."""
        results = {
            "status": "unsupported",
            "max_grammars_tested": 0,
            "reason": "No distinct grammar population fixtures supplied",
        }
        self.benchmark_results["scalability"] = results
        return results

    def optimize_performance(self) -> dict[str, Any]:
        """Do not alter caches to invent a speedup observation."""
        results = {
            "status": "unsupported",
            "optimizations": [],
            "recommendations": [],
            "reason": "No controlled cache-effectiveness fixture supplied",
        }
        self.benchmark_results["optimization"] = results
        return results

    def generate_performance_report(self) -> str:
        """Generate comprehensive performance report."""
        report = []
        report.append("=" * 60)
        report.append("PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        # Operation benchmarks
        if "operations" in self.benchmark_results:
            report.append("OPERATION PERFORMANCE:")
            report.append("-" * 40)
            for op_name, metrics in self.benchmark_results["operations"][
                "operations"
            ].items():
                report.append(f"  {op_name}:")
                report.append(f"    Average: {metrics['avg_time']:.3f}s")
                report.append(f"    Min: {metrics['min_time']:.3f}s")
                report.append(f"    Max: {metrics['max_time']:.3f}s")
            report.append("")

        # Scalability results
        if "scalability" in self.benchmark_results:
            report.append("SCALABILITY:")
            report.append("-" * 40)
            report.append(
                f"  Status: {self.benchmark_results['scalability']['status']}",
            )
            report.append(
                f"  Max grammars tested: {self.benchmark_results['scalability']['max_grammars_tested']}",
            )
            report.append("")

        # Optimization results
        if "optimization" in self.benchmark_results:
            report.append("OPTIMIZATIONS:")
            report.append("-" * 40)
            opts = self.benchmark_results["optimization"]
            if opts["optimizations"]:
                report.append(f"  Effective: {', '.join(opts['optimizations'])}")
            if opts["recommendations"]:
                report.append("  Recommendations:")
                for rec in opts["recommendations"]:
                    report.append(f"    - {rec}")
            report.append("")

        report.append("=" * 60)
        return "\n".join(report)


def _run_test_worker(
    test_dir: Path,
    operation: str,
    sample_path: Path | None,
    language: str,
    grammar_path: Path | None,
    *,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Reap a bounded fixture worker before removing its private operation root."""
    with tempfile.TemporaryDirectory(prefix="worker-", dir=test_dir) as temporary:
        root = Path(temporary)
        request = root / "request.json"
        response = root / "response.json"
        request.write_text(
            json.dumps(
                {
                    "operation": operation,
                    "test_dir": str(root),
                    "sample_path": str(sample_path.absolute()) if sample_path else None,
                    "language": language,
                    "grammar_path": (
                        str(grammar_path.absolute()) if grammar_path else None
                    ),
                }
            ),
            encoding="utf-8",
        )
        package_root = Path(__file__).resolve().parents[2]
        command = [
            sys.executable,
            "-I",
            "-c",
            "import sys; sys.path.insert(0, sys.argv[1]); "
            "from chunker.grammar_management.testing import _test_worker_main; "
            "_test_worker_main(sys.argv[2], sys.argv[3])",
            str(package_root),
            str(request),
            str(response),
        ]
        try:
            # CLI printing cannot pollute the result or grow captured pipes.
            # subprocess.run kills and reaps a timed-out direct worker.
            subprocess.run(
                command,
                cwd=root,
                check=True,
                timeout=timeout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            with response.open("rb") as result_file:
                payload = result_file.read(1024 * 1024 + 1)
            if len(payload) > 1024 * 1024:
                raise ValueError("Worker result exceeds the size limit")
            envelope = json.loads(payload)
            if not isinstance(envelope, dict) or envelope.get("operation") != operation:
                raise ValueError("Worker result does not match the operation")
            result = envelope.get("result")
            if (
                not isinstance(result, dict)
                or not isinstance(result.get("status"), str)
                or result["status"]
                not in {
                    "pass",
                    "fail",
                    "unsupported",
                }
            ):
                raise ValueError("Worker result has no valid observed status")
            if operation == "workflow":
                if not isinstance(result.get("errors"), list) or not isinstance(
                    result.get("workflows_tested"), list
                ):
                    raise ValueError("Worker workflow result is incomplete")
            elif operation == "error_scenarios":
                if not all(
                    isinstance(result.get(field), list)
                    for field in (
                        "scenarios_tested",
                        "recovery_successful",
                        "recovery_failed",
                    )
                ) or not isinstance(result.get("unsupported"), dict):
                    raise ValueError("Worker scenario result is incomplete")
            elif not isinstance(result.get("summary"), dict) or not isinstance(
                result.get("test_suites"), dict
            ):
                raise ValueError("Worker suite result is incomplete")
            return result
        except (
            OSError,
            ValueError,
            RecursionError,
            subprocess.SubprocessError,
        ) as error:
            return {
                "status": "fail",
                "errors": [f"Fixture worker failed: {error}"],
                "workflows_tested": [],
                "scenarios_tested": [],
                "recovery_successful": [],
                "recovery_failed": [f"Fixture worker failed: {error}"],
                "unsupported": {},
                "test_suites": {},
                "summary": {
                    "total_tests": 1,
                    "passed": 0,
                    "failed": 1,
                    "unsupported": 0,
                },
            }


def _test_worker_main(request_path: str, response_path: str) -> None:
    """Execute only caller-supplied local fixtures; this is not native admission."""
    request = json.loads(Path(request_path).read_text(encoding="utf-8"))
    root = Path(request["test_dir"])
    sample = Path(request["sample_path"]) if request["sample_path"] else None
    grammar = Path(request["grammar_path"]) if request["grammar_path"] else None
    environment = IntegrationTester(root)
    if request["operation"] == "workflow":
        result = environment._test_complete_workflow_local(
            sample, request["language"], grammar
        )
    elif request["operation"] == "suite":
        result = _complete_suite_local(
            environment, sample, request["language"], grammar
        )
    elif request["operation"] == "error_scenarios":
        result = environment._test_error_scenarios_local()
    else:
        raise ValueError("Unknown fixture worker operation")
    Path(response_path).write_text(
        json.dumps({"operation": request["operation"], "result": result}),
        encoding="utf-8",
    )


def _complete_suite_local(
    environment: IntegrationTester,
    sample_path: Path | None,
    language: str,
    grammar_path: Path | None,
) -> dict[str, Any]:
    """Run bounded offline observations in the already isolated worker."""
    if sample_path is None or grammar_path is None:
        workflow = {
            "status": "unsupported",
            "reason": "Explicit sample and grammar fixtures required",
        }
    else:
        workflow = environment._test_complete_workflow_local(
            sample_path, language, grammar_path
        )
    root = environment.test_dir
    with (
        CLIValidator(test_dir=root) as cli,
        SystemValidator(
            environment.grammar_manager, environment.config, test_dir=root
        ) as system,
        PerformanceBenchmark(environment.grammar_manager, test_dir=root) as benchmark,
    ):
        suites = {
            "integration": {
                "workflow": workflow,
                "cross_component": environment.test_cross_component_integration(),
                "error_scenarios": environment._test_error_scenarios_local(),
            },
            "cli": {
                "commands": cli.test_all_commands(),
                "user_experience": cli.test_user_experience(),
                "error_handling": cli.test_error_handling(),
                "help_docs": cli.test_help_and_documentation(),
            },
            "system": {
                "health": system.check_system_health(),
                "configuration": system.validate_configuration(),
                "resources": {
                    "status": "unsupported",
                    "reason": "Resource metrics are observations, not health assertions",
                    "observations": system.monitor_resource_usage(),
                },
                "stability": {
                    "status": "unsupported",
                    "reason": "A bounded discovery check does not establish long-term stability",
                },
            },
            "performance": {
                "operations": benchmark.benchmark_grammar_operations(),
                "scalability": benchmark.test_scalability(),
                "optimization": benchmark.optimize_performance(),
            },
        }
        performance_report = benchmark.generate_performance_report()
    summary = {"total_tests": 0, "passed": 0, "failed": 0, "unsupported": 0}
    for suite in suites.values():
        for observation in suite.values():
            summary["total_tests"] += 1
            status = (
                observation.get("status") if isinstance(observation, dict) else None
            )
            if status in {"pass", "healthy", "valid"}:
                summary["passed"] += 1
            elif status == "unsupported":
                summary["unsupported"] += 1
            else:
                summary["failed"] += 1
    return {
        "status": (
            "fail"
            if summary["failed"]
            else "unsupported" if summary["unsupported"] else "pass"
        ),
        "test_suites": suites,
        "summary": summary,
        "timestamp": datetime.now().isoformat(),
        "performance_report": performance_report,
    }


def run_complete_test_suite(
    *,
    test_dir: Path | None = None,
    sample_path: Path | None = None,
    language: str = "python",
    grammar_path: Path | None = None,
    report_path: Path | None = None,
) -> dict[str, Any]:
    """Return isolated local observations; persist only to an explicit report."""
    environment = IntegrationTester(test_dir)
    try:
        result = _run_test_worker(
            environment.test_dir, "suite", sample_path, language, grammar_path
        )
    finally:
        environment.cleanup()
    if report_path is not None:
        report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    # Run test suite if executed directly
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    results = run_complete_test_suite()

    # Print summary
    print("\n" + "=" * 60)
    print("PHASE 1.8 TEST SUITE RESULTS")
    print("=" * 60)
    print(f"Status: {results['status']}")
    print(f"Total Tests: {results['summary']['total_tests']}")
    print(f"Passed: {results['summary']['passed']}")
    print(f"Failed: {results['summary']['failed']}")
    print(f"Unsupported: {results['summary']['unsupported']}")
    print("=" * 60)

    if "performance_report" in results:
        print("\n" + results["performance_report"])
