"""Configuration file processor.

Handles chunking of configuration files including:
- INI files with [sections] and key=value pairs
- TOML files with tables and nested structures
- YAML files with proper indentation awareness
- JSON configuration files
"""

import json
import re
from pathlib import Path
from typing import Any

import yaml

try:
    import toml
except ImportError:
    toml = None  # type: ignore[assignment]
from chunker.types import CodeChunk

from .base import ProcessorConfig, SpecializedProcessor


class ConfigProcessor(SpecializedProcessor):
    """Processor for configuration files.

    Supports INI, TOML, YAML, and JSON formats with intelligent
    section-based chunking that preserves configuration structure.
    """

    def __init__(self, config: ProcessorConfig | dict[str, Any] | None = None):
        """Initialize config processor.

        Args:
            config: Processor configuration
        """
        super().__init__(config)
        # Section headers like [section]
        self._ini_section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)
        self._yaml_key_pattern = re.compile(r"^(\s*)(\w+):\s*(.*)$", re.MULTILINE)
        # TOML table headers like [table] or [[array_table]]
        self._toml_table_pattern = re.compile(
            r"^\s*\[(\[)?([^\]]+)(\])?\]\s*$",
            re.MULTILINE,
        )

    def can_handle(self, file_path: str, content: str | None = None) -> bool:
        """Check if this processor can handle the file."""
        path = Path(file_path)
        if path.suffix.lower() in {
            ".ini",
            ".cfg",
            ".conf",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
        }:
            return True
        config_names = ["config", "settings", "configuration", "environment"]
        if path.stem.lower() in config_names:
            return True
        if path.name == ".env" or path.name.endswith(".env"):
            return True
        if content:
            return self.detect_format(file_path, content) is not None
        return False

    def detect_format(self, file_path: str, content: str) -> str | None:
        """Detect configuration file fmt."""
        content = content.strip()
        if not content:
            return None

        # List of detection methods in priority order
        detection_methods = [
            ConfigProcessor._detect_by_extension,
            ConfigProcessor._detect_json_by_content,
            # Try YAML then TOML; both parsers validate. If they fail, fall through to INI.
            self._detect_yaml_by_content,
            self._detect_toml_by_content,
            ConfigProcessor._detect_ini_by_content,
        ]

        for method in detection_methods:
            result = method(file_path, content)
            if result:
                return result

        return None

    def process(self, arg1: str, arg2: str | None = None) -> list[CodeChunk]:
        """Process a configuration file and return chunks.

        Supports both call orders for backward compatibility:
        - process(content, file_path)
        - process(file_path, content)
        """
        # Determine which argument is content vs file_path
        content: str
        file_path: str
        if arg2 is None:
            # Single-arg usage: treat as content with default file name
            content = arg1
            file_path = "config"
        else:
            # Heuristic: the content string typically contains newlines or braces/brackets
            a_has_newline = (
                "\n" in arg1 or "{" in arg1 or "[" in arg1 or ":" in arg1 or "=" in arg1
            )
            b_has_newline = (
                "\n" in arg2 or "{" in arg2 or "[" in arg2 or ":" in arg2 or "=" in arg2
            )
            if a_has_newline and not b_has_newline:
                content, file_path = arg1, arg2
            elif (b_has_newline and not a_has_newline) or Path(arg1).suffix:
                file_path, content = arg1, arg2
            else:
                content, file_path = arg1, arg2

        fmt = self.detect_format(file_path, content)
        if fmt is not None:
            structure = self.parse_structure(content, fmt)
            chunks = self.chunk_content(content, structure, file_path)
            return chunks
        # Fallback heuristics: attempt concrete formats in order JSON → YAML → TOML → INI
        try:
            data = json.loads(content)
            structure = {
                "fmt": "json",
                "type": "object" if isinstance(data, dict) else "array",
                "keys": list(data.keys()) if isinstance(data, dict) else [],
            }
            return self._chunk_json(content, structure, file_path)
        except Exception:
            pass
        if yaml is not None:
            try:
                yaml.safe_load(content)
                structure = self._parse_yaml_structure(content)
                return self._chunk_yaml(content, structure, file_path)
            except Exception:
                pass
        if toml is not None:
            try:
                toml.loads(content)
                structure = self._parse_toml_structure(content)
                return self._chunk_toml(content, structure, file_path)
            except Exception:
                pass
        if "=" in content:
            structure = self._parse_ini_structure(content)
            return self._chunk_ini(content, structure, file_path)
        # As last resort, return single chunk to avoid hard failure
        return self._chunk_ini(
            content,
            {
                "fmt": "ini",
                "sections": {},
                "global_section": {
                    "start": 0,
                    "end": len(content.split("\n")) - 1,
                    "keys": [],
                },
            },
            file_path,
        )

    @staticmethod
    def _detect_by_extension(file_path: str, _content: str) -> str | None:
        """Detect format by file extension."""
        path = Path(file_path)
        ext = path.suffix.lower()

        extension_map = {
            ".ini": "ini",
            ".cfg": "ini",
            ".conf": "ini",
            ".toml": "toml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".json": "json",
        }

        return extension_map.get(ext)

    @staticmethod
    def _detect_json_by_content(_file_path: str, content: str) -> str | None:
        """Detect JSON format by content."""
        if content.startswith(("{", "[")):
            try:
                json.loads(content)
                return "json"
            except (IndexError, KeyError, ValueError):
                pass
        return None

    def _detect_yaml_by_content(self, _file_path: str, content: str) -> str | None:
        """Detect YAML format by content."""
        if yaml and ":" in content:
            try:
                yaml.safe_load(content)
                if not self._ini_section_pattern.search(content):
                    return "yaml"
            except (IndexError, KeyError):
                pass
        return None

    def _detect_toml_by_content(self, _file_path: str, content: str) -> str | None:
        """Detect TOML format by content."""
        if toml and ("[[" in content or self._toml_table_pattern.search(content)):
            try:
                toml.loads(content)
                return "toml"
            except Exception:
                # If TOML parsing fails, do not classify as TOML; allow INI/YAML detection
                return None
        return None

    @staticmethod
    def _detect_ini_by_content(_file_path: str, content: str) -> str | None:
        """Detect INI format by content."""
        if "=" in content:
            lines = content.split("\n")
            key_value_count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith(("#", ";")) and "=" in stripped:
                    key_value_count += 1
            if key_value_count > 0:
                return "ini"
        return None

    def parse_structure(self, content: str, fmt: str) -> dict[str, Any]:
        """Parse configuration structure."""
        if fmt == "ini":
            return self._parse_ini_structure(content)
        if fmt == "toml":
            return self._parse_toml_structure(content)
        if fmt == "yaml":
            return self._parse_yaml_structure(content)
        if fmt == "json":
            return self._parse_json_structure(content)
        raise ValueError(f"Unsupported fmt: {fmt}")

    def _parse_ini_structure(self, content: str) -> dict[str, Any]:
        """Parse INI file structure."""
        lines = content.split("\n")
        structure = {
            "fmt": "ini",
            "sections": {},
            "global_section": {"start": 0, "end": 0, "keys": []},
        }
        current_section = None
        first_section_line = None
        has_global_content = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")):
                continue
            section_match = self._ini_section_pattern.match(line)
            if section_match:
                if current_section:
                    structure["sections"][current_section]["end"] = i - 1
                elif first_section_line is None:
                    structure["global_section"]["end"] = i - 1
                    first_section_line = i
                current_section = section_match.group(1)
                structure["sections"][current_section] = {
                    "start": i,
                    "end": len(lines) - 1,
                    "keys": [],
                }
            elif "=" in line:
                key = line.split("=", 1)[0].strip()
                if key:
                    if current_section:
                        structure["sections"][current_section]["keys"].append(key)
                    else:
                        structure["global_section"]["keys"].append(key)
                        has_global_content = True
        if not structure["sections"] and has_global_content:
            structure["global_section"]["end"] = len(lines) - 1
        if current_section:
            structure["sections"][current_section]["end"] = len(lines) - 1
        return structure

    def _parse_toml_structure(self, content: str) -> dict[str, Any]:
        """Parse TOML file structure."""
        if not toml:
            raise ImportError("toml library not available")
        data = toml.loads(content)
        lines = content.split("\n")
        structure = {"fmt": "toml", "tables": {}, "root_keys": []}
        for i, line in enumerate(lines):
            table_match = self._toml_table_pattern.match(line)
            if table_match:
                # Per pattern, group(2) holds the table name
                table_name = table_match.group(2).strip()
                bracket_count = len(re.match(r"^(\[+)", line.strip()).group(1))
                is_array = bracket_count > 1
                structure["tables"][table_name] = {
                    "start": i,
                    "end": len(lines) - 1,
                    "is_array": is_array,
                    "keys": [],
                }
        table_names = list(structure["tables"].keys())
        for i, table in enumerate(table_names):
            if i < len(table_names) - 1:
                next_start = structure["tables"][table_names[i + 1]]["start"]
                structure["tables"][table]["end"] = next_start - 1
        for key in data:
            if not isinstance(data[key], dict) or key not in structure["tables"]:
                structure["root_keys"].append(key)
        return structure

    def _parse_yaml_structure(self, content: str) -> dict[str, Any]:
        """Parse YAML file structure."""
        if not yaml:
            raise ImportError("yaml library not available")
        yaml.safe_load(content)
        lines = content.split("\n")
        structure = {"fmt": "yaml", "sections": {}, "root_keys": []}
        current_section = None
        section_indent = -1
        for i, line in enumerate(lines):
            if not line.strip() or line.strip().startswith("#"):
                continue
            match = self._yaml_key_pattern.match(line)
            if match:
                indent = len(match.group(1))
                key = match.group(2)
                value = match.group(3).strip()
                if indent == 0:
                    if not value or value in {"|", ">"}:
                        current_section = key
                        section_indent = indent
                        structure["sections"][key] = {
                            "start": i,
                            "end": len(lines) - 1,
                            "indent": indent,
                            "keys": [],
                        }
                    else:
                        structure["root_keys"].append(key)
                        current_section = None
                elif current_section and indent > section_indent:
                    structure["sections"][current_section]["keys"].append(key)
                else:
                    if current_section:
                        structure["sections"][current_section]["end"] = i - 1
                    current_section = None
        return structure

    @staticmethod
    def _parse_json_structure(content: str) -> dict[str, Any]:
        """Parse JSON file structure."""
        data = json.loads(content)
        structure = {
            "fmt": "json",
            "type": "object" if isinstance(data, dict) else "array",
            "keys": list(data.keys()) if isinstance(data, dict) else [],
            "size": len(data),
        }
        if isinstance(data, dict):
            structure["nested_objects"] = []
            for key, value in data.items():
                if isinstance(value, dict):
                    structure["nested_objects"].append(key)
        return structure

    def chunk_content(
        self,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk configuration content based on structure."""
        fmt = structure.get("fmt")
        if fmt == "ini":
            return self._chunk_ini(content, structure, file_path)
        if fmt == "toml":
            return self._chunk_toml(content, structure, file_path)
        if fmt == "yaml":
            return self._chunk_yaml(content, structure, file_path)
        if fmt == "json":
            return self._chunk_json(content, structure, file_path)
        raise ValueError(f"Unsupported fmt: {fmt}")

    def _chunk_ini(
        self,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk INI file by sections."""
        chunks = []
        lines = content.split("\n")
        global_section = structure["global_section"]
        if global_section["keys"] or global_section["end"] >= global_section["start"]:
            global_content = "\n".join(
                lines[global_section["start"] : global_section["end"] + 1],
            )
            if global_content.strip():
                chunks.append(
                    CodeChunk(
                        content=global_content,
                        start_line=global_section["start"] + 1,
                        end_line=global_section["end"] + 1,
                        node_type="ini_global",
                        parent_context="[global]",
                        file_path=file_path,
                        language="ini",
                        byte_start=0,
                        byte_end=len(global_content.encode()),
                        metadata={
                            "section": "global",
                            "keys": global_section["keys"],
                            "fmt": "ini",
                            "name": "[global]",
                        },
                    ),
                )
        sections_to_process = list(structure["sections"].items())
        processed_sections = set()
        for section_name, section_info in sections_to_process:
            if section_name in processed_sections:
                continue
            section_content = "\n".join(
                lines[section_info["start"] : section_info["end"] + 1],
            )
            if self.config.group_related:
                available_sections = {
                    k: v
                    for k, v in structure["sections"].items()
                    if k not in processed_sections
                }
                related = self._find_related_sections(section_name, available_sections)
                if related:
                    all_sections = [section_name, *related]
                    start = min(structure["sections"][s]["start"] for s in all_sections)
                    end = max(structure["sections"][s]["end"] for s in all_sections)
                    grouped_content = "\n".join(lines[start : end + 1])
                    chunks.append(
                        CodeChunk(
                            content=grouped_content,
                            start_line=start + 1,
                            end_line=end + 1,
                            node_type="ini_section_group",
                            parent_context=f"[{', '.join(all_sections)}]",
                            file_path=file_path,
                            language="ini",
                            byte_start=sum(
                                len(line.encode()) + 1 for line in lines[:start]
                            ),
                            byte_end=sum(
                                len(line.encode()) + 1 for line in lines[: end + 1]
                            ),
                            metadata={
                                "sections": all_sections,
                                "fmt": "ini",
                                "grouped": True,
                                "name": f"[{', '.join(all_sections)}]",
                            },
                        ),
                    )
                    processed_sections.add(section_name)
                    for s in related:
                        processed_sections.add(s)
                    continue
            chunks.append(
                CodeChunk(
                    content=section_content,
                    start_line=section_info["start"] + 1,
                    end_line=section_info["end"] + 1,
                    node_type="ini_section",
                    parent_context=f"[{section_name}]",
                    file_path=file_path,
                    language="ini",
                    byte_start=sum(
                        len(line.encode()) + 1
                        for line in lines[: section_info["start"]]
                    ),
                    byte_end=sum(
                        len(line.encode()) + 1
                        for line in lines[: section_info["end"] + 1]
                    ),
                    metadata={
                        "section": section_name,
                        "keys": section_info["keys"],
                        "fmt": "ini",
                        "name": f"[{section_name}]",
                    },
                ),
            )
        return chunks

    @classmethod
    def _chunk_toml(
        cls,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk TOML file by tables."""
        chunks = []
        lines = content.split("\n")
        if structure["root_keys"]:
            first_table_line = min(
                (info["start"] for info in structure["tables"].values()),
                default=len(lines),
            )
            if first_table_line > 0:
                root_content = "\n".join(lines[0:first_table_line])
                if root_content.strip():
                    chunks.append(
                        CodeChunk(
                            content=root_content,
                            start_line=1,
                            end_line=first_table_line,
                            node_type="toml_root",
                            parent_context="[root]",
                            file_path=file_path,
                            language="toml",
                            byte_start=0,
                            byte_end=len(root_content.encode()),
                            metadata={
                                "keys": structure["root_keys"],
                                "fmt": "toml",
                                "name": "[root]",
                            },
                        ),
                    )
        for table_name, table_info in structure["tables"].items():
            table_content = "\n".join(
                lines[table_info["start"] : table_info["end"] + 1],
            )
            chunks.append(
                CodeChunk(
                    content=table_content,
                    start_line=table_info["start"] + 1,
                    end_line=table_info["end"] + 1,
                    node_type=(
                        "toml_table"
                        if not table_info["is_array"]
                        else "toml_array_table"
                    ),
                    parent_context=(
                        f"[{table_name}]"
                        if not table_info["is_array"]
                        else f"[[{table_name}]]"
                    ),
                    file_path=file_path,
                    language="toml",
                    byte_start=sum(
                        len(line.encode()) + 1 for line in lines[: table_info["start"]]
                    ),
                    byte_end=sum(
                        len(line.encode()) + 1
                        for line in lines[: table_info["end"] + 1]
                    ),
                    metadata={
                        "table": table_name,
                        "is_array": table_info["is_array"],
                        "fmt": "toml",
                        "name": (
                            f"[{table_name}]"
                            if not table_info["is_array"]
                            else f"[[{table_name}]]"
                        ),
                    },
                ),
            )
        return chunks

    def _chunk_yaml(
        self,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk YAML file by top-level sections."""
        chunks = []
        lines = content.split("\n")
        if structure["root_keys"]:
            root_lines = []
            for i, line in enumerate(lines):

                if (
                    not line.strip()
                    or (line.strip().startswith("#") and i == 0)
                    or (i > 0 and root_lines)
                ):
                    root_lines.append(i)
                    continue
                match = self._yaml_key_pattern.match(line)
                if match and len(match.group(1)) == 0:
                    key = match.group(2)
                    if key in structure["root_keys"]:
                        root_lines.append(i)
            if root_lines:
                root_content = "\n".join(lines[i] for i in sorted(set(root_lines)))
                chunks.append(
                    CodeChunk(
                        content=root_content,
                        start_line=min(root_lines) + 1,
                        end_line=max(root_lines) + 1,
                        node_type="yaml_root",
                        parent_context="root",
                        file_path=file_path,
                        language="yaml",
                        byte_start=0,
                        byte_end=len(root_content.encode()),
                        metadata={
                            "keys": structure["root_keys"],
                            "fmt": "yaml",
                            "name": "root",
                        },
                    ),
                )
        for section_name, section_info in structure["sections"].items():
            section_content = "\n".join(
                lines[section_info["start"] : section_info["end"] + 1],
            )
            chunks.append(
                CodeChunk(
                    content=section_content,
                    start_line=section_info["start"] + 1,
                    end_line=section_info["end"] + 1,
                    node_type="yaml_section",
                    parent_context=section_name,
                    file_path=file_path,
                    language="yaml",
                    byte_start=sum(
                        len(line.encode()) + 1
                        for line in lines[: section_info["start"]]
                    ),
                    byte_end=sum(
                        len(line.encode()) + 1
                        for line in lines[: section_info["end"] + 1]
                    ),
                    metadata={
                        "section": section_name,
                        "indent": section_info["indent"],
                        "keys": section_info["keys"],
                        "fmt": "yaml",
                        "name": section_name,
                    },
                ),
            )
        return chunks

    def _chunk_json(
        self,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk JSON file intelligently."""
        chunks = []
        data = json.loads(content)
        if structure["type"] == "object":
            if self.config.preserve_structure and len(structure["keys"]) <= 5:
                chunks.append(
                    CodeChunk(
                        content=content,
                        start_line=1,
                        end_line=len(content.split("\n")),
                        node_type="json_object",
                        parent_context="root",
                        file_path=file_path,
                        language="json",
                        byte_start=0,
                        byte_end=len(content.encode()),
                        metadata={
                            "keys": structure["keys"],
                            "fmt": "json",
                            "name": "root",
                        },
                    ),
                )
            else:
                for key in structure["keys"]:
                    value = data[key]
                    key_content = json.dumps({key: value}, indent=2)
                    chunks.append(
                        CodeChunk(
                            content=key_content,
                            start_line=1,
                            end_line=len(key_content.split("\n")),
                            node_type="json_property",
                            parent_context=key,
                            file_path=file_path,
                            language="json",
                            byte_start=0,
                            byte_end=len(key_content.encode()),
                            metadata={
                                "key": key,
                                "value_type": type(value).__name__,
                                "is_nested": isinstance(value, dict | list),
                                "fmt": "json",
                                "name": key,
                            },
                        ),
                    )
        elif len(data) <= 10:
            chunks.append(
                CodeChunk(
                    content=content,
                    start_line=1,
                    end_line=len(content.split("\n")),
                    node_type="json_array",
                    parent_context="root",
                    file_path=file_path,
                    language="json",
                    byte_start=0,
                    byte_end=len(content.encode()),
                    metadata={"size": len(data), "fmt": "json", "name": "root"},
                ),
            )
        else:
            chunk_size = self.config.chunk_size
            for i in range(0, len(data), chunk_size):
                chunk_data = data[i : i + chunk_size]
                chunk_content = json.dumps(chunk_data, indent=2)
                chunks.append(
                    CodeChunk(
                        content=chunk_content,
                        start_line=1,
                        end_line=len(chunk_content.split("\n")),
                        node_type="json_array_chunk",
                        parent_context=f"items[{i}:{i + len(chunk_data)}]",
                        file_path=file_path,
                        language="json",
                        byte_start=0,
                        byte_end=len(chunk_content.encode()),
                        metadata={
                            "start_index": i,
                            "end_index": i + len(chunk_data),
                            "fmt": "json",
                            "name": f"items[{i}:{i + len(chunk_data)}]",
                        },
                    ),
                )
        return chunks

    @staticmethod
    def _find_related_sections(
        section_name: str,
        all_sections: dict[str, Any],
    ) -> list[str]:
        """Find sections related to the given section."""
        related: list[str] = []
        base_name = section_name.lower()
        # 1) Numeric suffix pattern: server1, server2, ...
        base_without_number = re.sub(r"\d+$", "", base_name)
        if base_without_number != base_name:
            related.extend(
                other
                for other in all_sections
                if other != section_name
                and other.lower().startswith(base_without_number)
            )
        # 2) Underscore prefix pattern: server_a, server_b
        parts = base_name.split("_")
        if len(parts) > 1:
            prefix = parts[0]
            related.extend(
                other
                for other in all_sections
                if other != section_name and other.lower().startswith(prefix)
            )
        # 3) Hyphen prefix pattern: server-1, server-2
        hyphen_prefix = base_name.split("-")[0]
        related.extend(
            other
            for other in all_sections
            if other != section_name and other.lower().startswith(hyphen_prefix)
        )
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_related: list[str] = []
        for r in related:
            if r not in seen:
                unique_related.append(r)
                seen.add(r)
        return unique_related[:3]

    @staticmethod
    def get_supported_formats() -> list[str]:
        """Get list of supported formats."""
        formats = ["ini", "json"]
        if toml:
            formats.append("toml")
        if yaml:
            formats.append("yaml")
        return formats

    @staticmethod
    def get_format_extensions() -> dict[str, list[str]]:
        """Get file extensions for each fmt."""
        return {
            "ini": [".ini", ".cfg", ".conf"],
            "toml": [".toml"],
            "yaml": [".yaml", ".yml"],
            "json": [".json"],
        }
