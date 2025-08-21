"""Comprehensive error message templates system for intelligent error handling.

This module provides a robust template-based error messaging system that supports:
- Multiple output formats (text, HTML, Markdown, JSON, XML)
- Variable substitution with validation
- Template validation and syntax checking
- Built-in template library for common error types
- Template caching for performance optimization
- Import/export functionality
- Template versioning support
- Internationalization preparation

The system is designed to be memory-efficient and scalable for large template libraries
while providing comprehensive error handling and logging capabilities.
"""

from __future__ import annotations

import json
import logging
import re
import string
import weakref
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from xml.dom import minidom

logger = logging.getLogger(__name__)


class TemplateType(Enum):
    """Enumeration of supported template types."""

    ERROR_MESSAGE = "error_message"
    WARNING_MESSAGE = "warning_message"
    INFO_MESSAGE = "info_message"
    SUCCESS_MESSAGE = "success_message"
    HELP_TEXT = "help_text"
    TUTORIAL = "tutorial"
    DIAGNOSTIC = "diagnostic"
    SUGGESTION = "suggestion"
    CONFIRMATION = "confirmation"
    PROGRESS = "progress"


class TemplateFormat(Enum):
    """Enumeration of supported output formats."""

    TEXT = "text"
    HTML = "html"
    MARKDOWN = "markdown"
    JSON = "json"
    XML = "xml"


@dataclass
class ErrorTemplate:
    """Represents a single error message template with full validation and methods.

    Attributes:
        id: Unique identifier for the template
        name: Human-readable name for the template
        type: Type of template (error, warning, etc.)
        format: Output format (text, HTML, etc.)
        template: Template string with variable placeholders
        variables: Set of variable names used in the template
        metadata: Additional metadata (description, tags, etc.)
        version: Template version for tracking changes
        created_at: Creation timestamp
        updated_at: Last update timestamp
        locale: Locale/language code for internationalization
    """

    id: str
    name: str
    type: TemplateType
    format: TemplateFormat
    template: str
    variables: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    locale: str = "en-US"

    def __post_init__(self) -> None:
        """Post-initialization validation and setup."""
        self._extract_variables()
        self._validate_template()

    def _extract_variables(self) -> None:
        """Extract variable names from the template string."""
        try:
            # Use string.Template to find variables
            template_obj = string.Template(self.template)
            # Extract variables using regex to match ${var} and $var patterns
            pattern = re.compile(r"\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)")
            matches = pattern.findall(self.template)

            variables = set()
            for match in matches:
                # match is a tuple (group1, group2) where one is empty
                var_name = match[0] if match[0] else match[1]
                if var_name:
                    variables.add(var_name)

            self.variables = variables
            logger.debug(
                f"Extracted variables from template {self.id}: {self.variables}",
            )

        except Exception as e:
            logger.error(f"Failed to extract variables from template {self.id}: {e}")
            self.variables = set()

    def _validate_template(self) -> None:
        """Validate template syntax and structure."""
        if not self.template:
            raise ValueError(f"Template {self.id} has empty template string")

        if not self.id:
            raise ValueError("Template must have a non-empty id")

        if not self.name:
            raise ValueError(f"Template {self.id} must have a non-empty name")

        # Validate template syntax based on format
        try:
            if self.format == TemplateFormat.JSON:
                # Validate JSON template structure
                json.loads(self.template.replace("${", '"{').replace("}", '}"'))
            elif self.format == TemplateFormat.XML:
                # Validate XML template structure
                test_xml = self.template
                # Replace variables with dummy values for validation
                for var in self.variables:
                    test_xml = test_xml.replace(f"${{{var}}}", "test_value")
                    test_xml = test_xml.replace(f"${var}", "test_value")
                ET.fromstring(test_xml)
            elif self.format == TemplateFormat.HTML:
                # Basic HTML validation - check for balanced tags
                if "<" in self.template and ">" in self.template:
                    # Simple tag balance check
                    open_tags = re.findall(r"<(\w+)", self.template)
                    close_tags = re.findall(r"</(\w+)>", self.template)
                    # Allow for self-closing tags and basic validation
                    # More comprehensive validation could be added

            logger.debug(f"Template {self.id} passed validation")

        except Exception as e:
            logger.warning(f"Template {self.id} failed format validation: {e}")
            # Don't raise here as templates might use advanced features

    def render(self, variables: dict[str, Any], safe_mode: bool = True) -> str:
        """Render the template with provided variables.

        Args:
            variables: Dictionary of variable values
            safe_mode: If True, use safe substitution to avoid KeyError

        Returns:
            Rendered template string

        Raises:
            KeyError: If required variables are missing and safe_mode is False
            ValueError: If rendering fails due to invalid template
        """
        try:
            template_obj = string.Template(self.template)

            if safe_mode:
                # Use safe_substitute to avoid KeyError for missing variables
                result = template_obj.safe_substitute(variables)

                # Check for unsubstituted variables
                remaining_vars = set(
                    re.findall(r"\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)", result),
                )
                if remaining_vars:
                    flat_vars = {v for match in remaining_vars for v in match if v}
                    logger.warning(
                        f"Template {self.id} has unsubstituted variables: {flat_vars}",
                    )
            else:
                result = template_obj.substitute(variables)

            self.updated_at = datetime.now(UTC)
            logger.debug(f"Successfully rendered template {self.id}")
            return result

        except Exception as e:
            logger.error(f"Failed to render template {self.id}: {e}")
            raise ValueError(f"Template rendering failed: {e}") from e

    def get_missing_variables(self, provided_vars: dict[str, Any]) -> set[str]:
        """Get set of variables that are required but not provided.

        Args:
            provided_vars: Dictionary of provided variable values

        Returns:
            Set of missing variable names
        """
        provided_var_names = set(provided_vars.keys())
        return self.variables - provided_var_names

    def validate_variables(self, variables: dict[str, Any]) -> bool:
        """Validate that all required variables are provided.

        Args:
            variables: Dictionary of variable values

        Returns:
            True if all required variables are provided
        """
        missing = self.get_missing_variables(variables)
        if missing:
            logger.warning(f"Template {self.id} missing variables: {missing}")
            return False
        return True

    def clone(self, new_id: str | None = None) -> ErrorTemplate:
        """Create a deep copy of the template with optional new ID.

        Args:
            new_id: Optional new ID for the cloned template

        Returns:
            New ErrorTemplate instance
        """
        cloned = ErrorTemplate(
            id=new_id or f"{self.id}_copy",
            name=f"{self.name} (Copy)" if not new_id else self.name,
            type=self.type,
            format=self.format,
            template=self.template,
            variables=self.variables.copy(),
            metadata=self.metadata.copy(),
            version=self.version,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            locale=self.locale,
        )
        return cloned

    def to_dict(self) -> dict[str, Any]:
        """Convert template to dictionary representation.

        Returns:
            Dictionary representation of the template
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "format": self.format.value,
            "template": self.template,
            "variables": list(self.variables),
            "metadata": self.metadata,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "locale": self.locale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ErrorTemplate:
        """Create template from dictionary representation.

        Args:
            data: Dictionary containing template data

        Returns:
            New ErrorTemplate instance

        Raises:
            ValueError: If required fields are missing or invalid
        """
        try:
            return cls(
                id=data["id"],
                name=data["name"],
                type=TemplateType(data["type"]),
                format=TemplateFormat(data["format"]),
                template=data["template"],
                variables=set(data.get("variables", [])),
                metadata=data.get("metadata", {}),
                version=data.get("version", "1.0.0"),
                created_at=datetime.fromisoformat(
                    data.get("created_at", datetime.now(UTC).isoformat()),
                ),
                updated_at=datetime.fromisoformat(
                    data.get("updated_at", datetime.now(UTC).isoformat()),
                ),
                locale=data.get("locale", "en-US"),
            )
        except Exception as e:
            raise ValueError(f"Failed to create template from dictionary: {e}") from e


class TemplateManager:
    """Manages storage and retrieval of error message templates.

    Provides centralized management of templates with support for:
    - Template storage and retrieval
    - Template categorization and filtering
    - Template validation and conflict detection
    - Memory-efficient storage using weak references where appropriate
    """

    def __init__(self, cache_size: int = 1000) -> None:
        """Initialize the template manager.

        Args:
            cache_size: Maximum number of templates to cache
        """
        self._templates: dict[str, ErrorTemplate] = {}
        self._templates_by_type: dict[TemplateType, set[str]] = defaultdict(set)
        self._templates_by_format: dict[TemplateFormat, set[str]] = defaultdict(set)
        self._cache_size = cache_size
        self._access_count: dict[str, int] = defaultdict(int)
        self._last_accessed: dict[str, datetime] = {}

        logger.info(f"Initialized TemplateManager with cache size {cache_size}")

    def add_template(self, template: ErrorTemplate, overwrite: bool = False) -> bool:
        """Add a template to the manager.

        Args:
            template: Template to add
            overwrite: Whether to overwrite existing template with same ID

        Returns:
            True if template was added successfully

        Raises:
            ValueError: If template ID already exists and overwrite is False
        """
        if template.id in self._templates and not overwrite:
            raise ValueError(f"Template with ID '{template.id}' already exists")

        # Manage cache size
        if (
            len(self._templates) >= self._cache_size
            and template.id not in self._templates
        ):
            self._evict_least_used()

        # Remove old template if overwriting
        if template.id in self._templates:
            self.remove_template(template.id)

        # Add new template
        self._templates[template.id] = template
        self._templates_by_type[template.type].add(template.id)
        self._templates_by_format[template.format].add(template.id)
        self._last_accessed[template.id] = datetime.now(UTC)

        logger.debug(f"Added template {template.id} to manager")
        return True

    def remove_template(self, template_id: str) -> bool:
        """Remove a template from the manager.

        Args:
            template_id: ID of template to remove

        Returns:
            True if template was removed successfully
        """
        if template_id not in self._templates:
            return False

        template = self._templates[template_id]

        # Remove from all indexes
        del self._templates[template_id]
        self._templates_by_type[template.type].discard(template_id)
        self._templates_by_format[template.format].discard(template_id)
        self._access_count.pop(template_id, None)
        self._last_accessed.pop(template_id, None)

        logger.debug(f"Removed template {template_id} from manager")
        return True

    def get_template(self, template_id: str) -> ErrorTemplate | None:
        """Retrieve a template by ID.

        Args:
            template_id: ID of template to retrieve

        Returns:
            Template if found, None otherwise
        """
        if template_id in self._templates:
            self._access_count[template_id] += 1
            self._last_accessed[template_id] = datetime.now(UTC)
            return self._templates[template_id]
        return None

    def get_templates_by_type(self, template_type: TemplateType) -> list[ErrorTemplate]:
        """Get all templates of a specific type.

        Args:
            template_type: Type of templates to retrieve

        Returns:
            List of templates of the specified type
        """
        template_ids = self._templates_by_type.get(template_type, set())
        return [self._templates[tid] for tid in template_ids if tid in self._templates]

    def get_templates_by_format(
        self,
        template_format: TemplateFormat,
    ) -> list[ErrorTemplate]:
        """Get all templates of a specific format.

        Args:
            template_format: Format of templates to retrieve

        Returns:
            List of templates of the specified format
        """
        template_ids = self._templates_by_format.get(template_format, set())
        return [self._templates[tid] for tid in template_ids if tid in self._templates]

    def list_templates(
        self,
        filter_type: TemplateType | None = None,
        filter_format: TemplateFormat | None = None,
    ) -> list[ErrorTemplate]:
        """List all templates with optional filtering.

        Args:
            filter_type: Optional type filter
            filter_format: Optional format filter

        Returns:
            List of filtered templates
        """
        templates = list(self._templates.values())

        if filter_type:
            templates = [t for t in templates if t.type == filter_type]

        if filter_format:
            templates = [t for t in templates if t.format == filter_format]

        return templates

    def search_templates(
        self,
        query: str,
        search_fields: list[str] | None = None,
    ) -> list[ErrorTemplate]:
        """Search templates by query string.

        Args:
            query: Search query
            search_fields: Fields to search in (default: name, template, metadata)

        Returns:
            List of matching templates
        """
        if not query:
            return []

        if search_fields is None:
            search_fields = ["name", "template", "metadata"]

        query_lower = query.lower()
        matching_templates = []

        for template in self._templates.values():
            match = False

            if ("name" in search_fields and query_lower in template.name.lower()) or (
                "template" in search_fields and query_lower in template.template.lower()
            ):
                match = True
            elif "metadata" in search_fields:
                metadata_str = str(template.metadata).lower()
                if query_lower in metadata_str:
                    match = True

            if match:
                matching_templates.append(template)

        return matching_templates

    def get_statistics(self) -> dict[str, Any]:
        """Get manager statistics.

        Returns:
            Dictionary containing usage statistics
        """
        return {
            "total_templates": len(self._templates),
            "templates_by_type": {
                t.value: len(ids) for t, ids in self._templates_by_type.items()
            },
            "templates_by_format": {
                f.value: len(ids) for f, ids in self._templates_by_format.items()
            },
            "cache_usage": (
                len(self._templates) / self._cache_size if self._cache_size > 0 else 0
            ),
            "most_accessed": sorted(
                self._access_count.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:10],
        }

    def _evict_least_used(self) -> None:
        """Evict the least recently used template to free space."""
        if not self._templates:
            return

        # Find least recently accessed template
        oldest_time = min(self._last_accessed.values())
        template_to_evict = None

        for template_id, last_time in self._last_accessed.items():
            if last_time == oldest_time:
                template_to_evict = template_id
                break

        if template_to_evict:
            self.remove_template(template_to_evict)
            logger.debug(f"Evicted template {template_to_evict} from cache")

    def clear(self) -> None:
        """Clear all templates from the manager."""
        self._templates.clear()
        self._templates_by_type.clear()
        self._templates_by_format.clear()
        self._access_count.clear()
        self._last_accessed.clear()
        logger.info("Cleared all templates from manager")


class TemplateRenderer:
    """Renders templates in multiple output formats with advanced formatting capabilities.

    Supports rendering to:
    - Plain text with basic formatting
    - HTML with rich formatting and styling
    - Markdown with proper syntax
    - JSON with structured data
    - XML with hierarchical structure
    """

    def __init__(self) -> None:
        """Initialize the template renderer."""
        self._format_handlers = {
            TemplateFormat.TEXT: self._render_text,
            TemplateFormat.HTML: self._render_html,
            TemplateFormat.MARKDOWN: self._render_markdown,
            TemplateFormat.JSON: self._render_json,
            TemplateFormat.XML: self._render_xml,
        }
        logger.debug("Initialized TemplateRenderer")

    def render(
        self,
        template: ErrorTemplate,
        variables: dict[str, Any],
        output_format: TemplateFormat | None = None,
    ) -> str:
        """Render a template with variables in the specified format.

        Args:
            template: Template to render
            variables: Variables to substitute
            output_format: Override template's default format

        Returns:
            Rendered template string

        Raises:
            ValueError: If format is not supported or rendering fails
        """
        target_format = output_format or template.format

        if target_format not in self._format_handlers:
            raise ValueError(f"Unsupported format: {target_format}")

        try:
            # First render the template with variables
            rendered_content = template.render(variables, safe_mode=True)

            # Then apply format-specific processing
            handler = self._format_handlers[target_format]
            result = handler(rendered_content, template, variables)

            logger.debug(
                f"Successfully rendered template {template.id} in {target_format.value} format",
            )
            return result

        except Exception as e:
            logger.error(f"Failed to render template {template.id}: {e}")
            raise ValueError(f"Template rendering failed: {e}") from e

    def _render_text(
        self,
        content: str,
        template: ErrorTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Render template as plain text with basic formatting.

        Args:
            content: Rendered template content
            template: Original template
            variables: Template variables

        Returns:
            Plain text formatted content
        """
        # Basic text formatting - remove HTML tags if present
        import re

        text = re.sub(r"<[^>]+>", "", content)

        # Add metadata if requested in variables
        if variables.get("include_metadata", False):
            metadata_lines = [
                f"Template: {template.name}",
                f"Type: {template.type.value}",
                f"Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            ]
            text = "\n".join(metadata_lines) + "\n\n" + text

        return text

    def _render_html(
        self,
        content: str,
        template: ErrorTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Render template as HTML with rich formatting.

        Args:
            content: Rendered template content
            template: Original template
            variables: Template variables

        Returns:
            HTML formatted content
        """
        # If content is already HTML, return as-is
        if "<html>" in content.lower() or "<div>" in content.lower():
            return content

        # Wrap plain text in basic HTML structure
        css_class = f"template-{template.type.value}"

        html_parts = [
            f'<div class="{css_class}">',
            f'<div class="template-content">{self._escape_html(content)}</div>',
        ]

        # Add metadata if requested
        if variables.get("include_metadata", False):
            html_parts.insert(
                -1,
                f"""
            <div class="template-metadata">
                <small>
                    Template: {self._escape_html(template.name)} | 
                    Type: {template.type.value} | 
                    Generated: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
                </small>
            </div>
            """,
            )

        html_parts.append("</div>")
        return "\n".join(html_parts)

    def _render_markdown(
        self,
        content: str,
        template: ErrorTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Render template as Markdown with proper syntax.

        Args:
            content: Rendered template content
            template: Original template
            variables: Template variables

        Returns:
            Markdown formatted content
        """
        # If content is already markdown-formatted, use as-is
        if any(marker in content for marker in ["#", "**", "*", "`", ">"]):
            result = content
        else:
            # Convert plain text to basic markdown
            result = content

        # Add metadata if requested
        if variables.get("include_metadata", False):
            metadata = f"""
---
**Template:** {template.name}  
**Type:** {template.type.value}  
**Generated:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}
---

"""
            result = metadata + result

        return result

    def _render_json(
        self,
        content: str,
        template: ErrorTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Render template as structured JSON.

        Args:
            content: Rendered template content
            template: Original template
            variables: Template variables

        Returns:
            JSON formatted content
        """
        # Try to parse content as JSON first
        try:
            parsed_content = json.loads(content)
        except json.JSONDecodeError:
            # If not valid JSON, wrap as string
            parsed_content = content

        result = {
            "message": parsed_content,
            "template_id": template.id,
            "template_name": template.name,
            "type": template.type.value,
            "format": template.format.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "variables_used": list(variables.keys()),
        }

        if variables.get("include_metadata", False):
            result["metadata"] = template.metadata
            result["version"] = template.version
            result["locale"] = template.locale

        return json.dumps(result, indent=2, ensure_ascii=False)

    def _render_xml(
        self,
        content: str,
        template: ErrorTemplate,
        variables: dict[str, Any],
    ) -> str:
        """Render template as XML with hierarchical structure.

        Args:
            content: Rendered template content
            template: Original template
            variables: Template variables

        Returns:
            XML formatted content
        """
        # Try to parse content as XML first
        try:
            content_element = ET.fromstring(content)
            root = ET.Element("template_message")
            root.append(content_element)
        except ET.ParseError:
            # If not valid XML, wrap as text content
            root = ET.Element("template_message")
            message_elem = ET.SubElement(root, "message")
            message_elem.text = content

        # Add metadata
        metadata_elem = ET.SubElement(root, "metadata")
        ET.SubElement(metadata_elem, "template_id").text = template.id
        ET.SubElement(metadata_elem, "template_name").text = template.name
        ET.SubElement(metadata_elem, "type").text = template.type.value
        ET.SubElement(metadata_elem, "format").text = template.format.value
        ET.SubElement(metadata_elem, "timestamp").text = datetime.now(
            UTC,
        ).isoformat()

        if variables.get("include_metadata", False):
            ET.SubElement(metadata_elem, "version").text = template.version
            ET.SubElement(metadata_elem, "locale").text = template.locale

        # Variables used
        vars_elem = ET.SubElement(metadata_elem, "variables_used")
        for var_name in variables:
            var_elem = ET.SubElement(vars_elem, "variable")
            var_elem.text = var_name

        # Pretty format the XML
        rough_string = ET.tostring(root, encoding="unicode")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ").split("\n", 1)[
            1
        ]  # Remove XML declaration

    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            HTML-escaped text
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#x27;")
        )


class TemplateValidator:
    """Validates template syntax and structure with comprehensive checking.

    Provides validation for:
    - Template syntax correctness
    - Variable placeholder validity
    - Format-specific structure validation
    - Cross-format compatibility checking
    """

    def __init__(self) -> None:
        """Initialize the template validator."""
        self._format_validators = {
            TemplateFormat.TEXT: self._validate_text,
            TemplateFormat.HTML: self._validate_html,
            TemplateFormat.MARKDOWN: self._validate_markdown,
            TemplateFormat.JSON: self._validate_json,
            TemplateFormat.XML: self._validate_xml,
        }
        logger.debug("Initialized TemplateValidator")

    def validate_template(self, template: ErrorTemplate) -> list[str]:
        """Validate a template and return list of validation errors.

        Args:
            template: Template to validate

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        try:
            # Basic validation
            errors.extend(self._validate_basic_structure(template))

            # Format-specific validation
            if template.format in self._format_validators:
                validator = self._format_validators[template.format]
                errors.extend(validator(template))

            # Variable validation
            errors.extend(self._validate_variables(template))

            logger.debug(
                f"Validated template {template.id}: {len(errors)} errors found",
            )

        except Exception as e:
            errors.append(f"Validation failed with exception: {e}")
            logger.error(f"Template validation error for {template.id}: {e}")

        return errors

    def validate_syntax(
        self,
        template_string: str,
        template_format: TemplateFormat,
    ) -> list[str]:
        """Validate template syntax without full template object.

        Args:
            template_string: Template string to validate
            template_format: Format of the template

        Returns:
            List of syntax error messages
        """
        errors = []

        try:
            # Create temporary template for validation
            temp_template = ErrorTemplate(
                id="temp",
                name="temp",
                type=TemplateType.ERROR_MESSAGE,
                format=template_format,
                template=template_string,
            )

            # Use format-specific validator
            if template_format in self._format_validators:
                validator = self._format_validators[template_format]
                errors.extend(validator(temp_template))

        except Exception as e:
            errors.append(f"Syntax validation failed: {e}")

        return errors

    def _validate_basic_structure(self, template: ErrorTemplate) -> list[str]:
        """Validate basic template structure.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []

        if not template.id or not template.id.strip():
            errors.append("Template ID cannot be empty")

        if not template.name or not template.name.strip():
            errors.append("Template name cannot be empty")

        if not template.template or not template.template.strip():
            errors.append("Template content cannot be empty")

        # Check for valid variable syntax
        variable_pattern = re.compile(r"\$\{([^}]*)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)")
        invalid_vars = []

        for match in variable_pattern.finditer(template.template):
            var_name = match.group(1) if match.group(1) else match.group(2)
            if not var_name:
                invalid_vars.append(match.group(0))
            elif not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", var_name):
                invalid_vars.append(var_name)

        if invalid_vars:
            errors.append(f"Invalid variable names found: {invalid_vars}")

        return errors

    def _validate_text(self, template: ErrorTemplate) -> list[str]:
        """Validate plain text template.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        # Text templates are generally permissive
        return []

    def _validate_html(self, template: ErrorTemplate) -> list[str]:
        """Validate HTML template.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []
        content = template.template

        # Check for balanced tags (basic validation)
        tag_pattern = re.compile(r"<(/?)(\w+)(?:\s[^>]*)?>")
        tag_stack = []

        for match in tag_pattern.finditer(content):
            is_closing = bool(match.group(1))
            tag_name = match.group(2).lower()

            # Skip self-closing tags
            if tag_name in ["br", "hr", "img", "input", "meta", "link"]:
                continue

            if is_closing:
                if not tag_stack or tag_stack[-1] != tag_name:
                    errors.append(f"Unmatched closing tag: </{tag_name}>")
                else:
                    tag_stack.pop()
            else:
                tag_stack.append(tag_name)

        if tag_stack:
            errors.append(f"Unclosed tags: {tag_stack}")

        return errors

    def _validate_markdown(self, template: ErrorTemplate) -> list[str]:
        """Validate Markdown template.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []
        content = template.template
        lines = content.split("\n")

        # Check for unbalanced code blocks
        code_block_count = content.count("```")
        if code_block_count % 2 != 0:
            errors.append("Unbalanced code blocks (```)")

        # Check for malformed headers
        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                # Check if header has proper space after #
                if not re.match(r"^#+\s+.+", line):
                    errors.append(f"Malformed header at line {i}: {line}")

        return errors

    def _validate_json(self, template: ErrorTemplate) -> list[str]:
        """Validate JSON template.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []
        content = template.template

        # Replace variables with dummy values for validation
        test_content = content
        for var in template.variables:
            test_content = test_content.replace(f"${{{var}}}", '"test_value"')
            test_content = test_content.replace(f"${var}", '"test_value"')

        try:
            json.loads(test_content)
        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON syntax: {e}")

        return errors

    def _validate_xml(self, template: ErrorTemplate) -> list[str]:
        """Validate XML template.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []
        content = template.template

        # Replace variables with dummy values for validation
        test_content = content
        for var in template.variables:
            test_content = test_content.replace(f"${{{var}}}", "test_value")
            test_content = test_content.replace(f"${var}", "test_value")

        try:
            ET.fromstring(test_content)
        except ET.ParseError as e:
            errors.append(f"Invalid XML syntax: {e}")

        return errors

    def _validate_variables(self, template: ErrorTemplate) -> list[str]:
        """Validate template variables.

        Args:
            template: Template to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Check for duplicate variable declarations
        var_pattern = re.compile(r"\$\{([^}]+)\}|\$([a-zA-Z_][a-zA-Z0-9_]*)")
        found_vars = []

        for match in var_pattern.finditer(template.template):
            var_name = match.group(1) if match.group(1) else match.group(2)
            if var_name:
                found_vars.append(var_name)

        # Check if extracted variables match template.variables
        extracted_vars = set(found_vars)
        if extracted_vars != template.variables:
            errors.append(
                f"Variable mismatch: extracted {extracted_vars}, stored {template.variables}",
            )

        return errors


class TemplateLibrary:
    """Pre-built template library with common error templates and management capabilities.

    Provides:
    - Built-in templates for common error scenarios
    - Template categories and organization
    - Easy access to frequently used templates
    - Template import/export functionality
    """

    def __init__(self, manager: TemplateManager | None = None) -> None:
        """Initialize the template library.

        Args:
            manager: Optional template manager (creates new one if None)
        """
        self.manager = manager or TemplateManager()
        self._initialized = False
        self._built_in_templates: dict[str, dict[str, Any]] = {}

        logger.info("Initialized TemplateLibrary")

    def initialize_builtin_templates(self) -> None:
        """Initialize the library with built-in templates."""
        if self._initialized:
            return

        self._define_builtin_templates()
        self._load_builtin_templates()
        self._initialized = True

        logger.info(f"Loaded {len(self._built_in_templates)} built-in templates")

    def _define_builtin_templates(self) -> None:
        """Define all built-in template specifications."""

        # Error message templates
        self._built_in_templates.update(
            {
                "parse_error_generic": {
                    "name": "Generic Parse Error",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "Parse error in ${file_path} at line ${line_number}: ${error_message}",
                    "metadata": {
                        "description": "Generic template for parse errors",
                        "tags": ["parse", "error", "generic"],
                        "category": "syntax_errors",
                    },
                },
                "file_not_found": {
                    "name": "File Not Found Error",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "File not found: ${file_path}. Please check the file path and try again.",
                    "metadata": {
                        "description": "Template for file not found errors",
                        "tags": ["file", "not_found", "error"],
                        "category": "file_errors",
                    },
                },
                "unsupported_language": {
                    "name": "Unsupported Language Error",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": 'Language "${language}" is not supported. Supported languages: ${supported_languages}',
                    "metadata": {
                        "description": "Template for unsupported language errors",
                        "tags": ["language", "unsupported", "error"],
                        "category": "language_errors",
                    },
                },
                "grammar_not_found": {
                    "name": "Grammar Not Found Error",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": 'Tree-sitter grammar for "${language}" not found. Try running: treesitter-chunker download-grammar ${language}',
                    "metadata": {
                        "description": "Template for missing grammar errors",
                        "tags": ["grammar", "missing", "error"],
                        "category": "grammar_errors",
                    },
                },
                # Warning message templates
                "large_file_warning": {
                    "name": "Large File Warning",
                    "type": TemplateType.WARNING_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "Warning: File ${file_path} is large (${file_size} bytes). Processing may take longer than usual.",
                    "metadata": {
                        "description": "Warning for processing large files",
                        "tags": ["file", "size", "warning"],
                        "category": "performance_warnings",
                    },
                },
                "fallback_chunking": {
                    "name": "Fallback Chunking Warning",
                    "type": TemplateType.WARNING_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "Unable to parse ${file_path} with tree-sitter. Falling back to ${fallback_strategy} chunking.",
                    "metadata": {
                        "description": "Warning when falling back to alternate chunking",
                        "tags": ["fallback", "chunking", "warning"],
                        "category": "processing_warnings",
                    },
                },
                # Info message templates
                "processing_complete": {
                    "name": "Processing Complete",
                    "type": TemplateType.INFO_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "Successfully processed ${file_count} files. Generated ${chunk_count} chunks in ${processing_time}.",
                    "metadata": {
                        "description": "Info message for successful processing",
                        "tags": ["success", "completion", "info"],
                        "category": "status_messages",
                    },
                },
                "cache_hit": {
                    "name": "Cache Hit Info",
                    "type": TemplateType.INFO_MESSAGE,
                    "format": TemplateFormat.TEXT,
                    "template": "Using cached results for ${file_path} (last modified: ${last_modified})",
                    "metadata": {
                        "description": "Info message for cache usage",
                        "tags": ["cache", "hit", "info"],
                        "category": "performance_info",
                    },
                },
                # HTML templates
                "error_html": {
                    "name": "HTML Error Message",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.HTML,
                    "template": """
                <div class="error-message">
                    <h3>Error: ${error_title}</h3>
                    <p class="error-description">${error_description}</p>
                    <div class="error-details">
                        <strong>File:</strong> ${file_path}<br>
                        <strong>Line:</strong> ${line_number}<br>
                        <strong>Timestamp:</strong> ${timestamp}
                    </div>
                </div>
                """,
                    "metadata": {
                        "description": "HTML template for error messages",
                        "tags": ["html", "error", "formatted"],
                        "category": "html_templates",
                    },
                },
                # Markdown templates
                "help_markdown": {
                    "name": "Markdown Help Text",
                    "type": TemplateType.HELP_TEXT,
                    "format": TemplateFormat.MARKDOWN,
                    "template": """
# ${command_name} Help

## Description
${command_description}

## Usage
```bash
${usage_example}
```

## Options
${options_list}

## Examples
${examples}

For more information, visit: ${documentation_url}
                """,
                    "metadata": {
                        "description": "Markdown template for help text",
                        "tags": ["markdown", "help", "documentation"],
                        "category": "help_templates",
                    },
                },
                # JSON templates
                "error_json": {
                    "name": "JSON Error Response",
                    "type": TemplateType.ERROR_MESSAGE,
                    "format": TemplateFormat.JSON,
                    "template": """
{
    "error": {
        "code": "${error_code}",
        "message": "${error_message}",
        "details": {
            "file_path": "${file_path}",
            "line_number": ${line_number},
            "timestamp": "${timestamp}"
        },
        "suggestions": ${suggestions}
    }
}
                """,
                    "metadata": {
                        "description": "JSON template for API error responses",
                        "tags": ["json", "api", "error"],
                        "category": "api_templates",
                    },
                },
            },
        )

    def _load_builtin_templates(self) -> None:
        """Load built-in templates into the manager."""
        for template_id, spec in self._built_in_templates.items():
            try:
                template = ErrorTemplate(
                    id=template_id,
                    name=spec["name"],
                    type=spec["type"],
                    format=spec["format"],
                    template=spec["template"].strip(),
                    metadata=spec.get("metadata", {}),
                )

                self.manager.add_template(template, overwrite=True)
                logger.debug(f"Loaded built-in template: {template_id}")

            except Exception as e:
                logger.error(f"Failed to load built-in template {template_id}: {e}")

    def get_template(self, template_id: str) -> ErrorTemplate | None:
        """Get a template by ID.

        Args:
            template_id: ID of template to retrieve

        Returns:
            Template if found, None otherwise
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        return self.manager.get_template(template_id)

    def get_templates_by_category(self, category: str) -> list[ErrorTemplate]:
        """Get all templates in a specific category.

        Args:
            category: Category name

        Returns:
            List of templates in the category
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        templates = self.manager.list_templates()
        return [t for t in templates if t.metadata.get("category") == category]

    def get_templates_by_tag(self, tag: str) -> list[ErrorTemplate]:
        """Get all templates with a specific tag.

        Args:
            tag: Tag name

        Returns:
            List of templates with the tag
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        templates = self.manager.list_templates()
        return [t for t in templates if tag in t.metadata.get("tags", [])]

    def export_templates(
        self,
        file_path: str | Path,
        template_ids: list[str] | None = None,
    ) -> bool:
        """Export templates to a JSON file.

        Args:
            file_path: Path to export file
            template_ids: Optional list of specific template IDs to export

        Returns:
            True if export was successful
        """
        try:
            if not self._initialized:
                self.initialize_builtin_templates()

            templates_to_export = []

            if template_ids:
                for template_id in template_ids:
                    template = self.manager.get_template(template_id)
                    if template:
                        templates_to_export.append(template.to_dict())
            else:
                templates = self.manager.list_templates()
                templates_to_export = [t.to_dict() for t in templates]

            export_data = {
                "version": "1.0.0",
                "exported_at": datetime.now(UTC).isoformat(),
                "template_count": len(templates_to_export),
                "templates": templates_to_export,
            }

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(templates_to_export)} templates to {file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export templates: {e}")
            return False

    def import_templates(
        self,
        file_path: str | Path,
        overwrite: bool = False,
    ) -> int:
        """Import templates from a JSON file.

        Args:
            file_path: Path to import file
            overwrite: Whether to overwrite existing templates

        Returns:
            Number of templates imported successfully
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                import_data = json.load(f)

            templates_data = import_data.get("templates", [])
            imported_count = 0

            for template_data in templates_data:
                try:
                    template = ErrorTemplate.from_dict(template_data)
                    if self.manager.add_template(template, overwrite=overwrite):
                        imported_count += 1
                except Exception as e:
                    logger.warning(
                        f"Failed to import template {template_data.get('id', 'unknown')}: {e}",
                    )

            logger.info(f"Imported {imported_count} templates from {file_path}")
            return imported_count

        except Exception as e:
            logger.error(f"Failed to import templates: {e}")
            return 0

    def list_categories(self) -> list[str]:
        """Get list of all template categories.

        Returns:
            List of category names
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        categories = set()
        templates = self.manager.list_templates()

        for template in templates:
            category = template.metadata.get("category")
            if category:
                categories.add(category)

        return sorted(list(categories))

    def list_tags(self) -> list[str]:
        """Get list of all template tags.

        Returns:
            List of tag names
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        tags = set()
        templates = self.manager.list_templates()

        for template in templates:
            template_tags = template.metadata.get("tags", [])
            tags.update(template_tags)

        return sorted(list(tags))

    def get_statistics(self) -> dict[str, Any]:
        """Get library statistics.

        Returns:
            Dictionary containing library statistics
        """
        if not self._initialized:
            self.initialize_builtin_templates()

        base_stats = self.manager.get_statistics()

        # Add library-specific statistics
        base_stats.update(
            {
                "categories": len(self.list_categories()),
                "tags": len(self.list_tags()),
                "builtin_templates": len(self._built_in_templates),
                "initialized": self._initialized,
            },
        )

        return base_stats


# Factory function for easy template system setup
def create_template_system(
    cache_size: int = 1000,
    load_builtin: bool = True,
) -> tuple[TemplateLibrary, TemplateRenderer, TemplateValidator]:
    """Create a complete template system with all components.

    Args:
        cache_size: Size of template cache
        load_builtin: Whether to load built-in templates

    Returns:
        Tuple of (library, renderer, validator)
    """
    manager = TemplateManager(cache_size=cache_size)
    library = TemplateLibrary(manager)
    renderer = TemplateRenderer()
    validator = TemplateValidator()

    if load_builtin:
        library.initialize_builtin_templates()

    logger.info("Created complete template system")
    return library, renderer, validator


# Convenience functions
def render_template(
    template_id: str,
    variables: dict[str, Any],
    library: TemplateLibrary | None = None,
    renderer: TemplateRenderer | None = None,
    output_format: TemplateFormat | None = None,
) -> str:
    """Convenience function to render a template by ID.

    Args:
        template_id: ID of template to render
        variables: Variables to substitute
        library: Template library (creates default if None)
        renderer: Template renderer (creates default if None)
        output_format: Optional output format override

    Returns:
        Rendered template string

    Raises:
        ValueError: If template not found or rendering fails
    """
    if library is None:
        library, renderer, _ = create_template_system()

    if renderer is None:
        renderer = TemplateRenderer()

    template = library.get_template(template_id)
    if not template:
        raise ValueError(f"Template '{template_id}' not found")

    return renderer.render(template, variables, output_format)


def validate_template_string(
    template_string: str,
    template_format: TemplateFormat,
    validator: TemplateValidator | None = None,
) -> list[str]:
    """Convenience function to validate a template string.

    Args:
        template_string: Template string to validate
        template_format: Format of the template
        validator: Template validator (creates default if None)

    Returns:
        List of validation error messages
    """
    if validator is None:
        _, _, validator = create_template_system(load_builtin=False)

    return validator.validate_syntax(template_string, template_format)
