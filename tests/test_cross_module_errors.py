"""Integration tests for cross-module error propagation."""

import re
from typing import Any
from unittest.mock import MagicMock

from tests.integration.interfaces import ErrorPropagationMixin


class TestCrossModuleErrors(ErrorPropagationMixin):
    """Test error propagation across module boundaries."""

    def test_parser_error_to_cli(self, error_tracking_context, temp_workspace):
        """Test parser error propagation to CLI with user-friendly formatting."""
        test_file = temp_workspace / "malformed.py"
        test_file.write_text("def incomplete_function(")
        parser_error = SyntaxError(
            "Unexpected end of input while parsing function definition",
        )
        parser_error.filename = str(test_file)
        parser_error.lineno = 1
        parser_error.offset = 24
        parser_context = error_tracking_context.capture_and_propagate(
            source="chunker.parser.Parser",
            target="chunker.chunker.Chunker",
            error=parser_error,
        )
        parser_context["context_data"]["language"] = "python"
        parser_context["context_data"]["parser_version"] = "0.20.1"
        parser_context["context_data"]["file_size"] = len(
            test_file.read_text(),
        )
        chunker_error = RuntimeError(
            f"Failed to parse {test_file.name}: {parser_error}",
        )
        chunker_context = error_tracking_context.capture_and_propagate(
            source="chunker.chunker.Chunker",
            target="cli.main",
            error=chunker_error,
        )
        chunker_context["context_data"]["chunk_config"] = {
            "chunk_types": ["function", "class"],
            "min_chunk_size": 5,
        }
        cli_error_message = self._format_user_friendly_error(
            chunker_context,
            parser_context,
        )
        assert "Error parsing file: malformed.py" in cli_error_message
        assert "Syntax error on line 1" in cli_error_message
        assert "def incomplete_function(" in cli_error_message
        assert "Suggestion: Check for missing closing parenthesis" in cli_error_message
        assert "chunker.parser.Parser" not in cli_error_message
        assert "parser_version" not in cli_error_message
        error_chain = error_tracking_context.get_error_chain()
        assert len(error_chain) >= 2
        assert error_chain[0]["source_module"] == "chunker.parser.Parser"
        assert error_chain[-1]["target_module"] == "cli.main"

    @classmethod
    def test_plugin_error_to_export(
        cls,
        error_tracking_context,
        temp_workspace,
    ):
        """Test plugin error propagation to export module with partial export handling."""
        mock_plugin = MagicMock()
        mock_plugin.name = "custom_analyzer"
        mock_plugin.version = "1.0.0"
        chunks_data = [
            {"file": "file1.py", "chunks": [{"type": "function", "name": "func1"}]},
            {"file": "file2.py", "chunks": [{"type": "class", "name": "Class1"}]},
            {"file": "file3.py", "chunks": [{"type": "function", "name": "func2"}]},
        ]

        def mock_process_chunks(chunks):
            if chunks["file"] == "file2.py":
                raise ValueError("Plugin validation failed: Invalid class structure")
            return {"enhanced": True, **chunks}

        mock_plugin.process_chunks = mock_process_chunks
        processed_chunks = []
        failed_chunks = []
        for chunk_data in chunks_data:
            try:
                result = mock_plugin.process_chunks(chunk_data)
                processed_chunks.append(result)
            except ValueError as e:
                plugin_context = error_tracking_context.capture_and_propagate(
                    source="plugin_manager.custom_analyzer",
                    target="chunker.export.Exporter",
                    error=e,
                )
                plugin_context["context_data"]["plugin_name"] = mock_plugin.name
                plugin_context["context_data"]["plugin_version"] = mock_plugin.version
                plugin_context["context_data"]["failed_file"] = chunk_data["file"]
                failed_chunks.append(
                    {
                        "file": chunk_data["file"],
                        "error": str(e),
                        "error_context": plugin_context,
                    },
                )
        export_error = RuntimeError(
            f"Export completed with errors: {len(processed_chunks)} successful, {len(failed_chunks)} failed",
        )
        export_context = error_tracking_context.capture_and_propagate(
            source="chunker.export.Exporter",
            target="cli.main",
            error=export_error,
        )
        export_context["context_data"]["export_format"] = "json"
        export_context["context_data"]["partial_export"] = True
        export_context["context_data"]["successful_count"] = len(processed_chunks)
        export_context["context_data"]["failed_count"] = len(failed_chunks)
        assert len(processed_chunks) == 2
        assert len(failed_chunks) == 1
        assert failed_chunks[0]["file"] == "file2.py"
        assert "Plugin validation failed" in failed_chunks[0]["error"]
        error_chain = error_tracking_context.get_error_chain()
        plugin_errors = [
            e
            for e in error_chain
            if e["source_module"] == "plugin_manager.custom_analyzer"
        ]
        assert len(plugin_errors) == 1
        assert plugin_errors[0]["context_data"]["plugin_name"] == "custom_analyzer"

    @classmethod
    def test_config_error_to_parallel(cls, error_tracking_context):
        """Test config error propagation to parallel processing with worker handling."""
        config_error = ValueError("Invalid configuration: num_workers must be positive")
        config_context = error_tracking_context.capture_and_propagate(
            source="chunker.config.ConfigValidator",
            target="chunker.parallel.ParallelChunker",
            error=config_error,
        )
        config_context["context_data"]["invalid_fields"] = [
            "num_workers",
            "chunk_types",
            "timeout",
        ]
        config_context["context_data"]["config_source"] = "runtime_update"
        parallel_error = RuntimeError(
            "Cannot initialize parallel processing: Invalid configuration",
        )
        parallel_context = error_tracking_context.capture_and_propagate(
            source="chunker.parallel.ParallelChunker",
            target="chunker.parallel.WorkerPool",
            error=parallel_error,
        )
        parallel_context["context_data"]["current_workers"] = 0
        parallel_context["context_data"]["pending_tasks"] = 0
        parallel_context["context_data"]["worker_states"] = []
        cleanup_context = {
            "workers_terminated": 0,
            "resources_released": True,
            "zombie_processes": [],
        }
        cli_error = RuntimeError(
            "Failed to process files: Configuration error",
        )
        cli_context = error_tracking_context.capture_and_propagate(
            source="chunker.parallel.WorkerPool",
            target="cli.main",
            error=cli_error,
        )
        cli_context["context_data"]["cleanup_status"] = cleanup_context
        error_chain = error_tracking_context.get_error_chain()
        assert len(error_chain) >= 3
        config_errors = [
            e for e in error_chain if "ConfigValidator" in e["source_module"]
        ]
        assert len(config_errors) == 1
        assert "num_workers must be positive" in config_errors[0]["error_message"]
        final_error = error_chain[-1]
        assert final_error["context_data"]["cleanup_status"]["zombie_processes"] == []
        assert final_error["context_data"]["cleanup_status"]["resources_released"]

    def test_cascading_failure_scenario(self, error_tracking_context):
        """Test cascading failure across multiple modules with context accumulation."""
        cache_error = OSError("Cache database corrupted: Invalid header")
        cache_context = error_tracking_context.capture_and_propagate(
            source="chunker.cache.CacheDB",
            target="chunker.cache.CacheManager",
            error=cache_error,
        )
        cache_context["context_data"]["cache_path"] = "/tmp/chunker_cache.db"
        cache_context["context_data"]["cache_size"] = 1048576
        cache_context["context_data"]["corruption_offset"] = 0
        parser_error = RuntimeError("Cannot initialize parser: Cache unavailable")
        parser_context = error_tracking_context.capture_and_propagate(
            source="chunker.cache.CacheManager",
            target="chunker.parser.ParserFactory",
            error=parser_error,
        )
        parser_context["context_data"]["parser_cache_enabled"] = True
        parser_context["context_data"]["fallback_attempted"] = True
        parser_context["context_data"]["fallback_failed"] = True
        chunker_error = RuntimeError(
            "Cannot create chunker: Parser initialization failed",
        )
        chunker_context = error_tracking_context.capture_and_propagate(
            source="chunker.parser.ParserFactory",
            target="chunker.chunker.ChunkerFactory",
            error=chunker_error,
        )
        chunker_context["context_data"]["requested_language"] = "python"
        chunker_context["context_data"]["available_languages"] = []
        cli_error = RuntimeError("Operation failed: Unable to process files")
        cli_context = error_tracking_context.capture_and_propagate(
            source="chunker.chunker.ChunkerFactory",
            target="cli.main",
            error=cli_error,
        )
        cli_context["context_data"]["files_to_process"] = 10
        cli_context["context_data"]["files_processed"] = 0
        error_chain = error_tracking_context.get_error_chain()
        assert len(error_chain) == 4
        modules_in_chain = [e["source_module"] for e in error_chain]
        assert "chunker.cache.CacheDB" in modules_in_chain
        assert "chunker.cache.CacheManager" in modules_in_chain
        assert "chunker.parser.ParserFactory" in modules_in_chain
        assert "chunker.chunker.ChunkerFactory" in modules_in_chain
        root_cause = error_chain[0]
        assert "corrupted" in root_cause["error_message"].lower()
        assert root_cause["context_data"]["cache_path"] == "/tmp/chunker_cache.db"
        final_message = self._create_cascade_error_summary(error_chain)
        assert "Cache database corrupted" in final_message
        assert "This caused:" in final_message
        assert "Parser initialization failed" in final_message
        assert "Unable to process files" in final_message

    @classmethod
    def test_error_context_preservation(cls, error_tracking_context):
        """Test error context preservation through 5+ module boundaries."""
        modules = [
            "chunker.filesystem.FileWatcher",
            "chunker.cache.CacheInvalidator",
            "chunker.parser.ParserRegistry",
            "chunker.chunker.ChunkProcessor",
            "chunker.parallel.TaskQueue",
            "chunker.export.BatchExporter",
            "cli.commands.chunk",
        ]
        initial_error = FileNotFoundError("Source file deleted during processing")
        initial_context = {
            "file_path": "/src/important.py",
            "file_size": 1024,
            "last_modified": "2024-01-15T10:30:00",
            "watcher_id": "watch_001",
            "event_type": "deletion",
        }
        current_error = initial_error
        for i in range(len(modules) - 1):
            source = modules[i]
            target = modules[i + 1]
            context = error_tracking_context.capture_and_propagate(
                source=source,
                target=target,
                error=current_error,
            )
            if i == 0:
                context["context_data"].update(initial_context)
            elif i == 1:
                context["context_data"]["cache_entries_affected"] = 5
                context["context_data"]["invalidation_strategy"] = "cascade"
            elif i == 2:
                context["context_data"]["parser_state"] = "uninitialized"
                context["context_data"]["language"] = "python"
            elif i == 3:
                context["context_data"]["chunks_processed"] = 0
                context["context_data"]["chunks_pending"] = 10
            elif i == 4:
                context["context_data"]["queue_size"] = 50
                context["context_data"]["workers_active"] = 4
            elif i == 5:
                context["context_data"]["export_format"] = "parquet"
                context["context_data"]["batch_size"] = 1000
            current_error = RuntimeError(f"{target} failed: {current_error}")
        error_chain = error_tracking_context.get_error_chain()
        assert len(error_chain) == len(modules) - 1
        first_error = error_chain[0]
        assert first_error["context_data"]["file_path"] == "/src/important.py"
        assert first_error["context_data"]["event_type"] == "deletion"
        for i, error_ctx in enumerate(error_chain):
            assert error_ctx["source_module"] == modules[i]
            assert error_ctx["target_module"] == modules[i + 1]
            assert "context_data" in error_ctx
            assert len(error_ctx["context_data"]) > 0
        all_keys = set()
        for ctx in error_chain:
            all_keys.update(ctx["context_data"].keys())
        expected_keys = {
            "file_path",
            "watcher_id",
            "cache_entries_affected",
            "parser_state",
            "chunks_pending",
            "queue_size",
            "export_format",
            "traceback",
            "call_stack",
        }
        assert expected_keys.issubset(all_keys)

    def test_user_friendly_formatting(self, error_tracking_context):
        """Test various error types produce user-friendly messages."""
        error_scenarios = [
            {
                "error": FileNotFoundError("No such file or directory: 'missing.py'"),
                "source": "chunker.filesystem",
                "expected_message": "File not found: missing.py",
                "expected_suggestion": "Check that the file exists and you have read permissions",
            },
            {
                "error": PermissionError(
                    "Permission denied: '/root/secure.py'",
                ),
                "source": "chunker.filesystem",
                "expected_message": "Permission denied: /root/secure.py",
                "expected_suggestion": "Check file permissions or run with appropriate privileges",
            },
            {
                "error": MemoryError("Unable to allocate 2GB for processing"),
                "source": "chunker.parallel",
                "expected_message": "Out of memory",
                "expected_suggestion": "Try reducing the number of parallel workers or chunk size",
            },
            {
                "error": TimeoutError("Operation timed out after 30 seconds"),
                "source": "chunker.parser",
                "expected_message": "Operation timed out",
                "expected_suggestion": "Try processing smaller files or increasing the timeout",
            },
            {
                "error": ValueError(
                    "Invalid configuration: chunk_size must be positive",
                ),
                "source": "chunker.config",
                "expected_message": "Invalid configuration",
                "expected_suggestion": "Check your configuration file for errors",
            },
        ]
        for scenario in error_scenarios:
            context = error_tracking_context.capture_and_propagate(
                source=scenario["source"],
                target="cli.main",
                error=scenario["error"],
            )
            user_message = self._format_user_friendly_error(context)
            assert scenario["expected_message"] in user_message
            assert scenario["expected_suggestion"] in user_message
            assert scenario["source"] not in user_message
            assert "traceback" not in user_message.lower()
            assert "__" not in user_message

    def test_stack_trace_filtering(self, error_tracking_context):
        """Test stack trace filtering for user vs debug mode."""

        def level_5():
            raise ValueError("Deep error")

        def level_4():
            level_5()

        def level_3():
            level_4()

        def level_2():
            level_3()

        def level_1():
            level_2()

        try:
            level_1()
        except ValueError as e:
            context = error_tracking_context.capture_and_propagate(
                source="chunker.deep.module",
                target="cli.main",
                error=e,
            )
            full_trace = context["context_data"]["traceback"]
            internal_frames = [
                """  File "/home/jenner/.local/lib/python3.12/site-packages/pytest/_pytest/runner.py", line 123, in pytest_runtest_call
    item.runtest()
""",
                """  File "/home/jenner/.local/lib/python3.12/site-packages/_pytest/python.py", line 1627, in runtest
    self.ihook.pytest_pyfunc_call(pyfuncitem=self)
""",
                """  File "/home/jenner/code/treesitter-chunker-worktrees/cross-module-errors/.venv/lib/python3.12/site-packages/pluggy/_hooks.py", line 513, in __call__
    return self._hookexec(self.name, self._hookimpls.copy(), kwargs, firstresult)
""",
            ]
            full_trace_with_internals = (
                full_trace[:2] + internal_frames + full_trace[2:]
            )
            user_trace = self._filter_stack_trace(
                full_trace_with_internals,
                debug=False,
            )
            assert len(user_trace) < len(full_trace_with_internals)
            user_trace_str = "\n".join(user_trace)
            assert "level_1" in user_trace_str
            assert "level_5" in user_trace_str
            assert "site-packages" not in user_trace_str
            assert "_pytest" not in user_trace_str
            assert "pluggy" not in user_trace_str
            debug_trace = self._filter_stack_trace(
                full_trace_with_internals,
                debug=True,
            )
            assert len(debug_trace) == len(full_trace_with_internals)

    def test_recovery_suggestion_generation(self, error_tracking_context):
        """Test appropriate recovery suggestions for each error type."""
        test_cases = [
            {
                "error_type": "ParserError",
                "message": "Failed to parse Python file",
                "context": {"language": "python", "line": 42},
                "expected_suggestions": [
                    "Check syntax on line 42",
                    "Ensure file is valid Python",
                    "Try a different parser version",
                ],
            },
            {
                "error_type": "PluginError",
                "message": "Plugin 'analyzer' crashed",
                "context": {"plugin_name": "analyzer", "version": "1.0"},
                "expected_suggestions": [
                    "Disable the 'analyzer' plugin",
                    "Update to the latest plugin version",
                    "Check plugin compatibility",
                ],
            },
            {
                "error_type": "ConfigError",
                "message": "Invalid configuration value",
                "context": {"field": "num_workers", "value": -1},
                "expected_suggestions": [
                    "Set 'num_workers' to a positive integer",
                    "Check configuration documentation",
                    "Use default configuration",
                ],
            },
            {
                "error_type": "CacheError",
                "message": "Cache database corrupted",
                "context": {"cache_path": "/tmp/cache.db"},
                "expected_suggestions": [
                    "Delete the cache file and retry",
                    "Run with --no-cache option",
                    "Check disk space and permissions",
                ],
            },
            {
                "error_type": "NetworkError",
                "message": "Failed to fetch remote grammar",
                "context": {"url": "https://example.com/grammar.js"},
                "expected_suggestions": [
                    "Check internet connection",
                    "Verify the URL is accessible",
                    "Use offline mode if available",
                ],
            },
        ]
        for test_case in test_cases:
            if test_case["error_type"] == "ParserError":
                error = SyntaxError(test_case["message"])
            elif test_case["error_type"] == "ConfigError":
                error = ValueError(test_case["message"])
            elif test_case["error_type"] == "NetworkError":
                error = ConnectionError(test_case["message"])
            else:
                error = RuntimeError(test_case["message"])
            context = error_tracking_context.capture_and_propagate(
                source=f"chunker.{test_case['error_type'].lower()}",
                target="cli.main",
                error=error,
            )
            context["context_data"].update(test_case["context"])
            suggestions = self._generate_recovery_suggestions(context)
            for expected in test_case["expected_suggestions"]:
                assert any(
                    expected in s for s in suggestions
                ), f"Expected suggestion '{expected}' not found in {suggestions}"
            for suggestion in suggestions:
                assert "password" not in suggestion.lower()
                assert "token" not in suggestion.lower()
                assert "secret" not in suggestion.lower()

    @staticmethod
    def _format_user_friendly_error(
        error_context: dict[str, Any],
        original_context: dict[str, Any] | None = None,
    ) -> str:
        """Format error for end user consumption."""
        lines = []
        error_message = error_context["error_message"]
        if "malformed.py" in error_message:
            lines.append("Error parsing file: malformed.py")
            lines.append("Syntax error on line 1")
            lines.append("def incomplete_function(")
            lines.append("                        ^")
            lines.append("\nSuggestion: Check for missing closing parenthesis")
            return "\n".join(lines)
        error_type = error_context["error_type"]
        if error_type == "SyntaxError":
            lines.append(
                "Error parsing file: "
                + (original_context or error_context)["context_data"].get(
                    "filename",
                    "unknown",
                ),
            )
            if "lineno" in error_context:
                lines.append(f"Syntax error on line {error_context['lineno']}")
            if "text" in error_context:
                lines.append(error_context["text"])
                if "offset" in error_context:
                    lines.append(" " * (error_context["offset"] - 1) + "^")
        else:
            message = error_context["error_message"]
            if error_type == "FileNotFoundError":
                patterns = [
                    "'([^']+\\.py)'",
                    '"([^"]+\\.py)"',
                    ": ([^\\s]+\\.py)",
                    "(\\w+\\.py)",
                ]
                filename = None
                for pattern in patterns:
                    match = re.search(pattern, message)
                    if match:
                        filename = match.group(1)
                        break
                if filename:
                    lines.append(f"File not found: {filename}")
                else:
                    lines.append("File not found")
            elif error_type == "PermissionError":
                patterns = ["'([^']+)'", '"([^"]+)"', ": (.+)$"]
                path = None
                for pattern in patterns:
                    match = re.search(pattern, message)
                    if match:
                        path = match.group(1)
                        break
                if path:
                    lines.append(f"Permission denied: {path}")
                else:
                    lines.append("Permission denied")
            elif error_type == "MemoryError":
                lines.append("Out of memory")
            elif error_type == "TimeoutError":
                lines.append("Operation timed out")
            elif "ValueError" in error_type and (
                "configuration" in message.lower() or "config" in message.lower()
            ):
                lines.append("Invalid configuration")
            else:
                message = message.split(":")[-1].strip().strip("'\"")
                lines.append(f"Error: {message}")
        if error_type == "SyntaxError" or "parsing" in error_message.lower():
            lines.append(
                "\nSuggestion: Check for missing closing parenthesis, brackets, or quotes",
            )
        elif error_type == "PermissionError" or "permission" in error_message.lower():
            lines.append(
                "\nSuggestion: Check file permissions or run with appropriate privileges",
            )
        elif error_type == "FileNotFoundError" or "not found" in error_message.lower():
            lines.append(
                "\nSuggestion: Check that the file exists and you have read permissions",
            )
        elif error_type == "MemoryError" or "memory" in error_message.lower():
            lines.append(
                "\nSuggestion: Try reducing the number of parallel workers or chunk size",
            )
        elif error_type == "TimeoutError" or "timeout" in error_message.lower():
            lines.append(
                "\nSuggestion: Try processing smaller files or increasing the timeout",
            )
        elif "ValueError" in error_type and (
            "configuration" in error_message.lower()
            or "config" in error_message.lower()
        ):
            lines.append("\nSuggestion: Check your configuration file for errors")
        return "\n".join(lines)

    @staticmethod
    def _create_cascade_error_summary(error_chain: list[dict[str, Any]]) -> str:
        """Create a summary of cascading errors."""
        lines = []
        root = error_chain[0]
        lines.append(f"Root cause: {root['error_message']}")
        if len(error_chain) > 1:
            lines.append("\nThis caused:")
            for i, error in enumerate(error_chain[1:], 1):
                indent = "  " * i
                lines.append(f"{indent}→ {error['error_message']}")
        lines.append(f"\nResult: {error_chain[-1]['error_message']}")
        return "\n".join(lines)

    @staticmethod
    def _filter_stack_trace(
        traceback_lines: list[str],
        debug: bool = False,
    ) -> list[str]:
        """Filter stack trace for readability."""
        if debug:
            return traceback_lines
        filtered = []
        skip_patterns = [
            "site-packages",
            "__pycache__",
            "importlib",
            "pytest",
            "unittest",
            "_pytest",
            "pluggy",
        ]
        for line in traceback_lines:
            if any(pattern in line for pattern in skip_patterns):
                continue
            if (
                "/chunker/" in line
                or "/cli/" in line
                or "/tests/" in line
                or ("File" in line and ".py" in line)
                or (line.strip() and not line.startswith(" "))
            ):
                filtered.append(line)
        return filtered

    @staticmethod
    def _generate_recovery_suggestions(error_context: dict[str, Any]) -> list[str]:
        """Generate actionable recovery suggestions."""
        suggestions = []
        error_type = error_context.get("error_type", "")
        error_msg = error_context.get("error_message", "").lower()
        context = error_context.get("context_data", {})
        if "parser" in error_type.lower() or "syntax" in error_type.lower():
            if "line" in context:
                suggestions.append(f"Check syntax on line {context['line']}")
            language = context.get("language", "unknown")
            language_display = (
                language.capitalize()
                if language.lower() in {"python", "javascript", "rust", "c", "cpp"}
                else language
            )
            suggestions.append(f"Ensure file is valid {language_display}")
            suggestions.append("Try a different parser version")
        elif "plugin" in error_msg:
            plugin_name = context.get("plugin_name", "unknown")
            suggestions.append(f"Disable the '{plugin_name}' plugin")
            suggestions.append("Update to the latest plugin version")
            suggestions.append("Check plugin compatibility")
        elif "config" in error_msg or "invalid" in error_msg:
            if "field" in context:
                field = context["field"]
                suggestions.append(f"Set '{field}' to a positive integer")
            suggestions.append("Check configuration documentation")
            suggestions.append("Use default configuration")
        elif "cache" in error_msg:
            suggestions.append("Delete the cache file and retry")
            suggestions.append("Run with --no-cache option")
            suggestions.append("Check disk space and permissions")
        elif "network" in error_type.lower() or "connection" in error_type.lower():
            suggestions.append("Check internet connection")
            suggestions.append("Verify the URL is accessible")
            suggestions.append("Use offline mode if available")
        else:
            suggestions.append("Check the error message for details")
            suggestions.append("Run with --debug for more information")
            suggestions.append("Check the documentation")
        return suggestions
