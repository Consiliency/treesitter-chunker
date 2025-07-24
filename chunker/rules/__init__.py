"""Custom chunking rules module."""

from .builtin import (
    ConfigurationBlockRule,
    CopyrightHeaderRule,
    CustomMarkerRule,
    DebugStatementRule,
    DocstringRule,
    ImportBlockRule,
    LanguageSpecificCommentRule,
    SectionHeaderRule,
    TestAnnotationRule,
    TodoCommentRule,
    get_builtin_rules,
)
from .comment import (
    DocumentationBlockRule,
    HeaderCommentRule,
    InlineCommentGroupRule,
    StructuredCommentRule,
    TodoBlockRule,
    create_comment_rule_chain,
)
from .custom import BaseCommentBlockRule, BaseCustomRule, BaseRegexRule, MetadataRule
from .engine import DefaultRuleEngine
from .regex import (
    AnnotationRule,
    FoldingMarkerRule,
    PatternBoundaryRule,
    RegionMarkerRule,
    SeparatorLineRule,
    create_custom_regex_rule,
)

__all__ = [
    # Base classes
    "BaseCustomRule",
    "BaseRegexRule",
    "BaseCommentBlockRule",
    "MetadataRule",
    # Engine
    "DefaultRuleEngine",
    # Built-in rules
    "TodoCommentRule",
    "CopyrightHeaderRule",
    "DocstringRule",
    "ImportBlockRule",
    "CustomMarkerRule",
    "SectionHeaderRule",
    "ConfigurationBlockRule",
    "LanguageSpecificCommentRule",
    "DebugStatementRule",
    "TestAnnotationRule",
    "get_builtin_rules",
    # Regex rules
    "RegionMarkerRule",
    "PatternBoundaryRule",
    "AnnotationRule",
    "FoldingMarkerRule",
    "SeparatorLineRule",
    "create_custom_regex_rule",
    # Comment rules
    "TodoBlockRule",
    "DocumentationBlockRule",
    "HeaderCommentRule",
    "InlineCommentGroupRule",
    "StructuredCommentRule",
    "create_comment_rule_chain",
]
