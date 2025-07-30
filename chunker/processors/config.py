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

try:
    import toml
except ImportError:
    toml = None

try:
    import yaml
except ImportError:
    yaml = None

from chunker.types import CodeChunk

from .base import ProcessorConfig, SpecializedProcessor


class ConfigProcessor(SpecializedProcessor):
    """Processor for configuration files.

    Supports INI, TOML, YAML, and JSON formats with intelligent
    section-based chunking that preserves configuration structure.
    """

    def __init__(self, config: ProcessorConfig | None = None):
        """Initialize config processor.

        Args:
            config: Processor configuration
        """
        super().__init__(config)

        # Compiled regex patterns for fmt detection
        self._ini_section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*$", re.MULTILINE)
        self._yaml_key_pattern = re.compile(r"^(\s*)(\w+):\s*(.*)$", re.MULTILINE)
        self._toml_table_pattern = re.compile(r"^\s*\[+([^\]]+)\]+\s*$", re.MULTILINE)

    def can_handle(self, file_path: str, content: str | None = None) -> bool:
        """Check if this processor can handle the file."""
        path = Path(file_path)

        # Check by extension
        if path.suffix.lower() in [
            ".ini",
            ".cfg",
            ".conf",
            ".toml",
            ".yaml",
            ".yml",
            ".json",
        ]:
            return True

        # Check common config file names
        config_names = ["config", "settings", "configuration", "environment"]
        if path.stem.lower() in config_names:
            return True

        # Special handling for .env files
        if path.name == ".env" or path.name.endswith(".env"):
            return True

        # If content provided, try fmt detection
        if content:
            return self.detect_format(file_path, content) is not None

        return False

    def detect_format(self, file_path: str, content: str) -> str | None:
        """Detect configuration file fmt."""
        path = Path(file_path)
        ext = path.suffix.lower()

        # Check for empty content first
        content = content.strip()
        if not content:
            return None

        # Try by extension first
        if ext in [".ini", ".cfg", ".conf"]:
            return "ini"
        if ext == ".toml":
            return "toml"
        if ext in [".yaml", ".yml"]:
            return "yaml"
        if ext == ".json":
            return "json"

        # Try content-based detection

        # Try JSON
        if content.startswith(("{", "[")):
            try:
                json.loads(content)
                return "json"
            except (IndexError, KeyError, ValueError):
                pass

        # Try YAML (must have yaml library)
        if yaml and ":" in content:
            try:
                yaml.safe_load(content)
                # Additional check to distinguish from INI
                if not self._ini_section_pattern.search(content):
                    return "yaml"
            except (IndexError, KeyError):
                pass

        # Try TOML (must have toml library)
        if toml and ("[[" in content or self._toml_table_pattern.search(content)):
            try:
                toml.loads(content)
                return "toml"
            except (FileNotFoundError, IndexError, KeyError):
                pass

        # Try INI - .env files are a special case of INI without sections
        if "=" in content:
            # Check if it looks like key=value pairs
            lines = content.split("\n")
            key_value_count = 0
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith(("#", ";")) and "=" in stripped:
                    key_value_count += 1

            # If we have key=value pairs, it's likely INI fmt
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

        # Parse line by line to handle structure
        current_section = None
        first_section_line = None
        has_global_content = False

        for i, line in enumerate(lines):
            stripped = line.strip()

            # Skip empty lines and comments
            if not stripped or stripped.startswith(("#", ";")):
                continue

            # Check for section header
            section_match = self._ini_section_pattern.match(line)
            if section_match:
                # Mark end of previous section or global
                if current_section:
                    structure["sections"][current_section]["end"] = i - 1
                elif first_section_line is None:
                    # End of global section
                    structure["global_section"]["end"] = i - 1
                    first_section_line = i

                # Start new section
                current_section = section_match.group(1)
                structure["sections"][current_section] = {
                    "start": i,
                    "end": len(lines) - 1,  # Will be updated
                    "keys": [],
                }
            elif "=" in line:
                # Key-value pair
                key = line.split("=", 1)[0].strip()
                if key:
                    if current_section:
                        structure["sections"][current_section]["keys"].append(key)
                    else:
                        structure["global_section"]["keys"].append(key)
                        has_global_content = True

        # If no sections found, everything is global
        if not structure["sections"] and has_global_content:
            structure["global_section"]["end"] = len(lines) - 1

        # Close last section
        if current_section:
            structure["sections"][current_section]["end"] = len(lines) - 1

        return structure

    def _parse_toml_structure(self, content: str) -> dict[str, Any]:
        """Parse TOML file structure."""
        if not toml:
            raise ImportError("toml library not available")

        data = toml.loads(content)
        lines = content.split("\n")

        structure = {
            "fmt": "toml",
            "tables": {},
            "root_keys": [],
        }

        # Find table positions in content
        for i, line in enumerate(lines):
            table_match = self._toml_table_pattern.match(line)
            if table_match:
                table_name = table_match.group(1).strip()
                # Count brackets to determine table type
                bracket_count = len(re.match(r"^(\[+)", line.strip()).group(1))
                is_array = bracket_count > 1

                structure["tables"][table_name] = {
                    "start": i,
                    "end": len(lines) - 1,  # Will be updated
                    "is_array": is_array,
                    "keys": [],
                }

        # Update table ends
        table_names = list(structure["tables"].keys())
        for i, table in enumerate(table_names):
            if i < len(table_names) - 1:
                next_start = structure["tables"][table_names[i + 1]]["start"]
                structure["tables"][table]["end"] = next_start - 1

        # Extract root keys
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

        structure = {
            "fmt": "yaml",
            "sections": {},
            "root_keys": [],
        }

        # Track indentation levels
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

                # Root level key
                if indent == 0:
                    if not value or value in {"|", ">"}:
                        # This is a section
                        current_section = key
                        section_indent = indent
                        structure["sections"][key] = {
                            "start": i,
                            "end": len(lines) - 1,  # Will be updated
                            "indent": indent,
                            "keys": [],
                        }
                    else:
                        structure["root_keys"].append(key)
                        current_section = None
                elif current_section and indent > section_indent:
                    # Part of current section
                    structure["sections"][current_section]["keys"].append(key)
                else:
                    # End of section
                    if current_section:
                        structure["sections"][current_section]["end"] = i - 1
                    current_section = None

        return structure

    def _parse_json_structure(self, content: str) -> dict[str, Any]:
        """Parse JSON file structure."""
        data = json.loads(content)

        structure = {
            "fmt": "json",
            "type": "object" if isinstance(data, dict) else "array",
            "keys": list(data.keys()) if isinstance(data, dict) else [],
            "size": len(data),
        }

        # For objects, identify nested objects
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

        # Handle global section if it has content
        global_section = structure["global_section"]
        if global_section["keys"] or global_section["end"] >= global_section["start"]:
            global_content = "\n".join(
                lines[global_section["start"] : global_section["end"] + 1],
            )
            if global_content.strip():
                chunks.append(
                    CodeChunk(
                        content=global_content,
                        start_line=global_section["start"] + 1,  # 1-indexed
                        end_line=global_section["end"] + 1,
                        node_type="ini_global",
                        parent_context="[global]",
                        file_path=file_path,
                        language="ini",
                        byte_start=0,  # Would need actual byte positions
                        byte_end=len(global_content.encode()),
                        metadata={
                            "section": "global",
                            "keys": global_section["keys"],
                            "fmt": "ini",
                            "name": "[global]",
                        },
                    ),
                )

        # Handle each section
        sections_to_process = list(structure["sections"].items())
        processed_sections = set()

        for section_name, section_info in sections_to_process:
            if section_name in processed_sections:
                continue
            section_content = "\n".join(
                lines[section_info["start"] : section_info["end"] + 1],
            )

            # Group small related sections if configured
            if self.config.group_related and len(section_content.split("\n")) < 10:
                # Look for related sections to group
                available_sections = {
                    k: v
                    for k, v in structure["sections"].items()
                    if k not in processed_sections
                }
                related = self._find_related_sections(section_name, available_sections)
                if related:
                    # Group related sections
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
                            byte_start=sum(len(line.encode()) + 1 for line in lines[:start]),
                            byte_end=sum(len(line.encode()) + 1 for line in lines[: end + 1]),
                            metadata={
                                "sections": all_sections,
                                "fmt": "ini",
                                "grouped": True,
                                "name": f"[{', '.join(all_sections)}]",
                            },
                        ),
                    )

                    # Mark sections as processed
                    processed_sections.add(section_name)
                    for s in related:
                        processed_sections.add(s)
                    continue

            # Single section chunk
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
                        len(line.encode()) + 1 for line in lines[: section_info["start"]]
                    ),
                    byte_end=sum(
                        len(line.encode()) + 1 for line in lines[: section_info["end"] + 1]
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

    def _chunk_toml(
        self,
        content: str,
        structure: dict[str, Any],
        file_path: str,
    ) -> list[CodeChunk]:
        """Chunk TOML file by tables."""
        chunks = []
        lines = content.split("\n")

        # Handle root content if any
        if structure["root_keys"]:
            # Find where first table starts
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

        # Handle tables
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
                        len(line.encode()) + 1 for line in lines[: table_info["end"] + 1]
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

        # Handle root keys
        if structure["root_keys"]:
            # Collect all root key lines
            root_lines = []
            for i, line in enumerate(lines):
                if not line.strip() or line.strip().startswith("#"):
                    if i == 0 or (i > 0 and root_lines):
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
                        byte_start=0,  # Approximate
                        byte_end=len(root_content.encode()),
                        metadata={
                            "keys": structure["root_keys"],
                            "fmt": "yaml",
                            "name": "root",
                        },
                    ),
                )

        # Handle sections
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
                        len(line.encode()) + 1 for line in lines[: section_info["start"]]
                    ),
                    byte_end=sum(
                        len(line.encode()) + 1 for line in lines[: section_info["end"] + 1]
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
            # For objects, chunk by top-level keys or nested objects
            if self.config.preserve_structure and len(structure["keys"]) <= 5:
                # Small object - single chunk
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
                # Large object - chunk by keys
                for key in structure["keys"]:
                    value = data[key]
                    key_content = json.dumps({key: value}, indent=2)

                    chunks.append(
                        CodeChunk(
                            content=key_content,
                            start_line=1,  # Line numbers not accurate for JSON chunks
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
        # Array - chunk by elements or groups
        elif len(data) <= 10:
            # Small array - single chunk
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
                    metadata={
                        "size": len(data),
                        "fmt": "json",
                        "name": "root",
                    },
                ),
            )
        else:
            # Large array - chunk in groups
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

    def _find_related_sections(
        self,
        section_name: str,
        all_sections: dict[str, Any],
    ) -> list[str]:
        """Find sections related to the given section."""
        related = []

        # Common patterns for related sections
        base_name = section_name.lower()

        # Look for numbered sections (e.g., server1, server2)
        base_without_number = re.sub(r"\d+$", "", base_name)
        if base_without_number != base_name:
            for other in all_sections:
                if other != section_name and other.lower().startswith(
                    base_without_number,
                ):
                    related.append(other)

        # Look for sections with common prefixes
        parts = base_name.split("_")
        if len(parts) > 1:
            prefix = parts[0]
            for other in all_sections:
                if other != section_name and other.lower().startswith(prefix):
                    related.append(other)

        return related[:3]  # Limit grouping to avoid too large chunks

    def get_supported_formats(self) -> list[str]:
        """Get list of supported formats."""
        formats = ["ini", "json"]
        if toml:
            formats.append("toml")
        if yaml:
            formats.append("yaml")
        return formats

    def get_format_extensions(self) -> dict[str, list[str]]:
        """Get file extensions for each fmt."""
        return {
            "ini": [".ini", ".cfg", ".conf"],
            "toml": [".toml"],
            "yaml": [".yaml", ".yml"],
            "json": [".json"],
        }
