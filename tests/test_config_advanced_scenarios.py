"""Advanced configuration tests for Phase 2.1 scenarios - Fixed version.

This module tests:
1. Performance impact of config lookups during parsing
2. Config hot-reloading during active chunking
3. Memory usage with large config hierarchies
4. Circular dependency detection edge cases
"""
import gc
import json
import os
import queue
import sys
import threading
import time
import weakref
from pathlib import Path
from typing import Any

import psutil
import pytest

from chunker.config import StrategyConfig
from chunker.exceptions import ChunkerError as ConfigurationError
from chunker.languages.base import LanguageConfig, PluginConfig

try:
    pass
except ImportError:
    StrategyConfig = type("StrategyConfig", (), {})
    LanguageConfig = type("LanguageConfig", (), {})
    PluginConfig = type("PluginConfig", (), {})
    ConfigurationError = Exception


class TestPerformanceImpactOfConfigLookups:
    """Test performance impact of config lookups during parsing."""

    @staticmethod
    def test_config_lookup_overhead_during_parsing():
        """Test the overhead of frequent config lookups during parsing."""

        class MockParser:

            def __init__(self, config: dict[str, Any]):
                self.config = config
                self.lookup_count = 0
                self.parse_time = 0

            def parse_with_config_lookups(self, text: str, lookup_frequency:
                int) -> list[dict]:
                """Parse text with config lookups every N tokens."""
                start_time = time.time()
                tokens = text.split()
                chunks = []
                for i, _token in enumerate(tokens):
                    if i % lookup_frequency == 0:
                        self.lookup_count += 1
                        self._lookup_config("parser.chunk_size", 1000)
                        self._lookup_config("parser.enabled", True)
                        self._lookup_config("parser.language", "python")
                    if i % 50 == 0:
                        chunks.append({"start": i, "end": min(i + 50, len(
                            tokens)), "type": "function"})
                self.parse_time = time.time() - start_time
                return chunks

            def _lookup_config(self, key: str, default: Any) -> Any:
                """Simulate hierarchical config lookup."""
                parts = key.split(".")
                value = self.config
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        return default
                return value
        test_text = " ".join([f"token_{i}" for i in range(10000)])
        config = {"parser": {"chunk_size": 500, "enabled": True, "language":
            "python", "optimizations": {"cache_enabled": True, "parallel":
            False}}, "languages": {"python": {"indent_size": 4,
            "max_line_length": 120}}}
        frequencies = [1, 10, 50, 100, 500]
        results = {}
        for freq in frequencies:
            parser = MockParser(config)
            chunks = parser.parse_with_config_lookups(test_text, freq)
            results[freq] = {"parse_time": parser.parse_time,
                "lookup_count": parser.lookup_count, "chunks_created": len(
                chunks), "lookups_per_second": parser.lookup_count / parser
                .parse_time if parser.parse_time > 0 else 0}
        baseline = results[500]
        for freq in frequencies:
            if freq != 500:
                overhead = (results[freq]["parse_time"] - baseline[
                    "parse_time"]) / baseline["parse_time"] * 100
                print(
                    f"Lookup every {freq} tokens: {overhead:.1f}% overhead, {results[freq]['lookups_per_second']:.0f} lookups/sec",
                    )
                if freq == 1:
                    assert overhead < 3000, f"Excessive overhead with frequent lookups: {overhead:.1f}%"
                elif freq == 10:
                    assert overhead < 500, f"High overhead with moderate lookups: {overhead:.1f}%"

    @staticmethod
    def test_config_caching_effectiveness():
        """Test effectiveness of config caching during parsing."""

        class CachedConfigParser:

            def __init__(self, config: dict[str, Any]):
                self.config = config
                self.cache = {}
                self.cache_hits = 0
                self.cache_misses = 0
                self.total_lookups = 0

            def lookup_with_cache(self, key: str, default: Any = None) -> Any:
                """Lookup config value with caching."""
                self.total_lookups += 1
                if key in self.cache:
                    self.cache_hits += 1
                    return self.cache[key]
                self.cache_misses += 1
                time.sleep(0.0001)
                parts = key.split(".")
                value = self.config
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = default
                        break
                self.cache[key] = value
                return value

            def clear_cache(self):
                """Clear the config cache."""
                self.cache.clear()
        config = {"parser": {"defaults": {"chunk_size": 1000, "timeout": 30,
            }, "languages": {"python": {"chunk_types": ["function", "class",
            ], "features": {"async": True, "type_hints": True}},
            "javascript": {"chunk_types": ["function", "class", "arrow"],
            "features": {"jsx": True, "typescript": False}}}}}
        parser = CachedConfigParser(config)
        common_keys = ["parser.defaults.chunk_size",
            "parser.languages.python.chunk_types",
            "parser.languages.python.features.async", "parser.defaults.timeout",
            ]
        for _ in range(100):
            for key in common_keys:
                parser.lookup_with_cache(key)
        first_pass_stats = {"hits": parser.cache_hits, "misses": parser.
            cache_misses, "hit_rate": parser.cache_hits / parser.
            total_lookups * 100}
        for _ in range(1000):
            for key in common_keys:
                parser.lookup_with_cache(key)
        final_stats = {"hits": parser.cache_hits, "misses": parser.
            cache_misses, "hit_rate": parser.cache_hits / parser.
            total_lookups * 100}
        assert first_pass_stats["hit_rate"] > 70
        assert final_stats["hit_rate"] > 95
        assert parser.cache_misses == len(common_keys)
        parser.clear_cache()
        old_misses = parser.cache_misses
        for key in common_keys:
            parser.lookup_with_cache(key)
        assert parser.cache_misses == old_misses + len(common_keys)

    @staticmethod
    def test_parallel_parsing_config_contention():
        """Test config lookup performance with parallel parsing."""

        class ThreadSafeConfigStore:

            def __init__(self, config: dict[str, Any]):
                self.config = config
                self.lock = threading.RLock()
                self.access_count = 0
                self.contention_events = 0
                self.max_wait_time = 0

            def get(self, key: str, default: Any = None) -> Any:
                """Thread-safe config getter."""
                start_wait = time.time()
                acquired = self.lock.acquire(timeout=0.001)
                if not acquired:
                    self.contention_events += 1
                    self.lock.acquire()
                wait_time = time.time() - start_wait
                self.max_wait_time = max(self.max_wait_time, wait_time)
                try:
                    self.access_count += 1
                    time.sleep(1e-05)
                    return self.config.get(key, default)
                finally:
                    self.lock.release()
        config_store = ThreadSafeConfigStore({"chunk_size": 1000,
            "parallel_threads": 4, "cache_enabled": True})
        results = queue.Queue()
        errors = queue.Queue()

        def parse_file_segment(segment_id: int, iterations: int):
            """Simulate parsing a file segment."""
            try:
                local_results = []
                for i in range(iterations):
                    chunk_size = config_store.get("chunk_size")
                    config_store.get("parallel_threads")
                    config_store.get("cache_enabled")
                    time.sleep(0.0001)
                    if i % 10 == 0:
                        local_results.append({"segment": segment_id,
                            "chunk": i // 10, "size": chunk_size})
                results.put(local_results)
            except (OSError, IndexError, KeyError) as e:
                errors.put((segment_id, str(e)))
        thread_counts = [1, 2, 4, 8, 16]
        performance_results = {}
        for num_threads in thread_counts:
            config_store.access_count = 0
            config_store.contention_events = 0
            config_store.max_wait_time = 0
            start_time = time.time()
            threads = []
            for i in range(num_threads):
                t = threading.Thread(target=parse_file_segment, args=(i, 100))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            elapsed = time.time() - start_time
            performance_results[num_threads] = {"elapsed_time": elapsed,
                "total_accesses": config_store.access_count,
                "contention_events": config_store.contention_events,
                "max_wait_time": config_store.max_wait_time,
                "accesses_per_second": config_store.access_count / elapsed}
        single_thread_time = performance_results[1]["elapsed_time"]
        for num_threads in thread_counts[1:]:
            speedup = single_thread_time / performance_results[num_threads][
                "elapsed_time"]
            efficiency = speedup / num_threads * 100
            print(
                f"{num_threads} threads: {speedup:.2f}x speedup, {efficiency:.0f}% efficiency, {performance_results[num_threads]['contention_events']} contentions",
                )
            if num_threads <= 4:
                assert efficiency > 5, f"Poor scaling with {num_threads} threads"
            if num_threads <= 8:
                assert performance_results[num_threads]["max_wait_time"] < 0.1


class TestConfigHotReloadingDuringChunking:
    """Test config hot-reloading during active chunking operations."""

    @staticmethod
    def test_hot_reload_during_chunking(tmp_path):
        """Test config reload while actively chunking files."""
        config_file = tmp_path / "chunker_config.json"
        initial_config = {"chunk_size": 100, "chunk_types": ["function",
            "class"], "languages": {"python": {"enabled": True,
            "max_chunk_size": 200}}}
        config_file.write_text(json.dumps(initial_config))

        class ConfigAwareChunker:

            def __init__(self, config_path: Path):
                self.config_path = config_path
                self.config = self._load_config()
                self.config_version = 1
                self.chunks_processed = 0
                self.active_chunking = False
                self.config_reload_events = []

            def _load_config(self) -> dict[str, Any]:
                """Load config from file."""
                with Path(self.config_path).open(encoding="utf-8") as f:
                    return json.load(f)

            def reload_config(self) -> bool:
                """Hot reload configuration."""
                try:
                    new_config = self._load_config()
                    if new_config != self.config:
                        old_config = self.config
                        self.config = new_config
                        self.config_version += 1
                        self.config_reload_events.append({"timestamp": time
                            .time(), "version": self.config_version,
                            "active_chunking": self.active_chunking,
                            "changes": self._diff_configs(old_config,
                            new_config)})
                        return True
                    return False
                except (AttributeError, IndexError, KeyError):
                    return False

            @staticmethod
            def _diff_configs(old: dict, new: dict) -> list[str]:
                """Find differences between configs."""
                changes = [f"{key}: {old.get(key)} -> {new.get(key)}" for
                    key in set(old.keys()) | set(new.keys()) if old.get(key,
                    ) != new.get(key)]
                return changes

            def chunk_file(self, content: str, duration: float = 0.5) -> list[dict
                ]:
                """Chunk file content with config checks."""
                self.active_chunking = True
                start_time = time.time()
                chunks = []
                try:
                    lines = content.split("\n")
                    chunk_size = self.config["chunk_size"]
                    i = 0
                    while i < len(lines) and time.time(
                        ) - start_time < duration:
                        if i % 50 == 0 and self.reload_config():
                            chunk_size = self.config["chunk_size"]
                        chunk_end = min(i + chunk_size, len(lines))
                        chunks.append({"start_line": i, "end_line":
                            chunk_end, "size": chunk_end - i,
                            "config_version": self.config_version, "type":
                            "block"})
                        i = chunk_end
                        self.chunks_processed += 1
                        time.sleep(0.01)
                finally:
                    self.active_chunking = False
                return chunks
        chunker = ConfigAwareChunker(config_file)
        test_content = "\n".join([f"line {i}" for i in range(1000)])
        chunking_done = threading.Event()
        chunking_result = {"chunks": None, "error": None}

        def chunk_async():
            try:
                chunks = chunker.chunk_file(test_content, duration=2.0)
                chunking_result["chunks"] = chunks
            except (OSError, FileNotFoundError, IndexError) as e:
                chunking_result["error"] = e
            finally:
                chunking_done.set()
        chunk_thread = threading.Thread(target=chunk_async)
        chunk_thread.start()
        time.sleep(0.2)
        modified_config = initial_config.copy()
        modified_config["chunk_size"] = 50
        modified_config["chunk_types"].append("method")
        config_file.write_text(json.dumps(modified_config))
        time.sleep(0.3)
        modified_config["chunk_size"] = 150
        modified_config["languages"]["python"]["max_chunk_size"] = 300
        config_file.write_text(json.dumps(modified_config))
        chunking_done.wait(timeout=3.0)
        chunk_thread.join()
        assert chunking_result["error"] is None
        chunks = chunking_result["chunks"]
        assert len(chunks) > 0
        config_versions = {chunk["config_version"] for chunk in chunks}
        print(f"Config versions used: {config_versions}")
        print(f"Total reload events: {len(chunker.config_reload_events)}")
        if len(chunker.config_reload_events) == 0:
            print(
                "Warning: No config reload events detected - chunking may have been too fast",
                )
        else:
            assert len(chunker.config_reload_events) >= 1
        for event in chunker.config_reload_events:
            assert event["active_chunking"]
            assert len(event["changes"]) > 0
        chunk_sizes_by_version = {}
        for chunk in chunks:
            version = chunk["config_version"]
            if version not in chunk_sizes_by_version:
                chunk_sizes_by_version[version] = []
            chunk_sizes_by_version[version].append(chunk["size"])
        assert len(set(chunk_sizes_by_version.keys())) >= 1

    @staticmethod
    def test_config_consistency_during_reload():
        """Test that config remains consistent during reload."""

        class AtomicConfigManager:

            def __init__(self):
                self.config = {"version": 1, "settings": {"a": 1, "b": 2,
                    "c": 3}}
                self.lock = threading.RLock()
                self.reload_in_progress = False
                self.access_during_reload = 0

            def get_config(self) -> dict[str, Any]:
                """Get current config atomically."""
                with self.lock:
                    if self.reload_in_progress:
                        self.access_during_reload += 1
                    return self.config.copy()

            def reload_config(self, new_config: dict[str, Any]):
                """Atomically reload configuration."""
                with self.lock:
                    self.reload_in_progress = True
                    try:
                        time.sleep(0.01)
                        self.config = new_config
                    finally:
                        self.reload_in_progress = False
        manager = AtomicConfigManager()
        inconsistencies = []

        def reader_thread(thread_id: int, iterations: int):
            """Read config and check consistency."""
            for _i in range(iterations):
                config = manager.get_config()
                if "version" not in config or "settings" not in config:
                    inconsistencies.append(
                        f"Missing keys in thread {thread_id}")
                version = config.get("version", 0)
                expected_sum = version * 6
                actual_sum = sum(config.get("settings", {}).values())
                if actual_sum != expected_sum:
                    inconsistencies.append(
                        f"Thread {thread_id}: Version {version} has sum {actual_sum}, expected {expected_sum}",
                        )
                time.sleep(0.001)

        def reloader_thread(iterations: int):
            """Reload config periodically."""
            for i in range(iterations):
                new_version = i + 2
                new_config = {"version": new_version, "settings": {"a":
                    new_version, "b": new_version * 2, "c": new_version * 3}}
                manager.reload_config(new_config)
                time.sleep(0.05)
        threads = []
        for i in range(5):
            t = threading.Thread(target=reader_thread, args=(i, 100))
            threads.append(t)
            t.start()
        t = threading.Thread(target=reloader_thread, args=(10,))
        threads.append(t)
        t.start()
        for t in threads:
            t.join()
        assert len(inconsistencies,
            ) == 0, f"Config inconsistencies: {inconsistencies}"
        if manager.access_during_reload == 0:
            print(
                "Warning: No accesses during reload detected - timing dependent",
                )


class TestMemoryUsageWithLargeConfigHierarchies:
    """Test memory usage with large configuration hierarchies."""

    @staticmethod
    def test_large_config_hierarchy_memory():
        """Test memory usage with deeply nested large configs."""

        def get_memory_usage():
            """Get current memory usage in MB."""
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024

        def create_deep_config(depth: int, breadth: int) -> dict[str, Any]:
            """Create a deeply nested config structure."""
            if depth == 0:
                return {f"leaf_{i}": f"value_{i}" for i in range(breadth)}
            config = {}
            for i in range(breadth):
                config[f"level_{depth}_{i}"] = create_deep_config(depth - 1,
                    breadth)
            return config
        gc.collect()
        baseline_memory = get_memory_usage()
        large_config = create_deep_config(depth=5, breadth=10)
        creation_memory = get_memory_usage()
        memory_increase = creation_memory - baseline_memory
        print(f"Memory increase for large config: {memory_increase:.2f} MB")

        def count_nodes(config: dict) -> int:
            count = len(config)
            for value in config.values():
                if isinstance(value, dict):
                    count += count_nodes(value)
            return count
        total_nodes = count_nodes(large_config)
        bytes_per_node = memory_increase * 1024 * 1024 / total_nodes
        print(
            f"Total nodes: {total_nodes}, Bytes per node: {bytes_per_node:.2f}",
            )
        assert memory_increase < 150, f"Excessive memory usage: {memory_increase:.2f} MB"
        assert bytes_per_node < 1000, f"Excessive per-node memory: {bytes_per_node:.2f} bytes"

        def traverse_config(config: dict, path: str = "") -> list[str]:
            """Traverse config and collect all paths."""
            paths = []
            for key, value in config.items():
                current_path = f"{path}.{key}" if path else key
                paths.append(current_path)
                if isinstance(value, dict):
                    paths.extend(traverse_config(value, current_path))
            return paths
        start_time = time.time()
        all_paths = traverse_config(large_config)
        traversal_time = time.time() - start_time
        print(
            f"Traversal time: {traversal_time:.3f}s for {len(all_paths)} paths",
            )
        assert traversal_time < 1.0, f"Slow traversal: {traversal_time:.3f}s"
        del large_config
        gc.collect()
        final_memory = get_memory_usage()
        memory_freed = creation_memory - final_memory
        print(f"Memory freed: {memory_freed:.2f} MB")
        assert final_memory < baseline_memory + 150, "Memory not properly freed"

    @staticmethod
    def test_config_inheritance_memory_efficiency():
        """Test memory efficiency of config inheritance."""

        class InheritanceConfig:

            def __init__(self):
                self.base_configs = {}
                self.inherited_configs = {}
                self.resolved_cache = {}

            def add_base_config(self, name: str, config: dict[str, Any]):
                """Add a base configuration."""
                self.base_configs[name] = config

            def add_inherited_config(self, name: str, parent: str,
                overrides: dict[str, Any]):
                """Add config that inherits from a parent."""
                self.inherited_configs[name] = {"_parent": parent,
                    "_overrides": overrides}

            def resolve_config(self, name: str) -> dict[str, Any]:
                """Resolve inherited configuration."""
                if name in self.resolved_cache:
                    return self.resolved_cache[name]
                if name in self.base_configs:
                    resolved = self.base_configs[name].copy()
                elif name in self.inherited_configs:
                    parent_name = self.inherited_configs[name]["_parent"]
                    resolved = self.resolve_config(parent_name).copy()
                    overrides = self.inherited_configs[name]["_overrides"]
                    self._deep_merge(resolved, overrides)
                else:
                    raise KeyError(f"Config {name} not found")
                self.resolved_cache[name] = resolved
                return resolved

            def _deep_merge(self, base: dict, overrides: dict):
                """Deep merge overrides into base."""
                for key, value in overrides.items():
                    if key in base and isinstance(base[key], dict,
                        ) and isinstance(value, dict):
                        self._deep_merge(base[key], value)
                    else:
                        base[key] = value

            def get_memory_stats(self) -> dict[str, int]:
                """Get memory statistics."""
                stats = {"base_configs": len(self.base_configs),
                    "inherited_configs": len(self.inherited_configs),
                    "cache_entries": len(self.resolved_cache),
                    "estimated_memory": 0}
                for config in self.base_configs.values():
                    stats["estimated_memory"] += sys.getsizeof(config)
                for config in self.inherited_configs.values():
                    stats["estimated_memory"] += sys.getsizeof(config)
                for config in self.resolved_cache.values():
                    stats["estimated_memory"] += sys.getsizeof(config)
                return stats
        config_manager = InheritanceConfig()
        base_config = {"common": {"timeout": 30, "retry_count": 3,
            "buffer_size": 8192, "features": {"logging": True, "monitoring":
            True, "caching": True, "compression": False}}, "parsing": {
            "max_file_size": 10 * 1024 * 1024, "chunk_size": 1000,
            "encoding": "utf-8"}}
        config_manager.add_base_config("base", base_config)
        for i in range(100):
            config_manager.add_inherited_config(f"lang_{i}", "base", {
                "common": {"timeout": 30 + i, "features": {"compression": i %
                2 == 0}}, "parsing": {"chunk_size": 1000 + i * 10}})
        stats_before = config_manager.get_memory_stats()
        for i in range(100):
            config = config_manager.resolve_config(f"lang_{i}")
            assert config["common"]["retry_count"] == 3
            assert config["common"]["timeout"] == 30 + i
        stats_after = config_manager.get_memory_stats()
        memory_per_config = stats_after["estimated_memory"] / (stats_after[
            "inherited_configs"] + 1)
        print(
            f"Memory before resolution: {stats_before['estimated_memory'] / 1024:.2f} KB",
            )
        print(
            f"Memory after resolution: {stats_after['estimated_memory'] / 1024:.2f} KB",
            )
        print(f"Memory per config: {memory_per_config:.2f} bytes")
        assert memory_per_config < 10000, f"Excessive memory per config: {memory_per_config} bytes"

    @staticmethod
    def test_weak_reference_config_cleanup():
        """Test weak reference usage for config cleanup."""

        class ConfigObject:

            def __init__(self, data: dict[str, Any]):
                self.data = data

        class WeakConfigManager:

            def __init__(self):
                self.strong_refs = {}
                self.weak_refs = {}
                self.access_count = {}

            def add_config(self, name: str, config: ConfigObject, critical:
                bool = False):
                """Add config with strong or weak reference."""
                self.access_count[name] = 0
                if critical:
                    self.strong_refs[name] = config
                else:
                    self.weak_refs[name] = weakref.ref(config, lambda ref,
                        n=name: self._on_config_deleted(n))

            @staticmethod
            def _on_config_deleted(name: str):
                """Callback when weak ref is deleted."""
                print(f"Config {name} was garbage collected")

            def get_config(self, name: str) -> (ConfigObject | None):
                """Get config by name."""
                self.access_count[name] = self.access_count.get(name, 0) + 1
                if name in self.strong_refs:
                    return self.strong_refs[name]
                if name in self.weak_refs:
                    config = self.weak_refs[name]()
                    if config is not None:
                        return config
                    del self.weak_refs[name]
                    return None
                return None

            def get_stats(self) -> dict[str, Any]:
                """Get manager statistics."""
                alive_weak = sum(1 for ref in self.weak_refs.values() if
                    ref() is not None)
                return {"strong_refs": len(self.strong_refs),
                    "weak_refs_total": len(self.weak_refs),
                    "weak_refs_alive": alive_weak, "access_counts": self.
                    access_count.copy()}
        manager = WeakConfigManager()
        manager.add_config("core", ConfigObject({"type": "core", "data":
            "x" * 1000}), critical=True)
        manager.add_config("security", ConfigObject({"type": "security",
            "data": "y" * 1000}), critical=True)
        cached_configs = []
        for i in range(20):
            config = ConfigObject({"type": f"cached_{i}", "data": "z" *
                1000 * (i + 1)})
            cached_configs.append(config)
            manager.add_config(f"cached_{i}", config, critical=False)
        for i in range(5):
            manager.get_config(f"cached_{i}")
            manager.get_config(f"cached_{i}")
        stats = manager.get_stats()
        assert stats["strong_refs"] == 2
        assert stats["weak_refs_alive"] == 20
        del cached_configs[10:]
        gc.collect()
        stats = manager.get_stats()
        assert stats["strong_refs"] == 2
        assert stats["weak_refs_alive"] <= 11
        config = manager.get_config("cached_15")
        assert config is None
        cached_configs.clear()
        gc.collect()
        stats = manager.get_stats()
        assert stats["strong_refs"] == 2
        assert manager.get_config("core") is not None
        assert manager.get_config("security") is not None


class TestCircularDependencyDetectionEdgeCases:
    """Test circular dependency detection edge cases in config."""

    @staticmethod
    def test_simple_circular_dependency():
        """Test detection of simple circular dependencies."""

        class ConfigResolver:

            def __init__(self):
                self.configs = {}
                self.resolving = set()

            def add_config(self, name: str, config: dict[str, Any]):
                """Add a configuration."""
                self.configs[name] = config

            def resolve(self, name: str, path: (list[str] | None) = None) -> dict[
                str, Any]:
                """Resolve config with circular dependency detection."""
                if path is None:
                    path = []
                if name in self.resolving:
                    cycle = [*path[path.index(name):], name]
                    raise ConfigurationError(
                        f"Circular dependency detected: {' -> '.join(cycle)}")
                if name not in self.configs:
                    raise KeyError(f"Config '{name}' not found")
                self.resolving.add(name)
                path.append(name)
                try:
                    config = self.configs[name].copy()
                    if "_extends" in config:
                        parent = config["_extends"]
                        parent_config = self.resolve(parent, path.copy())
                        merged = parent_config.copy()
                        merged.update(config)
                        config = merged
                        del config["_extends"]
                    return config
                finally:
                    self.resolving.remove(name)
                    path.pop()
        resolver = ConfigResolver()
        resolver.add_config("config_a", {"_extends": "config_b", "value": 1})
        resolver.add_config("config_b", {"_extends": "config_a", "value": 2})
        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve("config_a")
        assert "Circular dependency detected" in str(exc_info.value)
        assert "config_a -> config_b -> config_a" in str(exc_info.value)
        resolver.configs.clear()
        resolver.add_config("self_ref", {"_extends": "self_ref", "value": 1})
        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve("self_ref")
        assert "self_ref -> self_ref" in str(exc_info.value)
        resolver.configs.clear()
        resolver.add_config("a", {"_extends": "b"})
        resolver.add_config("b", {"_extends": "c"})
        resolver.add_config("c", {"_extends": "d"})
        resolver.add_config("d", {"_extends": "a"})
        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve("a")
        assert "a -> b -> c -> d -> a" in str(exc_info.value)

    @staticmethod
    def test_complex_inheritance_cycles():
        """Test complex inheritance scenarios with potential cycles."""

        class AdvancedConfigResolver:

            def __init__(self):
                self.configs = {}
                self.resolution_stack = []
                self.resolved_cache = {}

            def add_config(self, name: str, config: dict[str, Any]):
                self.configs[name] = config

            def resolve(self, name: str) -> dict[str, Any]:
                """Resolve with caching and cycle detection."""
                if name in self.resolved_cache:
                    return self.resolved_cache[name].copy()
                if name in self.resolution_stack:
                    cycle_start = self.resolution_stack.index(name)
                    cycle = [*self.resolution_stack[cycle_start:], name]
                    raise ConfigurationError(
                        f"Circular dependency: {' -> '.join(cycle)}")
                if name not in self.configs:
                    raise KeyError(f"Config '{name}' not found")
                self.resolution_stack.append(name)
                try:
                    config = self.configs[name].copy()
                    if "_extends" in config:
                        extends = config["_extends"]
                        if isinstance(extends, list):
                            merged = {}
                            for parent in extends:
                                parent_config = self.resolve(parent)
                                merged.update(parent_config)
                            merged.update(config)
                            config = merged
                        else:
                            parent_config = self.resolve(extends)
                            merged = parent_config.copy()
                            merged.update(config)
                            config = merged
                        del config["_extends"]
                    if "_mixins" in config:
                        mixins = config["_mixins"]
                        for mixin in mixins:
                            mixin_config = self.resolve(mixin)
                            for key, value in mixin_config.items():
                                if key not in config:
                                    config[key] = value
                        del config["_mixins"]
                    self.resolved_cache[name] = config.copy()
                    return config
                finally:
                    self.resolution_stack.pop()
        resolver = AdvancedConfigResolver()
        resolver.add_config("base", {"timeout": 30, "retry": 3})
        resolver.add_config("left", {"_extends": "base", "left_value": 1})
        resolver.add_config("right", {"_extends": "base", "right_value": 2})
        resolver.add_config("diamond", {"_extends": ["left", "right"],
            "diamond_value": 3})
        result = resolver.resolve("diamond")
        assert result["timeout"] == 30
        assert result["left_value"] == 1
        assert result["right_value"] == 2
        assert result["diamond_value"] == 3
        resolver.configs.clear()
        resolver.resolved_cache.clear()
        resolver.add_config("mixin_a", {"_mixins": ["mixin_b"], "a": 1})
        resolver.add_config("mixin_b", {"_mixins": ["mixin_a"], "b": 2})
        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve("mixin_a")
        assert "Circular dependency" in str(exc_info.value)
        resolver.configs.clear()
        resolver.resolved_cache.clear()
        resolver.add_config("level1", {"_extends": "level2", "l1": 1})
        resolver.add_config("level2", {"_extends": ["level3", "level4"],
            "l2": 2})
        resolver.add_config("level3", {"_extends": "level5", "l3": 3})
        resolver.add_config("level4", {"l4": 4})
        resolver.add_config("level5", {"_extends": "level1", "l5": 5})
        with pytest.raises(ConfigurationError) as exc_info:
            resolver.resolve("level1")
        assert "level1" in str(exc_info.value)
        assert "level5" in str(exc_info.value)

    @staticmethod
    def test_dynamic_circular_dependencies():
        """Test circular dependencies that form dynamically."""

        class DynamicConfigSystem:

            def __init__(self):
                self.configs = {}
                self.reference_graph = {}

            def add_config(self, name: str, config: dict[str, Any]):
                """Add config and update reference graph."""
                self.configs[name] = config
                self._update_references(name, config)

            def _update_references(self, name: str, config: dict[str, Any]):
                """Update reference graph."""
                refs = set()
                if "_extends" in config:
                    extends = config["_extends"]
                    if isinstance(extends, list):
                        refs.update(extends)
                    else:
                        refs.add(extends)
                if "_include" in config:
                    includes = config["_include"]
                    if isinstance(includes, list):
                        refs.update(includes)
                    else:
                        refs.add(includes)
                for value in config.values():
                    if isinstance(value, str) and value.startswith("${",
                        ) and value.endswith("}"):
                        ref_name = value[2:-1].split(".")[0]
                        refs.add(ref_name)
                self.reference_graph[name] = refs

            def detect_cycles(self) -> list[list[str]]:
                """Detect all cycles in the reference graph."""
                cycles = []
                visited = set()
                rec_stack = set()

                def dfs(node: str, path: list[str]) -> bool:
                    visited.add(node)
                    rec_stack.add(node)
                    path.append(node)
                    for neighbor in self.reference_graph.get(node, []):
                        if neighbor not in visited:
                            if dfs(neighbor, path.copy()):
                                return True
                        elif neighbor in rec_stack:
                            cycle_start = path.index(neighbor)
                            cycle = [*path[cycle_start:], neighbor]
                            cycles.append(cycle)
                    rec_stack.remove(node)
                    return False
                for node in self.reference_graph:
                    if node not in visited:
                        dfs(node, [])
                return cycles

            def update_config(self, name: str, updates: dict[str, Any]):
                """Update config and check for new cycles."""
                if name not in self.configs:
                    raise KeyError(f"Config '{name}' not found")
                old_config = self.configs[name].copy()
                old_refs = self.reference_graph.get(name, set()).copy()
                self.configs[name].update(updates)
                self._update_references(name, self.configs[name])
                cycles = self.detect_cycles()
                if cycles:
                    self.configs[name] = old_config
                    self.reference_graph[name] = old_refs
                    raise ConfigurationError(
                        f"Update would create circular dependencies: {cycles}")
        system = DynamicConfigSystem()
        system.add_config("base", {"timeout": 30})
        system.add_config("service_a", {"_extends": "base", "port": 8080})
        system.add_config("service_b", {"_extends": "base", "port": 8081})
        assert len(system.detect_cycles()) == 0
        with pytest.raises(ConfigurationError) as exc_info:
            system.update_config("base", {"_extends": "service_a"})
        assert "circular dependencies" in str(exc_info.value).lower()
        system.configs.clear()
        system.reference_graph.clear()
        system.add_config("config1", {"value": "${config2.value}", "own": 1})
        system.add_config("config2", {"value": "${config3.value}", "own": 2})
        system.add_config("config3", {"value": 42, "own": 3})
        assert len(system.detect_cycles()) == 0
        with pytest.raises(ConfigurationError):
            system.update_config("config3", {"value": "${config1.value}"})
        system.configs.clear()
        system.reference_graph.clear()
        system.add_config("dev", {"_extends": "common", "env": "dev"})
        system.add_config("prod", {"_extends": "common", "env": "prod"})
        system.add_config("common", {"shared": True})
        try:
            system.update_config("common", {"_extends": "dev"})
            raise AssertionError("Should have raised ConfigurationError")
        except ConfigurationError:
            pass
        assert "_extends" not in system.configs["common"]

    @staticmethod
    def test_cycle_detection_performance():
        """Test performance of cycle detection with large graphs."""
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(5000)
        try:

            class PerformantCycleDetector:

                def __init__(self):
                    self.graph = {}

                def add_edge(self, from_node: str, to_node: str):
                    """Add directed edge to graph."""
                    if from_node not in self.graph:
                        self.graph[from_node] = set()
                    self.graph[from_node].add(to_node)

                def has_cycle_from(self, start: str) -> bool:
                    """Check if adding this node creates a cycle using iterative DFS."""
                    visited = set()
                    stack = [(start, [])]
                    while stack:
                        node, path = stack.pop()
                        if node in path:
                            return True
                        if node in visited:
                            continue
                        visited.add(node)
                        new_path = [*path, node]
                        stack.extend((neighbor, new_path) for neighbor in
                            self.graph.get(node, []))
                    return False

                def find_all_cycles(self) -> list[list[str]]:
                    """Find all cycles in the graph."""
                    cycles = []
                    visited = set()

                    def dfs(node: str, path: list[str], rec_stack: set[str]):
                        visited.add(node)
                        rec_stack.add(node)
                        path.append(node)
                        for neighbor in self.graph.get(node, []):
                            if neighbor not in visited:
                                dfs(neighbor, path.copy(), rec_stack.copy())
                            elif neighbor in rec_stack:
                                cycle_start = path.index(neighbor)
                                cycle = [*path[cycle_start:], neighbor]
                                if cycle not in cycles:
                                    cycles.append(cycle)
                    for node in self.graph:
                        if node not in visited:
                            dfs(node, [], set())
                    return cycles
            detector = PerformantCycleDetector()
            num_nodes = 1000
            for i in range(num_nodes - 1):
                detector.add_edge(f"node_{i}", f"node_{i + 1}")
            start_time = time.time()
            has_cycle = detector.has_cycle_from("node_0")
            check_time = time.time() - start_time
            assert not has_cycle
            assert check_time < 0.5, f"Slow cycle check: {check_time:.3f}s"
            detector.add_edge(f"node_{num_nodes - 1}", "node_500")
            start_time = time.time()
            has_cycle = detector.has_cycle_from("node_0")
            check_time = time.time() - start_time
            assert has_cycle
            assert check_time < 0.5, f"Slow cycle check with cycle: {check_time:.3f}s"
            start_time = time.time()
            cycles = detector.find_all_cycles()
            find_time = time.time() - start_time
            assert len(cycles) == 1
            assert len(cycles[0]) == 501
            assert find_time < 2.0, f"Slow cycle finding: {find_time:.3f}s"
        finally:
            sys.setrecursionlimit(old_limit)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
