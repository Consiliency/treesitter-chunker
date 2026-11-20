"""The binding allow-list (plan section 7.5, ruling A5).

Every named node kind of each pinned grammar (JavaScript, TypeScript, TSX and
Python) gets one classification:

- ``handled``: the analyzer understands the binding it introduces, with its
  binding class;
- ``ignored``: it introduces no value binding the lookup needs, with a reason
  (labels, for example);
- ``fail-closed``: a lookup that meets it gives ``none(unmapped)``;
- ``non-binding``: it cannot introduce a binding.

An analyzer consults :func:`classify` for every declaration-like node it
meets. A kind with no entry is treated as ``fail-closed``, so a grammar bump
can never add an unreviewed binding form that narrows an edge.
``tests/test_call_resolution_allowlist.py`` enumerates the kinds of each loaded
``Language`` and fails on any unclassified kind of a reviewed grammar.

The JavaScript, TypeScript and TSX grammars are reviewed (the JS/TS
analyzer, :mod:`.js_scope`, consults this list for every node it visits).
Python is still a stub and unreviewed; its analyzer change adds its
classification and lists it in :data:`REVIEWED_LANGUAGES`.

Named explicitly by the plan: TS ``import_alias`` is handled as a non-symbol
binding; ``for (const/let ... of/in)`` is ``for_in_statement``; JavaScript's
``using`` and ``await using`` are ``using_declaration``. The pinned
TypeScript and TSX grammars lack ``using_declaration`` and parse
``using x = f()`` as an assignment carrying a ``using`` token; the analyzer
binds such names fail-closed (``unmapped``).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

HANDLED = "handled"
IGNORED = "ignored"
FAIL_CLOSED = "fail-closed"
NON_BINDING = "non-binding"
CLASSIFICATIONS = (HANDLED, IGNORED, FAIL_CLOSED, NON_BINDING)

PINNED_GRAMMARS = ("javascript", "typescript", "tsx", "python")


@dataclass(frozen=True)
class Entry:
    """One node kind's classification."""

    classification: str
    # The binding class for ``handled`` kinds (for example ``"symbol"``,
    # ``"parameter"`` or ``"local-variable"``), or the reason for ``ignored``
    # and ``fail-closed`` kinds.
    detail: str = ""


_NB = Entry(NON_BINDING)
_TYPE_SPACE = Entry(IGNORED, "type space: binds no value")
_TYPE_MEMBER = Entry(IGNORED, "type-space member: binds no bare name")
_CLASS_MEMBER = Entry(IGNORED, "class member: a property, not a bare-name binding")
_LABEL = Entry(IGNORED, "labels bind no value")
_ENUM_MEMBER = Entry(IGNORED, "enum members are properties of the enum")
_PATTERN = Entry(HANDLED, "pattern: binds as its declaration or assignment")
_IMPORT = Entry(HANDLED, "import: value import or type-only")
_SCOPE = Entry(HANDLED, "scope")
_SYMBOL = Entry(HANDLED, "symbol")
_PARAMETER = Entry(HANDLED, "parameter")
_LOCAL = Entry(HANDLED, "local-variable")
_REASSIGNED = Entry(HANDLED, "reassigned: assignment target")

# Kinds every JS-family grammar has (javascript, typescript and tsx).
_JS_COMMON: dict[str, Entry] = {
    "arguments": _NB,
    "array": _NB,
    "array_pattern": _PATTERN,
    "arrow_function": Entry(HANDLED, "parameter scope"),
    "assignment_expression": _REASSIGNED,
    "assignment_pattern": _PATTERN,
    "augmented_assignment_expression": _REASSIGNED,
    "await_expression": _NB,
    "binary_expression": _NB,
    "break_statement": _NB,
    "call_expression": _NB,
    "catch_clause": _LOCAL,
    "class": Entry(HANDLED, "self-binding"),
    "class_body": Entry(IGNORED, "a class body binds no bare names; lookups skip it"),
    "class_declaration": _SYMBOL,
    "class_heritage": _NB,
    "class_static_block": _SCOPE,
    "comment": _NB,
    "computed_property_name": _NB,
    "continue_statement": _NB,
    "debugger_statement": _NB,
    "decorator": _NB,
    "do_statement": _NB,
    "else_clause": _NB,
    "empty_statement": _NB,
    "escape_sequence": _NB,
    "export_clause": _NB,
    "export_specifier": _NB,
    "export_statement": _NB,
    "expression_statement": _NB,
    "false": _NB,
    "finally_clause": _NB,
    "for_in_statement": _LOCAL,
    "for_statement": _SCOPE,
    "formal_parameters": _PARAMETER,
    "function_declaration": _SYMBOL,
    "function_expression": Entry(HANDLED, "self-binding"),
    "generator_function": Entry(HANDLED, "self-binding"),
    "generator_function_declaration": _SYMBOL,
    "hash_bang_line": _NB,
    "html_comment": _NB,
    "identifier": _NB,
    "if_statement": _NB,
    "import": _NB,
    "import_attribute": _NB,
    "import_clause": _IMPORT,
    "import_specifier": _IMPORT,
    "import_statement": _IMPORT,
    "jsx_text": _NB,
    "labeled_statement": _LABEL,
    "lexical_declaration": Entry(HANDLED, "local-variable, or symbol for one const"),
    "member_expression": _NB,
    "meta_property": _NB,
    "method_definition": Entry(HANDLED, "parameter scope"),
    "named_imports": _IMPORT,
    "namespace_export": _NB,
    "namespace_import": _IMPORT,
    "new_expression": _NB,
    "null": _NB,
    "number": _NB,
    "object": _NB,
    "object_assignment_pattern": _PATTERN,
    "object_pattern": _PATTERN,
    "optional_chain": _NB,
    "pair": _NB,
    "pair_pattern": _PATTERN,
    "parenthesized_expression": _NB,
    "private_property_identifier": _NB,
    "program": _SCOPE,
    "property_identifier": _NB,
    "regex": _NB,
    "regex_flags": _NB,
    "regex_pattern": _NB,
    "rest_pattern": _PATTERN,
    "return_statement": _NB,
    "sequence_expression": _NB,
    "shorthand_property_identifier": _NB,
    "shorthand_property_identifier_pattern": _PATTERN,
    "spread_element": _NB,
    "statement_block": _SCOPE,
    "statement_identifier": _LABEL,
    "string": _NB,
    "string_fragment": _NB,
    "subscript_expression": _NB,
    "super": _NB,
    "switch_body": _SCOPE,
    "switch_case": _NB,
    "switch_default": _NB,
    "switch_statement": _NB,
    "template_string": _NB,
    "template_substitution": _NB,
    "ternary_expression": _NB,
    "this": _NB,
    "throw_statement": _NB,
    "true": _NB,
    "try_statement": _NB,
    "unary_expression": _NB,
    "undefined": _NB,
    "update_expression": _REASSIGNED,
    "variable_declaration": _LOCAL,
    "variable_declarator": _LOCAL,
    "while_statement": _NB,
    "with_statement": Entry(HANDLED, "dynamic-scope"),
    "yield_expression": _NB,
}

# Kinds the JSX grammars have (javascript and tsx).
_JSX: dict[str, Entry] = {
    "html_character_reference": _NB,
    "jsx_attribute": _NB,
    "jsx_closing_element": _NB,
    "jsx_element": _NB,
    "jsx_expression": _NB,
    "jsx_namespace_name": _NB,
    "jsx_opening_element": _NB,
    "jsx_self_closing_element": _NB,
}

# Kinds only the javascript grammar has.
_JS_ONLY: dict[str, Entry] = {
    "field_definition": _CLASS_MEMBER,
    "using_declaration": _LOCAL,
}

# Kinds the typescript and tsx grammars add.
_TS_COMMON: dict[str, Entry] = {
    "abstract_class_declaration": _SYMBOL,
    "abstract_method_signature": _CLASS_MEMBER,
    "accessibility_modifier": _NB,
    "adding_type_annotation": _NB,
    "ambient_declaration": Entry(HANDLED, "ambient status of its declarations"),
    "array_type": _NB,
    "as_expression": _NB,
    "asserts": _NB,
    "asserts_annotation": _NB,
    "call_signature": _TYPE_MEMBER,
    "conditional_type": _NB,
    "constraint": _NB,
    "construct_signature": _TYPE_MEMBER,
    "constructor_type": _NB,
    "default_type": _NB,
    "enum_assignment": _ENUM_MEMBER,
    "enum_body": _ENUM_MEMBER,
    "enum_declaration": _SYMBOL,
    "existential_type": _NB,
    "extends_clause": _NB,
    "extends_type_clause": _NB,
    "flow_maybe_type": _NB,
    "function_signature": _SYMBOL,
    "function_type": _NB,
    "generic_type": _NB,
    "implements_clause": _NB,
    "import_alias": _LOCAL,
    "import_require_clause": _LOCAL,
    "index_signature": _TYPE_MEMBER,
    "index_type_query": _NB,
    "infer_type": _TYPE_SPACE,
    "instantiation_expression": _NB,
    "interface_body": _NB,
    "interface_declaration": _TYPE_SPACE,
    "internal_module": _SYMBOL,
    "intersection_type": _NB,
    "literal_type": _NB,
    "lookup_type": _NB,
    "mapped_type_clause": _TYPE_SPACE,
    "method_signature": _CLASS_MEMBER,
    "module": _SYMBOL,
    "nested_identifier": _NB,
    "nested_type_identifier": _NB,
    "non_null_expression": _NB,
    "object_type": _NB,
    "omitting_type_annotation": _NB,
    "opting_type_annotation": _NB,
    "optional_parameter": _PARAMETER,
    "optional_type": _NB,
    "override_modifier": _NB,
    "parenthesized_type": _NB,
    "predefined_type": _NB,
    "property_signature": _TYPE_MEMBER,
    "public_field_definition": _CLASS_MEMBER,
    "readonly_type": _NB,
    "required_parameter": _PARAMETER,
    "rest_type": _NB,
    "satisfies_expression": _NB,
    "template_literal_type": _NB,
    "template_type": _NB,
    "this_type": _NB,
    "tuple_type": _NB,
    "type_alias_declaration": _TYPE_SPACE,
    "type_annotation": _NB,
    "type_arguments": _NB,
    "type_identifier": _NB,
    "type_parameter": _TYPE_SPACE,
    "type_parameters": _NB,
    "type_predicate": _NB,
    "type_predicate_annotation": _NB,
    "type_query": _NB,
    "union_type": _NB,
}

# {grammar: {node kind: Entry}}. Python is unreviewed until its analyzer
# lands, so its kinds all fail closed.
ALLOWLIST: dict[str, dict[str, Entry]] = {
    "javascript": {**_JS_COMMON, **_JSX, **_JS_ONLY},
    "typescript": {**_JS_COMMON, **_TS_COMMON, "type_assertion": _NB},
    "tsx": {**_JS_COMMON, **_TS_COMMON, **_JSX},
    "python": {},
}

# Grammars whose every named node kind must be classified.
REVIEWED_LANGUAGES: frozenset[str] = frozenset({"javascript", "typescript", "tsx"})

_UNCLASSIFIED = Entry(FAIL_CLOSED, "unclassified")


def classify(language: str, kind: str) -> Entry:
    """The entry for ``kind``; an unclassified kind fails closed."""
    return ALLOWLIST.get(language, {}).get(kind, _UNCLASSIFIED)


def named_node_kinds(language: str) -> frozenset[str]:
    """Every visible named node kind of the loaded ``language`` grammar.

    Read from the loaded ``Language``, so no grammar sources are needed.
    """
    from chunker.parser import get_parser

    loaded = get_parser(language).language
    if loaded is None:  # pragma: no cover - get_parser always sets one
        msg = f"no language loaded for {language}"
        raise RuntimeError(msg)
    return frozenset(
        str(loaded.node_kind_for_id(kind_id))
        for kind_id in range(loaded.node_kind_count)
        if loaded.node_kind_is_named(kind_id) and loaded.node_kind_is_visible(kind_id)
    )


def unclassified_kinds(
    kinds: Iterable[str],
    entries: Mapping[str, Entry],
) -> list[str]:
    """Kinds with no entry, sorted."""
    return sorted(kind for kind in set(kinds) if kind not in entries)


def unknown_entries(
    kinds: Iterable[str],
    entries: Mapping[str, Entry],
) -> list[str]:
    """Entries naming no kind of the grammar (typos, removed kinds), sorted."""
    known = set(kinds)
    return sorted(kind for kind in entries if kind not in known)


def invalid_entries(entries: Mapping[str, Entry]) -> list[str]:
    """Entries with an unknown classification or a missing detail, sorted."""
    return sorted(
        kind
        for kind, entry in entries.items()
        if entry.classification not in CLASSIFICATIONS
        or (entry.classification != NON_BINDING and not entry.detail)
    )
