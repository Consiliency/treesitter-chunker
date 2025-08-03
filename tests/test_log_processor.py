"""Tests for the LogProcessor module."""
from pathlib import Path
from textwrap import dedent

import pytest

from chunker.processors.logs import LogProcessor


class TestLogProcessor:
    """Test suite for LogProcessor."""

    @classmethod
    @pytest.fixture
    def processor(cls):
        """Create a default LogProcessor instance."""
        return LogProcessor()

    @staticmethod
    @pytest.fixture
    def syslog_content():
        """Sample syslog format content."""
        return dedent(
            """
            Jan  1 00:00:00 server01 sshd[1234]: Accepted password for user from 192.168.1.100 port 22 ssh2
            Jan  1 00:00:01 server01 sshd[1234]: pam_unix(sshd:session): session opened for user user
            Jan  1 00:05:00 server01 kernel: [123456.789] Out of memory: Kill process 5678
            Jan  1 00:05:01 server01 kernel: [123456.790] Killed process 5678 (apache2) total-vm:123456kB
            Jan  1 00:10:00 server01 sshd[1234]: pam_unix(sshd:session): session closed for user user
        """,
            ).strip()

    @staticmethod
    @pytest.fixture
    def apache_content():
        """Sample Apache log content."""
        return dedent(
            """
            192.168.1.100 - - [01/Jan/2024:00:00:00 +0000] "GET /index.html HTTP/1.1" 200 1234
            192.168.1.100 - - [01/Jan/2024:00:00:01 +0000] "GET /style.css HTTP/1.1" 200 5678
            192.168.1.101 - - [01/Jan/2024:00:00:02 +0000] "GET /api/data HTTP/1.1" 500 123
            192.168.1.101 - - [01/Jan/2024:00:00:03 +0000] "GET /favicon.ico HTTP/1.1" 404 0
            192.168.1.102 - - [01/Jan/2024:00:05:00 +0000] "POST /api/login HTTP/1.1" 200 456
        """,
            ).strip()

    @staticmethod
    @pytest.fixture
    def application_log_content():
        """Sample application log with ISO timestamps and levels."""
        return dedent(
            """
            2024-01-01 00:00:00,000 [INFO] Application starting up
            2024-01-01 00:00:01,000 [INFO] Loading configuration from config.yaml
            2024-01-01 00:00:02,000 [DEBUG] Configuration loaded: {'host': 'localhost', 'port': 8080}
            2024-01-01 00:00:03,000 [INFO] Starting web server on localhost:8080
            2024-01-01 00:00:04,000 [ERROR] Failed to bind to port 8080: Address already in use
            2024-01-01 00:00:05,000 [ERROR] Traceback (most recent call last):
              File "server.py", line 42, in start_server
                server.bind(('localhost', 8080))
            OSError: [Errno 98] Address already in use
            2024-01-01 00:00:06,000 [CRITICAL] Application failed to start
            2024-01-01 00:00:07,000 [INFO] Shutting down
        """,
            ).strip()

    @staticmethod
    @pytest.fixture
    def java_log_content():
        """Sample Java/Log4j style log content."""
        return dedent(
            """
            2024-01-01 00:00:00,000 INFO [main] com.example.Application - Starting Application v1.0.0
            2024-01-01 00:00:01,000 DEBUG [main] com.example.config.ConfigLoader - Loading properties from application.properties
            2024-01-01 00:00:02,000 INFO [main] com.example.db.DatabaseConnection - Connecting to database: jdbc:mysql://localhost:3306/mydb
            2024-01-01 00:00:03,000 ERROR [main] com.example.db.DatabaseConnection - Failed to connect to database
            java.sql.SQLException: Access denied for user 'root'@'localhost'
                at com.mysql.jdbc.SQLError.createSQLException(SQLError.java:1074)
                at com.mysql.jdbc.MysqlIO.checkErrorPacket(MysqlIO.java:4120)
                at com.mysql.jdbc.MysqlIO.checkErrorPacket(MysqlIO.java:4052)
            2024-01-01 00:00:04,000 FATAL [main] com.example.Application - Application startup failed
        """,
            ).strip()

    @classmethod
    def test_can_process_log_files(cls, processor):
        """Test file type detection."""
        assert processor.can_process(Path("/var/log/syslog"))
        assert processor.can_process(Path("application.log"))
        assert processor.can_process(Path("debug.txt"))
        assert processor.can_process(Path("error.out"))
        log_content = "2024-01-01 00:00:00 [INFO] Test message"
        assert processor.can_process(Path("test.txt"), log_content)
        assert not processor.can_process(Path("script.py"))
        assert not processor.can_process(Path("data.json"))

    @staticmethod
    def test_parse_syslog_format(processor, syslog_content):
        """Test parsing of syslog format."""
        chunks = processor.process(syslog_content)
        assert len(chunks) > 0
        chunk = chunks[0]
        assert chunk.chunk_type == "log"
        assert chunk.metadata["entry_count"] > 0
        assert "syslog" in chunk.metadata["formats"]

    @staticmethod
    def test_parse_apache_format(processor, apache_content):
        """Test parsing of Apache log format."""
        chunks = processor.process(apache_content)
        assert len(chunks) > 0
        chunk = chunks[0]
        assert "apache" in chunk.metadata["formats"]
        assert chunk.metadata["entry_count"] > 0

    @staticmethod
    def test_parse_application_logs(processor, application_log_content):
        """Test parsing of application logs with ISO timestamps."""
        chunks = processor.process(application_log_content)
        assert len(chunks) > 0
        chunk = chunks[0]
        assert "iso_timestamp" in chunk.metadata["formats"]
        assert set(chunk.metadata["levels"]) >= {"INFO", "ERROR", "CRITICAL"}

    @staticmethod
    def test_parse_java_logs(processor, java_log_content):
        """Test parsing of Java/Log4j style logs with stack traces."""
        chunks = processor.process(java_log_content)
        assert len(chunks) > 0
        chunk = chunks[0]
        assert "log4j" in chunk.metadata["formats"]
        assert "java.sql.SQLException" in chunk.content

    @classmethod
    def test_chunk_by_time(cls, processor, application_log_content):
        """Test time-based chunking."""
        processor = LogProcessor(config={"chunk_by": "time", "time_window": 5})
        chunks = processor.process(application_log_content)
        assert len(chunks) >= 2
        for chunk in chunks:
            if "start_time" in chunk.metadata:
                assert "end_time" in chunk.metadata

    @classmethod
    def test_chunk_by_lines(cls, processor, application_log_content):
        """Test line-based chunking."""
        processor = LogProcessor(config={"chunk_by": "lines",
            "max_chunk_lines": 3})
        chunks = processor.process(application_log_content)
        for chunk in chunks:
            assert chunk.metadata["entry_count"] <= 3

    @classmethod
    def test_chunk_by_level(cls, processor, application_log_content):
        """Test log level-based chunking."""
        processor = LogProcessor(config={"chunk_by": "level"})
        chunks = processor.process(application_log_content)
        level_chunks = {}
        for chunk in chunks:
            level = chunk.metadata.get("log_level")
            if level:
                level_chunks[level] = chunk
        assert "ERROR" in level_chunks
        assert "INFO" in level_chunks
        assert "CRITICAL" in level_chunks

    @classmethod
    def test_session_detection(cls):
        """Test session boundary detection."""
        content = dedent(
            """
            2024-01-01 00:00:00 [INFO] User login successful for user123
            2024-01-01 00:00:01 [INFO] Session started for user123
            2024-01-01 00:00:02 [INFO] User accessed /dashboard
            2024-01-01 00:00:03 [INFO] User accessed /profile
            2024-01-01 00:00:04 [INFO] User logout initiated
            2024-01-01 00:00:05 [INFO] Session ended for user123
            2024-01-01 00:01:00 [INFO] User login successful for user456
            2024-01-01 00:01:01 [INFO] Session started for user456
        """,
            ).strip()
        processor = LogProcessor(config={"chunk_by": "session",
            "detect_sessions": True})
        chunks = processor.process(content)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert "session_id" in chunk.metadata

    @classmethod
    def test_error_context_grouping(cls):
        """Test error context extraction."""
        content = dedent(
            """
            2024-01-01 00:00:00 [INFO] Processing request 123
            2024-01-01 00:00:01 [INFO] Validating input data
            2024-01-01 00:00:02 [ERROR] Validation failed: Invalid format
            2024-01-01 00:00:03 [ERROR] Request 123 failed
            2024-01-01 00:00:04 [INFO] Sending error response
            2024-01-01 00:00:05 [INFO] Request completed
            2024-01-01 00:00:10 [INFO] Processing request 124
            2024-01-01 00:00:11 [INFO] Request 124 successful
        """,
            ).strip()
        processor = LogProcessor(config={"chunk_by": "lines",
            "max_chunk_lines": 100, "group_errors": True, "context_lines": 2})
        chunks = processor.process(content)
        error_chunks = [c for c in chunks if c.metadata.get("has_errors")]
        assert len(error_chunks) > 0
        error_chunk = error_chunks[0]
        assert error_chunk.metadata["error_count"] == 2
        assert "Processing request 123" in error_chunk.content
        assert "Sending error response" in error_chunk.content

    @classmethod
    def test_multiline_entries(cls, java_log_content):
        """Test handling of multi-line log entries (stack traces)."""
        processor = LogProcessor()
        chunks = processor.process(java_log_content)
        chunk = chunks[0]
        assert "java.sql.SQLException" in chunk.content
        assert "at com.mysql.jdbc.SQLError" in chunk.content
        entries = chunk.content.split("\n")
        error_idx = next(i for i, line in enumerate(entries) if
            "Failed to connect" in line)
        assert "SQLException" in entries[error_idx + 1]

    @staticmethod
    def test_streaming_processing(processor, application_log_content):
        """Test streaming log processing."""
        lines = application_log_content.split("\n")

        def line_generator():
            for line in lines:
                yield line + "\n"
        chunks = list(processor.process_stream(line_generator()))
        assert len(chunks) > 0
        batch_chunks = processor.process(application_log_content)
        assert len(chunks) == len(batch_chunks)

    @classmethod
    def test_timestamp_parsing(cls):
        """Test various timestamp format parsing."""
        processor = LogProcessor()
        test_cases = [("2024-01-01 12:00:00,000", "iso_timestamp"), (
            "2024-01-01T12:00:00Z", "iso_timestamp"), (
            "2024-01-01T12:00:00.123+00:00", "iso_timestamp"), (
            "Jan  1 12:00:00", "syslog"), ("01/Jan/2024:12:00:00 +0000",
            "apache")]
        for timestamp_str, expected_format in test_cases:
            if expected_format == "syslog":
                line = f"{timestamp_str} hostname process: message"
            elif expected_format == "apache":
                line = (
                    f'127.0.0.1 - - [{timestamp_str}] "GET / HTTP/1.1" 200 0')
            else:
                line = f"{timestamp_str} [INFO] Test message"
            entry = processor._parse_line(line, 1, 0)
            assert entry.metadata.get("format") == expected_format
            if expected_format != "syslog":
                assert entry.timestamp is not None

    @classmethod
    def test_log_level_detection(cls):
        """Test log level detection from various formats."""
        processor = LogProcessor()
        test_cases = [("[ERROR] Something went wrong", "ERROR"), (
            "CRITICAL: System failure", "CRITICAL"), ("Warning: Low memory",
            "WARNING"), ("INFO - Application started", "INFO"), (
            "DEBUG: Variable x = 42", "DEBUG"), ("Something bad happened",
            None)]
        for line, expected_level in test_cases:
            level = processor._detect_log_level(line)
            assert level == expected_level

    @classmethod
    def test_custom_patterns(cls):
        """Test custom log pattern configuration."""
        custom_pattern = (
            "^(?P<timestamp>\\d{2}:\\d{2}:\\d{2})\\s+\\[(?P<component>\\w+)\\]\\s+(?P<message>.*)"
            )
        processor = LogProcessor(config={"patterns": {"custom":
            custom_pattern}})
        content = dedent(
            """
            12:00:00 [AUTH] User login attempt
            12:00:01 [AUTH] Login successful
            12:00:02 [API] Request received
        """,
            ).strip()
        chunks = processor.process(content)
        assert len(chunks) > 0
        assert "custom" in chunks[0].metadata["formats"]

    @classmethod
    def test_invalid_configuration(cls):
        """Test validation of invalid configurations."""
        with pytest.raises(ValueError, match="Invalid chunk_by"):
            LogProcessor(config={"chunk_by": "invalid"})
        with pytest.raises(ValueError, match="time_window must be positive"):
            LogProcessor(config={"time_window": -1})
        with pytest.raises(ValueError, match="max_chunk_lines must be positive",
            ):
            LogProcessor(config={"max_chunk_lines": 0})

    @staticmethod
    def test_empty_content(processor):
        """Test handling of empty content."""
        chunks = processor.process("")
        assert chunks == []
        chunks = list(processor.process_stream(iter([])))
        assert chunks == []

    @staticmethod
    def test_metadata_output(processor):
        """Test processor metadata."""
        metadata = processor.get_metadata()
        assert metadata["name"] == "LogProcessor"
        assert metadata["chunk_by"] == "time"
        assert metadata["time_window"] == 300
        assert metadata["max_chunk_lines"] == 1000
        assert metadata["supported_formats"] == [".log", ".txt", ".out"]
        assert "pattern_names" in metadata
        assert "log4j" in metadata["pattern_names"]
        assert "syslog" in metadata["pattern_names"]
