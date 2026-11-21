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

import re
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


# A path whose own name no unit source spells: ``analyze`` without a path
# fails closed, so unit cases pass one.
NEUTRAL_PATH = "unit_case_module.py"


def outcome(source: str, callee: str, occurrence: int = 0) -> dict[str, Any]:
    """The analyzer's outcome for the ``occurrence``-th call of ``callee``."""
    data = source.encode()
    root = get_parser("python").parse(data).root_node
    assert not root.has_error, source
    node = _callees(root, data, callee)[occurrence]
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    bindings = py_scope.analyze(root, data, "python", [span], path=NEUTRAL_PATH)
    return bindings["bindings"][f"{node.start_byte}:{node.end_byte}"]


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
    "execfile('x.py')",
    "import sys\nsys._getframe().f_locals['x'] = 1",
    "import sys\nsys._getframe().f_builtins['helper'] = len",
    # The #695 panel fold: ``__main__``, literal attribute names, any
    # receiver's ``modules[__name__]``.
    "import __main__\n__main__.helper = len",
    "import __main__ as m\nsetattr(m, 'helper', len)",
    "getattr(f, '__globals__')['helper'] = len",
    "getattr(frame, 'f_globals')['helper'] = len",
    "operator.attrgetter('sys.modules')(os)[__name__].helper = len",
    "getattr(f, '__glo' + 'bals__')['helper'] = len",
    "getattr(f, '__glo' 'bals__')['helper'] = len",
    "getattr(f, r'__globals__')['helper'] = len",
    "getattr(f, f'__globals__')['helper'] = len",
    'getattr(f, """__globals__""")["helper"] = len',
    "x = 'modules'",
    "collections._sys.modules[__name__].helper = len",
    "pkg.sys_alias.modules.get(__name__).helper = len",
    "x.modules.__getitem__(__name__).helper = len",
    "x.modules.setdefault(__name__).helper = len",
    # B-5: parentheses are only a spelling of the ruled shape.
    "collections._sys.modules[(__name__)].helper = len",
    "collections._sys.modules[((__name__))].helper = len",
    "x.modules.get((__name__)).helper = len",
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


LOCAL_HELPER = "def f():\n    def helper():\n        return 1\n    return helper()\n"


def test_exec_and_locals_leave_function_scopes_alone() -> None:
    """``exec`` and ``locals()`` cannot rebind a function's locals; only
    ``frame.f_locals`` can (below)."""
    for form in ("exec('x')", "locals()['helper'] = len", "globals()['x'] = 1"):
        source = form + "\n\n\n" + LOCAL_HELPER
        assert proof_text(source) == ["def helper():\n        return 1"], form


@pytest.mark.parametrize(
    "form",
    [
        "import sys\nsys._getframe().f_locals['helper'] = len",
        "import inspect\ninspect.currentframe().f_locals['helper'] = len",
        "getattr(frame, 'f_locals')['helper'] = len",
        "attrgetter('f_back.f_locals')",
        "x = 'f_' 'locals'",
        "x = 'f_' + 'locals'",
    ],
)
def test_f_locals_fails_closed_for_every_lookup(form: str) -> None:
    """A frame's ``f_locals`` writes through to a function's locals (PEP 667,
    Python 3.13+), so every lookup of the file fails closed."""
    source = form + "\n\n\n" + LOCAL_HELPER
    assert reason(source) == "dynamic-scope", form
    in_function = "def f():\n    def helper():\n        return 1\n    " + (
        form.replace("\n", "\n    ") + "\n    return helper()\n"
    )
    assert reason(in_function) == "dynamic-scope", form


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
    result = py_scope.analyze(root, data, "python", [span], path=NEUTRAL_PATH)[
        "bindings"
    ]
    assert result == {
        f"{node.start_byte}:{node.end_byte}": {"outcome": "none", "reason": "unbound"}
    }


def test_a_callee_span_with_no_node_has_no_entry() -> None:
    data = HELPER.encode() + b"helper()\n"
    root = get_parser("python").parse(data).root_node
    facts = [{"callee_byte_start": 0, "callee_byte_end": 5}]
    assert (
        py_scope.analyze(root, data, "python", facts, path=NEUTRAL_PATH)["bindings"]
        == {}
    )


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


# ---------------------------------------------------------------------------
# The #695 panel fold: every fix only adds ``none``


def test_classes_with_bases_or_keywords_open_their_namespace() -> None:
    """A metaclass's ``__prepare__`` (possibly inherited from a base in
    another file) or a ``__missing__`` namespace may supply any name."""
    for header in ("class K(Base):", "class K(metaclass=M):", "class K(object, x=1):"):
        for code in (
            "x = helper()",
            "def m(self, x=helper()):\n        return x",
            "@helper()\n    def m(self):\n        return 0",
            "xs = [y for y in helper()]",
        ):
            source = HELPER + f"{header}\n    {code}\n"
            assert reason(source) == "class-scope-bound", (header, code)
    # Without bases the class namespace is a plain dict.
    assert proof_text(HELPER + "class K():\n    x = helper()\n") == PROOF
    # Methods still skip the class, and the bases run outside it.
    method = HELPER + "class K(Base):\n    def m(self):\n        return helper()\n"
    assert proof_text(method) == PROOF
    assert proof_text(HELPER + "class K(helper()):\n    pass\n") == PROOF


def test_module_level_builtin_names_never_prove() -> None:
    """Until a module-level ``def len`` runs, ``len`` is the builtin."""
    source = (
        "def use():\n    return len('ab')\n\n\nuse()\n\n\ndef len(*a):\n    return 1\n"
    )
    assert reason(source, "len") == "builtin-shadow"
    imported = "from m import open\n\n\ndef use():\n    return open('f')\n"
    assert reason(imported, "open") == "builtin-shadow"
    py2 = "def xrange(n):\n    return n\n\n\ndef use():\n    return xrange(3)\n"
    assert reason(py2, "xrange") == "builtin-shadow"
    # B-6: a builtin only Windows has.
    windows = "def f():\n    return WindowsError(1)\n\n\nclass WindowsError(Exception):\n    pass\n"
    assert reason(windows, "WindowsError") == "builtin-shadow"
    # A function-local definition shadows the builtin for the whole body.
    local = "def use():\n    def len(*a):\n        return 1\n    return len('ab')\n"
    assert proof_text(local, "len") == ["def len(*a):\n        return 1"]


def test_builtin_pin_matches_the_interpreter() -> None:
    """``BUILTINS_314`` is ``dir(builtins)`` of CPython 3.14 (``python -I``)
    less the platform builtins (``WindowsError`` on Windows, B-6), so the
    pin holds on every OS; a new interpreter that adds a builtin must update
    it. ``BUILTINS`` is a superset of the running interpreter's builtins."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-I", "-c", "import builtins; print(*sorted(dir(builtins)))"],
        capture_output=True,
        text=True,
        check=True,
    )
    running = frozenset(result.stdout.split())
    assert running <= py_scope.BUILTINS
    assert running - py_scope.PLATFORM_BUILTINS == py_scope.BUILTINS_314
    assert "WindowsError" in py_scope.PLATFORM_BUILTINS
    assert not py_scope.PY2_BUILTINS & py_scope.BUILTINS_314
    assert not py_scope.PLATFORM_BUILTINS & py_scope.BUILTINS_314
    assert {"xrange", "unicode", "raw_input", "execfile"} <= py_scope.PY2_BUILTINS


@pytest.mark.parametrize(
    ("source", "line"),
    [
        ("def f():\n       \tpass\n", 2),
        ("if x:\n    pass\n \t\tpass\n", 3),
        ("x = 1\n\f\ny = 2\n", 2),
        ("def f():\n  \f  pass\n", 2),
    ],
)
def test_tab_width_dependent_indentation_is_not_analyzed(
    source: str, line: int
) -> None:
    data = source.encode()
    assert py_scope.ambiguous_indentation(data) == line
    root = get_parser("python").parse(data).root_node
    with pytest.raises(py_scope.AmbiguousIndentationError):
        py_scope.analyze(root, data, "python", [])


def test_tabs_alone_are_unambiguous() -> None:
    for source in (
        "def f():\n\treturn 1\n",
        "def f():\n\t    return 1\n",
        "x = 'a \t b'\n",
    ):
        assert py_scope.ambiguous_indentation(source.encode()) is None, source


@pytest.mark.parametrize(
    ("path", "names"),
    [
        ("a.py", {"a"}),
        ("pkg/a.py", {"a"}),
        ("pkg/__init__.py", {"pkg"}),
        ("__init__.py", set()),
        ("pkg\\sub\\mod.py", {"mod"}),
        ("my-script.py", {"my-script"}),
        ("pkg/my-pkg/__init__.py", {"my-pkg"}),
        ("a.b.py", {"a.b", "a", "b"}),
    ],
)
def test_own_module_names(path: str, names: set[str]) -> None:
    assert py_scope.own_module_names(path) == names


@pytest.mark.parametrize(
    "form",
    [
        "import a\na.helper = len",
        "import pkg.a\npkg.a.helper = len",
        "import a as me\nsetattr(me, 'helper', len)",
        "from . import a",
        "from pkg import a as me",
    ],
)
def test_self_imports_fail_closed(form: str) -> None:
    data = (HELPER + form + "\n\n\ndef use():\n    return helper()\n").encode()
    root = get_parser("python").parse(data).root_node
    (node,) = _callees(root, data, "helper")
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    key = f"{node.start_byte}:{node.end_byte}"
    own = py_scope.analyze(root, data, "python", [span], path="a.py")
    assert own["bindings"][key] == {"outcome": "none", "reason": "dynamic-scope"}
    other = py_scope.analyze(root, data, "python", [span], path="b.py")
    assert other["bindings"][key]["outcome"] in ("local", "none")


@pytest.mark.parametrize(
    "form",
    [
        "self.modules.append(1)",
        "x = self.modules[0]",
        "x = 'modules list'",
        "x = f'{y}modules'",
        "x = 'f_locals_count'",
        "import __main__ as m",
        "from __main__ import x",
    ],
)
def test_more_non_dynamic_lookalikes_still_resolve(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert proof_text(source) == PROOF, form


def test_natural_unmapped_forms_poison_their_scope() -> None:
    """Valid code the target reader does not understand fails closed."""
    for form in ("del f()", "with a as f():\n    pass", "type(x).attr = v"):
        source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
        assert reason(source) == "unmapped", form
    local = "def use():\n    def helper():\n        return 1\n    del f()\n    return helper()\n"
    assert reason(local) == "unmapped"


def test_a_line_continuation_in_a_target_is_only_a_token() -> None:
    source = HELPER + "x, \\\n    y = 1, 2\n\n\ndef use():\n    return helper()\n"
    assert proof_text(source) == PROOF
    bound = HELPER + "x, \\\n    helper = 1, 2\n\n\ndef use():\n    return helper()\n"
    assert reason(bound) == "mixed-bindings"


def _decoys(a_py: str) -> str:
    names = sorted(
        set(re.findall(r"([A-Za-z_]\w*)\s*\(", a_py))
        - {
            "print",
            "def",
            "class",
            "if",
            "while",
            "return",
            "lambda",
            "not",
            "and",
            "or",
            "in",
        }
    )
    return "".join(f"def {name}(*a, **k):\n    return 'decoy'\n\n" for name in names)


H695 = "def helper(*a):\n    return 'mod'\n\n"
U695 = "\ndef use():\n    return helper('ab')\n\nuse()\n"
L695 = "import sys\ndef use():\n    def helper(*a):\n        return 'l'\n"
OTHER_LOCAL = (
    "def other():\n    def helper(*a):\n        return 'decoy'\n    return helper\n"
)
PANEL_695 = {
    "class_kw_metaclass_prepare": {
        "a.py": H695
        + "class M(type):\n    @classmethod\n    def __prepare__(m, name, bases):\n"
        "        return {'helper': len}\n\nclass C(metaclass=M):\n    x = helper('ab')\n"
    },
    "class_base_prepare_crossfile": {
        "a.py": H695 + "from m import Base\n\nclass C(Base):\n    x = helper('ab')\n",
        "m.py": "class M(type):\n    @classmethod\n    def __prepare__(m, name, bases):\n"
        "        return {'helper': len}\n\nclass Base(metaclass=M):\n    pass\n",
    },
    "flocals_proxy_write": {
        "a.py": L695
        + "    sys._getframe().f_locals['helper'] = len\n    return helper('ab')\nuse()\n",
        "b.py": OTHER_LOCAL,
    },
    "getattr_literal_flocals_func": {
        "a.py": L695 + "    getattr(sys._getframe(), 'f_locals')['helper'] = len\n"
        "    return helper('ab')\nuse()\n",
        "b.py": OTHER_LOCAL,
    },
    "builtin_shadow_func_early": {
        "a.py": "def use():\n    return len('ab')\n\nuse()\n\ndef len(*a):\n    return 'mine'\n"
    },
    "builtin_shadow_default": {
        "a.py": "def use(x=len('ab')):\n    return x\n\ndef len(*a):\n    return 'mine'\n"
    },
    "import_main": {"a.py": H695 + "import __main__\n__main__.helper = len\n" + U695},
    "self_import_by_name": {
        "a.py": H695 + "import a\na.helper = len\n" + U695,
        "main.py": "import a\n",
    },
    "operator_attrgetter_sys": {
        "a.py": H695
        + "import operator, os\nm = operator.attrgetter('sys.modules')(os)\n"
        "m[__name__].helper = len\n" + U695
    },
    "types_function_globals": {
        "a.py": H695 + "def use2():\n    pass\ng = getattr(use2, '__glo' + 'bals__')\n"
        "g['helper'] = len\n" + U695
    },
    "getattr_literal_globals": {
        "a.py": H695
        + "def use2():\n    pass\ngetattr(use2, '__globals__')['helper'] = len\n"
        + U695
    },
    "tab_width_dedent": {
        "a.py": "def outer():\n        def helper(*a):\n            return 'A'\n"
        "        class C:\n               x = 1\n       \tdef helper(*a):\n"
        "                return 'B'\n        return helper('ab')\nouter()\n",
        "b.py": OTHER_LOCAL,
    },
    "sys_through_another_module": {
        "a.py": H695 + "import collections\n"
        "collections._sys.modules[__name__].helper = len\n" + U695
    },
}


@pytest.mark.parametrize("case", sorted(PANEL_695))
def test_panel_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    """Each tree resolved wrongly at 9cff92b9 under a runtime trace (#695
    panel A, B and Codex 4653329444); every edge now stays as off."""
    files = dict(PANEL_695[case])
    files.setdefault("b.py", _decoys(files["a.py"]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == "a.py"]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == "a.py"] == off_calls


NATURAL_UNMAPPED = {
    "del-call": "del f()",
    "with-call-target": "with x as f():\n    pass",
    "type-attribute": "type(x).attr = v",
}


@pytest.mark.parametrize("case", sorted(NATURAL_UNMAPPED))
def test_natural_unmapped_forms_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    source = HELPER + NATURAL_UNMAPPED[case] + "\n\n\ndef use():\n    return helper()\n"
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous"
    assert _helper_edge(on) == _helper_edge(off)
    (facts,) = (
        item
        for item in (
            extract_symbol_facts_for_file(
                root / "a.py", root, None, call_resolution=MODE
            ),
        )
    )
    edge = _helper_edge(off)
    key = f"{edge['callee_byte_start']}:{edge['callee_byte_end']}"
    assert facts["scope_facts"]["bindings"][key] == {
        "outcome": "none",
        "reason": "unmapped",
    }


def test_line_continuation_target_end_to_end(tmp_path: Path) -> None:
    source = HELPER + "x, \\\n    y = 1, 2\n\n\ndef use():\n    return helper()\n"
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    on = extract_symbol_graph(root, call_resolution=MODE)
    assert _helper_edge(on)["resolution"] == "resolved"


def test_builtin_shadow_end_to_end(tmp_path: Path) -> None:
    source = "def use():\n    return len('ab')\n\n\ndef len(*args):\n    return 1\n"
    root = _tree(tmp_path, {"a.py": source, "b.py": "def len(*args):\n    return 2\n"})
    off, on = _off_on(root)
    edge = _helper_edge(off, "len")
    assert edge["resolution"] == "ambiguous"
    assert _helper_edge(on, "len") == edge
    facts = extract_symbol_facts_for_file(
        root / "a.py", root, None, call_resolution=MODE
    )
    key = f"{edge['callee_byte_start']}:{edge['callee_byte_end']}"
    assert facts["scope_facts"]["bindings"][key]["reason"] == "builtin-shadow"


# ---------------------------------------------------------------------------
# The president's #695 ruling (B-1 to B-6): every fix only adds ``none``.
# The trees are the ruling's own, each wrong under a runtime trace at
# a58f502e; ``__target__`` names the file whose edges are checked.

RULING_695: dict[str, tuple[str, dict[str, str]]] = {
    "bs_moves_def_into_sibling": (
        "B-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def f():\n"
            "    def g():\n"
            "        pass\n"
            "    \\\n"
            "    def helper(*a):\n"
            "        return 'inner'\n"
            "    return helper()\n"
            "\n"
            "f()\n"
        },
    ),
    "bs_moves_def_into_sibling_1sp": (
        "B-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def f():\n"
            " def g():\n"
            "  pass\n"
            " \\\n"
            " def helper(*a):\n"
            "  return 'inner'\n"
            " return helper()\n"
            "\n"
            "f()\n"
        },
    ),
    "init_abs_submodule": (
        "B-3",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "import pkg.helper\n",
            "pkg/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "init_pyi_dir_named": (
        "B-4",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "def patch():\n"
            "    import pkg.x\n"
            "    pkg.helper = len\n",
            "pkg/x.py": "",
        },
    ),
    "init_rel_plain": (
        "B-3",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "from .helper import x\n",
            "pkg/helper.py": "x = 1\n",
        },
    ),
    "init_rel_submodule": (
        "B-3",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "from .helper import M\n",
            "pkg/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "mangle_classbody": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mangled'\n"
            "\n"
            "def __helper(*a):\n"
            "    return 'plain'\n"
            "\n"
            "class C:\n"
            "    x = __helper()\n"
        },
    ),
    "mangle_classbody_global_write": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return _C__helper('ab')\n"
            "\n"
            "class C:\n"
            "    global __helper\n"
            "    __helper = len\n"
            "\n"
            "use()\n"
        },
    ),
    "mangle_global": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mangled'\n"
            "\n"
            "def __helper(*a):\n"
            "    return 'plain'\n"
            "\n"
            "class C:\n"
            "    def m(self):\n"
            "        return __helper()\n"
            "\n"
            "C().m()\n"
        },
    ),
    "mangle_global_write": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return _C__helper()\n"
            "\n"
            "class C:\n"
            "    def m(self):\n"
            "        global __helper\n"
            "        __helper = len\n"
            "\n"
            "C().m()\n"
            "use()\n"
        },
    ),
    "mangle_import_in_class": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return _C__helper('ab')\n"
            "\n"
            "class C:\n"
            "    def m(self):\n"
            "        global __helper\n"
            "        from builtins import len as __helper\n"
            "\n"
            "C().m()\n"
            "use()\n"
        },
    ),
    "mangle_lambda_in_class": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mangled'\n"
            "\n"
            "def __helper(*a):\n"
            "    return 'plain'\n"
            "\n"
            "class C:\n"
            "    f = staticmethod(lambda: __helper())\n"
            "\n"
            "C.f()\n"
        },
    ),
    "mangle_leading_us_class": (
        "B-1",
        {
            "a.py": "def _C__helper(*a):\n"
            "    return 'mangled'\n"
            "\n"
            "def __helper(*a):\n"
            "    return 'plain'\n"
            "\n"
            "class __C:\n"
            "    def m(self):\n"
            "        return __helper()\n"
            "\n"
            "__C().m()\n"
        },
    ),
    "modules_paren_name": (
        "B-5",
        {
            "a.py": "import collections\n"
            "import types\n"
            "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "collections._sys.modules[(__name__)].helper = len\n"
            "use()\n"
        },
    ),
    "root_init_self_import": (
        "B-4",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import root_init_self_import as me\n"
            "    me.helper = len\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "sub_parent_attr_in_func": (
        "B-4",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    pkg.a.helper = len\n",
        },
    ),
    "sub_parent_getattr_in_func": (
        "B-4",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    setattr(pkg.a, 'helper', len)\n",
        },
    ),
}


@pytest.mark.parametrize("case", sorted(RULING_695))
def test_ruling_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = RULING_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


def test_private_names_inside_a_class_never_prove() -> None:
    """B-1: CPython looks up ``_C__x`` for ``__x`` inside class ``C``."""
    plain = "def __helper():\n    return 1\n\n\n"
    for code in (
        "class C:\n    def m(self):\n        return __helper()\n",
        "class C:\n    x = __helper()\n",
        "class __C:\n    x = __helper()\n",
        "class C:\n    f = lambda: __helper()\n",
        "class C:\n    xs = [__helper() for y in z]\n",
        "class C:\n    class D:\n        x = __helper()\n",
    ):
        assert reason(plain + code, "__helper") == "unmapped", code
    # Outside a class, under an all-underscore class, and for dunder names
    # nothing is mangled.
    assert proof_text(plain + "def use():\n    return __helper()\n", "__helper") == [
        "def __helper():\n    return 1"
    ]
    assert proof_text(plain + "class _:\n    x = __helper()\n", "__helper") == [
        "def __helper():\n    return 1"
    ]
    dunder = "def __helper__():\n    return 1\n\n\nclass C:\n    x = __helper__()\n"
    assert reason(dunder, "__helper__") == "class-scope-bound"


@pytest.mark.parametrize(
    "write",
    [
        "    def m(self):\n        global __helper\n        __helper = len",
        "    global __helper\n    __helper = len",
        "    def m(self):\n        global __helper\n        from x import y as __helper",
        "    def m(self):\n        global __helper\n        def __helper():\n            return 2",
    ],
)
def test_private_name_global_writes_bind_the_mangled_name(write: str) -> None:
    """B-1: ``global __x`` inside class ``C`` writes the module's ``_C__x``."""
    source = (
        "def _C__helper():\n    return 1\n\n\ndef use():\n    return _C__helper()\n\n\n"
        f"class C:\n{write}\n"
    )
    assert reason(source, "_C__helper") == "mixed-bindings", write


def test_private_name_local_bindings_also_bind_the_mangled_name() -> None:
    """``__x = …`` in a method binds ``_C__x``, which ``_C__x`` reaches."""
    source = (
        "def _C__helper():\n    return 1\n\n\n"
        "class C:\n    def m(self):\n        __helper = len\n        return _C__helper()\n"
    )
    assert reason(source, "_C__helper") == "local-variable"
    nonlocal_write = (
        "def f():\n    def _C__h():\n        return 1\n\n"
        "    class C:\n        def m(self):\n            nonlocal __h\n            __h = len\n"
        "    return _C__h()\n"
    )
    assert reason(nonlocal_write, "_C__h") == "mixed-bindings"


def test_backslash_led_lines_are_not_analyzed() -> None:
    """B-2: CPython takes a continued logical line's indentation from its
    first physical line; tree-sitter adds the next line's."""
    for source in (
        "def f():\n    \\\n    pass\n",
        "x = 1\n\\\ny = 2\n",
        "if x:\n \\\n pass\n",
    ):
        assert py_scope.ambiguous_indentation(source.encode()) is not None, source
    assert py_scope.ambiguous_indentation(b"x = 1 + \\\n    2\n") is None


def _ts_nesting(parser: Any, source: str) -> Any:
    tree = parser.parse(source.encode())
    if tree.root_node.has_error:
        return None
    found: list[tuple[str, tuple[str, ...]]] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        for child in node.named_children:
            if child.type in ("function_definition", "class_definition"):
                name = child.child_by_field_name("name").text.decode()
                found.append((name, path))
                walk(child, (*path, name))
            else:
                walk(child, path)

    walk(tree.root_node, ())
    return sorted(found)


def _py_nesting(source: str) -> Any:
    import ast

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    found: list[tuple[str, tuple[str, ...]]] = []

    def walk(node: Any, path: tuple[str, ...]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                found.append((child.name, path))
                walk(child, (*path, child.name))
            else:
                walk(child, path)

    walk(tree, ())
    return sorted(found)


def test_whitespace_differential_has_no_silent_misparse() -> None:
    """The president's generator (B-2): 50,625 nested-``def`` sources built
    from whitespace pieces. Every source where tree-sitter's ``def`` nesting
    differs from CPython's ``ast`` without a parse error on either side must
    be caught by :func:`py_scope.ambiguous_indentation` (73 got past the
    tab rule alone)."""
    import itertools

    parser = get_parser("python")
    pieces = [
        "", " ", "  ", "    ", "\t", " \t", "\t ", "\\\n", " \\\n ", "\f",
        "#c\n", "\r\n", "\x0c ", "\\\n    ", "    \\\n",
    ]  # fmt: skip
    template = "def f():\n{0}def g():\n{1}pass\n{2}def h():\n{3}  pass\n"
    total = mismatched = missed = 0
    for parts in itertools.product(pieces, repeat=4):
        source = template.format(*parts)
        total += 1
        ours, cpython = _ts_nesting(parser, source), _py_nesting(source)
        if ours is None or cpython is None or ours == cpython:
            continue
        mismatched += 1
        if py_scope.ambiguous_indentation(source.encode()) is None:
            missed += 1
    assert total == 50625
    assert mismatched > 0
    assert missed == 0


@pytest.mark.parametrize(
    ("path", "init", "root_init", "components"),
    [
        ("a.py", False, False, ("a",)),
        ("pkg/a.py", False, False, ("pkg", "a")),
        ("pkg/__init__.py", True, False, ("pkg",)),
        ("top/pkg/__init__.py", True, False, ("top", "pkg")),
        ("__init__.py", True, True, ()),
    ],
)
def test_module_path(
    path: str, init: bool, root_init: bool, components: tuple[str, ...]
) -> None:
    info = py_scope.module_path(path)
    assert (info.package_init, info.root_init, info.components) == (
        init,
        root_init,
        components,
    )


def _outcome_at(source: str, callee: str, path: str) -> dict[str, Any]:
    data = source.encode()
    root = get_parser("python").parse(data).root_node
    (node,) = _callees(root, data, callee)
    span = {"callee_byte_start": node.start_byte, "callee_byte_end": node.end_byte}
    bindings = py_scope.analyze(root, data, "python", [span], path=path)["bindings"]
    return bindings[f"{node.start_byte}:{node.end_byte}"]


@pytest.mark.parametrize(
    "form",
    [
        "from .helper import M",
        "from .helper.sub import M",
        "from . import helper",
        "import pkg.helper",
        "import pkg.helper.sub as s",
        "from pkg.helper import M",
        "from pkg import helper",
        "def patch():\n    from .helper import M",
    ],
)
def test_submodule_imports_in_a_package_init_rebind(form: str) -> None:
    """B-3: importing submodule ``pkg.X`` sets ``pkg/__init__.py``'s ``X``."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/__init__.py")["outcome"] == "none"
    # The same imports in a plain module rebind nothing of its own.
    plain = HELPER + "from .other import M\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(plain, "helper", "pkg/a.py")["outcome"] == "local"


@pytest.mark.parametrize(
    ("path", "form"),
    [
        ("pkg/__init__.py", "def patch():\n    import pkg.x\n    pkg.helper = len"),
        ("pkg/a.py", "def patch():\n    import pkg\n    pkg.a.helper = len"),
        ("pkg/a.py", "def patch():\n    import pkg\n    setattr(pkg.a, 'helper', len)"),
        (
            "pkg/a.py",
            "def patch():\n    import pkg\n    getattr(pkg, 'a').helper = len",
        ),
        ("__init__.py", "def patch():\n    import anything as me\n    me.helper = len"),
        ("__init__.py", "from anything import x"),
    ],
)
def test_more_self_import_shapes_fail_closed(path: str, form: str) -> None:
    """B-4: the file's own module reached by ``import pkg.x`` in its
    ``__init__.py``, through its parent package, or from a root-level
    ``__init__.py`` whose name is unknown (any absolute import)."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path) == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }


def test_root_init_with_relative_imports_only_still_resolves() -> None:
    source = HELPER + "from .x import y\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "__init__.py")["outcome"] == "local"


# ---------------------------------------------------------------------------
# The president's re-check at 5efc7eec (N-1 to N-3): one general rule for
# self-reference and submodule rebinding replaces the per-shape fixes.

RECHECK_695: dict[str, tuple[str, dict[str, str]]] = {
    "init_nested_abs_from": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "from pkg.sub.helper import M\n",
            "pkg/sub/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = "
            "M\n",
        },
    ),
    "init_nested_abs_import": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "import pkg.sub.helper\n",
            "pkg/sub/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = "
            "M\n",
        },
    ),
    "init_nested_rel2": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "from ..sub.helper import M\n",
            "pkg/sub/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "init_nested_rel2_name": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "from ..sub import helper\n"
            "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper()\n"
            "\n"
            "del helper\n"
            "from ..sub import helper\n",
            "pkg/sub/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = "
            "M\n",
        },
    ),
    "nested_init_rel2_self": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from .. import sub as me\n"
            "    me.helper = len\n",
        },
    ),
    "nested_init_self_attr": (
        "N-1",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg.sub.x\n"
            "    pkg.sub.helper = len\n",
            "pkg/sub/x.py": "",
        },
    ),
    "ns_root_init_depth1_attr": (
        "N-2",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import "
            "ns_root_init_depth1_attr\n"
            "    "
            "ns_root_init_depth1_attr.pkg.helper "
            "= len\n",
        },
    ),
    "ns_root_parent_attr": (
        "N-2",
        {
            "__target__": "a.py",
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import ns_root_parent_attr\n"
            "    ns_root_parent_attr.a.helper = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "ns_sub_parent_attr": (
        "N-2",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    pkg.a.helper = len\n",
        },
    ),
    "root_pkg_sub_from_import": (
        "N-2",
        {
            "__init__.py": "",
            "__target__": "a.py",
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from root_pkg_sub_from_import import a as "
            "me\n"
            "    me.helper = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
        },
    ),
    "root_pkg_sub_parent_attr": (
        "N-2",
        {
            "__init__.py": "",
            "__target__": "a.py",
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import root_pkg_sub_parent_attr\n"
            "    root_pkg_sub_parent_attr.a.helper = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
        },
    ),
    "root_pkg_sub_parent_setattr": (
        "N-2",
        {
            "__init__.py": "",
            "__target__": "a.py",
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import root_pkg_sub_parent_setattr\n"
            "    setattr(root_pkg_sub_parent_setattr.a, "
            "'helper', len)\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
        },
    ),
    "sub_from_parent_as": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from pkg import a as y\n"
            "    y.helper = len\n",
        },
    ),
    "sub_parent_dict": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    pkg.__dict__['a'].helper = len\n",
        },
    ),
    "sub_parent_getattr_kw_str_var": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "NAME = 'a'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    getattr(pkg, NAME).helper = "
            "len\n",
        },
    ),
    "sub_parent_getattr_static": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg, inspect\n"
            "    inspect.getattr_static(pkg, "
            "'a').helper = len\n",
        },
    ),
    "sub_parent_getattr_var": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    g = getattr\n"
            "    g(pkg, 'a').helper = len\n",
        },
    ),
    "sub_parent_getattribute": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    pkg.__getattribute__('a').helper = "
            "len\n",
        },
    ),
    "sub_parent_obj_getattribute": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg, types\n"
            "    "
            "types.ModuleType.__getattribute__(pkg, "
            "'a').helper = len\n",
        },
    ),
    "sub_parent_vars": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    vars(pkg)['a'].helper = len\n",
        },
    ),
    "sub_rel_parent_as": (
        "N-3",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def load():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from . import a as y\n"
            "    y.helper = len\n",
        },
    ),
}


@pytest.mark.parametrize("case", sorted(RECHECK_695))
def test_recheck_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = RECHECK_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    ("path", "form"),
    [
        # N-1: submodule imports at any depth, absolute or relative.
        ("pkg/sub/__init__.py", "import pkg.sub.helper"),
        ("pkg/sub/__init__.py", "from pkg.sub.helper import M"),
        ("pkg/sub/__init__.py", "from ..sub.helper import M"),
        ("pkg/sub/__init__.py", "from ..sub import helper"),
        ("pkg/sub/__init__.py", "def f():\n    from ..sub.helper import M"),
        ("a/b/c/__init__.py", "from ...b.c.helper import M"),
        ("a/b/c/__init__.py", "import outer.a.b.c.helper"),
        ("a/b/c/__init__.py", "from . import helper"),
        ("__init__.py", "from .helper import M"),
    ],
)
def test_submodule_imports_rebind_at_any_depth(path: str, form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path)["outcome"] == "none", (path, form)


@pytest.mark.parametrize(
    ("path", "form"),
    [
        # N-2: the run root may itself be a package (regular or namespace).
        ("a.py", "def patch():\n    import R\n    R.a.helper = len"),
        ("a.py", "def patch():\n    import R\n    setattr(R.a, 'helper', len)"),
        ("pkg/__init__.py", "def patch():\n    import R\n    R.pkg.helper = len"),
        # N-3: any constant string naming the module, anywhere.
        (
            "pkg/a.py",
            "def patch():\n    import pkg\n    pkg.__dict__['a'].helper = len",
        ),
        ("pkg/a.py", "def patch():\n    pkg.__getattribute__('a').helper = len"),
        ("pkg/a.py", "def patch():\n    inspect.getattr_static(pkg, 'a').x = 1"),
        ("pkg/a.py", "def patch():\n    g = getattr\n    g(pkg, 'a').helper = len"),
        ("pkg/a.py", "NAME = 'a'"),
        ("pkg/a.py", "x = 'pkg.a'"),
        ("a.py", "x = 'R.a.helper'"),
        # Any import that may name the module or a path through it.
        ("pkg/a.py", "from pkg.a import helper as h"),
        ("pkg/sub/__init__.py", "from .. import sub as me"),
        ("pkg/sub/__init__.py", "import pkg.sub.x\npkg.sub.helper = len"),
    ],
)
def test_any_possible_self_reference_fails_closed(path: str, form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path) == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, (path, form)


def test_unrelated_imports_and_strings_still_resolve() -> None:
    source = (
        HELPER + "import os\nfrom .other import thing\nx = 'b'\nos.path.join('x')\n"
        "\n\ndef use():\n    return helper()\n"
    )
    assert _outcome_at(source, "helper", "pkg/a.py")["outcome"] == "local"
    # Function-local lookups are unaffected by the module-scope rule.
    local = "NAME = 'a'\n\n\ndef use():\n    def helper():\n        return 1\n    return helper()\n"
    assert _outcome_at(local, "helper", "pkg/a.py")["outcome"] == "local"


# ---------------------------------------------------------------------------
# The president's re-check at f7f0b0bd (N-4 to N-6) and the R-5 family: names
# matched whatever node spells them, raw own names, ``..`` from a root
# ``__init__.py``, and attribute writes through any receiver.

FOLD4_695: dict[str, tuple[str, dict[str, str]]] = {
    "custom_loader_name": (
        "R-5",
        {
            "__target__": "a.py",
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import zzz\n"
            "    zzz.helper = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
        },
    ),
    "kw_param_dict_unpack": (
        "R-5",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    def g(a=None, **k):\n"
            "        a.helper = len\n"
            "    g(**pkg.__dict__)\n",
        },
    ),
    "match_kw_frame_globals": (
        "N-4",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "import inspect\n"
            "def patch():\n"
            "    match inspect.currentframe():\n"
            "        case object(f_globals=g):\n"
            "            g['helper'] = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "match_kw_globals": (
        "N-4",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    match use:\n"
            "        case object(__globals__=g):\n"
            "            g['helper'] = len\n",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "match_kw_init_self": (
        "N-4",
        {
            "__target__": "pkg/sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    match pkg:\n"
            "        case object(sub=m):\n"
            "            m.helper = len\n",
        },
    ),
    "match_kw_pattern": (
        "N-4",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    match pkg:\n"
            "        case object(a=m):\n"
            "            m.helper = len\n",
        },
    ),
    "match_kw_pattern_ns": (
        "N-4",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    match pkg:\n"
            "        case object(a=m):\n"
            "            m.helper = len\n",
        },
    ),
    "modules_spec_name": (
        "R-5",
        {
            "a.py": "import collections\n"
            "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "collections._sys.modules[__spec__.name if __spec__ "
            "else __name__].helper = len\n"
            "use()\n"
        },
    ),
    "nonident_dir_init": (
        "N-5",
        {
            "__target__": "my-pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "my-pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from .helper import M\n",
            "my-pkg/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "nonident_dir_init_abs": (
        "N-5",
        {
            "__target__": "my-pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "my-pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import sys\n"
            "    from . import other\n"
            "    other.up.helper = len\n",
            "my-pkg/other.py": "import importlib\n"
            "up = "
            "importlib.import_module('my-pkg')\n",
        },
    ),
    "nonident_nested_init": (
        "N-5",
        {
            "__target__": "pkg/my-sub/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/my-sub/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from .helper import M\n",
            "pkg/my-sub/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = "
            "M\n",
        },
    ),
    "nonident_stem_dict": (
        "N-5",
        {
            "__target__": "pkg/my-mod.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/my-mod.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    pkg.__dict__['my-mod'].helper = len\n",
        },
    ),
    "nonident_stem_getattr": (
        "N-5",
        {
            "__target__": "pkg/my-mod.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/my-mod.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    getattr(pkg, 'my-mod').helper = "
            "len\n",
        },
    ),
    "pkgutil_resolve": (
        "R-5",
        {
            "a.py": "import pkgutil\n"
            "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    pkgutil.resolve_name(__name__).helper = len\n"
            "\n"
            "patch()\n"
            "use()\n"
        },
    ),
    "pydoc_locate": (
        "R-5",
        {
            "a.py": "import pydoc\n"
            "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    pydoc.locate(__name__).helper = len\n"
            "\n"
            "patch()\n"
            "use()\n"
        },
    ),
    "reexport_sibling": (
        "R-5",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from .sib import mod\n"
            "    mod.helper = len\n",
            "pkg/sib.py": "from . import a as mod\n",
        },
    ),
    "reexport_sibling_func": (
        "R-5",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from .sib import me\n"
            "    me().helper = len\n",
            "pkg/sib.py": "def me():\n    import pkg.a\n    return pkg.a\n",
        },
    ),
    "rootpar_self": (
        "N-6",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    from .. import rootpar_self as me\n"
            "    me.helper = len\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "rootpar_sub": (
        "N-6",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from ..rootpar_sub.helper import M\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "str_bytes_decode": (
        "R-5",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    getattr(patch, b'__globals__'.decode())['helper'] "
            "= len\n"
            "patch()\n"
            "use()\n"
        },
    ),
    "str_fstring_nested": (
        "R-5",
        {
            "__target__": "pkg/a.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n"
            "\n"
            "def me():\n"
            "    pass\n",
            "pkg/__init__.py": "",
            "pkg/a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    import pkg\n"
            "    getattr(pkg, f'{\"x\"}a'[-1]).helper = "
            "len\n",
        },
    ),
    "str_percent": (
        "R-5",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "def patch():\n"
            "    getattr(patch, '__%s__' % 'glob' 'als')['helper'] = "
            "len\n"
            "patch()\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD4_695))
def test_fold4_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD4_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    ("path", "form"),
    [
        # N-4: a name is an attribute lookup whatever node spells it.
        (
            "pkg/a.py",
            "def patch():\n    match pkg:\n        case object(a=m):\n            m.__dict__.clear()",
        ),
        (
            "a.py",
            "def patch():\n    match use:\n        case object(__globals__=g):\n            g.clear()",
        ),
        (
            "a.py",
            "def patch():\n    match fr:\n        case object(f_globals=g):\n            g.clear()",
        ),
        ("a.py", "from inspect import getmodule"),
        ("pkg/a.py", "x = dict(a=1)"),
        ("pkg/a.py", "match v:\n    case pkg.a:\n        pass"),
        # N-5: raw, non-identifier own names.
        ("pkg/my-mod.py", "def patch():\n    getattr(pkg, 'my-mod').__dict__.clear()"),
        ("my-pkg/__init__.py", "x = 'my-pkg'"),
        # N-6: a root ``__init__.py`` reached through ``..``.
        ("__init__.py", "def patch():\n    from .. import R as me"),
        ("__init__.py", "from ..R.helper import M"),
        # ``X[__name__]`` / getters on any receiver.
        ("a.py", "def patch(m):\n    m[__name__].__dict__.clear()"),
        ("a.py", "def patch(m):\n    m.get((__name__)).__dict__.clear()"),
    ],
)
def test_fold4_rules_fail_closed(path: str, form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path) == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, (path, form)


def test_f_locals_as_a_class_pattern_keyword_fails_closed_everywhere() -> None:
    source = (
        "def f(fr):\n    def helper():\n        return 1\n"
        "    match fr:\n        case object(f_locals=fl):\n            fl.clear()\n"
        "    return helper()\n"
    )
    assert reason(source) == "dynamic-scope"


def test_nonidentifier_package_init_rebinds_submodules() -> None:
    source = HELPER + "from .helper import M\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "my-pkg/__init__.py") == {
        "outcome": "none",
        "reason": "mixed-bindings",
    }
    nested = _outcome_at(source, "helper", "pkg/my-sub/__init__.py")
    assert nested["outcome"] == "none"


def test_an_unknown_path_fails_closed() -> None:
    """``compute_scope_facts`` without a path cannot know the own name."""
    from chunker.call_resolution import facts

    source = (HELPER + "def use():\n    return helper()\n").encode()
    start = source.rindex(b"helper")
    call = {"callee_byte_start": start, "callee_byte_end": start + 6}
    unknown = facts.compute_scope_facts(
        language="python", source=source, call_facts=[call], symbols=[]
    )
    known = facts.compute_scope_facts(
        language="python", source=source, call_facts=[call], symbols=[], path="a.py"
    )
    key = f"{start}:{start + 6}"
    assert unknown["bindings"][key] == {"outcome": "none", "reason": "dynamic-scope"}
    assert known["bindings"][key]["outcome"] == "local"


@pytest.mark.parametrize(
    "form",
    [
        "def patch(mod):\n    mod.helper = len",
        "def patch(mod):\n    mod.helper += 1",
        "def patch(mod):\n    del mod.helper",
        "def patch(mod):\n    mod.__dict__['helper'] = len",
        "def patch(mod):\n    setattr(mod, 'helper', len)",
        "def patch(mod):\n    delattr(mod, 'helper')",
        "def patch(mod):\n    object.__setattr__(mod, 'helper', len)",
        "def patch(mod):\n    mod.__dict__.update(helper=len)",
        "def patch(mod):\n    mod.__dict__.update({'helper': len})",
        "def patch(mod):\n    mod.__dict__.update(**{'helper': len})",
        "def patch(mod):\n    mod.__dict__.setdefault('helper', len)",
        "def patch(mod):\n    mod.__dict__.pop('helper')",
        "def patch(mod):\n    mod.__dict__.__setitem__('helper', len)",
        "def patch(mod):\n    for mod.helper in [len]:\n        pass",
    ],
)
def test_attribute_writes_through_any_receiver_rebind(form: str) -> None:
    """Any receiver may be this module, handed over by a sibling, a function
    or a loader: a write of attribute ``helper`` is a non-definition binding
    of the module's ``helper`` (#695 re-check R-5 family)."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "mixed-bindings",
    }, form


@pytest.mark.parametrize(
    "form",
    [
        # Reads, and names the analysis cannot confuse with a write.
        "def patch(mod):\n    return mod.helper",
        "match v:\n    case {'helper': h}:\n        pass",
        "__all__ = ['helper']",
        "class K:\n    __slots__ = ('helper',)",
        "@decorate\ndef other():\n    return 1",
        "def f(a, *a2, **kw):\n    return 0",
        "def a():\n    return 0",
    ],
)
def test_reads_and_bindings_still_resolve(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py")["outcome"] == "local", form
    # A parameter or ``def`` named like the module is a scope binding, not a
    # lookup (a later load of that variable does over-trigger, by design).
    param = (
        HELPER + "def f(a, *a2):\n    return 0\n\n\ndef use():\n    return helper()\n"
    )
    assert _outcome_at(param, "helper", "pkg/a.py")["outcome"] == "local"


# ---------------------------------------------------------------------------
# The president's re-check at 06f5dc32 (N-7): names and dotted paths come from
# identifier tokens, never raw node text (whitespace, comments and backslash
# continuations may sit between the tokens).

FOLD5_695: dict[str, tuple[str, dict[str, str]]] = {
    "ws_init_rel_contline": (
        "N-7",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from .\\\n"
            "helper import M\n",
            "pkg/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "ws_init_rel_deep": (
        "N-7",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from . helper.x import y\n",
            "pkg/helper/__init__.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = "
            "M\n",
            "pkg/helper/x.py": "y = 1\n",
        },
    ),
    "ws_init_rel_submodule": (
        "N-7",
        {
            "__target__": "pkg/__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "pkg/__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from . helper import M\n",
            "pkg/helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "ws_rootinit_rel_submodule": (
        "N-7",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from . helper import M\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "ws_rootpar_contline": (
        "N-7",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from .\\\n"
            ".ws_rootpar_contline.helper import M\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
    "ws_rootpar_self": (
        "N-7",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = dict(helper=len)\n"
            "def patch():\n"
            "    from . . import ws_rootpar_self as me\n"
            "    me.__dict__.update(D)\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
        },
    ),
    "ws_rootpar_sub": (
        "N-7",
        {
            "__init__.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "from . . ws_rootpar_sub.helper import M\n",
            "__target__": "__init__.py",
            "b.py": "def helper(*a):\n"
            "    return 'decoy'\n"
            "\n"
            "def use():\n"
            "    pass\n"
            "\n"
            "def patch():\n"
            "    pass\n",
            "helper.py": "import sys, types\n"
            "class M(types.ModuleType):\n"
            "    def __call__(self, *a):\n"
            "        return 'callable-module'\n"
            "sys.modules[__name__].__class__ = M\n",
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD5_695))
def test_fold5_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD5_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    ("source", "level", "parts"),
    [
        ("from . helper import M\n", 1, ["helper"]),
        ("from .\\\nhelper import M\n", 1, ["helper"]),
        ("from . . import R\n", 2, []),
        ("from .\\\n.R.helper import M\n", 2, ["R", "helper"]),
        ("from ... x . y import z\n", 3, ["x", "y"]),
        ("from os . sys import modules\n", 0, ["os", "sys"]),
        ("from \\\n  sys import modules\n", 0, ["sys"]),
    ],
)
def test_module_parts_come_from_tokens(
    source: str, level: int, parts: list[str]
) -> None:
    data = source.encode()
    root = get_parser("python").parse(data).root_node
    assert not root.has_error
    (statement,) = root.named_children
    assert py_scope._module_parts(statement, data) == (level, parts)


@pytest.mark.parametrize(
    ("path", "form", "expected"),
    [
        # B-3 and N-1 with whitespace or a continuation after the dots.
        ("pkg/__init__.py", "from . helper import M", "mixed-bindings"),
        ("pkg/__init__.py", "from .\\\nhelper import M", "mixed-bindings"),
        ("pkg/sub/__init__.py", "from . helper . x import y", "mixed-bindings"),
        ("pkg/sub/__init__.py", "from . . sub . helper import M", "dynamic-scope"),
        ("__init__.py", "from . helper import M", "mixed-bindings"),
        # N-6 with the dots apart.
        ("__init__.py", "def patch():\n    from . . import R as me", "dynamic-scope"),
        ("__init__.py", "from .\\\n.R.helper import M", "dynamic-scope"),
        # ``from sys import modules`` with the module path spaced out.
        ("pkg/a.py", "from os . sys import modules", "dynamic-scope"),
        ("pkg/a.py", "from \\\n  sys import modules", "dynamic-scope"),
    ],
)
def test_spaced_import_tokens_fail_closed(path: str, form: str, expected: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path) == {
        "outcome": "none",
        "reason": expected,
    }, (path, form)


def test_analyze_without_a_path_fails_closed() -> None:
    """``analyze(path=None)`` cannot know the own name, like ``""``."""
    source = (HELPER + "def use():\n    return helper()\n").encode()
    root = get_parser("python").parse(source).root_node
    start = source.rindex(b"helper")
    call = [{"callee_byte_start": start, "callee_byte_end": start + 6}]
    key = f"{start}:{start + 6}"
    for path in (None, ""):
        result = py_scope.analyze(root, source, "python", call, path=path)
        assert result["bindings"][key] == {
            "outcome": "none",
            "reason": "dynamic-scope",
        }, path
    named = py_scope.analyze(root, source, "python", call, path="a.py")
    assert named["bindings"][key]["outcome"] == "local"


# ---------------------------------------------------------------------------
# Codex 4654363963: names recorded from class code take every runtime
# spelling, mangled ``_Class__x`` included.

CODEX_4654363963 = (
    "def _K__helper():\n    return 1\n\n\ndef replacement():\n    return 2\n\n\n"
    "def run(mod):\n    class K:\n        mod.__helper = replacement\n"
    "    return _K__helper()\n"
)


def test_codex_4654363963_end_to_end(tmp_path: Path) -> None:
    """Passed this module, ``run`` calls ``replacement``: the class-body write
    ``mod.__helper`` is ``mod._K__helper`` at run time."""
    root = _tree(
        tmp_path,
        {"a.py": CODEX_4654363963, "b.py": "def _K__helper():\n    return 3\n"},
    )
    off, on = _off_on(root)
    edge = _helper_edge(off, "_K__helper")
    assert edge["resolution"] == "ambiguous"
    assert _helper_edge(on, "_K__helper") == edge


@pytest.mark.parametrize(
    "write",
    [
        "    class K:\n        mod.__helper = replacement",
        "    class K:\n        del mod.__helper",
        "    class K:\n        mod.__helper += 1",
        "    class K:\n        def m(self):\n            mod.__helper = replacement",
        "    class K:\n        f = lambda: setattr(mod, 'x', 1) or mod.__dict__",
        "    class Outer:\n        class K:\n            mod.__helper = replacement",
        "    class K:\n        g = (lambda: [mod for mod.__helper in [replacement]])",
        "    class K:\n        def m(self):\n            global __helper\n            mod.__helper = 1",
        "    class K:\n        with cm as mod.__helper:\n            pass",
    ],
)
def test_class_code_attribute_writes_bind_the_mangled_name(write: str) -> None:
    source = (
        "def _K__helper():\n    return 1\n\n\ndef replacement():\n    return 2\n\n\n"
        f"def run(mod, cm):\n{write}\n    return _K__helper()\n"
    )
    result = _outcome_at(source, "_K__helper", "pkg/a.py")
    if "lambda: setattr" in write:
        # Control: no ``__helper`` write, so ``_K__helper`` still resolves.
        assert result["outcome"] == "local", write
    else:
        assert result["outcome"] == "none", write


def test_class_code_names_take_mangled_spellings_in_every_scan() -> None:
    """The own-name and dynamic-name scans see the mangled spelling too."""
    # A module whose own name is the mangled spelling of a class-code name.
    source = (
        HELPER + "class K:\n    x = pkg.__helper\n\n\ndef use():\n    return helper()\n"
    )
    assert _outcome_at(source, "helper", "pkg/_K__helper.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }
    # Outside a class nothing is mangled.
    plain = HELPER + "x = pkg.__helper\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(plain, "helper", "pkg/_K__helper.py")["outcome"] == "local"


def test_class_code_submodule_imports_bind_mangled_names() -> None:
    source = (
        "def _K__helper():\n    return 1\n\n\nclass K:\n    from . import __helper\n\n\n"
        "def use():\n    return _K__helper()\n"
    )
    assert _outcome_at(source, "_K__helper", "pkg/__init__.py")["outcome"] == "none"
