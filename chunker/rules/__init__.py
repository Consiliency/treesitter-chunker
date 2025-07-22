"""Custom chunking rules module."""

from .custom import (
    BaseCustomRule,
    BaseRegexRule,
    BaseCommentBlockRule,
    MetadataRule
)

from .engine import DefaultRuleEngine

from .builtin import (
    TodoCommentRule,
    CopyrightHeaderRule,
    DocstringRule,
    ImportBlockRule,
    CustomMarkerRule,
    SectionHeaderRule,
    ConfigurationBlockRule,
    LanguageSpecificCommentRule,
    DebugStatementRule,
    TestAnnotationRule,
    get_builtin_rules
)

from .regex import (
    RegionMarkerRule,
    PatternBoundaryRule,
    AnnotationRule,
    FoldingMarkerRule,
    SeparatorLineRule,
    create_custom_regex_rule
)

from .comment import (
    TodoBlockRule,
    DocumentationBlockRule,
    HeaderCommentRule,
    InlineCommentGroupRule,
    StructuredCommentRule,
    create_comment_rule_chain
)

__all__ = [
    # Base classes
    'BaseCustomRule',
    'BaseRegexRule',
    'BaseCommentBlockRule',
    'MetadataRule',
    
    # Engine
    'DefaultRuleEngine',
    
    # Built-in rules
    'TodoCommentRule',
    'CopyrightHeaderRule',
    'DocstringRule',
    'ImportBlockRule',
    'CustomMarkerRule',
    'SectionHeaderRule',
    'ConfigurationBlockRule',
    'LanguageSpecificCommentRule',
    'DebugStatementRule',
    'TestAnnotationRule',
    'get_builtin_rules',
    
    # Regex rules
    'RegionMarkerRule',
    'PatternBoundaryRule',
    'AnnotationRule',
    'FoldingMarkerRule',
    'SeparatorLineRule',
    'create_custom_regex_rule',
    
    # Comment rules
    'TodoBlockRule',
    'DocumentationBlockRule',
    'HeaderCommentRule',
    'InlineCommentGroupRule',
    'StructuredCommentRule',
    'create_comment_rule_chain'
]