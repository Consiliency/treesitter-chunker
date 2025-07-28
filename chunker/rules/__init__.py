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
    "AnnotationRule",
    "BaseCommentBlockRule",
    # Base classes
    "BaseCustomRule",
    "BaseRegexRule",
    "ConfigurationBlockRule",
    "CopyrightHeaderRule",
    "CustomMarkerRule",
    "DebugStatementRule",
    # Engine
    "DefaultRuleEngine",
    "DocstringRule",
    "DocumentationBlockRule",
    "FoldingMarkerRule",
    "HeaderCommentRule",
    "ImportBlockRule",
    "InlineCommentGroupRule",
    "LanguageSpecificCommentRule",
    "MetadataRule",
    "PatternBoundaryRule",
    # Regex rules
    "RegionMarkerRule",
    "SectionHeaderRule",
    "SeparatorLineRule",
    "StructuredCommentRule",
    "TestAnnotationRule",
    # Comment rules
    "TodoBlockRule",
    # Built-in rules
    "TodoCommentRule",
    "create_comment_rule_chain",
    "create_custom_regex_rule",
    "get_builtin_rules",
]
