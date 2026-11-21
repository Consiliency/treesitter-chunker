"""Tier 1 Python scope analysis (treesitter-chunker#682, PR 4).

Plan ``plans/detailed-scoped-call-resolution-682.md`` sections 7.3, 7.4, 7.5,
7.6 and 8. The expected tables (``test_call_resolution_engine.py``) pin every
fixture call end to end; this module adds:

- analyzer unit cases on short sources, one per rule of 7.3 that the
  fixtures do not isolate: LEGB, class scopes (ruling A10), comprehension,
  lambda and PEP 695 type-parameter scopes, ``global``/``nonlocal``;
- fail-closed handling built in from the start: every write form binds,
  dynamic binding (``exec``, ``globals``, ``sys.modules`` and the like) gives
  ``dynamic-scope``, decorated and conditional definitions never prove, and
  a file with a non-ASCII identifier is not analyzed (Python compares
  identifiers after NFKC normalization);
- the allow-list contract: every handled kind has a handler;
- end-to-end trees the tests write, because a committed tree would change the
  off-mode baseline (plan 11.2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from chunker.call_resolution import allowlist, py_scope
from chunker.parser import get_parser
from chunker.symbol_graph import extract_symbol_facts_for_file, extract_symbol_graph

MODE = "structural"


def _callees(root: Any, source: bytes, text: str) -> list[Any]:
    found = []
    stack = [root]
    while stack:
        current = stack.pop()
        callee = (
            current.child_by_field_name("function") if current.type == "call" else None
        )
        if callee is not None and source[callee.start_byte : callee.end_byte] == (
            text.encode()
        ):
            found.append(callee)
        stack.extend(reversed(current.children))
    return sorted(found, key=lambda item: item.start_byte)


def outcome(source: str, callee: str, occurrence: int = 0) -> dict[str, Any]:
    """The analyzer's outcome for the ``occurrence``-th call of ``callee``."""
    data = source.encode()
    root = get_parser("python").parse(data).root_node
    assert not root.has_error, source
    node = _callees(root, data, callee)[occurrence]
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    bindings = py_scope.analyze(root, data, "python", [span])["bindings"]
    return bindings[f"{node.start_byte}:{node.end_byte}"]


def reason(source: str, callee: str = "helper", occurrence: int = 0) -> str:
    result = outcome(source, callee, occurrence)
    assert result["outcome"] == "none", result
    return str(result["reason"])


def proof_text(source: str, callee: str = "helper", occurrence: int = 0) -> list[str]:
    result = outcome(source, callee, occurrence)
    assert result["outcome"] == "local", result
    data = source.encode()
    return [data[start:end].decode() for _, start, end in result["proof"]]


HELPER = "def helper():\n    return 1\n\n\n"
PROOF = ["def helper():\n    return 1"]


# ---------------------------------------------------------------------------
# Scope chain (7.3)


def test_function_scope_resolves_the_innermost_binding() -> None:
    source = (
        HELPER + "def f():\n    def helper():\n        return 2\n    return helper()\n"
    )
    assert proof_text(source) == ["def helper():\n        return 2"]


def test_lookup_does_not_depend_on_position() -> None:
    # A local bound after the call is still local (UnboundLocalError).
    source = HELPER + "def f():\n    helper()\n    helper = 2\n"
    assert reason(source) == "local-variable"
    # A module-level call before the only definition is a NameError.
    assert proof_text("helper()\n" + HELPER) == PROOF


def test_unbound_names_are_builtins_or_name_errors() -> None:
    assert reason("def f():\n    return helper()\n") == "unbound"


def test_parameters_and_lambda_parameters_bind() -> None:
    for signature in (
        "helper",
        "*helper",
        "**helper",
        "helper: int",
        "helper=1",
        "helper: int = 1",
        "helper, /",
        "*, helper",
    ):
        source = HELPER + f"def f({signature}):\n    return helper()\n"
        assert reason(source) == "parameter", signature
    assert reason(HELPER + "g = lambda helper: helper()\n") == "parameter"
    assert reason(HELPER + "g = lambda *helper: helper()\n") == "parameter"


def test_defaults_and_annotations_run_in_the_enclosing_scope() -> None:
    # The parameter ``helper`` is not visible to its own default.
    source = HELPER + "def f(helper=helper()):\n    return 0\n"
    assert proof_text(source) == PROOF
    annotated = HELPER + "def f(x: helper()) -> helper():\n    return 0\n"
    assert proof_text(annotated, occurrence=0) == PROOF
    assert proof_text(annotated, occurrence=1) == PROOF
    lam = HELPER + "g = lambda helper=helper(): 0\n"
    assert proof_text(lam) == PROOF


def test_decorators_run_in_the_enclosing_scope() -> None:
    source = (
        HELPER + "def wrap(f):\n    def helper():\n        return 2\n"
        "    @helper()\n    def g():\n        return 0\n    return g\n"
    )
    assert proof_text(source) == ["def helper():\n        return 2"]


def test_comprehension_targets_and_first_iterable() -> None:
    source = HELPER + "def f(xs):\n    return [helper() for helper in xs]\n"
    assert reason(source) == "local-variable"
    # The first iterable runs in the enclosing scope, so it sees the module.
    first = HELPER + "def f():\n    return {helper for helper in helper()}\n"
    assert proof_text(first) == PROOF
    # A later iterable runs in the comprehension scope.
    later = HELPER + "def f(xs):\n    return [1 for helper in xs for y in helper()]\n"
    assert reason(later) == "local-variable"
    for kind in ("{helper() for helper in xs}", "(helper() for helper in xs)"):
        assert reason(HELPER + f"def f(xs):\n    return {kind}\n") == "local-variable"
    dict_comp = HELPER + "def f(xs):\n    return {helper: helper() for helper in xs}\n"
    assert reason(dict_comp) == "local-variable"


def test_python2_list_comprehension_targets_also_bind_outside() -> None:
    """The grammar accepts Python 2, where list-comprehension targets leaked
    into the enclosing scope; the extra binding fails closed."""
    source = HELPER + "[0 for helper in range(3)]\n\ndef f():\n    return helper()\n"
    assert reason(source) == "mixed-bindings"
    generator = (
        HELPER + "list(0 for helper in range(3))\n\ndef f():\n    return helper()\n"
    )
    assert proof_text(generator) == PROOF


def test_walrus_binds_in_the_nearest_non_comprehension_scope() -> None:
    source = (
        HELPER
        + "def f(xs):\n    [y for y in xs if (helper := y)]\n    return helper()\n"
    )
    assert reason(source) == "local-variable"
    module = (
        HELPER + "[y for y in [1] if (helper := y)]\n\ndef f():\n    return helper()\n"
    )
    assert reason(module) == "mixed-bindings"
    # A walrus in a default value binds in the enclosing scope.
    default = (
        HELPER
        + "def f(x=(helper := 1)):\n    return 0\n\ndef g():\n    return helper()\n"
    )
    assert reason(default) == "mixed-bindings"


# ---------------------------------------------------------------------------
# Class scope (ruling A10 as modified)


def test_class_body_code_sees_names_the_class_binds() -> None:
    body = "def helper(self):\n        return 2\n"
    for code in (
        "x = helper()",
        "@helper()\n    def m(self):\n        return 0",
        "def m(self, x=helper()):\n        return x",
        "def m(self, x: helper()):\n        return x",
        "class Inner(helper()):\n        pass",
        "xs = [y for y in helper()]",
        "f = lambda x=helper(): x",
    ):
        source = HELPER + f"class K:\n    {body}\n    {code}\n"
        assert reason(source) == "class-scope-bound", code


def test_class_body_binding_has_no_positional_variant() -> None:
    source = HELPER + "class K:\n    x = helper()\n    helper = 2\n"
    assert reason(source) == "class-scope-bound"


def test_methods_lambdas_and_comprehension_bodies_skip_the_class() -> None:
    body = "def helper(self):\n        return 2\n"
    for code in (
        "def m(self):\n        return helper()",
        "f = lambda: helper()",
        "xs = [helper() for y in range(3)]",
        "def m(self, x=lambda: helper()):\n        return x",
    ):
        source = HELPER + f"class K:\n    {body}\n    {code}\n"
        assert proof_text(source) == PROOF, code


def test_free_names_in_a_class_continue_through_enclosing_functions() -> None:
    source = (
        HELPER + "def f():\n    def helper():\n        return 2\n"
        "    class K:\n        x = helper()\n    return K\n"
    )
    assert proof_text(source) == ["def helper():\n        return 2"]


def test_nested_class_bodies_do_not_see_outer_classes() -> None:
    source = HELPER + "class A:\n    helper = 1\n\n    class B:\n        x = helper()\n"
    assert proof_text(source) == PROOF


def test_class_cell_and_dunder_names() -> None:
    source = "def __class__():\n    return 1\n\n\nclass K:\n    def m(self):\n        return __class__()\n"
    assert reason(source, "__class__") == "local-variable"
    module = "def __name__():\n    return 1\n\n\ndef f():\n    return __name__()\n"
    assert reason(module, "__name__") == "mixed-bindings"


# ---------------------------------------------------------------------------
# PEP 695 type parameters


def test_type_parameters_bind_for_their_definition() -> None:
    assert reason(HELPER + "def f[helper]():\n    return helper()\n") == "parameter"
    assert reason(HELPER + "class K[helper]:\n    x = helper()\n") == "parameter"
    method = HELPER + "class K[helper]:\n    def m(self):\n        return helper()\n"
    assert reason(method) == "parameter"
    # Lookups from a generic function's defaults also pass through them.
    default = HELPER + "def f[helper](x=helper()):\n    return x\n"
    assert reason(default) == "parameter"
    alias = HELPER + "type X[helper] = helper()\n"
    assert reason(alias) == "parameter"
    # Other names continue outward.
    assert proof_text(HELPER + "def f[T]():\n    return helper()\n") == PROOF


def test_type_statement_binds_its_name() -> None:
    source = HELPER + "type helper = int\n\ndef f():\n    return helper()\n"
    assert reason(source) == "mixed-bindings"


# ---------------------------------------------------------------------------
# Every write form binds (fail closed)

MODULE_WRITES = [
    "helper = 1",
    "helper: int = 1",
    "helper: int",
    "helper += 1",
    "helper, x = 1, 2",
    "(helper, x) = 1, 2",
    "[helper, x] = 1, 2",
    "*helper, x = 1, 2",
    "x, *helper = 1, 2",
    "(helper) = 1",
    "x = helper = 1",
    "for helper in []:\n    pass",
    "for x, (y, helper) in []:\n    pass",
    "with open('f') as helper:\n    pass",
    "with open('f') as (x, helper):\n    pass",
    "try:\n    pass\nexcept E as helper:\n    pass",
    "try:\n    pass\nexcept* E as helper:\n    pass",
    "try:\n    pass\nexcept E, helper:\n    pass",
    "match v:\n    case helper:\n        pass",
    "match v:\n    case [x, *helper]:\n        pass",
    "match v:\n    case {'k': x, **helper}:\n        pass",
    "match v:\n    case P(x=helper):\n        pass",
    "match v:\n    case P() as helper:\n        pass",
    "match v:\n    case [1, helper] | [helper, 1]:\n        pass",
    "del helper",
    "del (x, helper)",
    "import helper",
    "import x.y as helper",
    "import helper.sub",
    "from m import helper",
    "from m import x as helper",
    "from . import helper",
    "if (helper := 1):\n    pass",
    "type helper = int",
]


@pytest.mark.parametrize("write", MODULE_WRITES)
def test_module_write_forms_bind(write: str) -> None:
    source = HELPER + write + "\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "mixed-bindings", write


def test_future_import_binds_its_name() -> None:
    source = (
        "from __future__ import annotations\n\n\ndef annotations():\n    return 1\n\n\n"
        "def use():\n    return annotations()\n"
    )
    assert reason(source, "annotations") == "mixed-bindings"


def test_member_and_subscript_writes_do_not_bind() -> None:
    for write in (
        "helper.x = 1",
        "helper[0] = 1",
        "helper.x += 1",
        "helper.x: int = 1",
    ):
        source = HELPER + write + "\n\n\ndef use():\n    return helper()\n"
        assert proof_text(source) == PROOF, write
    # Their parts are still read: a walrus in a subscript binds.
    walrus = HELPER + "x[(helper := 0)] = 1\n\n\ndef use():\n    return helper()\n"
    assert reason(walrus) == "mixed-bindings"


def test_case_value_patterns_do_not_bind() -> None:
    for pattern in ("Color.RED", "helper.X", "1"):
        source = (
            HELPER
            + f"match v:\n    case {pattern}:\n        pass\n\n\ndef use():\n    return helper()\n"
        )
        assert proof_text(source) == PROOF, pattern
    keyword = (
        HELPER
        + "match v:\n    case P(helper=1):\n        pass\n\n\ndef use():\n    return helper()\n"
    )
    assert proof_text(keyword) == PROOF
    class_name = (
        HELPER
        + "match v:\n    case helper():\n        pass\n\n\ndef use():\n    return helper()\n"
    )
    assert proof_text(class_name) == PROOF


@pytest.mark.parametrize(
    "write",
    [
        "helper = other",
        "del helper",
        "helper += 1",
        "for helper in []:\n        pass",
        "with open('f') as helper:\n        pass",
        "import helper",
        "from m import helper",
        "def helper():\n        return 2",
        "class helper:\n        pass",
        "(helper := 1)",
    ],
)
def test_global_writes_are_non_definition_bindings(write: str) -> None:
    source = (
        HELPER
        + f"def patch():\n    global helper\n    {write}\n\n\ndef use():\n    return helper()\n"
    )
    assert reason(source) == "mixed-bindings", write
    in_class = (
        HELPER
        + f"class K:\n    global helper\n    {write}\n\n\ndef use():\n    return helper()\n"
    )
    assert reason(in_class) == "mixed-bindings", write


def test_global_redirects_lookups_to_the_module() -> None:
    source = (
        HELPER + "def outer():\n    def helper():\n        return 2\n"
        "    def g():\n        global helper\n        return helper()\n    return g\n"
    )
    assert proof_text(source) == PROOF
    # A ``global`` in an enclosing function hides that function's binding
    # from nested functions too (CPython's symbol table).
    hidden = (
        HELPER
        + "def outer():\n    global helper\n    def g():\n        return helper()\n    return g\n"
    )
    assert proof_text(hidden) == PROOF
    # A global write in a nested function does not touch the enclosing one.
    sibling = (
        "def outer():\n    def helper():\n        return 2\n"
        "    def g():\n        global helper\n        helper = 1\n"
        "    return helper()\n"
    )
    assert proof_text(sibling) == ["def helper():\n        return 2"]


@pytest.mark.parametrize(
    "write",
    [
        "helper = other",
        "del helper",
        "helper += 1",
        "for helper in []:\n            pass",
        "with open('f') as helper:\n            pass",
        "try:\n            pass\n        except E as helper:\n            pass",
        "import helper",
        "def helper():\n            return 3",
        "class helper:\n            pass",
        "(helper := 1)",
    ],
)
def test_nonlocal_writes_are_non_definition_bindings(write: str) -> None:
    source = (
        "def outer(other):\n    def helper():\n        return 1\n\n"
        f"    def swap():\n        nonlocal helper\n        {write}\n\n"
        "    swap()\n    return helper()\n"
    )
    assert reason(source) == "mixed-bindings", write


def test_nonlocal_reads_redirect_to_the_owning_scope() -> None:
    source = (
        "def outer():\n    def helper():\n        return 1\n\n"
        "    class K:\n        def m(self):\n            nonlocal helper\n"
        "            return helper()\n    return K\n"
    )
    assert proof_text(source) == ["def helper():\n        return 1"]


# ---------------------------------------------------------------------------
# Definitions and groups (7.4, 8)


def test_a_single_decorated_definition_is_not_a_proof() -> None:
    """A decorator can replace the function: the name is its result."""
    source = "def deco(f):\n    return f\n\n\n@deco\ndef helper():\n    return 1\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "expression-bound"
    klass = "@dataclass\nclass helper:\n    pass\n\n\ndef use():\n    return helper()\n"
    assert reason(klass) == "expression-bound"
    nested = "def f():\n    @deco\n    def helper():\n        return 1\n    return helper()\n"
    assert reason(nested) == "expression-bound"


def test_decorated_members_join_a_group_that_never_resolves() -> None:
    source = (
        "@overload\ndef f(x: int) -> int: ...\n@overload\ndef f(x: str) -> str: ...\n"
        "def f(x):\n    return x\n\n\ndef use():\n    return f(1)\n"
    )
    assert len(proof_text(source, "f")) == 3


@pytest.mark.parametrize(
    "wrapper",
    [
        "if X:\n    {d}",
        "if X:\n    pass\nelif Y:\n    {d}",
        "if X:\n    pass\nelse:\n    {d}",
        "try:\n    {d}\nexcept E:\n    pass",
        "try:\n    pass\nexcept E:\n    {d}",
        "try:\n    pass\nfinally:\n    {d}",
        "while X:\n    {d}",
        "for x in y:\n    {d}",
        "for x in y:\n    pass\nelse:\n    {d}",
        "with x:\n    {d}",
        "match x:\n    case 1:\n        {d}",
    ],
)
def test_a_single_conditional_definition_is_not_a_proof(wrapper: str) -> None:
    source = wrapper.format(d="def helper(): return 1")
    source += "\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "conditional", source
    decorated = wrapper.format(d="@deco\n    def helper(): return 1")
    if "case" not in wrapper:
        # A decorated single definition is not a proof either; its own
        # reason is reported first.
        assert reason(decorated + "\n\n\ndef use():\n    return helper()\n") == (
            "expression-bound"
        )


def test_conditional_imports() -> None:
    source = "if X:\n    from m import helper\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "conditional"
    local = "def use(flag):\n    if flag:\n        from m import helper\n    return helper()\n"
    assert reason(local) == "conditional"
    unconditional = "def use():\n    from m import helper\n    return helper()\n"
    assert outcome(unconditional, "helper")["outcome"] == "import"


def test_redefinitions_prove_the_group() -> None:
    source = (
        HELPER + "def helper():\n    return 2\n\n\ndef use():\n    return helper()\n"
    )
    assert len(proof_text(source)) == 2
    mixed = (
        HELPER
        + "if X:\n    def helper():\n        return 2\n\n\ndef use():\n    return helper()\n"
    )
    assert len(proof_text(mixed)) == 2
    kinds = HELPER + "class helper:\n    pass\n\n\ndef use():\n    return helper()\n"
    assert len(proof_text(kinds)) == 2


def test_definitions_mixed_with_imports_or_locals() -> None:
    source = "from m import helper\n\n\n" + HELPER + "def use():\n    return helper()\n"
    assert reason(source) == "mixed-bindings"
    two_imports = "from a import helper\nfrom b import helper\n\n\ndef use():\n    return helper()\n"
    assert reason(two_imports) == "mixed-bindings"


# ---------------------------------------------------------------------------
# Dynamic binding and star imports fail closed

DYNAMIC_FORMS = [
    "exec('helper = len')",
    "eval('0')",
    "globals()['helper'] = len",
    "vars()['helper'] = len",
    "locals()['helper'] = len",
    "g = globals",
    "__import__('builtins')",
    "__builtins__.helper = len",
    "import builtins\nbuiltins.helper = len",
    "import builtins as b\nb.x = 1",
    "from builtins import exec as run",
    "import importlib\nimportlib.import_module(__name__).helper = len",
    "from importlib import import_module",
    "import sys\nsys.modules[__name__].helper = len",
    "import sys\nsetattr(sys.modules[__name__], 'helper', len)",
    "import sys as s\ns.modules[__name__].helper = len",
    "from sys import modules\nmodules[__name__].helper = len",
    "from sys import modules as m",
    "import os\nos.sys.modules[__name__].helper = len",
    "import sys\ngetattr(sys, 'modules')[__name__].helper = len",
    "import sys\nm = sys",
    "import sys\nsys.__dict__['modules'][__name__].helper = len",
    "import inspect\ninspect.getmodule(len).helper = len",
    "def f():\n    pass\nf.__globals__['helper'] = len",
    "import sys\nsys._getframe().f_globals['helper'] = len",
    "exec 'helper = len'",
    "def g():\n    exec('helper = len')",
]


@pytest.mark.parametrize("form", DYNAMIC_FORMS)
def test_dynamic_binding_fails_closed_for_module_lookups(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "dynamic-scope", form


@pytest.mark.parametrize(
    "form",
    [
        "self.eval()",
        "model.exec()",
        "x.globals",
        "f(locals=1)",
        "import sys\nprint(sys.argv)",
        "import os\nos.path.join('a')",
        "class K:\n    def eval(self):\n        return 0",
    ],
)
def test_non_dynamic_lookalikes_still_resolve(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert proof_text(source) == PROOF, form


def test_dynamic_binding_leaves_function_scopes_alone() -> None:
    """``exec`` and ``locals()`` writes cannot rebind a function's locals."""
    source = "exec('x')\n\n\ndef f():\n    def helper():\n        return 1\n    return helper()\n"
    assert proof_text(source) == ["def helper():\n        return 1"]


def test_dynamic_binding_fails_closed_for_class_body_lookups() -> None:
    """A class body's namespace is a dict ``exec``/``locals()`` can write."""
    source = (
        "def f():\n    def helper():\n        return 1\n\n"
        "    class K:\n        exec('helper = len')\n        x = helper()\n    return K\n"
    )
    assert reason(source) == "dynamic-scope"


def test_star_import_fails_closed_for_module_lookups() -> None:
    source = "from m import *\n\n\n" + HELPER + "def use():\n    return helper()\n"
    assert reason(source) == "star-import"
    local = "from m import *\n\n\ndef f():\n    def helper():\n        return 1\n    return helper()\n"
    assert proof_text(local) == ["def helper():\n        return 1"]


# ---------------------------------------------------------------------------
# Identifiers are compared by source spelling: non-ASCII fails closed


@pytest.mark.parametrize(
    "source",
    [
        # U+FB01 LATIN SMALL LIGATURE FI is NFKC-equal to ``fi``: ``ﬁle`` is
        # ``file`` at run time.
        "def file():\n    return 1\n\n\nﬁle = len\n\n\ndef use():\n    return file()\n",
        "def helper():\n    return 1\n\n\ndef use(ｈelper):\n    return helper()\n",
        "def helper():\n    return 1\n\n\ndef use():\n    return f'{ｈelper}' + helper()\n",
        "def helper():\n    return 1\n\n\nobj.ｈelper = 1\n",
    ],
)
def test_non_ascii_identifiers_are_not_analyzed(source: str) -> None:
    data = source.encode()
    root = get_parser("python").parse(data).root_node
    assert not root.has_error
    assert py_scope.non_ascii_name(root, data) is not None
    with pytest.raises(py_scope.NonAsciiNameError):
        py_scope.analyze(root, data, "python", [])


def test_non_ascii_text_in_strings_and_comments_is_fine() -> None:
    source = (
        HELPER
        + "# ﬁle\nx = 'ﬁle'\ny = f'ﬁ{len(x)}é'\n\n\ndef use():\n    return helper()\n"
    )
    assert proof_text(source) == PROOF


# ---------------------------------------------------------------------------
# Member callees, fail-closed kinds and the allow-list


def test_member_callees_record_the_head_lookup() -> None:
    assert reason(HELPER + "def f(helper):\n    return helper.x()\n", "helper.x") == (
        "parameter"
    )
    assert proof_text(HELPER + "def f():\n    return helper.x()\n", "helper.x") == PROOF
    data = b"class C:\n    pass\n\n\nC().c()\n"
    root = get_parser("python").parse(data).root_node
    (node,) = _callees(root, data, "C().c")
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    result = py_scope.analyze(root, data, "python", [span])["bindings"]
    assert result == {
        f"{node.start_byte}:{node.end_byte}": {"outcome": "none", "reason": "unbound"}
    }


def test_a_callee_span_with_no_node_has_no_entry() -> None:
    data = HELPER.encode() + b"helper()\n"
    root = get_parser("python").parse(data).root_node
    facts = [{"callee_byte_start": 0, "callee_byte_end": 5}]
    assert py_scope.analyze(root, data, "python", facts)["bindings"] == {}


def test_a_fail_closed_kind_poisons_only_its_scopes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(allowlist.ALLOWLIST["python"], "assert_statement")
    source = (
        HELPER
        + "def g():\n    assert x\n    return helper()\n\n\ndef h():\n    return helper()\n"
    )
    assert reason(source, occurrence=0) == "unmapped"
    assert proof_text(source, occurrence=1) == PROOF
    # A fail-closed kind at module level poisons module-scope lookups.
    module = HELPER + "assert x\n\n\ndef h():\n    return helper()\n"
    assert reason(module) == "unmapped"


def test_a_call_under_an_unvisited_scope_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(allowlist.ALLOWLIST["python"], "return_statement")
    source = (
        HELPER + "class K:\n    def m(self):\n        return [helper() for x in y]\n"
    )
    assert reason(source) == "unmapped"


HANDLED_BY_PARENT = {
    # Opened as scopes by their parents, or the root of the pass.
    "module",
    # Bound by the definition, parameter list, import or target that
    # contains them; the pass only descends into them.
    "aliased_import",
    "as_pattern_target",
    "class_pattern",
    "default_parameter",
    "dict_pattern",
    "dictionary_splat_pattern",
    "for_in_clause",
    "keyword_pattern",
    "lambda_parameters",
    "list_pattern",
    "list_splat_pattern",
    "parameters",
    "pattern_list",
    "splat_pattern",
    "tuple_pattern",
    "type_parameter",
    "typed_default_parameter",
    "typed_parameter",
    "union_pattern",
    "with_item",
}


def test_every_handled_kind_has_a_handler() -> None:
    handled = {
        kind
        for kind, entry in allowlist.ALLOWLIST["python"].items()
        if entry.classification == allowlist.HANDLED
    }
    root = get_parser("python").parse(b"").root_node
    handlers = set(py_scope._Analysis(root, b"").handlers)
    assert handled - handlers - HANDLED_BY_PARENT == set()
    assert handled >= HANDLED_BY_PARENT


def test_plan_named_kinds_are_classified() -> None:
    for kind in (
        "function_definition",
        "class_definition",
        "lambda",
        "global_statement",
        "nonlocal_statement",
        "named_expression",
        "delete_statement",
        "wildcard_import",
        "type_alias_statement",
        "type_parameter",
        "case_pattern",
        "exec_statement",
    ):
        assert allowlist.classify("python", kind).classification == allowlist.HANDLED


# ---------------------------------------------------------------------------
# End to end, on trees the tests write (plan 11.2)


def _tree(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "tree"
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root


def _helper_edge(graph: dict[str, Any], reference: str = "helper") -> dict[str, Any]:
    (edge,) = (
        edge
        for edge in graph["relationships"]
        if edge["type"] == "calls"
        and edge["file"] == "a.py"
        and edge["reference"] == reference
    )
    return edge


def _off_on(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    return extract_symbol_graph(root), extract_symbol_graph(root, call_resolution=MODE)


OTHER = "def helper():\n    return 3\n"


def _assert_unchanged(tmp_path: Path, a_py: str) -> None:
    root = _tree(tmp_path, {"a.py": a_py, "b.py": OTHER})
    off, on = _off_on(root)
    edge = _helper_edge(off)
    assert edge["resolution"] == "ambiguous", "the case must start ambiguous"
    assert _helper_edge(on) == edge
    assert on["relationships"] == off["relationships"]


DECORATED = {
    "function": "@deco\ndef helper():\n    return 1\n\n\ndef use():\n    return helper()\n",
    "class": "@deco\nclass helper:\n    pass\n\n\ndef use():\n    return helper()\n",
    "nested": "def use():\n    @deco\n    def helper():\n        return 1\n    return helper()\n",
}


@pytest.mark.parametrize("case", sorted(DECORATED))
def test_decorated_definitions_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    source = DECORATED[case]
    if case == "nested":
        root = _tree(
            tmp_path,
            {
                "a.py": source,
                "b.py": "def other():\n    def helper():\n        return 2\n",
            },
        )
        off, on = _off_on(root)
        assert _helper_edge(off)["resolution"] == "ambiguous"
        assert on["relationships"] == off["relationships"]
        return
    _assert_unchanged(tmp_path, "def deco(f):\n    return f\n\n\n" + source)


def test_non_ascii_identifiers_make_the_file_unsupported(tmp_path: Path) -> None:
    """``ｈelper = len`` (a fullwidth ``h``) rebinds ``helper`` at run time,
    because Python normalizes identifiers to NFKC; the file is not analyzed
    and keeps exactly its off-mode edges."""
    a_py = "def helper():\n    return 1\n\n\nｈelper = len\n\n\ndef use():\n    return helper()\n"
    root = _tree(tmp_path, {"a.py": a_py, "b.py": OTHER})
    (facts,) = (
        item
        for item in (
            extract_symbol_facts_for_file(root / name, root, None, call_resolution=MODE)
            for name in ("a.py", "b.py")
        )
        if item["path"] == "a.py"
    )
    assert facts["scope_facts"]["supported"] is False
    assert facts["errors"] == []
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous"
    assert on["relationships"] == off["relationships"]
    # The same file spelled in ASCII resolves.
    ascii_root = _tree(
        tmp_path / "ascii",
        {"a.py": a_py.replace("ｈelper = len\n\n\n", ""), "b.py": OTHER},
    )
    assert _helper_edge(extract_symbol_graph(ascii_root, call_resolution=MODE))[
        "resolution"
    ] == ("resolved")


@pytest.mark.parametrize(
    "form",
    [
        "exec('helper = len')",
        "globals()['helper'] = len",
        "import builtins as b\nb.helper = len",
        "import sys as s\nsetattr(s.modules[__name__], 'helper', len)",
        "from importlib import import_module\nimport_module(__name__).helper = len",
        "from m import *",
    ],
)
def test_dynamic_binding_forms_keep_their_off_mode_edge(
    tmp_path: Path, form: str
) -> None:
    _assert_unchanged(
        tmp_path, HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    )


@pytest.mark.parametrize(
    "write",
    [
        "helper, x = 1, 2",
        "try:\n    pass\nexcept E as helper:\n    pass",
        "match v:\n    case [*helper]:\n        pass",
        "def patch():\n    global helper\n    del helper",
        "if X:\n    def helper():\n        return 2",
    ],
)
def test_write_forms_keep_their_off_mode_edge(tmp_path: Path, write: str) -> None:
    source = HELPER + write + "\n\n\ndef use():\n    return helper()\n"
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    edge = _helper_edge(off)
    assert edge["resolution"] == "ambiguous"
    on_edge = _helper_edge(on)
    # Only a redefinition group may narrow, and never to one candidate.
    assert on_edge["resolution"] == "ambiguous"
    assert set(on_edge["candidates"]) <= set(edge["candidates"])


POSITIVES = {
    "module": HELPER + "def use():\n    return helper()\n",
    "method": HELPER
    + "class K:\n    def helper(self):\n        return 2\n\n    def m(self):\n        return helper()\n",
    "class-free-name": HELPER + "class K:\n    x = helper()\n",
    "decorator-argument": HELPER
    + "def reg(x):\n    return lambda f: f\n\n\n@reg(helper())\ndef g():\n    return 0\n",
    "comprehension": HELPER + "def use(xs):\n    return [helper() for x in xs]\n",
    "lambda": HELPER + "def use():\n    return lambda: helper()\n",
}


@pytest.mark.parametrize("case", sorted(POSITIVES))
def test_python_positives_end_to_end(tmp_path: Path, case: str) -> None:
    root = _tree(tmp_path, {"a.py": POSITIVES[case], "b.py": OTHER})
    off, on = _off_on(root)
    off_edge = _helper_edge(off)
    assert off_edge["resolution"] == "ambiguous"
    on_edge = _helper_edge(on)
    assert on_edge["resolution"] == "resolved"
    assert on_edge["provenance"]["call_rules"] == ["t1.lexical"]
    (target,) = on_edge["candidates"]
    assert on["symbol_lookup"][target]["file"] == "a.py"
    assert on["symbol_lookup"][target]["line"] == 1
