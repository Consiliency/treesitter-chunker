"""Integration tests for LogProcessor with real-world scenarios."""

from datetime import datetime, timedelta

from chunker.processors.logs import LogProcessor


class TestLogProcessorIntegration:
    """Integration tests for LogProcessor."""

    def test_process_mixed_format_logs(self):
        """Test processing logs with mixed formats in a single file."""
        processor = LogProcessor(
            config={
                "chunk_by": "time",
                "time_window": 300,
                "group_errors": True,
            },
        )

        # Simulate a real log file with mixed formats
        log_content = """
2024-01-01 08:00:00,000 [INFO] Starting application
Jan  1 08:00:01 server kernel: [123456.789] Memory allocation successful
192.168.1.1 - - [01/Jan/2024:08:00:02 +0000] "GET / HTTP/1.1" 200 1234
2024-01-01 08:00:03,000 ERROR [Thread-1] com.app.Service - Database connection failed
java.sql.SQLException: Connection timeout
    at com.mysql.jdbc.Driver.connect(Driver.java:123)
2024-01-01 08:00:04,000 [WARNING] Retrying database connection
Jan  1 08:00:05 server sshd[1234]: Failed password for invalid user admin
2024-01-01 08:00:06,000 [INFO] Database connection restored
        """.strip()

        chunks = processor.process(log_content)

        # Should detect multiple formats
        formats = set()
        for chunk in chunks:
            formats.update(chunk.metadata.get("formats", []))

        assert "iso_timestamp" in formats
        assert "syslog" in formats
        assert "apache" in formats
        assert "log4j" in formats

        # Should group error with stack trace
        error_chunks = [c for c in chunks if c.metadata.get("has_errors")]
        assert len(error_chunks) > 0
        assert "java.sql.SQLException" in error_chunks[0].content

    def test_streaming_large_log_simulation(self):
        """Test streaming processing of a simulated large log file."""
        processor = LogProcessor(
            config={
                "chunk_by": "lines",
                "max_chunk_lines": 100,
            },
        )

        def generate_large_log():
            """Simulate a large log file being read line by line."""
            base_time = datetime(2024, 1, 1, 8, 0, 0)

            for i in range(1000):
                timestamp = base_time + timedelta(seconds=i)
                level = "INFO" if i % 10 != 0 else "ERROR"
                yield f"{timestamp.isoformat()} [{level}] Event {i}: Processing request\n"

                # Add some multi-line entries
                if level == "ERROR":
                    yield f"  Stack trace for event {i}\n"
                    yield "    at module.function(file.py:123)\n"

        chunks = list(processor.process_stream(generate_large_log()))

        # Should create appropriate number of chunks
        assert len(chunks) > 0

        # Each chunk should respect max lines
        for chunk in chunks:
            assert chunk.metadata["entry_count"] <= 100

        # Total lines should be preserved
        total_lines = sum(chunk.line_count for chunk in chunks)
        assert total_lines == 1200  # 1000 main + 200 stack trace lines

    def test_session_tracking_scenario(self):
        """Test tracking user sessions across log entries."""
        processor = LogProcessor(
            config={
                "chunk_by": "session",
                "detect_sessions": True,
            },
        )

        log_content = """
2024-01-01 08:00:00 [INFO] User alice attempting login
2024-01-01 08:00:01 [INFO] Authentication successful for alice
2024-01-01 08:00:02 [INFO] Session started for user alice (session_id: abc123)
2024-01-01 08:00:03 [INFO] User alice accessed /dashboard
2024-01-01 08:00:04 [INFO] User alice accessed /profile
2024-01-01 08:00:05 [INFO] User alice initiated logout
2024-01-01 08:00:06 [INFO] Session ended for user alice
2024-01-01 08:01:00 [INFO] User bob attempting login
2024-01-01 08:01:01 [ERROR] Authentication failed for bob: Invalid password
2024-01-01 08:01:02 [INFO] User bob attempting login (retry)
2024-01-01 08:01:03 [INFO] Authentication successful for bob
2024-01-01 08:01:04 [INFO] Session started for user bob (session_id: def456)
2024-01-01 08:01:05 [INFO] User bob accessed /dashboard
        """.strip()

        chunks = processor.process(log_content)

        # Should create session-based chunks
        session_ids = [c.metadata.get("session_id") for c in chunks]
        assert all(sid is not None for sid in session_ids)

        # Each session should contain relevant entries
        for chunk in chunks:
            lines = chunk.content.lower()
            # Session chunks should be coherent
            if "alice" in lines:
                assert "bob" not in lines
            if "bob" in lines:
                assert "alice" not in lines

    def test_error_analysis_workflow(self):
        """Test a typical error analysis workflow."""
        # First pass: identify time periods with errors
        processor = LogProcessor(
            config={
                "chunk_by": "time",
                "time_window": 60,  # 1 minute chunks
            },
        )

        log_content = """
2024-01-01 08:00:00 [INFO] System healthy
2024-01-01 08:00:30 [INFO] Processing batch 1
2024-01-01 08:01:00 [ERROR] Failed to process item 42
2024-01-01 08:01:01 [ERROR] Database timeout
2024-01-01 08:01:02 [ERROR] Retry failed
2024-01-01 08:01:30 [INFO] Switching to backup database
2024-01-01 08:02:00 [INFO] Processing resumed
2024-01-01 08:02:30 [INFO] Batch 2 completed
2024-01-01 08:03:00 [CRITICAL] Out of memory error
2024-01-01 08:03:01 [INFO] Emergency garbage collection
2024-01-01 08:03:30 [INFO] Memory recovered
        """.strip()

        chunks = processor.process(log_content)

        # Find chunks with errors
        error_periods = [
            chunk
            for chunk in chunks
            if any(
                level in chunk.metadata.get("levels", [])
                for level in ["ERROR", "CRITICAL"]
            )
        ]

        assert len(error_periods) >= 2

        # Second pass: deep dive into error periods with context
        processor2 = LogProcessor(
            config={
                "chunk_by": "lines",
                "max_chunk_lines": 1000,
                "group_errors": True,
                "context_lines": 2,
            },
        )

        chunks2 = processor2.process(log_content)
        error_chunks = [c for c in chunks2 if c.metadata.get("has_errors")]

        # Should have grouped errors with context
        assert len(error_chunks) > 0
        for chunk in error_chunks:
            # Should include some context lines
            assert chunk.metadata["error_count"] > 0
            assert chunk.line_count > chunk.metadata["error_count"]

    def test_real_world_apache_log_processing(self):
        """Test processing Apache logs for traffic analysis."""
        processor = LogProcessor(
            config={
                "chunk_by": "time",
                "time_window": 300,  # 5 minute chunks
            },
        )

        # Simulate Apache access log
        log_content = """
192.168.1.100 - alice [01/Jan/2024:08:00:00 +0000] "GET /api/users HTTP/1.1" 200 1234 "-" "Mozilla/5.0"
192.168.1.100 - alice [01/Jan/2024:08:00:01 +0000] "GET /api/users/123 HTTP/1.1" 200 567 "-" "Mozilla/5.0"
192.168.1.101 - bob [01/Jan/2024:08:00:02 +0000] "POST /api/orders HTTP/1.1" 201 89 "-" "curl/7.68.0"
192.168.1.102 - - [01/Jan/2024:08:00:03 +0000] "GET /admin HTTP/1.1" 403 0 "-" "Bot/1.0"
192.168.1.103 - carol [01/Jan/2024:08:04:00 +0000] "GET /api/products HTTP/1.1" 500 123 "-" "Mobile/1.0"
192.168.1.103 - carol [01/Jan/2024:08:04:01 +0000] "GET /api/products HTTP/1.1" 500 123 "-" "Mobile/1.0"
192.168.1.104 - - [01/Jan/2024:08:05:00 +0000] "GET /health HTTP/1.1" 200 15 "-" "kube-probe/1.0"
192.168.1.100 - alice [01/Jan/2024:08:10:00 +0000] "POST /api/logout HTTP/1.1" 200 0 "-" "Mozilla/5.0"
        """.strip()

        chunks = processor.process(log_content)

        # Analyze traffic patterns
        for chunk in chunks:
            assert "apache" in chunk.metadata["formats"]

            # Could analyze status codes, IPs, etc.
            lines = chunk.content.split("\n")
            status_codes = []
            for line in lines:
                if '" 200 ' in line:
                    status_codes.append(200)
                elif '" 500 ' in line:
                    status_codes.append(500)
                elif '" 403 ' in line:
                    status_codes.append(403)

            # Chunks should preserve temporal ordering
            if chunk.metadata.get("start_time"):
                assert chunk.metadata.get("end_time")

    def test_custom_application_log_format(self):
        """Test handling custom log format with configuration."""
        # Define custom format for a specific application
        custom_pattern = r"^(?P<timestamp>\d{2}:\d{2}:\d{2}\.\d{3})\s+\|(?P<level>\w+)\|\s+\[(?P<module>[^\]]+)\]\s+(?P<message>.*)"

        processor = LogProcessor(
            config={
                "patterns": {
                    "custom_app": custom_pattern,
                },
                "chunk_by": "level",
            },
        )

        log_content = """
08:00:00.000 |INFO| [auth.login] User authentication initiated
08:00:00.100 |DEBUG| [auth.validate] Checking credentials
08:00:00.200 |INFO| [auth.login] Login successful
08:00:01.000 |ERROR| [db.connect] Connection pool exhausted
08:00:01.100 |ERROR| [api.handler] Request failed due to DB error
08:00:02.000 |WARN| [cache.manager] Cache hit rate below threshold
08:00:03.000 |INFO| [api.health] Health check passed
        """.strip()

        chunks = processor.process(log_content)

        # Should detect custom format
        assert any(
            "custom_app" in chunk.metadata.get("formats", []) for chunk in chunks
        )

        # Should group by level
        levels = {chunk.metadata.get("log_level") for chunk in chunks}
        assert "ERROR" in levels
        assert "INFO" in levels
