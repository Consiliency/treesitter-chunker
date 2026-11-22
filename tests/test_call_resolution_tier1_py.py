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
    # Annotations run in the enclosing scope too, but ``annotationlib`` may
    # evaluate them under substitute globals, so they prove nothing (#695
    # re-check at 14e8f044, Q-2).
    annotated = HELPER + "def f(x: helper()) -> helper():\n    return 0\n"
    assert reason(annotated, occurrence=0) == "dynamic-scope"
    assert reason(annotated, occurrence=1) == "dynamic-scope"
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
        "class Inner(helper()):\n        pass",
        "xs = [y for y in helper()]",
        "f = lambda x=helper(): x",
    ):
        source = HELPER + f"class K:\n    {body}\n    {code}\n"
        assert reason(source) == "class-scope-bound", code
    # An annotation proves nothing before the class step (#695 Q-2).
    source = HELPER + f"class K:\n    {body}\n    def m(self, x: helper()):\n"
    assert reason(source + "        return x\n") == "dynamic-scope"


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
    # A ``type`` value proves nothing before the type-parameter step (#695
    # re-check at a6734480, S-2).
    alias = HELPER + "type X[helper] = helper()\n"
    assert reason(alias) == "dynamic-scope"
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


def test_namespace_dunder_writes_fail_closed() -> None:
    """Since fold 23 (E-21 A-2) a dunder on a namespace dict is off the
    allow-list: ``mod.__dict__.__setitem__('helper', len)`` fails closed as
    ``dynamic-scope`` instead of being recorded (``mixed-bindings``)."""
    form = "def patch(mod):\n    mod.__dict__.__setitem__('helper', len)"
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }


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
        # (Control below. Since fold 19 a namespace dict escaping through a
        # lambda body fails closed, so the control reads it instead.)
        "    class K:\n        f = lambda: setattr(mod, 'x', 1) or mod.__dict__.get('x')",
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


# ---------------------------------------------------------------------------
# The president's re-check at 13c38360 (I-3): the ``sys``/``__main__`` alias
# sets and their uses compare every runtime spelling, mangled included.

FOLD7_695: dict[str, tuple[str, dict[str, str]]] = {
    "m18_main_alias_in_class": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "class K:\n"
            "    global __m\n"
            "    import __main__ as __m\n"
            "_K__m.__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m18_main_alias_in_class_setattr": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "class K:\n"
            "    global __m\n"
            "    import __main__ as __m\n"
            "setattr(_K__m, n, len)\n"
            "use()\n"
        },
    ),
    "m18_main_alias_setattr": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "import __main__ as _K__m\n"
            "n = ''.join(['hel', 'per'])\n"
            "class K:\n"
            "    setattr(__m, n, len)\n"
            "use()\n"
        },
    ),
    "m18_main_alias_use_in_class": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "import __main__ as _K__m\n"
            "class K:\n"
            "    __m.__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m18_main_alias_use_in_method": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "import __main__ as _K__m\n"
            "class K:\n"
            "    def f(self):\n"
            "        __m.__dict__.update(D)\n"
            "K().f()\n"
            "use()\n"
        },
    ),
    "m18_sys_alias_in_class": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "k = __name__\n"
            "class K:\n"
            "    global __s\n"
            "    import sys as __s\n"
            "_K__s.modules[k].__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m18_sys_alias_use_in_class": (
        "I-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "k = __name__\n"
            "import sys as _K__s\n"
            "class K:\n"
            "    __s.modules[k].__dict__.update(D)\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD7_695))
def test_fold7_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD7_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    "form",
    [
        # Defined in class code (binds ``_K__m``), used outside it.
        "class K:\n    global __m\n    import __main__ as __m\n_K__m.__dict__.clear()",
        "class K:\n    global __s\n    import sys as __s\n_K__s.modules",
        # Defined outside, used in class code (``__m`` reads ``_K__m``).
        "import __main__ as _K__m\nclass K:\n    __m.__dict__.clear()",
        "import sys as _K__s\nclass K:\n    def m(self):\n        return __s.modules",
    ],
)
def test_mangled_sys_and_main_aliases_fail_closed(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, form


# ---------------------------------------------------------------------------
# The president's re-check at eae66582 (J-3): ``__main__`` reached through a
# class attribute or a ``from __main__`` import.

FOLD8_695: dict[str, tuple[str, dict[str, str]]] = {
    "m19_from_main_dict": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from __main__ import __dict__ as g\n"
            "g.update(D)\n"
            "use()\n"
        },
    ),
    "m19_from_main_dict_bare": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from __main__ import __dict__\n"
            "__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m19_from_main_dict_class": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    from __main__ import __dict__ as __g\n"
            "    __g.update(D)\n"
            "use()\n"
        },
    ),
    "m19_from_main_setattr": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from __main__ import __dict__ as g\n"
            "g[n] = len\n"
            "use()\n"
        },
    ),
    "m19_main_chain_attr": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as __m\n"
            "K._K__m.__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m19_main_classattr_self": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as __m\n"
            "    def f(self):\n"
            "        self.__m.__dict__.update(D)\n"
            "K().f()\n"
            "use()\n"
        },
    ),
    "m20_ctrl_classattr_plain": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as mm\n"
            "K.mm.__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m20_ctrl_cls": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as __m\n"
            "    @classmethod\n"
            "    def f(cls):\n"
            "        cls.__m.__dict__.update(D)\n"
            "K.f()\n"
            "use()\n"
        },
    ),
    "m20_ctrl_getattr_const": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as mm\n"
            "getattr(K, 'mm').__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m20_ctrl_self_plain": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as mm\n"
            "    def f(self):\n"
            "        self.mm.__dict__.update(D)\n"
            "K().f()\n"
            "use()\n"
        },
    ),
    "m20_ctrl_setattr_plain": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as mm\n"
            "setattr(K.mm, n, len)\n"
            "use()\n"
        },
    ),
    "m20_ctrl_type_self": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__ as __m\n"
            "    def f(self):\n"
            "        type(self)._K__m.__dict__.update(D)\n"
            "K().f()\n"
            "use()\n"
        },
    ),
    "m20_from_main_classattr": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    from __main__ import __dict__ as g\n"
            "K.g.update(D)\n"
            "use()\n"
        },
    ),
    "m20_from_main_dict_fn": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "def f():\n"
            "    from __main__ import __dict__ as g\n"
            "    g.update(D)\n"
            "f()\n"
            "use()\n"
        },
    ),
    "m20_from_main_getitem": (
        "J-3b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from __main__ import __dict__ as g\n"
            "g.__setitem__(n, len)\n"
            "use()\n"
        },
    ),
    "m20_main_plain_import_in_class": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import __main__\n"
            "K.__main__.__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m20_sys_classattr_k": (
        "J-3a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "class K:\n"
            "    import sys as ss\n"
            "K.ss.modules[k].__dict__.update(D)\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD8_695))
def test_fold8_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD8_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    "form",
    [
        # J-3a: a class-body import of ``sys`` or ``__main__`` is a class
        # attribute no identifier rule sees.
        "class K:\n    import __main__ as mm\nK.mm.__dict__.clear()",
        "class K:\n    import __main__",
        "class K:\n    import sys as ss",
        "class K:\n    from os import sys",
        "class K:\n    from __main__ import x",
        # J-3b: names a ``from __main__`` import binds are aliases.
        "from __main__ import __dict__ as g\ng.clear()",
        "from __main__ import __dict__\n__dict__.clear()",
        "from __main__ import __dict__ as g\ndef f(n):\n    g[n] = len",
        # The bound name takes its mangled spelling too: ``__g`` under
        # ``global`` in a method of ``K`` binds the module's ``_K__g``.
        "class K:\n    def m(self):\n        global __g\n"
        "        from __main__ import __dict__ as __g\n_K__g.clear()",
    ],
)
def test_main_through_class_attributes_and_from_imports_fails_closed(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, form


@pytest.mark.parametrize(
    "form",
    [
        "from __main__ import __dict__ as g",
        "from __main__ import x",
        "def f():\n    import sys\n    return sys.argv",
        "class K:\n    def m(self):\n        import sys\n        return sys.argv",
        "class K:\n    def m(self):\n        import os\n        return os.sep",
    ],
)
def test_unused_main_from_imports_and_function_imports_still_resolve(form: str) -> None:
    """An unused ``from __main__`` import binds nothing used; an import in a
    method is not a class attribute (#695 J-4)."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py")["outcome"] == "local", form


# ---------------------------------------------------------------------------
# The president's re-check at f2b38014 (K-3): ``"__main__"`` as a constant
# string names this module by string when the file runs as a script.

FOLD9_695: dict[str, tuple[str, dict[str, str]]] = {
    "m21_name_const_main": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "import pydoc\n"
            "MM = '__main__'\n"
            "pydoc.locate(MM).__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m21_pkgutil_resolve_main": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "import pkgutil\n"
            "pkgutil.resolve_name('__main__').__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m21_pydoc_locate_main": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "import pydoc\n"
            "pydoc.locate('__main__').__dict__.update(D)\n"
            "use()\n"
        },
    ),
    "m22_mock_patch_dict_main": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from unittest import mock\n"
            "import pydoc\n"
            "with "
            "mock.patch.dict(pydoc.locate('__main__').__dict__, "
            "D):\n"
            "    use()\n"
        },
    ),
    "m22_mock_patch_main_literal": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "from unittest import mock\n"
            "with mock.patch('__main__.helper', len):\n"
            "    use()\n"
        },
    ),
    "m22_operator_attrgetter": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "import pydoc, operator\n"
            "setattr(pydoc.locate('__main__'), n, len)\n"
            "use()\n"
        },
    ),
    "m22_resolve_name_colon": (
        "K-3",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "k = __name__\n"
            "import pkgutil\n"
            "pkgutil.resolve_name('__main__:__dict__').update(D)\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD9_695))
def test_fold9_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD9_695[case]
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
        # K-3: ``"__main__"`` as a component, split on ``.`` and ``:``.
        ("pkg/a.py", "with mock.patch('__main__.helper', len):\n    pass"),
        ("pkg/a.py", "pydoc.locate('__main__').__dict__.update(D)"),
        ("pkg/a.py", "pkgutil.resolve_name('__main__:__dict__').update(D)"),
        ("pkg/a.py", "MM = '__main__'"),
        # A multiprocessing spawn child imports the script as ``__mp_main__``.
        ("pkg/a.py", "pydoc.locate('__mp_main__').__dict__.update(D)"),
        ("pkg/a.py", "import __mp_main__ as m\nm.__dict__.update(D)"),
        # ``:`` also separates the own name and the dynamic attribute names.
        ("pkg/a.py", "pkgutil.resolve_name('pkg.a:__dict__').update(D)"),
        ("pkg/a.py", "pkgutil.resolve_name('sys:modules')[k].__dict__.update(D)"),
    ],
)
def test_main_and_own_name_strings_fail_closed(path: str, form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", path) == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, form


@pytest.mark.parametrize(
    "form",
    [
        "if __name__ == '__main__':\n    pass",
        "if '__main__' == __name__:\n    pass",
        "if __name__ != ('__main__'):\n    pass",
        "if (__name__ == '__main__'):\n    pass",
        "if ((__name__) == '__main__'):\n    pass",
        "if x:\n    pass\nelif __name__ == '__main__':\n    pass",
    ],
)
def test_main_guards_still_resolve(form: str) -> None:
    """The positive allow-list (#695 M-2, executive decision): exactly
    ``__name__ == '__main__'`` or ``!=``, either order, optionally
    parenthesized, as the whole test of a module-level ``if`` or ``elif``, in
    a file that never rebinds ``__name__``. ``__name__`` is then a module
    global ``str``: no user ``__eq__`` runs and no class namespace is
    involved."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py")["outcome"] == "local", form


@pytest.mark.parametrize(
    "form",
    [
        # Flipped by the allow-list (resolved under the fold-10 deny-list).
        "if __name__ in ('__main__',):\n    pass",
        "if __name__ not in ['__main__', '__mp_main__']:\n    pass",
        "match __name__:\n    case '__main__':\n        pass",
        "match __name__:\n    case '__main__' | '__mp_main__':\n        pass",
        "def main():\n    if __name__ == '__main__':\n        pass",
        "class K:\n    def m(self):\n        return __name__ == '__main__'",
        # Never allowed.
        "if __name__ == '__main__' == __name__:\n    pass",
        "if __name__ == '__main__' and x:\n    pass",
        "if not __name__ == '__main__':\n    pass",
        "if __name__ == '__mp_main__':\n    pass",
        "x = __name__ == '__main__'",
        "while __name__ == '__main__':\n    break",
        "if x:\n    if __name__ == '__main__':\n        pass",
        "class K:\n    if __name__ == '__main__':\n        pass",
        "if __name__ < '__main__':\n    pass",
        "if __name__ is '__main__':\n    pass",
        "if __name__ is not '__main__':\n    pass",
        "if x == '__main__':\n    pass",
        "if __name__.lower() == '__main__':\n    pass",
        "if __name__ == '__ma' 'in__':\n    pass",
        # An allowed guard in a file that rebinds ``__name__``.
        "__name__ = P()\nif __name__ == '__main__':\n    pass",
        "def f(mod):\n    mod.__name__ = P()\n\n\nif __name__ == '__main__':\n    pass",
    ],
)
def test_main_guards_off_the_allow_list_fail_closed(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, form


# ---------------------------------------------------------------------------
# The president's re-check at 3b2d8fae (L-2): the ``__main__`` guard exemption
# narrowed to code that can hand the constant to no user code.

FOLD10_695: dict[str, tuple[str, dict[str, str]]] = {
    "m23_case_class_kw": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class K:\n"
            "    __match_args__ = ()\n"
            "    def __getattr__(self, k):\n"
            "        return self\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match K():\n"
            "    case K(x='__main__.helper'):\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m23_case_value_eq": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match P():\n"
            "    case '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m23_contains_dunder": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class R:\n"
            "    def __contains__(self, k):\n"
            "        mock.patch(k, len).start()\n"
            "        return True\n"
            "'__main__.helper' in R()\n"
            "use()\n"
        },
    ),
    "m23_eq_dunder_patch": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "P() == '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m23_eq_dunder_reflected": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "'__main__.helper' == P()\n"
            "use()\n"
        },
    ),
    "m23_eq_locate": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "import pydoc\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        pydoc.locate(o).__dict__.update(D)\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "P() == '__main__'\n"
            "use()\n"
        },
    ),
    "m23_in_list_eq": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "P() in ['__main__.helper']\n"
            "use()\n"
        },
    ),
    "m23_in_tuple_eq": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "P() in ('__main__.helper',)\n"
            "use()\n"
        },
    ),
    "m23_lt_dunder": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __lt__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "P() < '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m23_ne_dunder": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "P() != '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m24_case_or_eq": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match P():\n"
            "    case '__main__.helper' | 'x':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m24_chained": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "P() == '__main__.helper' == '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m24_name_assign": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "__name__ = P()\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_aug": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "__name__ += ''\n"
            "__name__ = P()\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_classbody": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class K:\n"
            "    __name__ = P()\n"
            "    __name__ == '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m24_name_comp": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "[__name__ == '__main__.helper' for __name__ in [P()]]\n"
            "use()\n"
        },
    ),
    "m24_name_except": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class E(Exception):\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "try:\n"
            "    raise E()\n"
            "except E as __name__:\n"
            "    __name__ == '__main__.helper'\n"
            "use()\n"
        },
    ),
    "m24_name_for": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "for __name__ in [P()]:\n"
            "    pass\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_global_fn": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "def g():\n"
            "    global __name__\n"
            "    __name__ = P()\n"
            "g()\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_lambda": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "(lambda __name__: __name__ == '__main__.helper')(P())\n"
            "use()\n"
        },
    ),
    "m24_name_match_capture": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match P():\n"
            "    case __name__:\n"
            "        pass\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_param": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "def f(__name__):\n"
            "    return __name__ == '__main__.helper'\n"
            "f(P())\n"
            "use()\n"
        },
    ),
    "m24_name_walrus": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "(__name__ := P())\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_name_with": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "import contextlib\n"
            "with contextlib.nullcontext(P()) as __name__:\n"
            "    pass\n"
            "if __name__ == '__main__.helper':\n"
            "    pass\n"
            "use()\n"
        },
    ),
    "m24_prepare_ns": (
        "L-2",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class NS(dict):\n"
            "    def __missing__(self, k):\n"
            "        return P()\n"
            "class Meta(type):\n"
            "    @classmethod\n"
            "    def __prepare__(m, *a, **k):\n"
            "        return NS()\n"
            "class K(metaclass=Meta):\n"
            "    __name__ == '__main__.helper'\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD10_695))
def test_fold10_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD10_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


@pytest.mark.parametrize(
    "form",
    [
        # An operand user code receives (``__eq__``, ``__contains__``).
        "x = P() == '__main__'",
        "x = '__main__' in R()",
        "x = P() in ('__main__',)",
        # A ``case`` value pattern on another subject, or a nested pattern.
        "match P():\n    case '__main__':\n        pass",
        "match __name__:\n    case '__main__' as s:\n        pass",
        "match __name__:\n    case K(x='__main__'):\n        pass",
        # A class body may supply ``__name__`` (``__prepare__``).
        "class K(metaclass=M):\n    x = __name__ == '__main__'",
        "class K(metaclass=M):\n    match __name__:\n        case '__main__':\n"
        "            pass",
        # ``__name__`` rebound anywhere, also by an attribute write through
        # a receiver that may be this module.
        "__name__ = P()\nx = __name__ == '__main__'",
        "def f(__name__):\n    return __name__ == '__main__'",
        "def f():\n    global __name__\n    __name__ = P()\nx = __name__ == '__main__'",
        "for __name__ in [P()]:\n    pass\nx = __name__ == '__main__'",
        "del __name__\nx = 1 if __name__ == '__main__' else 0",
        "def f(mod):\n    mod.__name__ = P()\nx = __name__ == '__main__'",
    ],
)
def test_narrowed_main_guard_fails_closed(form: str) -> None:
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert _outcome_at(source, "helper", "pkg/a.py") == {
        "outcome": "none",
        "reason": "dynamic-scope",
    }, form


# ---------------------------------------------------------------------------
# The president's re-check at 8006c72c (M-2): multi-subject ``match`` and
# defaults evaluated in a class namespace, closed by the positive allow-list.

FOLD11_695: dict[str, tuple[str, dict[str, str]]] = {
    "m25_match_multi_subject": (
        "M-2a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match __name__, P():\n"
            "    case _, '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m25_match_multi_subject_lit": (
        "M-2a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match __name__, P():\n"
            "    case '__main__', '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m25_match_multi_subject_trailing": (
        "M-2a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match __name__, P(),:\n"
            "    case _, '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m25_prepare_default": (
        "M-2b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class NS(dict):\n"
            "    def __missing__(self, k):\n"
            "        if k == '__name__':\n"
            "            return P()\n"
            "        raise KeyError(k)\n"
            "class Meta(type):\n"
            "    @classmethod\n"
            "    def __prepare__(m, *a, **k):\n"
            "        return NS()\n"
            "class K(metaclass=Meta):\n"
            "    def m(self, x=(__name__ == "
            "'__main__.helper')):\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m25_prepare_kwonly_default": (
        "M-2b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class NS(dict):\n"
            "    def __missing__(self, k):\n"
            "        if k == '__name__':\n"
            "            return P()\n"
            "        raise KeyError(k)\n"
            "class Meta(type):\n"
            "    @classmethod\n"
            "    def __prepare__(m, *a, **k):\n"
            "        return NS()\n"
            "class K(metaclass=Meta):\n"
            "    def m(self, *, x=__name__ == "
            "'__main__.helper'):\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m25_prepare_lambda_default": (
        "M-2b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class NS(dict):\n"
            "    def __missing__(self, k):\n"
            "        if k == '__name__':\n"
            "            return P()\n"
            "        raise KeyError(k)\n"
            "class Meta(type):\n"
            "    @classmethod\n"
            "    def __prepare__(m, *a, **k):\n"
            "        return NS()\n"
            "class K(metaclass=Meta):\n"
            "    f = lambda x=(__name__ == "
            "'__main__.helper'): x\n"
            "use()\n"
        },
    ),
    "m25_prepare_typed_default": (
        "M-2b",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "class NS(dict):\n"
            "    def __missing__(self, k):\n"
            "        if k == '__name__':\n"
            "            return P()\n"
            "        raise KeyError(k)\n"
            "class Meta(type):\n"
            "    @classmethod\n"
            "    def __prepare__(m, *a, **k):\n"
            "        return NS()\n"
            "class K(metaclass=Meta):\n"
            "    def m(self, x: int = (__name__ == "
            "'__main__.helper')):\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m26_match_multi_seq3": (
        "M-2a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "match __name__, __name__, P():\n"
            "    case '__main__', _, '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
    "m26_match_star_subject": (
        "M-2a",
        {
            "a.py": "def helper(*a):\n"
            "    return 'mod'\n"
            "\n"
            "def use():\n"
            "    return helper('ab')\n"
            "\n"
            "D = {'helper': len}\n"
            "n = ''.join(['hel', 'per'])\n"
            "from unittest import mock\n"
            "class P:\n"
            "    def __eq__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __ne__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    def __contains__(self, o):\n"
            "        mock.patch(o, len).start()\n"
            "        return True\n"
            "    __hash__ = object.__hash__\n"
            "xs = [P()]\n"
            "match __name__, *xs:\n"
            "    case _, '__main__.helper':\n"
            "        pass\n"
            "use()\n"
        },
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD11_695))
def test_fold11_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, spec = FOLD11_695[case]
    files = dict(spec)
    target = files.pop("__target__", "a.py")
    files.setdefault("b.py", _decoys(files[target]))
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == target]
    assert any(edge["resolution"] == "ambiguous" for edge in off_calls), case
    assert [e for e in on["relationships"] if e["file"] == target] == off_calls


# ---------------------------------------------------------------------------
# Codex 4655078224: closure cells, code objects and other routes that rebind
# a binding without spelling an assignment make every lookup dynamic.

CODEX_4655078224 = (
    "def replacement():\n    return 2\n\n\n"
    "def run():\n    def helper():\n        return 1\n\n"
    "    def invoke():\n        return helper()\n\n"
    "    invoke.__closure__[0].cell_contents = replacement\n"
    "    return invoke()\n"
)


def _invoke_helper_edge(graph: dict[str, Any]) -> dict[str, Any]:
    (edge,) = (
        edge
        for edge in graph["relationships"]
        if edge["type"] == "calls"
        and edge["file"] == "a.py"
        and edge["reference"] == "helper"
    )
    return edge


CLOSURE_VARIANTS = {
    "codex": CODEX_4655078224,
    "in-a-method": CODEX_4655078224.replace(
        "def run():", "class K:\n    pass\n\n\ndef run():"
    ).replace(
        "    invoke.__closure__[0].cell_contents = replacement\n",
        "    class J:\n        def m(self):\n"
        "            invoke.__closure__[0].cell_contents = replacement\n"
        "    J().m()\n",
    ),
    "setattr-string": CODEX_4655078224.replace(
        "    invoke.__closure__[0].cell_contents = replacement\n",
        "    cell = getattr(invoke, '__clo' + 'sure__')[0]\n"
        "    setattr(cell, 'cell_contents', replacement)\n",
    ),
    "celltype": CODEX_4655078224.replace(
        "    invoke.__closure__[0].cell_contents = replacement\n"
        "    return invoke()\n",
        "    import types\n"
        "    new = types.FunctionType(code, {}, None, None, "
        "(types.CellType(replacement),))\n    return new()\n",
    ),
    "nested-closure": CODEX_4655078224.replace(
        "    def invoke():\n        return helper()\n\n",
        "    def outer():\n        def invoke():\n            return helper()\n"
        "        return invoke\n\n    invoke = outer()\n",
    ),
}


@pytest.mark.parametrize("case", sorted(CLOSURE_VARIANTS))
def test_codex_4655078224_closure_rebinding_end_to_end(
    tmp_path: Path, case: str
) -> None:
    """Python calls ``replacement``; the analyzer must not prove the local
    ``helper`` (Codex 4655078224)."""
    # A nested ``helper`` in ``b.py`` keeps the off-mode edge ambiguous
    # between the two nested definitions.
    other = "def other():\n    def helper():\n        return 3\n    return helper\n"
    root = _tree(tmp_path, {"a.py": CLOSURE_VARIANTS[case], "b.py": other})
    off, on = _off_on(root)
    edge = _invoke_helper_edge(off)
    assert edge["resolution"] == "ambiguous", case
    assert _invoke_helper_edge(on) == edge, case


LOCAL_PROOF = "def f():\n    def helper():\n        return 1\n    return helper()\n"


# Pinned here, not read from the module, so dropping a name fails a case.
FILE_WIDE_NAMES = (
    "f_locals",
    "__closure__",
    "cell_contents",
    "CellType",
    "FunctionType",
    "LambdaType",
    "CodeType",
    "__code__",
    "gi_code",
    "cr_code",
    "ag_code",
    "f_code",
    "co_code",
    "co_names",
    "co_consts",
    "co_varnames",
    "co_freevars",
    "co_cellvars",
    "ctypes",
    "pythonapi",
    "PyFrame_LocalsToFast",
    # The #695 re-check at 606c689f (O-3a): code objects from ``dis`` and
    # ``sys.monitoring``.
    "dis",
    "codeobj",
    "_get_code_object",
    "monitoring",
    # The #695 re-check at 8fd7c1a2 (P-3): the profiler's code objects and
    # inspect's helpers that return a frame's live locals (PEP 667).
    "getstats",
    "getgeneratorlocals",
    "getcoroutinelocals",
    "getasyncgenlocals",
    "getargvalues",
    # The #695 re-check at 14e8f044 (Q-3): a traceback frame summary's and
    # bdb's code objects, pdb's live frame locals, and annotationlib running a
    # user function under substitute globals.
    "_code",
    "code_linenos",
    "curframe_locals",
    "call_annotate_function",
    "call_evaluate_function",
    "__annotate__",
    # The #695 re-check at a6734480 (S-3): the class-dict key behind
    # ``type.__annotate__``.
    "__annotate_func__",
)


def test_file_wide_names_are_pinned() -> None:
    assert frozenset(FILE_WIDE_NAMES) == py_scope._FILE_WIDE_NAMES


@pytest.mark.parametrize("name", FILE_WIDE_NAMES)
def test_each_file_wide_name_makes_function_lookups_dynamic(name: str) -> None:
    """Every file-wide trigger reaches function scopes, as an identifier in
    any position and as a constant string."""
    for mention in (f"x = obj.{name}", f"x = '{name}'"):
        source = mention + "\n\n\n" + LOCAL_PROOF
        assert reason(source) == "dynamic-scope", (name, mention)
    assert proof_text(LOCAL_PROOF) == ["def helper():\n        return 1"]


def test_a_closure_keyword_makes_function_lookups_dynamic() -> None:
    """``exec(code, g, closure=cells)`` runs existing code against new cells,
    with nothing else spelled (cells from heap walking)."""
    source = "exec(obj, {}, closure=cells)\n\n\n" + LOCAL_PROOF
    assert reason(source) == "dynamic-scope"
    other = "f(obj, enclosure=cells)\n\n\n" + LOCAL_PROOF
    assert proof_text(other) == ["def helper():\n        return 1"]


def test_code_surgery_and_ctypes_fail_closed_everywhere() -> None:
    surgery = (
        "def f():\n    def helper():\n        return 1\n"
        "    f.__code__ = f.__code__.replace(co_names=('replacement',))\n"
        "    return helper()\n"
    )
    assert reason(surgery) == "dynamic-scope"
    poke = "import ctypes\n\n\n" + LOCAL_PROOF
    assert reason(poke) == "dynamic-scope"


@pytest.mark.parametrize(
    "form",
    [
        # Heap walking alone, parameter defaults, read-only views and
        # introspection metadata cannot change a proven binding (plan R12).
        # ``__self__`` and ``__builtins__`` reach the builtins namespace,
        # which only module-scope lookups fall back to (#695 O-3b).
        "import gc\nrefs = gc.get_referrers(f)",
        "f.__defaults__ = (1,)",
        "f.__kwdefaults__ = {'a': 1}",
        "m = obj.__func__\ns = obj.__self__",
        "b = f.__builtins__",
        "g.__wrapped__ = f",
        "import inspect, sys\nfr = inspect.currentframe()\nfr2 = sys._getframe()",
    ],
)
def test_routes_that_cannot_rebind_a_proof_still_resolve(form: str) -> None:
    source = form + "\n\n\n" + LOCAL_PROOF
    assert proof_text(source) == ["def helper():\n        return 1"], form


def test_heap_walked_dict_writes_are_caught_by_the_attribute_write_rule() -> None:
    source = (
        HELPER
        + "import gc\nfor d in gc.get_referrers(helper):\n    d['helper'] = len\n"
        "\n\ndef use():\n    return helper()\n"
    )
    assert reason(source) == "mixed-bindings"


# ---------------------------------------------------------------------------
# The #695 re-check at 606c689f (O-3): a function rebuilt over existing code
# without spelling a trigger (O-3a), and builtins injected before a
# module-level definition runs (O-3b). Each tree is the ruling's own and
# runtime-traced: Python calls ``len``, and 606c689f proved ``a.py``'s
# ``helper``.

G13 = "def helper(*a):\n    return 'mod'\n\ndef run():\n    return helper('ab')\n\n"
LATE13 = "def run():\n    return helper('ab')\n\n"
DEF13 = "def helper(*a):\n    return 'mod'\n"
NESTED13 = (
    "def helper(*a):\n    return 'mod'\n\n"
    "def outer():\n    def inner():\n        return helper('ab')\n"
    "    return inner\n\n"
)

FOLD13_695: dict[str, tuple[str, str]] = {
    "l1_dis_type_globals": (
        "O-3a",
        G13 + "import dis\ntype(run)(dis.Bytecode(run).codeobj, {'helper': len})()\n",
    ),
    "l1_dis_lambda_type": (
        "O-3a",
        G13 + "import dis\nF = type(lambda: 0)\n"
        "F(dis.Bytecode(run).codeobj, {'helper': len})()\n",
    ),
    "l1_dis_class_attr": (
        "O-3a",
        G13 + "import dis\n(run.__class__)(dis.Bytecode(run).codeobj, "
        "{'helper': len})()\n",
    ),
    "n31_dis_instr_nested_globals": (
        "O-3a",
        NESTED13 + "import dis\nc = [i.argval for i in dis.get_instructions(outer) "
        "if type(i.argval).__name__ == 'code'][0]\n"
        "type(outer)(c, {'helper': len})()\n",
    ),
    "n31_dis_computed_keys": (
        "O-3a",
        G13 + "import dis\nb = dis.Bytecode(run)\n"
        "g = {i.argval: len for i in b if i.opname == 'LOAD_GLOBAL'}\n"
        "type(run)(b.codeobj, g)()\n",
    ),
    "n31_monitoring_code": (
        "O-3a",
        G13 + "import sys\nM = sys.monitoring\nseen = []\nM.use_tool_id(3, 'x')\n"
        "M.register_callback(3, M.events.PY_START, lambda c, o: seen.append(c))\n"
        "M.set_events(3, M.events.PY_START)\nrun()\nM.set_events(3, 0)\n"
        "c = seen[0]\ntype(run)(c, {'helper': len})()\n",
    ),
    "l2_fn_builtins_update_var": (
        "O-3b",
        LATE13 + "D = dict(helper=len)\nrun.__builtins__.update(D)\nrun()\n" + DEF13,
    ),
    "n31_os_builtins_var": (
        "O-3b",
        "import os\n"
        + LATE13
        + "D = dict(helper=len)\nos.__builtins__.update(D)\nrun()\n"
        + DEF13,
    ),
    "l2_self_builtins_update_var": (
        "O-3b",
        LATE13
        + "D = dict(helper=len)\nlen.__self__.__dict__.update(D)\nrun()\n"
        + DEF13,
    ),
    "n31_self_getattr_str_var": (
        "O-3b",
        LATE13 + "D = dict(helper=len)\ngetattr(print, '__self__').__dict__.update(D)\n"
        "run()\n" + DEF13,
    ),
    "n31_self_ior": (
        "O-3b",
        LATE13 + "b = len.__self__.__dict__\nb |= {'helper': len}\nrun()\n" + DEF13,
    ),
    "l5_update_wrapper_dict_builtins": (
        "O-3b",
        "import functools\n"
        + LATE13
        + "functools.update_wrapper(len.__self__, type('S', (), dict(helper=len)), "
        "assigned=(), updated=('__dict__',))\nrun()\n" + DEF13,
    ),
}

# One control per tree: the same shape without the code-object source or the
# builtins receiver still resolves to ``a.py``'s ``helper``.
FOLD13_CONTROLS = {
    "l1_dis_type_globals": G13 + "F = type(run)\nrun()\n",
    "l1_dis_lambda_type": G13 + "F = type(lambda: 0)\nrun()\n",
    "l1_dis_class_attr": G13 + "F = run.__class__\nrun()\n",
    "n31_dis_instr_nested_globals": NESTED13 + "outer()()\n",
    "n31_dis_computed_keys": G13 + "b = [run]\ng = {i: len for i in b}\nrun()\n",
    "n31_monitoring_code": G13 + "import sys\nseen = [sys.argv]\nrun()\n",
    "l2_fn_builtins_update_var": LATE13
    + "D = dict(helper=len)\nn = run.__name__\n"
    + DEF13
    + "run()\n",
    "n31_os_builtins_var": "import os\n"
    + LATE13
    + "D = dict(helper=len)\nos.environ.update(D)\n"
    + DEF13
    + "run()\n",
    "l2_self_builtins_update_var": LATE13
    + "D = dict(helper=len)\nn = len.__name__\n"
    + DEF13
    + "run()\n",
    "n31_self_getattr_str_var": LATE13
    + "D = dict(helper=len)\nn = getattr(print, '__name__')\n"
    + DEF13
    + "run()\n",
    # ``x |= {"helper": …}`` writes ``helper`` of any receiver since fold 18,
    # like ``x.update({…})``; the control writes another name.
    "n31_self_ior": LATE13 + "b = {}\nb |= {'other': len}\n" + DEF13 + "run()\n",
    "l5_update_wrapper_dict_builtins": "import functools\n"
    + LATE13
    + "functools.update_wrapper(run, type('S', (), dict(helper=len)), "
    "assigned=(), updated=())\n" + DEF13 + "run()\n",
}


@pytest.mark.parametrize("case", sorted(FOLD13_695))
def test_fold13_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, source = FOLD13_695[case]
    root = _tree(tmp_path, {"a.py": source, "b.py": _decoys(source)})
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == "a.py"]
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    assert [e for e in on["relationships"] if e["file"] == "a.py"] == off_calls


def test_fold13_controls_pair_with_the_trees() -> None:
    assert set(FOLD13_CONTROLS) == set(FOLD13_695)


@pytest.mark.parametrize("case", sorted(FOLD13_CONTROLS))
def test_fold13_controls_still_resolve(tmp_path: Path, case: str) -> None:
    source = FOLD13_CONTROLS[case]
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    on_edge = _helper_edge(on)
    assert on_edge["resolution"] == "resolved", case
    assert on_edge["provenance"]["call_rules"] == ["t1.lexical"]
    (target,) = on_edge["candidates"]
    assert on["symbol_lookup"][target]["file"] == "a.py"


@pytest.mark.parametrize(
    "form",
    [
        "b = f.__builtins__",
        "b = os.__builtins__",
        "b = len.__self__",
        "b = getattr(print, '__self__')",
        "b = getattr(f, '__built' 'ins__')",
        # The #695 re-check at 8fd7c1a2 (P-2): the builtins module by name.
        "b = inspect.builtins",
        "b = enum.bltns",
        "mock.patch('builtins.x', len)",
        "pydoc.locate('builtins')",
    ],
)
def test_builtins_reached_as_an_attribute_fail_closed(form: str) -> None:
    """``f.__builtins__``, ``os.__builtins__`` and ``len.__self__`` (the
    ``builtins`` module) reach the namespace a module-scope lookup falls back
    to before a module-level definition runs (#695 O-3b)."""
    source = HELPER + form + "\n\n\ndef use():\n    return helper()\n"
    assert reason(source) == "dynamic-scope", form


# ---------------------------------------------------------------------------
# The #695 re-check at 8fd7c1a2 (P-2, P-3): the ``builtins`` module reached as
# another module's attribute or a constant string (P-2a), as ``enum.bltns``
# (P-2b), a code object from the profiler (P-3a), and a function's live
# locals through ``inspect`` helpers (P-3b; PEP 667). Each tree is the
# ruling's own and runtime-traced: Python calls ``len``, and 8fd7c1a2 proved
# ``a.py``'s ``helper``.

GEN14 = (
    "def gen():\n    def helper(*a):\n        return 'loc'\n"
    "    yield 1\n    yield helper('ab')\n\n"
)
CO14 = (
    "async def co():\n    def helper(*a):\n        return 'loc'\n"
    "    await A()\n    return helper('ab')\n\n"
    "class A:\n    def __await__(self):\n        yield 1\n\n"
)
AG14 = (
    "async def ag():\n    def helper(*a):\n        return 'loc'\n"
    "    yield 1\n    yield helper('ab')\n\n"
)
STEP_AG14 = "try:\n    g.asend(None).send(None)\nexcept StopIteration:\n    pass\n"
STEP_CO14 = "try:\n    k.send(None)\nexcept StopIteration:\n    pass\n"
ARGV14 = (
    "import inspect\ndef run():\n    def helper(*a):\n        return 'loc'\n"
    "    {line}\n    return helper('ab')\n\nrun()\n"
)
# A nested ``helper`` elsewhere keeps a function-local proof's off-mode edge
# ambiguous.
OTHER14 = "def other():\n    def helper(*a):\n        return 3\n    return helper\n"

FOLD14_695: dict[str, tuple[str, str]] = {
    "q34_inspect_builtins_update": (
        "P-2a",
        "import inspect\n"
        + LATE13
        + "D = dict(helper=len)\ninspect.builtins.__dict__.update(D)\nrun()\n"
        + DEF13,
    ),
    "q34_site_builtins_ior": (
        "P-2a",
        "import site\n"
        + LATE13
        + "b = site.builtins.__dict__\nb |= {'helper': len}\nrun()\n"
        + DEF13,
    ),
    "q34_mock_patch_builtins": (
        "P-2a",
        "from unittest import mock\n"
        + LATE13
        + "mock.patch('builtins.helper', len, create=True).start()\nrun()\n"
        + DEF13,
    ),
    "q34_mock_patch_dict_builtins": (
        "P-2a",
        "from unittest import mock\n"
        + LATE13
        + "D = dict(helper=len)\nmock.patch.dict('builtins.__dict__', D).start()\n"
        "run()\n" + DEF13,
    ),
    "q34_pydoc_locate_builtins": (
        "P-2a",
        "import pydoc\n"
        + LATE13
        + "D = dict(helper=len)\npydoc.locate('builtins').__dict__.update(D)\n"
        "run()\n" + DEF13,
    ),
    "q34_resolve_name_builtins": (
        "P-2a",
        "import pkgutil\n"
        + LATE13
        + "D = dict(helper=len)\npkgutil.resolve_name('builtins').__dict__.update(D)\n"
        "run()\n" + DEF13,
    ),
    "q34_enum_bltns_update": (
        "P-2b",
        "import enum\n"
        + LATE13
        + "D = dict(helper=len)\nenum.bltns.__dict__.update(D)\nrun()\n"
        + DEF13,
    ),
    "q34_from_enum_bltns": (
        "P-2b",
        "from enum import bltns\n"
        + LATE13
        + "D = dict(helper=len)\nbltns.__dict__.update(D)\nrun()\n"
        + DEF13,
    ),
    "q34_cprofile_getstats_code": (
        "P-3a",
        G13 + "import cProfile\np = cProfile.Profile()\np.enable()\nrun()\n"
        "p.disable()\nc = [e.code for e in p.getstats() "
        "if 'code object run' in repr(e.code)][0]\n"
        "type(run)(c, {'helper': len})()\n",
    ),
    "g35_genlocals_update": (
        "P-3b",
        "import inspect\n" + GEN14 + "g = gen()\nnext(g)\nD = dict(helper=len)\n"
        "inspect.getgeneratorlocals(g).update(D)\nnext(g)\n",
    ),
    "g35_genlocals_ior": (
        "P-3b",
        "import inspect\n" + GEN14 + "g = gen()\nnext(g)\n"
        "L = inspect.getgeneratorlocals(g)\nL |= {'helper': len}\nnext(g)\n",
    ),
    "g35_genlocals_setitem": (
        "P-3b",
        "import inspect\n" + GEN14 + "g = gen()\nnext(g)\n"
        "inspect.getgeneratorlocals(g)['helper'] = len\nnext(g)\n",
    ),
    "g35_corolocals_update": (
        "P-3b",
        "import inspect\n" + CO14 + "k = co()\nk.send(None)\nD = dict(helper=len)\n"
        "inspect.getcoroutinelocals(k).update(D)\n" + STEP_CO14,
    ),
    "g35_asyncgenlocals_update": (
        "P-3b",
        "import inspect\n" + AG14 + "g = ag()\n" + STEP_AG14 + "D = dict(helper=len)\n"
        "inspect.getasyncgenlocals(g).update(D)\n" + STEP_AG14,
    ),
    "g35_argvalues_update": (
        "P-3b",
        "import inspect\ndef run():\n    def helper(*a):\n        return 'loc'\n"
        "    D = dict(helper=len)\n"
        "    inspect.getargvalues(inspect.currentframe()).locals.update(D)\n"
        "    return helper('ab')\n\nrun()\n",
    ),
}

# One control per tree: the same shape without the builtins module, the
# code-object source or the live-locals helper still resolves.
FOLD14_CONTROLS = {
    "q34_inspect_builtins_update": "import inspect\n"
    + LATE13
    + "D = dict(helper=len)\nx = inspect.signature\n"
    + DEF13
    + "run()\n",
    "q34_site_builtins_ior": "import site\n"
    + LATE13
    + "x = site.getsitepackages\nb = {}\nb |= {'other': len}\n"
    + DEF13
    + "run()\n",
    "q34_mock_patch_builtins": "from unittest import mock\n"
    + LATE13
    + "mock.patch('os.getcwd', len).start()\n"
    + DEF13
    + "run()\n",
    "q34_mock_patch_dict_builtins": "from unittest import mock\n"
    + LATE13
    + "D = dict(helper=len)\nmock.patch.dict('os.environ', D).start()\n"
    + DEF13
    + "run()\n",
    # Since fold 21 (E-20) any mention of ``pydoc.locate`` or
    # ``resolve_name`` fails closed, so these controls use another attribute.
    "q34_pydoc_locate_builtins": "import pydoc\n"
    + LATE13
    + "D = dict(helper=len)\nx = pydoc.render_doc\n"
    + DEF13
    + "run()\n",
    "q34_resolve_name_builtins": "import pkgutil\n" + LATE13 + "D = dict(helper=len)\n"
    "x = pkgutil.iter_modules\n" + DEF13 + "run()\n",
    "q34_enum_bltns_update": "import enum\n"
    + LATE13
    + "D = dict(helper=len)\nx = enum.Enum\n"
    + DEF13
    + "run()\n",
    "q34_from_enum_bltns": "from enum import Enum\n"
    + LATE13
    + "D = dict(helper=len)\nx = Enum\n"
    + DEF13
    + "run()\n",
    "q34_cprofile_getstats_code": G13
    + "import cProfile\np = cProfile.Profile()\np.enable()\nrun()\n"
    "p.disable()\np.print_stats()\n",
    "g35_genlocals_update": "import inspect\n"
    + GEN14
    + "g = gen()\nnext(g)\ns = inspect.getgeneratorstate(g)\nnext(g)\n",
    "g35_genlocals_ior": "import inspect\n"
    + GEN14
    + "g = gen()\nnext(g)\nL = {}\nL |= {'helper': len}\nnext(g)\n",
    "g35_genlocals_setitem": "import inspect\n"
    + GEN14
    + "g = gen()\nnext(g)\nL = {}\nL['helper'] = len\nnext(g)\n",
    "g35_corolocals_update": "import inspect\n"
    + CO14
    + "k = co()\nk.send(None)\ns = inspect.getcoroutinestate(k)\n"
    + STEP_CO14,
    "g35_asyncgenlocals_update": "import inspect\n"
    + AG14
    + "g = ag()\n"
    + STEP_AG14
    + "s = inspect.getasyncgenstate(g)\n"
    + STEP_AG14,
    "g35_argvalues_update": ARGV14.format(line="n = inspect.currentframe().f_lineno"),
}


def _other14(case: str, source: str) -> str:
    """``b.py`` for a tree: decoys for module-level proofs, a nested
    ``helper`` for the function-local (P-3b) ones."""
    return OTHER14 if case.startswith("g35_") else _decoys(source)


@pytest.mark.parametrize("case", sorted(FOLD14_695))
def test_fold14_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, source = FOLD14_695[case]
    root = _tree(tmp_path, {"a.py": source, "b.py": _other14(case, source)})
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == "a.py"]
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    assert [e for e in on["relationships"] if e["file"] == "a.py"] == off_calls


def test_fold14_controls_pair_with_the_trees() -> None:
    assert set(FOLD14_CONTROLS) == set(FOLD14_695)


@pytest.mark.parametrize("case", sorted(FOLD14_CONTROLS))
def test_fold14_controls_still_resolve(tmp_path: Path, case: str) -> None:
    source = FOLD14_CONTROLS[case]
    other = OTHER14 if case.startswith("g35_") else OTHER
    root = _tree(tmp_path, {"a.py": source, "b.py": other})
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    on_edge = _helper_edge(on)
    assert on_edge["resolution"] == "resolved", case
    assert on_edge["provenance"]["call_rules"] == ["t1.lexical"]
    (target,) = on_edge["candidates"]
    assert on["symbol_lookup"][target]["file"] == "a.py"


def test_getargvalues_alone_fails_closed() -> None:
    """Reading ``getargvalues(frame).args`` is harmless, but the name alone
    triggers: the one correct resolution fold 14 gives up (``g35_argvalues_ctrl``)."""
    source = ARGV14.format(line="n = inspect.getargvalues(inspect.currentframe()).args")
    assert reason(source) == "dynamic-scope"


# ---------------------------------------------------------------------------
# The #695 re-check at 14e8f044 (Q-2, Q-3): a call in an annotation, which
# ``annotationlib`` evaluates under substitute globals for the ``FORWARDREF``
# and ``STRING`` formats (Q-2), and reflective routes a name closes (Q-3).
# Each tree is the ruling's own and runtime-traced: 14e8f044 proved
# ``a.py``'s ``helper``, and Python called a stand-in or ``len`` instead.

DEF15 = "def helper(*a):\n    return 'mod'\n"
USER_FN15 = (
    "\ndef run(fmt=1, _n=[0]):\n    _n[0] += 1\n    if _n[0] == 1:\n"
    "        raise NotImplementedError\n    if _n[0] == 2:\n        raise ValueError\n"
    "    return helper('ab')\n\n"
)
TRY15 = "try:\n    {call}\nexcept Exception:\n    pass\n"

FOLD15_695: dict[str, tuple[str, str]] = {
    "a37_dataclass_late": (
        "Q-2",
        "from dataclasses import dataclass\n\n@dataclass\nclass C:\n"
        "    x: helper('ab')\n\n" + DEF15,
    ),
    "a37_class_fwdref_late": (
        "Q-2",
        "import annotationlib\n\nclass C:\n    x: helper('ab')\n\n"
        "annotationlib.get_annotations(C, format=annotationlib.Format.FORWARDREF)\n"
        + DEF15,
    ),
    "a37_func_fwdref_late": (
        "Q-2",
        "import annotationlib\n\ndef g(x: helper('ab')):\n    pass\n\n"
        "annotationlib.get_annotations(g, format=annotationlib.Format.FORWARDREF)\n"
        + DEF15,
    ),
    "a38_return_annot_late": (
        "Q-2",
        "import annotationlib\n\ndef g() -> helper('ab'):\n    pass\n\n"
        "annotationlib.get_annotations(g, format=annotationlib.Format.FORWARDREF)\n"
        + DEF15,
    ),
    "a37_inspect_signature_late": (
        "Q-2",
        "import inspect\n\ndef g(x: helper('ab')):\n    pass\n\n"
        "inspect.signature(g, annotation_format=inspect.Format.FORWARDREF)\n" + DEF15,
    ),
    "a37_typing_hints_late": (
        "Q-2",
        "import typing, annotationlib\n\nclass C:\n    x: helper('ab')\n\n"
        + TRY15.format(
            call="typing.get_type_hints(C, format=annotationlib.Format.FORWARDREF)"
        )
        + DEF15,
    ),
    "a38_singledispatch_late": (
        "Q-2",
        "import functools\n\n@functools.singledispatch\ndef f(x):\n    pass\n\n"
        "@f.register\ndef _(x: helper('ab')):\n    pass\n\n" + DEF15,
    ),
    "a37_func_string_early": (
        "Q-2 (mixed)",
        DEF15 + "\nimport annotationlib\n\ndef g(x: helper('ab')):\n    pass\n\n"
        "annotationlib.get_annotations(g, format=annotationlib.Format.STRING)\n",
    ),
    "a37_call_annotate_user_fn": (
        "Q-3",
        DEF15
        + USER_FN15
        + "import annotationlib\n"
        + TRY15.format(
            call="annotationlib.call_annotate_function(run, "
            "annotationlib.Format.STRING)"
        ),
    ),
    "a38_call_evaluate_user_fn": (
        "Q-3",
        DEF15
        + USER_FN15
        + "from annotationlib import call_evaluate_function as cef, Format\n"
        + TRY15.format(call="cef(run, Format.STRING)"),
    ),
    "a37_annotate_attr_user_fn": (
        "Q-3",
        DEF15
        + USER_FN15
        + "import annotationlib\nclass K:\n    pass\nK.__annotate__ = run\n"
        + TRY15.format(
            call="annotationlib.get_annotations(K, format=annotationlib.Format.STRING)"
        ),
    ),
    "a38_class_body_annotate": (
        "Q-3",
        DEF15
        + USER_FN15
        + "import annotationlib\nclass K:\n    __annotate__ = run\n"
        + TRY15.format(
            call="annotationlib.get_annotations(K, format=annotationlib.Format.STRING)"
        ),
    ),
    "t38_traceback_framesummary_code": (
        "Q-3",
        DEF15 + "\nimport traceback\nS = []\ndef run():\n"
        "    S.append(traceback.extract_stack(limit=1)[0])\n    return helper('ab')\n\n"
        "run()\ntype(run)(S[0]._code, {'helper': len, 'S': [], "
        "'traceback': traceback})()\n",
    ),
    "t38_bdb_code_linenos": (
        "Q-3",
        DEF15 + "\nimport bdb, inspect\nB = bdb.Bdb()\ndef run():\n"
        "    B._lineno_in_frame(10**6, inspect.currentframe())\n"
        "    return helper('ab')\n\nrun()\ncode = next(iter(B.code_linenos))\n"
        "type(run)(code, {'helper': len, 'B': B, 'inspect': inspect})()\n",
    ),
    "p38_pdb_curframe_locals": (
        "Q-3",
        "import pdb, inspect, warnings\nwarnings.simplefilter('ignore')\ndef run():\n"
        "    def helper(*a):\n        return 'loc'\n    p = pdb.Pdb()\n"
        "    p.curframe = inspect.currentframe()\n"
        "    p.curframe_locals['helper'] = len\n    return helper('ab')\n\nrun()\n",
    ),
}

# One control per tree: the call moved from the annotation into a value
# position (Q-2), or the reflective name left out (Q-3), still resolves.
_Q2_MOVES = (
    ("    x: helper('ab')\n", "    x: int = helper('ab')\n"),
    ("def g(x: helper('ab')):", "def g(x=helper('ab')):"),
    ("def g() -> helper('ab'):\n    pass", "def g() -> int:\n    return helper('ab')"),
    ("def _(x: helper('ab')):", "def _(x: int = helper('ab')):"),
)
_Q3_DROPS = {
    "a37_call_annotate_user_fn": (
        "annotationlib.call_annotate_function(run, annotationlib.Format.STRING)",
        "annotationlib.get_annotations(run)",
    ),
    "a38_call_evaluate_user_fn": (
        "call_evaluate_function as cef",
        "get_annotations as cef",
    ),
    "a37_annotate_attr_user_fn": ("K.__annotate__ = run", "K.attr = run"),
    "a38_class_body_annotate": ("    __annotate__ = run", "    attr = run"),
    "t38_traceback_framesummary_code": (
        "type(run)(S[0]._code, {'helper': len, 'S': [], 'traceback': traceback})()",
        "n = S[0].lineno",
    ),
    "t38_bdb_code_linenos": (
        "code = next(iter(B.code_linenos))\n"
        "type(run)(code, {'helper': len, 'B': B, 'inspect': inspect})()\n",
        "",
    ),
    "p38_pdb_curframe_locals": ("    p.curframe_locals['helper'] = len\n", ""),
}


def _fold15_control(case: str) -> str:
    _, source = FOLD15_695[case]
    if case in _Q3_DROPS:
        old, new = _Q3_DROPS[case]
        assert old in source, case
        return source.replace(old, new)
    for old, new in _Q2_MOVES:
        if old in source:
            return source.replace(old, new)
    raise AssertionError(case)


def _other15(case: str, source: str) -> str:
    return OTHER14 if case.startswith("p38_") else _decoys(source)


@pytest.mark.parametrize("case", sorted(FOLD15_695))
def test_fold15_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, source = FOLD15_695[case]
    root = _tree(tmp_path, {"a.py": source, "b.py": _other15(case, source)})
    off, on = _off_on(root)
    off_calls = [e for e in off["relationships"] if e["file"] == "a.py"]
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    assert [e for e in on["relationships"] if e["file"] == "a.py"] == off_calls


@pytest.mark.parametrize("case", sorted(FOLD15_695))
def test_fold15_controls_still_resolve(tmp_path: Path, case: str) -> None:
    source = _fold15_control(case)
    other = OTHER14 if case.startswith("p38_") else OTHER
    root = _tree(tmp_path, {"a.py": source, "b.py": other})
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    on_edge = _helper_edge(on)
    assert on_edge["resolution"] == "resolved", case
    assert on_edge["provenance"]["call_rules"] == ["t1.lexical"]
    (target,) = on_edge["candidates"]
    assert on["symbol_lookup"][target]["file"] == "a.py"


@pytest.mark.parametrize(
    "annotation",
    [
        "def f(x: helper()):\n    pass",
        "def f(x: helper() = 1):\n    pass",
        "def f(*x: helper()):\n    pass",
        "def f() -> helper():\n    pass",
        "x: helper()",
        "x: helper() = 1",
        "class K:\n    x: helper()",
        "def f():\n    x: helper() = 1",
        "def f(x: list[helper()]):\n    pass",
        # A correct resolution given up: ``helper`` is defined first, and a
        # ``VALUE``-format evaluation would call it (``a37_dataclass_early_ctrl``).
        "from dataclasses import dataclass\n@dataclass\nclass C:\n    x: helper()",
    ],
)
def test_annotations_prove_nothing(annotation: str) -> None:
    """``annotationlib`` evaluates annotation scopes under substitute globals
    for ``FORWARDREF``/``STRING`` (PEP 649/749), so a name in any annotation
    proves nothing (#695 Q-2)."""
    assert reason(HELPER + annotation + "\n") == "dynamic-scope", annotation


@pytest.mark.parametrize(
    "form",
    [
        "def f(x=helper()):\n    pass",
        "x: int = helper()",
        "def f() -> int:\n    return helper()",
        "class K:\n    x: int = helper()",
    ],
)
def test_values_next_to_annotations_still_resolve(form: str) -> None:
    assert proof_text(HELPER + form + "\n") == PROOF, form


# ---------------------------------------------------------------------------
# The #695 re-check at a6734480 (S-2, S-3): a class-body ``type`` value reads
# the live class namespace through ``__classdict__`` (PEP 695), so a later
# class write whose attribute name is not a literal at the write site
# rebinds it (S-2); ``__annotate_func__`` is the class-dict key behind
# ``type.__annotate__`` (S-3). Each tree is the ruling's own and
# runtime-traced: a6734480 proved ``a.py``'s ``helper``, and Python called
# ``len`` or a stand-in instead.

DEF16 = "def helper(*a):\n    return int\n"
ALIAS16 = "\nclass K:\n    type X = helper('ab')\n\n"
RUN16 = (
    "def run(fmt=1, _n=[0]):\n    _n[0] += 1\n    if _n[0] == 1:\n"
    "        raise NotImplementedError\n    if _n[0] == 2:\n        raise ValueError\n"
    "    return helper('ab')\n\n"
)
STRING16 = (
    "try:\n    annotationlib.get_annotations(K, format=annotationlib.Format.STRING)\n"
    "except Exception:\n    pass\n"
)

FOLD16_695: dict[str, tuple[str, str]] = {
    "ca40_var_name": (
        "S-2",
        DEF16 + ALIAS16 + "n = 'helper'\nsetattr(K, n, len)\nv = K.X.__value__\n",
    ),
    "ca40_star_args": (
        "S-2",
        DEF16 + ALIAS16 + "setattr(K, *('helper', len))\nv = K.X.__value__\n",
    ),
    "ca40_type_setattr_star": (
        "S-2",
        DEF16 + ALIAS16 + "type.__setattr__(K, *['helper', len])\nv = K.X.__value__\n",
    ),
    "ca40_kw_dict_items": (
        "S-2",
        DEF16
        + ALIAS16
        + "for k, f in dict(helper=len).items():\n    setattr(K, k, f)\n"
        "v = K.X.__value__\n",
    ),
    "ca40_func_param_name": (
        "S-2",
        DEF16 + ALIAS16 + "def put(cls, name, f):\n    setattr(cls, name, f)\n\n"
        "put(K, 'helper', len)\nv = K.X.__value__\n",
    ),
    "ca40_instance_class": (
        "S-2",
        DEF16
        + ALIAS16
        + "n = 'helper'\nsetattr(type(K()), n, len)\nv = K.X.__value__\n",
    ),
    "ca40_set_name": (
        "S-2",
        DEF16 + "\nclass D:\n    def __set_name__(self, owner, name):\n"
        "        setattr(owner, name[:-1], len)\n\n"
        "class K:\n    type X = helper('ab')\n    helperx = D()\n\nv = K.X.__value__\n",
    ),
    "ca40_generic_alias": (
        "S-2",
        DEF16 + "\nclass K:\n    type X[T] = helper('ab')\n\n"
        "n = 'helper'\nsetattr(K, n, len)\nv = K.X.__value__\n",
    ),
    "ca40_nested_class": (
        "S-2",
        DEF16 + "\nclass O:\n    class K:\n        type X = helper('ab')\n\n"
        "n = 'helper'\nsetattr(O.K, n, len)\nv = O.K.X.__value__\n",
    ),
    "ca40_generic_class": (
        "S-2",
        DEF16 + "\nclass K[T]:\n    type X = helper('ab')\n\n"
        "n = 'helper'\nsetattr(K, n, len)\nv = K.X.__value__\n",
    ),
    "ca40_in_function": (
        "S-2",
        DEF16 + "\ndef run():\n    class K:\n        type X = helper('ab')\n"
        "    n = 'helper'\n    setattr(K, n, len)\n    return K.X.__value__\n\nrun()\n",
    ),
    "ta39_alias_class_dict_update": (
        "S-2",
        DEF16 + ALIAS16 + "for name, f in [('helper', len)]:\n    setattr(K, name, f)\n"
        "v = K.X.__value__\n",
    ),
    "af39_class_body_annotate_func": (
        "S-3",
        DEF16
        + "\n"
        + RUN16
        + "import annotationlib\nclass K:\n    __annotate_func__ = run\n"
        + STRING16,
    ),
    "af39_attr_annotate_func": (
        "S-3",
        DEF16
        + "\n"
        + RUN16
        + "import annotationlib\nclass K:\n    pass\nK.__annotate_func__ = run\n"
        + STRING16,
    ),
    "af39_type3_annotate_func": (
        "S-3",
        DEF16
        + "\n"
        + RUN16
        + "import annotationlib\nK = type('K', (), {'__annotate_func__': run})\n"
        + STRING16,
    ),
    "af39_namedtuple_annotate_func": (
        "S-3",
        DEF16
        + "\n"
        + RUN16
        + "from typing import NamedTuple\ntry:\n    class P(NamedTuple):\n"
        "        __annotate_func__ = run\nexcept Exception:\n    pass\n",
    ),
}

# One control per tree: for S-2 the same write with the call in a method
# body, which a later class write cannot reach (``ca40_method_body_ctrl``);
# for S-3 the ``__annotate_func__`` install renamed (``af39_ctrl``).
_FOLD16_EDITS = {
    "ca40_generic_alias": ("    type X[T] = helper('ab')\n", None),
    "ca40_nested_class": (
        "        type X = helper('ab')\n",
        "        def m(self):\n            return helper('ab')\n",
    ),
    "ca40_in_function": (
        "        type X = helper('ab')\n",
        "        def m(self):\n            return helper('ab')\n",
    ),
    "af39_class_body_annotate_func": (
        "    __annotate_func__ = run\n",
        "    attr = run\n",
    ),
    "af39_attr_annotate_func": ("K.__annotate_func__ = run\n", "K.attr = run\n"),
    "af39_type3_annotate_func": ("{'__annotate_func__': run}", "{'attr': run}"),
    "af39_namedtuple_annotate_func": (
        "        __annotate_func__ = run\n",
        "        attr = run\n",
    ),
}
_S2_METHOD = "    def m(self):\n        return helper('ab')\n"


def _fold16_control(case: str) -> str:
    _, source = FOLD16_695[case]
    old, new = _FOLD16_EDITS.get(case, ("    type X = helper('ab')\n", None))
    assert old in source, case
    source = source.replace(old, _S2_METHOD if new is None else new)
    # Since fold 18 a literal ``*`` splat's constants are recorded like plain
    # arguments (``setattr(K, *('helper', len))`` writes ``helper`` of any
    # receiver), so these controls write another name.
    return source.replace("*('helper', len)", "*('other', len)").replace(
        "*['helper', len]", "*['other', len]"
    )


@pytest.mark.parametrize("case", sorted(FOLD16_695))
def test_fold16_695_cases_keep_their_off_mode_edge(tmp_path: Path, case: str) -> None:
    _, source = FOLD16_695[case]
    root = _tree(tmp_path, {"a.py": source, "b.py": _decoys(source)})
    off, on = _off_on(root)
    # Only the ``helper`` edge: ``ca40_set_name``'s local class ``D`` resolves
    # correctly against its decoy.
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    assert _helper_edge(on) == _helper_edge(off), case


# Since fold 19 (W-1) a writer with a computed name fails closed on any
# receiver, so these S-2 controls, which keep the tree's computed write, fail
# closed too; the rest still resolve.
FOLD16_COMPUTED_CONTROLS = frozenset(
    {
        "ca40_func_param_name",
        "ca40_generic_alias",
        "ca40_generic_class",
        "ca40_in_function",
        "ca40_instance_class",
        "ca40_kw_dict_items",
        "ca40_nested_class",
        "ca40_set_name",
        "ca40_var_name",
        "ta39_alias_class_dict_update",
    }
)


@pytest.mark.parametrize("case", sorted(FOLD16_COMPUTED_CONTROLS))
def test_fold16_computed_write_controls_fail_closed(tmp_path: Path, case: str) -> None:
    root = _tree(tmp_path, {"a.py": _fold16_control(case), "b.py": OTHER})
    off, on = _off_on(root)
    assert _helper_edge(on) == _helper_edge(off), case


@pytest.mark.parametrize("case", sorted(set(FOLD16_695) - FOLD16_COMPUTED_CONTROLS))
def test_fold16_controls_still_resolve(tmp_path: Path, case: str) -> None:
    source = _fold16_control(case)
    assert "type X" not in source and "__annotate_func__" not in source, case
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    assert _helper_edge(off)["resolution"] == "ambiguous", case
    on_edge = _helper_edge(on)
    assert on_edge["resolution"] == "resolved", case
    assert on_edge["provenance"]["call_rules"] == ["t1.lexical"]
    (target,) = on_edge["candidates"]
    assert on["symbol_lookup"][target]["file"] == "a.py"


@pytest.mark.parametrize(
    "form",
    [
        "class K:\n    type X = helper()",
        "class K:\n    type X[T] = helper()",
        "class K[T]:\n    type X = helper()",
        "class K:\n    type X = list[helper()]",
        "def f():\n    type X = helper()\n    return X",
        # Correct resolutions given up (no later write): ``ta39_alias_class_ctrl``,
        # ``ca40_ctrl_no_write`` and ``ta39_alias_func_closure_ctrl``.
        "class K:\n    type X = helper('ab')\n\nv = K.X.__value__",
        "def outer():\n    type X = helper('ab')\n    return X.__value__",
    ],
)
def test_type_statement_values_prove_nothing(form: str) -> None:
    """A ``type`` value is evaluated lazily (PEP 695); in a class body it
    reads the live class namespace (#695 S-2), so it proves nothing."""
    assert reason(HELPER + form + "\n") == "dynamic-scope", form


# ---------------------------------------------------------------------------
# Codex 4656123247 (fold 17): callees and receivers are classified after
# unwrapping parentheses. ``(setattr)(mod, 'helper', replacement)`` writes
# ``helper`` of a module handed over as ``mod``; Python then calls
# ``replacement`` from ``run``, and the analyzer must not prove ``helper``.

CODEX_4656123247 = (
    "def helper():\n    return 1\n\n\n"
    "def replacement():\n    return 2\n\n\n"
    "def run(mod):\n    {stmt}\n    return helper()\n"
)

# Each fails without the fix (the writer or module-getter check skipped a
# parenthesized callee or argument).
FOLD17_PARENTHESIZED = {
    # The Codex repro and its nested and commented forms (``_setattr_call``,
    # bare callee).
    "codex": "(setattr)(mod, 'helper', replacement)",
    "nested": "((setattr))(mod, 'helper', replacement)",
    "comment": "(setattr  # write\n    )(mod, 'helper', replacement)",
    "delattr": "(delattr)(mod, 'helper')",
    # ``_setattr_call``, an attribute callee in parentheses.
    "method": "(mod.__setattr__)('helper', replacement)",
    "object-setattr": "(object.__setattr__)(mod, 'helper', replacement)",
    "dict-update": "(mod.__dict__.update)({'helper': replacement})",
    "dict-update-keyword": "(mod.__dict__.update)(helper=replacement)",
    "dict-setitem": "(mod.__dict__.__setitem__)('helper', replacement)",
    "getattr-dict-update": "(getattr(mod, '__dict__').update)({'helper': replacement})",
    # ``_setattr_call``, a parenthesized argument.
    "dict-argument": "mod.__dict__.update(({'helper': replacement}))",
    "splat-argument": "mod.__dict__.update(**({'helper': replacement}))",
    # ``_module_by_name``, a parenthesized getter callee.
    "modules-get": "m = (mod.modules.get)(__name__)\n    m.__dict__.update(D)",
    "modules-getitem": "(mod.modules.__getitem__)(__name__).__dict__.update(D)",
}


@pytest.mark.parametrize("case", sorted(FOLD17_PARENTHESIZED))
def test_fold17_695_parenthesized_callees_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    source = CODEX_4656123247.format(stmt=FOLD17_PARENTHESIZED[case])
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    edge = _helper_edge(off)
    assert edge["resolution"] == "ambiguous", case
    assert _helper_edge(on) == edge, case


@pytest.mark.parametrize(
    "stmt",
    [
        # Mixed forms whose receiver alone is parenthesized: the callee is an
        # attribute already, or an identifier rule sees the name anywhere.
        "(mod).__setattr__('helper', replacement)",
        "(getattr(mod, '__dict__')).update({'helper': replacement})",
        "(vars(mod).update)({'helper': replacement})",
        "(mod).helper = replacement",
        "((mod.helper)) = replacement",
        "setattr(mod, ('helper'), replacement)",
        "(globals)()['helper'] = replacement",
        "(exec)('helper = replacement')",
        "import sys\n    (sys).modules[__name__].helper = replacement",
    ],
)
def test_parenthesized_receivers_already_fail_closed(stmt: str) -> None:
    result = outcome(CODEX_4656123247.format(stmt=stmt), "helper")
    assert result["outcome"] == "none", (stmt, result)


@pytest.mark.parametrize(
    "stmt",
    [
        # A write of another name proves nothing. (A trailing-comma tuple,
        # ``(setattr,)``, is not a parenthesized callee; since fold 18 the
        # tuple element hands ``setattr`` on and fails closed.)
        "(setattr)(mod, 'other', replacement)",
        "(mod.__dict__.update)({'other': replacement})",
    ],
)
def test_parenthesized_callee_controls_still_resolve(stmt: str) -> None:
    source = CODEX_4656123247.format(stmt=stmt)
    assert proof_text(source) == ["def helper():\n    return 1"], stmt


# ---------------------------------------------------------------------------
# Fold 18 (executive ruling on the fold-17 alias question): a writer handed
# on, a namespace mutator taken off its receiver, a computed write through a
# namespace dict, the ``operator`` writers and ``|=`` all use only spelled
# names and ordinary binding and call semantics, so each blocks. ``run(mod)``
# writes ``helper`` of the module handed over as ``mod``; Python then calls
# ``replacement``, and the analyzer must not prove ``helper``.

FOLD18_ALIASES = {
    # Rule 1: a writer anywhere but as the callee of a direct call.
    "r1-assign": "w = setattr\n    w(mod, 'helper', replacement)",
    "r1-walrus": "(w := setattr)(mod, 'helper', replacement)",
    "r1-conditional": "(setattr if mod else delattr)(mod, 'helper', replacement)",
    "r1-list-index": "[setattr][0](mod, 'helper', replacement)",
    "r1-tuple": "(setattr,)[0](mod, 'helper', replacement)",
    "r1-partial": "import functools\n    functools.partial(setattr, mod)('helper', replacement)",
    "r1-map": "list(map(setattr, [mod], ['helper'], [replacement]))",
    "r1-default": "def g(s=setattr):\n        return s\n    g()(mod, 'helper', replacement)",
    "r1-object-setattr": "f = object.__setattr__\n    f(mod, 'helper', replacement)",
    "r1-bound-setattr": "f = mod.__setattr__\n    f('helper', replacement)",
    "r1-delattr": "d = delattr\n    d(mod, 'helper')",
    "r1-string": "getattr(mod, '__setattr__')('helper', replacement)",
    # Literal ``*`` splats in a writer call (the constants are recorded).
    "splat": "setattr(mod, *('helper', replacement))",
    # Rule 2: a namespace mutator taken off its receiver.
    "r2-update": "u = mod.__dict__.update\n    u({'helper': replacement})",
    "r2-getattr-dict": "u = getattr(mod, '__dict__').update\n    u(helper=replacement)",
    "r2-setitem": "s = (mod.__dict__).__setitem__\n    s('helper', replacement)",
    "r2-setdefault": "s = mod.__dict__.setdefault\n    s('helper', replacement)",
    "r2-ior": "i = mod.__dict__.__ior__\n    i({'helper': replacement})",
    "r2-alias-receiver": "d = mod.__dict__\n    u = d.update\n    u({'helper': replacement})",
    # Computed writes through a namespace dict.
    "ns-update-mapping": "D = dict(helper=replacement)\n    mod.__dict__.update(D)",
    "ns-alias-update": "d = mod.__dict__\n    d.update(dict(helper=replacement))",
    "ns-computed-key": "k = 'helper'\n    mod.__dict__[k] = replacement",
    "ns-setdefault-key": "k = 'helper'\n    getattr(mod, '__dict__').setdefault(k, replacement)",
    # Rule 3: ``operator`` writers.
    "r3-setitem": "import operator\n    operator.setitem(mod.__dict__, 'helper', replacement)",
    "r3-from-import": "from operator import setitem as put\n"
    "    put(mod.__dict__, 'helper', replacement)",
    "r3-computed-key": "import operator\n    k = 'helper'\n"
    "    operator.setitem(mod.__dict__, k, replacement)",
    "r3-ior": "import operator\n    operator.ior(mod.__dict__, {'helper': replacement})",
    "r3-ior-computed": "import operator\n"
    "    operator.ior(mod.__dict__, dict(helper=replacement))",
    "r3-handed-on": "import operator, functools\n"
    "    functools.partial(operator.setitem, mod.__dict__)('helper', replacement)",
    # Rule 4: ``|=``.
    "r4-ior": "mod.__dict__ |= {'helper': replacement}",
    "r4-alias-ior": "d = mod.__dict__\n    d |= {'helper': replacement}",
    "r4-ior-computed": "mod.__dict__ |= dict(helper=replacement)",
}


@pytest.mark.parametrize("case", sorted(FOLD18_ALIASES))
def test_fold18_695_writer_aliases_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    source = CODEX_4656123247.format(stmt=FOLD18_ALIASES[case])
    root = _tree(tmp_path, {"a.py": source, "b.py": OTHER})
    off, on = _off_on(root)
    edge = _helper_edge(off)
    assert edge["resolution"] == "ambiguous", case
    assert _helper_edge(on) == edge, case


@pytest.mark.parametrize(
    "stmt",
    [
        # Rule 4: already caught before fold 18 (``vars`` is a trigger, a
        # constant subscript key is an attribute write).
        "vars(mod)['helper'] = replacement",
        "mod.__dict__['helper'] = replacement",
    ],
)
def test_namespace_subscript_writes_were_already_caught(stmt: str) -> None:
    result = outcome(CODEX_4656123247.format(stmt=stmt), "helper")
    assert result["outcome"] == "none", (stmt, result)


@pytest.mark.parametrize(
    "stmt",
    [
        # Mutator aliases and computed writes on ordinary receivers stay.
        "d = {}\n    u = d.update\n    u({'x': 1})",
        "cache = {}\n    p = cache.pop\n    p('helper', None)",
        "seen = {}\n    D = {}\n    seen.update(D)",
        "s = set()\n    s |= {1}",
        "k = 'x'\n    cache = {}\n    cache[k] = 1",
        # ``operator`` writers on an ordinary receiver, or handed on in a
        # file that names no namespace dict.
        "import operator\n    cache = {}\n    operator.setitem(cache, 'x', 1)",
        "import operator, functools\n    f = functools.partial(operator.setitem, {})",
        # Defining ``__setattr__`` and calling the writer directly with a
        # constant name (a computed name fails closed since fold 19, W-1).
        "class K:\n        def __setattr__(self, k, v):\n"
        "            super().__setattr__('x', v)",
        # A namespace dict read, and a literal write of another name (passing
        # it to a call escapes since fold 19, W-2).
        "n = mod.__dict__.get('x')\n    mod.__dict__.update({'other': replacement})",
    ],
)
def test_ordinary_mutator_aliases_still_resolve(stmt: str) -> None:
    source = CODEX_4656123247.format(stmt=stmt)
    assert proof_text(source) == ["def helper():\n    return 1"], stmt


# ---------------------------------------------------------------------------
# Fold 19 (the president's re-check at 1d6cbb17, U-3..U-5, and executive
# ruling E-19): computed writes are closed at the write site. B-1/W-4
# constant strings through comments, parentheses and constant f-strings;
# B-2 unbound mutators, mutators taken by name, conditional/boolean/tuple/
# match aliases; W-1 a writer with a computed name on any receiver; W-2 a
# namespace dict that escapes; W-3 ``unittest.mock`` patches with a computed
# target. The probe trees are the president's own (``mine/p44.py``..``p47.py``),
# each wrong at 1d6cbb17 under a runtime trace.

FOLD19_T = (
    "def helper(*a):\n    return 1\n\n\n"
    "def replacement(*a):\n    return 2\n\n\n"
    "def run(mod):\n    {stmt}\n    return helper()\n"
)
FOLD19_H = "def helper(*a):\n    return 1\n\n\ndef replacement(*a):\n    return 2\n\n\n"
FOLD19_R = "\n\ndef run():\n    return helper()\n"
FOLD19_DECOY = "def helper(*a):\n    return 3\n"

FOLD19_RUN = {
    "f17_comment_concat": "setattr(mod, 'hel'  # c\n        'per', replacement)",
    "f17_comment_plus": "setattr(mod, 'hel' + ('per'  # c\n        ), replacement)",
    "f18_attrgetter_update": "import operator\n    operator.attrgetter('__dict__.update')(mod)({'helper': replacement})",
    "f18_attrgetter_update_D": "import operator\n    D = dict(helper=replacement)\n    operator.attrgetter('__dict__.update')(mod)(D)",
    "f18_chainmap": "import collections\n    D = dict(helper=replacement)\n    collections.ChainMap(mod.__dict__).update(D)",
    "f18_chainmap_k": "import collections\n    k = 'helper'\n    collections.ChainMap(mod.__dict__)[k] = replacement",
    "f18_comprehension": "D = dict(helper=replacement)\n    [d.update(D) for d in [mod.__dict__]]",
    "f18_conditional_recv": "D = dict(helper=replacement)\n    (mod.__dict__ if mod else {}).update(D)",
    "f18_default_recv": "D = dict(helper=replacement)\n    def g(d=mod.__dict__):\n        d.update(D)\n    g()",
    "f18_dict_ior": "D = dict(helper=replacement)\n    dict.__ior__(mod.__dict__, D)",
    "f18_dict_or_eq_alias": "D = dict(helper=replacement)\n    x = [mod.__dict__]\n    x[0] |= D",
    "f18_dict_update": "D = dict(helper=replacement)\n    dict.update(mod.__dict__, D)",
    "f18_for_target": "D = dict(helper=replacement)\n    for d in [mod.__dict__]:\n        d.update(D)",
    "f18_getattr_update_D": "D = dict(helper=replacement)\n    getattr(mod.__dict__, 'update')(D)",
    "f18_inplace_or": "import operator\n    D = dict(helper=replacement)\n    operator.__ior__(mod.__dict__, D)",
    "f18_lambda_recv": "D = dict(helper=replacement)\n    (lambda d: d.update(D))(mod.__dict__)",
    "f18_list_elem": "D = dict(helper=replacement)\n    [mod.__dict__][0].update(D)",
    "f18_match_capture": "D = dict(helper=replacement)\n    match mod.__dict__:\n        case d:\n            d.update(D)",
    "f18_methodcaller_update": "import operator\n    operator.methodcaller('update', {'helper': replacement})(mod.__dict__)",
    "f18_methodcaller_update_ref": "import operator\n    D = {'helper': replacement}\n    operator.methodcaller('update', D)(mod.__dict__)",
    "f18_or_recv": "D = dict(helper=replacement)\n    (mod.__dict__ or {}).update(D)",
    "f18_setattr_computed": "n = 'helper'\n    setattr(mod, n, replacement)",
    "f18_splat_all_var": "t = (mod, 'helper', replacement)\n    setattr(*t)",
    "f18_splat_var": "t = ('helper', replacement)\n    setattr(mod, *t)",
    "f18_tuple_unpack": "D = dict(helper=replacement)\n    d, = (mod.__dict__,)\n    d.update(D)",
    "f18_tuple_unpack2": "D = dict(helper=replacement)\n    d, e = mod.__dict__, 0\n    d.update(D)",
    "f18_type_update": "D = dict(helper=replacement)\n    type(mod.__dict__).update(mod.__dict__, D)",
    "f18_with_as": "import contextlib\n    D = dict(helper=replacement)\n    with contextlib.nullcontext(mod.__dict__) as d:\n        d.update(D)",
    "al_cond_assign": "D = dict(helper=replacement)\n    d = mod.__dict__ if mod else {}\n    d.update(D)",
    "al_getattr_setattr_comment": "getattr(mod, '__set'  # c\n        'attr__')('helper', replacement)",
    "al_pkgdict_values": "D = dict(helper=replacement)\n    import collections\n    collections.ChainMap(mod.__dict__).maps[0].update(D)",
    "mp_patch_dict_handed": "from unittest import mock\n    mock.patch.dict(mod.__dict__, helper=replacement).start()",
    "mp_patch_dict_handed_D": "from unittest import mock\n    D = dict(helper=replacement)\n    mock.patch.dict(mod.__dict__, D).start()",
    "mp_patch_object_handed": "from unittest import mock\n    mock.patch.object(mod, 'helper', replacement).start()",
}
FOLD19_MODULE = {
    "acq_collections_sys_modules": "import collections\nm = collections._sys.modules[helper.__module__]\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_comment_globals": "g = getattr(helper, '__glo'  # c\n    'bals__')\nn = 'helper'\ng[n] = replacement\n",
    "acq_logging_resolve": "import logging.config\nm = logging.config._resolve(__name__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_mock_patch_dict": "from unittest import mock\nD = dict(helper=replacement)\nmock.patch.dict(__name__ + '.__dict__', D).start()\n",
    "acq_mock_patch_dict_lit": "from unittest import mock\nmock.patch.dict(__name__ + '.__dict__', {'helper': replacement}).start()\n",
    "acq_mock_patch_fstring": "from unittest import mock\nmock.patch(f'{__name__}.helper', replacement).start()\n",
    "acq_mock_patch_module_attr": "from unittest import mock\nmock.patch(helper.__module__ + '.' + 'helper', replacement).start()\n",
    "acq_mock_patch_name_concat": "from unittest import mock\nmock.patch(__name__ + '.helper', replacement).start()\n",
    "acq_mock_patch_object": "from unittest import mock\nimport pkgutil\nmock.patch.object(pkgutil.resolve_name(__name__), 'helper', replacement).start()\n",
    "acq_pickle_find_class": "import pickle, io\nm = pickle.Unpickler(io.BytesIO()).find_class('pkgutil', 'resolve_name')(__name__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_pydoc_locate_module": "import pydoc\nm = pydoc.locate(run.__module__) if 0 else pydoc.locate(helper.__module__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_pydoc_safeimport": "import pydoc\nm = pydoc.safeimport(__name__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_resolve_name_module": "import pkgutil\nm = pkgutil.resolve_name(helper.__module__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_resolve_name_name": "import pkgutil\nm = pkgutil.resolve_name(__name__)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "acq_spec_name": "import pkgutil\nm = pkgutil.resolve_name(__spec__.name)\nn = 'helper'\nsetattr(m, n, replacement)\n",
    "cs_concat_comment": "g = getattr(helper, '__glo'  # c\n    'bals__')\nn = 'helper'\ng[n] = replacement\n",
    "cs_concat_comment_paren": "g = getattr(helper, ('__glo'  # c\n    'bals__'))\nn = 'helper'\ng[n] = replacement\n",
    "cs_fstring_const_interp": "g = getattr(helper, f\"__glo{'bals'}__\")\nn = 'helper'\ng[n] = replacement\n",
    "cs_plus_paren_comment": "g = getattr(helper, '__glo' + ('bals__'  # c\n    ))\nn = 'helper'\ng[n] = replacement\n",
}
FOLD19_TREES = {
    "acq_pkg_getattr_rpartition": {
        "pkg/__init__.py": "",
        "pkg/a.py": "def helper(*a):\n    return 1\n\n\ndef replacement(*a):\n    return 2\n\n\nimport pkg\n\ndef run():\n    m = getattr(pkg, __name__.rpartition('.')[2])\n    n = 'helper'\n    setattr(m, n, replacement)\n    return helper()\n",
    },
    "acq_pkg_modname_module": {
        "pkg/__init__.py": "",
        "pkg/a.py": "def helper(*a):\n    return 1\n\n\ndef replacement(*a):\n    return 2\n\n\nimport pkg\n\ndef run():\n    m = getattr(pkg, helper.__module__.split('.')[-1])\n    n = 'helper'\n    setattr(m, n, replacement)\n    return helper()\n",
    },
    "acq_pkg_rel_parent": {
        "pkg/__init__.py": "",
        "pkg/a.py": "def helper(*a):\n    return 1\n\n\ndef replacement(*a):\n    return 2\n\n\nfrom . import __name__ as _x\nimport pkgutil\n\ndef run():\n    m = pkgutil.resolve_name(__package__ + ':' + helper.__module__.rpartition('.')[2])\n    n = 'helper'\n    setattr(m, n, replacement)\n    return helper()\n",
    },
    "pk_parent_dict_values": {
        "pkg/__init__.py": "",
        "pkg/a.py": "def helper(*a):\n    return 1\n\n\ndef replacement(*a):\n    return 2\n\n\nimport pkg\n\ndef run():\n    for m in list(pkg.__dict__.values()):\n        if getattr(m, '__file__', None) == __file__:\n            n = 'helper'\n            setattr(m, n, replacement)\n    return helper()\n",
    },
}


# One case per W rule beyond the probes (W-1 spellings, W-2 positions, W-3
# import forms), in ``run(mod)`` form.
FOLD19_RULES = {
    # B-2a: ``operator.__iadd__`` (and ``__ior__``) with a literal mapping
    # records its keys on any receiver.
    "b2a-iadd-any-receiver": "import operator\n"
    "    operator.__iadd__(mod, {'helper': replacement})",
    # B-2c: ``methodcaller`` with a mutator name in a file naming a
    # namespace dict, applied without passing the dict.
    "b2c-methodcaller": "x = mod.__dict__.get('x')\n    import operator\n"
    "    operator.methodcaller('update', dict(helper=replacement))(mod)",
    "w1-bound": "n = 'helper'\n    mod.__setattr__(n, replacement)",
    "w1-unbound": "n = 'helper'\n    object.__setattr__(mod, n, replacement)",
    "w1-delattr": "n = 'helper'\n    delattr(mod, n)",
    "w1-parenthesized": "n = 'helper'\n    (setattr)(mod, n, replacement)",
    "w2-return": "def g():\n        return mod.__dict__\n    g().update(dict(helper=replacement))",
    "w2-yield": "def g():\n        yield mod.__dict__\n    next(g()).update(dict(helper=replacement))",
    "w2-attribute-target": "class K:\n        pass\n    K.ns = mod.__dict__\n"
    "    K.ns.update(dict(helper=replacement))",
    "w2-keyword": "def g(ns):\n        ns.update(dict(helper=replacement))\n    g(ns=mod.__dict__)",
    "w2-walrus-argument": "def g(ns):\n        ns.update(dict(helper=replacement))\n"
    "    g(d := mod.__dict__)",
    "b2-walrus-receiver": "(d := mod.__dict__).update(dict(helper=replacement))",
    "w3-decorator": "from unittest import mock\n"
    "    @mock.patch(mod.__name__ + '.helper', replacement)\n    def g():\n        pass",
    "w3-from-import-alias": "from unittest.mock import patch as p\n"
    "    p(mod.__name__ + '.helper', replacement).start()",
    "w3-dotted": "import unittest.mock\n"
    "    unittest.mock.patch(mod.__name__ + '.helper', replacement).start()",
    "w3-handed-on": "from unittest import mock\n    p = mock.patch\n"
    "    p(mod.__name__ + '.helper', replacement).start()",
    "w3-object-constant": "from unittest import mock\n"
    "    mock.patch.object(mod, 'helper', replacement).start()",
    "w3-multiple": "from unittest import mock\n"
    "    mock.patch.multiple(mod, helper=replacement).start()",
}


def _fold19_edge(graph: dict[str, Any], target: str) -> dict[str, Any]:
    (edge,) = (
        edge
        for edge in graph["relationships"]
        if edge["type"] == "calls"
        and edge["file"] == target
        and edge["reference"] == "helper"
    )
    return edge


def _fold19_tree(case: str) -> tuple[dict[str, str], str]:
    if case in FOLD19_RUN:
        return {"a.py": FOLD19_T.format(stmt=FOLD19_RUN[case])}, "a.py"
    if case in FOLD19_RULES:
        return {"a.py": FOLD19_T.format(stmt=FOLD19_RULES[case])}, "a.py"
    if case in FOLD19_MODULE:
        return {"a.py": FOLD19_H + FOLD19_MODULE[case] + FOLD19_R}, "a.py"
    files = dict(FOLD19_TREES[case])
    return files, "pkg/a.py"


FOLD19_CASES = sorted(
    set(FOLD19_RUN) | set(FOLD19_MODULE) | set(FOLD19_TREES) | set(FOLD19_RULES)
)


@pytest.mark.parametrize("case", FOLD19_CASES)
def test_fold19_695_computed_writes_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    files, target = _fold19_tree(case)
    files["b.py"] = FOLD19_DECOY
    root = _tree(tmp_path, files)
    off, on = _off_on(root)
    edge = _fold19_edge(off, target)
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, target) == edge, case


@pytest.mark.parametrize(
    "stmt",
    [
        # Constant-name writers on ordinary receivers record one name.
        "class K:\n        pass\n    setattr(K, 'x', 1)",
        "class K:\n        pass\n    K().__setattr__('x', 1)",
        "class K:\n        pass\n    object.__setattr__(K(), 'x', 1)",
        # Ordinary ``.update`` aliases and computed writes elsewhere.
        "d = {}\n    u = d.update\n    u({'helper': 1})",
        "k = 'helper'\n    cache = {}\n    cache[k] = 1",
        # Namespace dict reads.
        "x = mod.__dict__.get('x')\n    y = 'x' in mod.__dict__\n"
        "    z = list(mod.__dict__.keys())",
        # ``unittest.mock`` with constant targets elsewhere, and a ``patch``
        # method that is not ``unittest.mock``'s.
        "from unittest import mock\n    mock.patch('os.getcwd', len).start()",
        "from unittest import mock\n    class K:\n        x = 1\n"
        "    mock.patch.object(K, 'x', 2).start()",
        "class S:\n        def patch(self, url):\n            pass\n"
        "    u = 'http://x'\n    S().patch(u)",
        # An f-string with a computed interpolation is no constant.
        "n = 'x'\n    v = getattr(mod, f'{n}')",
    ],
)
def test_fold19_controls_still_resolve(stmt: str) -> None:
    source = FOLD19_T.format(stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], stmt


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("'__glo'  # c\n  'bals__'", "__globals__"),
        ("('__glo'  # c\n  'bals__')", "__globals__"),
        ("'__glo' + ('bals__'  # c\n  )", "__globals__"),
        ("f\"__glo{'bals'}__\"", "__globals__"),
        ('f\'a{{b}}{"c" "d"}\'', "a{b}cd"),
        ("f'{x}'", None),
        ("f'{\"c\"!r}'", None),
        ("f'{\"c\":>3}'", None),
    ],
)
def test_fold19_constant_strings(text: str, value: str | None) -> None:
    source = f"x = ({text})\n".encode()
    root = get_parser("python").parse(source).root_node
    right = root.named_children[0].named_children[0].child_by_field_name("right")
    assert py_scope._constant_string(right, source) == value


# ---------------------------------------------------------------------------
# Fold 20: receiver-based patchers join W-3. Any ``X.patch.object``,
# ``X.patch.dict`` or ``X.patch.multiple`` chain (a), ``.patch`` on a
# pytest-mock fixture (b), and either handed on (c) follow ``unittest.mock``'s
# rules: a computed target or attribute fails closed, a constant
# ``patch.object`` attribute and ``patch.multiple`` keywords are writes.

FOLD20_T = (
    "def helper(*a):\n    return 1\n\n\n"
    "def replacement(*a):\n    return 2\n\n\n"
    "def run(mod, x, mocker, module_mocker, session_mocker, client):\n"
    "    n = 'helper'\n    {stmt}\n    return helper()\n"
)

FOLD20_PATCHERS = {
    # (a) ``X.patch.object``/``dict``/``multiple`` for any ``X``.
    "a-object-computed": "x.patch.object(mod, n, replacement)",
    "a-object-constant": "x.patch.object(mod, 'helper', replacement)",
    "a-dict-computed": "t = mod\n    x.patch.dict(t, helper=replacement)",
    "a-multiple": "x.patch.multiple(mod, helper=replacement)",
    "a-parenthesized": "(x.patch).object(mod, n, replacement)",
    # (b) ``.patch`` on a pytest-mock fixture.
    "b-mocker": "mocker.patch(mod.__name__ + '.helper', replacement)",
    "b-module-mocker": "module_mocker.patch(mod.__name__ + '.helper', replacement)",
    "b-session-mocker-object": "session_mocker.patch.object(mod, n, replacement)",
    "b-parenthesized": "(mocker).patch(mod.__name__ + '.helper', replacement)",
    # (c) handed on.
    "c-mocker-patch": "p = mocker.patch\n    p(mod.__name__ + '.helper', replacement)",
    "c-any-object": "o = x.patch.object\n    o(mod, 'helper', replacement)",
}


@pytest.mark.parametrize("case", sorted(FOLD20_PATCHERS))
def test_fold20_695_receiver_patchers_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    source = FOLD20_T.format(stmt=FOLD20_PATCHERS[case])
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


@pytest.mark.parametrize(
    "stmt",
    [
        # A plain ``.patch(url)`` on other receivers (HTTP clients).
        "u = 'http://x'\n    client.patch(u)",
        "u = 'http://x'\n    x.patch(u, json={})",
        "import requests\n    u = 'http://x'\n    requests.patch(u, data=n)",
        # Patchers with constant targets or another attribute name.
        "mocker.patch('os.getcwd', len)",
        "x.patch.object(client, 'other', 1)",
        "mocker.patch.multiple(client, other=1)",
    ],
)
def test_fold20_plain_patch_calls_still_resolve(stmt: str) -> None:
    source = FOLD20_T.format(stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], stmt


# ---------------------------------------------------------------------------
# Fold 21 (the president's re-check at bb8b75b4, V-4/V-5/V-7, and executive
# ruling E-20). B-4: a namespace alias read back as an attribute (``m.NS``,
# ``K.ns``, ``self.ns``, ``getattr(K, 'ns')``) is a namespace receiver. B-5:
# mock-module and pytest-mock aliases are tracked, a mock-module name in any
# other position fails closed, and so does a constant ``'patch'`` in a file
# importing the mock module. E-20: stdlib resolver mentions, a ``'__dict__'``
# subscript key and ``X._sys.modules`` fail closed. The module is handed in
# (``run(mod)``) so that no resolver trigger fires in the B-4/B-5 cases.

FOLD21_T = (
    "{pre}def helper(*a):\n    return 1\n\n\n"
    "def replacement(*a):\n    return 2\n\n\n"
    "def run(mod, mocker, client):\n    {stmt}\n    return helper()\n"
)
FOLD21_MOCK = "from unittest import mock\n\n\n"
FOLD21_TARGET = "mod.__name__ + '.helper', replacement"

FOLD21_CASES = {
    # B-4 (the six V-4 shapes, on a handed-in module).
    "b4-global-alias": (
        "NS = None\n\n\n",
        "global NS\n    NS = mod.__dict__\n    mod.NS.update(dict(helper=replacement))",
    ),
    "b4-module-level": (
        "import types\nNS = types.ModuleType('x').__dict__\n\n\n",
        "mod.NS.update(dict(helper=replacement))",
    ),
    "b4-class-body-subscript": (
        "",
        "class K:\n        ns = mod.__dict__\n    k = 'helper'\n    K.ns[k] = replacement",
    ),
    "b4-class-body-update": (
        "",
        "class K:\n        ns = mod.__dict__\n    K.ns.update(dict(helper=replacement))",
    ),
    "b4-class-body-getattr-dict": (
        "",
        "class K:\n        ns = getattr(mod, '__dict__')\n"
        "    K.ns.update(dict(helper=replacement))",
    ),
    "b4-self": (
        "",
        "class K:\n        ns = mod.__dict__\n        def put(self, D):\n"
        "            self.ns.update(D)\n    K().put(dict(helper=replacement))",
    ),
    "b4-getattr-alias": (
        "",
        "class K:\n        ns = mod.__dict__\n"
        "    getattr(K, 'ns').update(dict(helper=replacement))",
    ),
    # B-5 (the V-5 shapes, and the pytest-mock aliases).
    "b5-alias": (FOLD21_MOCK, f"mk = mock\n    mk.patch({FOLD21_TARGET}).start()"),
    "b5-walrus": (FOLD21_MOCK, f"(mk := mock).patch({FOLD21_TARGET}).start()"),
    "b5-tuple": (
        FOLD21_MOCK,
        f"mk, x = mock, 1\n    mk.patch({FOLD21_TARGET}).start()",
    ),
    "b5-class-attr": (
        FOLD21_MOCK,
        f"class K:\n        mk = mock\n    K.mk.patch({FOLD21_TARGET}).start()",
    ),
    "b5-self-attr": (
        FOLD21_MOCK,
        "class T:\n        def __init__(self):\n            self.mk = mock\n"
        f"    T().mk.patch({FOLD21_TARGET}).start()",
    ),
    "b5-getattr": (FOLD21_MOCK, f"getattr(mock, 'patch')({FOLD21_TARGET}).start()"),
    "b5-attrgetter": (
        FOLD21_MOCK,
        f"import operator\n    operator.attrgetter('patch')(mock)({FOLD21_TARGET}).start()",
    ),
    "b5-namespace-key": (
        FOLD21_MOCK,
        f"mock.__dict__['patch']({FOLD21_TARGET}).start()",
    ),
    "b5-mocker-alias": ("", f"mm = mocker\n    mm.patch({FOLD21_TARGET})"),
    "b5-self-mocker": (
        "",
        "class T:\n        def __init__(self, mocker):\n            self.mocker = mocker\n"
        f"    T(mocker).mocker.patch({FOLD21_TARGET})",
    ),
    # E-20 triggers.
    "t-resolve-name": ("", "import pkgutil\n    x = pkgutil.resolve_name"),
    "t-from-pkgutil": ("", "from pkgutil import resolve_name as rn"),
    "t-pydoc-locate": ("", "import pydoc\n    x = pydoc.locate"),
    "t-from-pydoc": ("", "from pydoc import locate"),
    "t-pydoc-safeimport": ("", "import pydoc as p\n    x = p.safeimport"),
    "t-logging-resolve": ("", "import logging.config\n    x = logging.config._resolve"),
    "t-logging-importer": ("", "from logging import config\n    x = config._importer"),
    "t-from-logging-config": ("", "from logging.config import _resolve"),
    "t-find-class": ("", "import pickle\n    x = pickle.Unpickler.find_class"),
    "t-resolver-string": (
        "",
        "import pkgutil\n    x = getattr(pkgutil, 'resolve_name')",
    ),
    "t-dict-key": ("", "import types\n    d = types.ModuleType.__dict__['__dict__']"),
    "t-sys-modules": (
        "",
        "import collections\n    m = collections._sys.modules[helper.__module__]",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD21_CASES))
def test_fold21_695_writes_and_triggers_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, stmt = FOLD21_CASES[case]
    source = FOLD21_T.format(pre=pre, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


@pytest.mark.parametrize(
    ("pre", "stmt"),
    [
        # Unrelated functions and methods named like the resolvers.
        ("", "def locate(*a):\n        return 0\n    locate(1)"),
        (
            "",
            "class G:\n        def locate(self):\n            return 0\n    G().locate()",
        ),
        (
            "",
            "class G:\n        def _resolve(self):\n            return 0\n    G()._resolve()",
        ),
        # A plain ``.patch(url)``, and ordinary ``.update`` aliases.
        ("", "u = 'http://x'\n    client.patch(u)"),
        ("", "d = {}\n    u = d.update\n    u({'x': 1})"),
        # The mock module used as a receiver, and ``'patch'`` without it.
        (FOLD21_MOCK, "m = mock.Mock()\n    m.patch('x')"),
        ("", "x = 'patch'"),
        # A class attribute that is no namespace alias.
        ("", "class K:\n        ns = {}\n    K.ns.update(dict(x=1))"),
    ],
)
def test_fold21_controls_still_resolve(pre: str, stmt: str) -> None:
    source = FOLD21_T.format(pre=pre, stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], stmt


# ---------------------------------------------------------------------------
# Fold 22 (the president's re-check at 78812ad2, W-5..W-7, and the executive
# direction to unify): one alias/readback/escape mechanism for every
# sensitive kind (a namespace dict, the mock module, ``patch``, a pytest-mock
# fixture). The module is handed in, so no resolver trigger fires.

FOLD22_T = (
    "{pre}def helper(*a):\n    return 1\n\n\n"
    "def replacement(*a):\n    return 2\n\n\n"
    "def run(mod, mocker, client):\n    {stmt}\n    return helper()\n"
)
FOLD22_TARGET = "mod.__name__ + '.helper', replacement"

# One case per president probe in W-5, W-6 and W-7.
FOLD22_PROBES = {
    # W-5: the mock module through an alias of the ``unittest`` package.
    "w5-unittest-as": (
        "import unittest as ut\nimport unittest.mock\n\n\n",
        f"ut.mock.patch({FOLD22_TARGET}).start()",
    ),
    "w5-unittest-decorator": (
        "import unittest as ut\nimport unittest.mock\n\n\n",
        f"@ut.mock.patch({FOLD22_TARGET})\n    def g():\n        pass\n    g()",
    ),
    "w5-unittest-alias": (
        "import unittest\nimport unittest.mock\n\n\n",
        f"u = unittest\n    u.mock.patch({FOLD22_TARGET}).start()",
    ),
    "w5-unittest-class-attr": (
        "import unittest\nimport unittest.mock\n\n\n",
        f"class K:\n        ut = unittest\n    K.ut.mock.patch({FOLD22_TARGET}).start()",
    ),
    # W-5: a constant ``'mock'`` in a file that imports the mock module.
    "w5-mock-namespace-key": (
        "import unittest\nimport unittest.mock\n\n\n",
        f"unittest.__dict__['mock'].patch({FOLD22_TARGET}).start()",
    ),
    "w5-getattr-mock": (
        "import unittest\nimport unittest.mock\n\n\n",
        f"getattr(unittest, 'mock').patch({FOLD22_TARGET}).start()",
    ),
    # W-6: mocker aliases beyond plain assignment.
    "w6-mocker-tuple": ("", f"mm, _ = mocker, 0\n    mm.patch({FOLD22_TARGET})"),
    "w6-mocker-walrus": ("", f"(mm := mocker).patch({FOLD22_TARGET})"),
    "w6-mocker-conditional": (
        "",
        f"mm = mocker if mod else None\n    mm.patch({FOLD22_TARGET})",
    ),
    "w6-mocker-for": (
        "",
        f"for mm in (mocker,):\n        mm.patch({FOLD22_TARGET})",
    ),
    "w6-mocker-setattr": (
        "",
        f"class T:\n        pass\n    setattr(T, 'mm', mocker)\n    T.mm.patch({FOLD22_TARGET})",
    ),
    "w6-mocker-list": ("", f"[mocker][0].patch({FOLD22_TARGET})"),
    "w6-mocker-local-helper": (
        "def _p(x, t, r):\n    x.patch(t, r)\n\n\n",
        f"_p(mocker, {FOLD22_TARGET})",
    ),
    "w8-getattr-mocker-patch": ("", f"getattr(mocker, 'patch')({FOLD22_TARGET})"),
    # W-7: a class-body namespace alias read back through the class.
    "w7-class-dict-update": (
        "",
        "class K:\n        ns = mod.__dict__\n"
        "    K.__dict__['ns'].update(dict(helper=replacement))",
    ),
    "w7-class-dict-key": (
        "",
        "class K:\n        ns = mod.__dict__\n"
        "    k = 'hel' + 'per'\n    K.__dict__['ns'][k] = replacement",
    ),
    "w7-type-getattribute": (
        "",
        "class K:\n        ns = mod.__dict__\n"
        "    type.__getattribute__(K, 'ns').update(dict(helper=replacement))",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD22_PROBES))
def test_fold22_695_president_probes_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, stmt = FOLD22_PROBES[case]
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


# The cross-kind matrix: every binding, readback and escape form x every
# sensitive kind fails closed. ``{V}`` is the kind's value and ``{R}`` the
# readback the form produces; each kind's use writes ``helper`` through it.
FOLD22_KINDS = {
    "namespace": ("", "mod.__dict__", "{R}.update(dict(helper=replacement))"),
    "mock": (
        "from unittest import mock\n\n\n",
        "mock",
        "{R}.patch(" + FOLD22_TARGET + ").start()",
    ),
    "patch": (
        "from unittest import mock\n\n\n",
        "mock.patch",
        "{R}(" + FOLD22_TARGET + ").start()",
    ),
    "mocker": ("", "mocker", "{R}.patch(" + FOLD22_TARGET + ")"),
}
FOLD22_FORMS = {
    # Alias binding.
    "assign": ("a = {V}", "a"),
    "tuple-target": ("a, _ = {V}, 0", "a"),
    "list-target": ("[a, _] = [{V}, 0]", "a"),
    "starred-target": ("a, *_ = {V}, 0", "a"),
    "walrus": ("", "(a := {V})"),
    "conditional": ("a = {V} if mod else None", "a"),
    "boolean": ("a = {V} or None", "a"),
    "for": ("for a in ({V},):\n        pass", "a"),
    "with": (
        "import contextlib\n    with contextlib.nullcontext({V}) as a:\n        pass",
        "a",
    ),
    "match": ("match {V}:\n        case a:\n            pass", "a"),
    "class-body": ("class K:\n        a = {V}", "K.a"),
    "attribute-target": ("class T:\n        pass\n    t = T()\n    t.a = {V}", "t.a"),
    "global": ("global A\n    A = {V}", "A"),
    "nonlocal": (
        "a = None\n    def _set():\n        nonlocal a\n        a = {V}\n    _set()",
        "a",
    ),
    "setattr": ("class K:\n        pass\n    setattr(K, 'a', {V})", "K.a"),
    # Readback.
    "readback-getattr": ("class K:\n        a = {V}", "getattr(K, 'a')"),
    "readback-getattribute": (
        "class K:\n        a = {V}",
        "type.__getattribute__(K, 'a')",
    ),
    "readback-subscript": ("class K:\n        a = {V}", "K.__dict__['a']"),
    "readback-attrgetter": (
        "import operator\n    class K:\n        a = {V}",
        "operator.attrgetter('a')(K)",
    ),
    # Escape.
    "escape-argument": ("def _id(x):\n        return x\n    a = _id({V})", "a"),
    "escape-container": ("box = [{V}]", "box[0]"),
    "escape-return": ("def g():\n        return {V}", "g()"),
}
FOLD22_MATRIX = sorted((kind, form) for kind in FOLD22_KINDS for form in FOLD22_FORMS)


@pytest.mark.parametrize(("kind", "form"), FOLD22_MATRIX)
def test_fold22_695_cross_kind_matrix_fails_closed(kind: str, form: str) -> None:
    """Every binding, readback and escape form fails closed for every
    sensitive kind (#695 fold 22): the class of bug where a form handled for
    one kind is missed for another cannot recur."""
    pre, value, use = FOLD22_KINDS[kind]
    setup, readback = FOLD22_FORMS[form]
    setup = setup.replace("{V}", value)
    readback = readback.replace("{V}", value)
    stmt = (setup + "\n    " if setup else "") + use.replace("{R}", readback)
    if form == "global":
        pre += "A = None\n\n\n"
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert reason(source) == "dynamic-scope", (kind, form)


@pytest.mark.parametrize(
    ("pre", "stmt"),
    [
        # Ordinary ``.update`` aliases, a plain ``.patch(url)``, ``mock.Mock()``,
        # a local ``def locate``.
        ("", "d = {}\n    u = d.update\n    u({'x': 1})"),
        ("", "u = 'http://x'\n    client.patch(u)"),
        ("from unittest import mock\n\n\n", "m = mock.Mock()\n    m.foo(1)"),
        ("", "def locate(*a):\n        return 0\n    locate(1)"),
        # A namespace dict read through a call does not carry it
        # (``string/__init__.py``). ``signal.__dict__.items()``
        # (``multiprocessing/process.py``) fails closed since fold 24 (Y-6).
        ("", "class C:\n        pass\n    p = C.__dict__.get('p', None)\n    q = (p,)"),
    ],
)
def test_fold22_controls_still_resolve(pre: str, stmt: str) -> None:
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], stmt


# ---------------------------------------------------------------------------
# Fold 23 (the president's re-check at 515de38e, X-5..X-7, and executive
# ruling E-21): the uses of a sensitive value are a CLOSED ALLOW-LIST
# (``py_scope._NS_READS``/``_NS_WRITES``/``_MOCK_SAFE``/``_MOCKER_SAFE``/
# ``_PATCH_SAFE`` and ``_safe_use``); every other use fails closed.

FOLD23_MOCK = "from unittest import mock\n\n\n"
FOLD23_PROBES = {
    # X-5: ``__ior__``/``ior`` returns the namespace itself.
    "x5-ior-method": (
        "",
        "k = 'hel' + 'per'\n    x = mod.__dict__.__ior__({})\n    x[k] = replacement",
    ),
    "x5-ior-inline": (
        "",
        "k = 'hel' + 'per'\n    mod.__dict__.__ior__({})[k] = replacement",
    ),
    "x5-dict-ior": (
        "",
        "k = 'hel' + 'per'\n    x = dict.__ior__(mod.__dict__, {})\n    x[k] = replacement",
    ),
    "x5-operator-ior": (
        "",
        "import operator\n    k = 'hel' + 'per'\n"
        "    x = operator.ior(mod.__dict__, {})\n    x[k] = replacement",
    ),
    "x5-operator-dunder-ior": (
        "",
        "import operator\n    k = 'hel' + 'per'\n"
        "    x = operator.__ior__(mod.__dict__, {})\n    x[k] = replacement",
    ),
    "x5-from-operator-ior": (
        "from operator import ior\n\n\n",
        "k = 'hel' + 'per'\n    x = ior(mod.__dict__, {})\n    x[k] = replacement",
    ),
    # X-6: class-pattern keywords read an attribute of the subject.
    "x6-match-dict-subscript": (
        "",
        "k = 'hel' + 'per'\n    match mod:\n        case object(__dict__=x):\n"
        "            x[k] = replacement",
    ),
    "x6-match-dict-update": (
        "",
        "k = 'hel' + 'per'\n    match mod:\n        case object(__dict__=x):\n"
        "            x.update({k: replacement})",
    ),
    "x6-match-dict-later": (
        "",
        "k = 'hel' + 'per'\n    match mod:\n        case object(__dict__=x):\n"
        "            pass\n    x[k] = replacement",
    ),
    "x6-match-mock-patch": (
        FOLD23_MOCK,
        f"match mock:\n        case object(patch=p):\n            p({FOLD22_TARGET}).start()",
    ),
    "x6-match-mocker-patch": (
        "",
        f"match mocker:\n        case object(patch=p):\n            p({FOLD22_TARGET})",
    ),
    "x6-match-unittest-mock": (
        "import unittest\nimport unittest.mock\n\n\n",
        f"match unittest:\n        case object(mock=x):\n            x.patch({FOLD22_TARGET}).start()",
    ),
    # X-7: ``patch`` read back through ``__call__`` or ``__get__``.
    "x7-mocker-patch-call": ("", f"mocker.patch.__call__({FOLD22_TARGET})"),
    "x7-mocker-patch-call-alias": (
        "",
        f"p = mocker.patch.__call__\n    p({FOLD22_TARGET})",
    ),
    "x7-mock-patch-call": (
        FOLD23_MOCK,
        f"mock.patch.__call__({FOLD22_TARGET}).start()",
    ),
    "x7-mock-patch-call-alias": (
        FOLD23_MOCK,
        f"p = mock.patch\n    p.__call__({FOLD22_TARGET}).start()",
    ),
    "x7-patch-call": (
        "from unittest.mock import patch\n\n\n",
        f"patch.__call__({FOLD22_TARGET}).start()",
    ),
    "x7-patch-get": (
        FOLD23_MOCK,
        f"p = mock.patch.__get__(None, object)\n    p({FOLD22_TARGET}).start()",
    ),
    # X-8: ``mocker.mock_module`` is the mock module.
    "x8-mocker-mock-module": ("", f"mocker.mock_module.patch({FOLD22_TARGET}).start()"),
}


@pytest.mark.parametrize("case", sorted(FOLD23_PROBES))
def test_fold23_695_president_probes_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, stmt = FOLD23_PROBES[case]
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


# The allow-list is closed: per kind, uses not on it fail closed.
FOLD23_VALUES = {
    "namespace": ("", "mod.__dict__"),
    "mock": (FOLD23_MOCK, "mock"),
    "patch": (FOLD23_MOCK, "mock.patch"),
    "mocker": ("", "mocker"),
}
FOLD23_UNLISTED = {
    "dunder-call": "x = {V}.__call__",
    "dunder-get": "x = {V}.__get__",
    "dunder-ior-used": "x = {V}.__ior__({{}})",
    "dunder-class": "x = {V}.__class__",
    "copy": "x = {V}.copy()",
    "fromkeys": "x = {V}.fromkeys(['a'])",
    "dunder-or": "x = {V}.__or__({{}})",
    "mock-module": "x = {V}.mock_module",
    "foo": "x = {V}.foo",
    "match-subject": "match {V}:\n        case _:\n            pass",
    "bare-statement": "{V}",
}
FOLD23_COMPLETENESS = sorted(
    (kind, use) for kind in FOLD23_VALUES for use in FOLD23_UNLISTED
)


@pytest.mark.parametrize(("kind", "use"), FOLD23_COMPLETENESS)
def test_fold23_695_allow_list_is_closed(kind: str, use: str) -> None:
    pre, value = FOLD23_VALUES[kind]
    stmt = FOLD23_UNLISTED[use].replace("{V}", value).replace("{{}}", "{}")
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert reason(source) == "dynamic-scope", (kind, use)


# Each A-1 entry, used safely, still resolves (or records its constant name).
FOLD23_SAFE = {
    # Namespace reads.
    "ns-subscript-read": ("", "x = mod.__dict__['other']"),
    "ns-get": ("", "x = mod.__dict__.get('other', None)"),
    "ns-keys": ("", "x = list(mod.__dict__.keys())"),
    "ns-in": ("", "x = 'other' in mod.__dict__"),
    "ns-len": ("", "x = len(mod.__dict__)"),
    # Namespace writes of another name, as statements.
    "ns-update": ("", "mod.__dict__.update({'other': 1})"),
    "ns-setdefault": ("", "mod.__dict__.setdefault('other', 1)"),
    "ns-pop": ("", "mod.__dict__.pop('other', None)"),
    "ns-subscript-write": ("", "mod.__dict__['other'] = 1"),
    "ns-del": ("", "del mod.__dict__['other']"),
    "ns-ior": ("", "ns = mod.__dict__\n    ns |= {'other': 1}"),
    "ns-dict-update": ("", "dict.update(mod.__dict__, {'other': 1})"),
    "ns-operator-setitem": (
        "",
        "import operator\n    operator.setitem(mod.__dict__, 'other', 1)",
    ),
    "ns-alias": ("", "ns = mod.__dict__\n    x = ns.get('other')"),
    # The mock module's constructors and constants.
    **{
        f"mock-{name}": (FOLD23_MOCK, f"x = mock.{name}")
        for name in sorted(py_scope._MOCK_SAFE)
    },
    # A fixture's helpers.
    **{
        f"mocker-{name}": ("", f"x = mocker.{name}")
        for name in sorted(py_scope._MOCKER_SAFE)
    },
    # ``patch`` with constant targets elsewhere.
    "patch-call": (FOLD23_MOCK, "mock.patch('os.getcwd', len).start()"),
    "patch-object": (FOLD23_MOCK, "mock.patch.object(client, 'other', 1).start()"),
    "patch-dict": (FOLD23_MOCK, "mock.patch.dict('os.environ', {'X': '1'}).start()"),
    "patch-multiple": (FOLD23_MOCK, "mock.patch.multiple(client, other=1).start()"),
    "mocker-patch": ("", "mocker.patch('os.getcwd', len)"),
}


@pytest.mark.parametrize("case", sorted(FOLD23_SAFE))
def test_fold23_695_allow_list_entries_still_resolve(case: str) -> None:
    pre, stmt = FOLD23_SAFE[case]
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], case


@pytest.mark.parametrize(
    "stmt",
    [
        "mod.__dict__.update({'helper': 1})",
        "mod.__dict__.setdefault('helper', 1)",
        "mod.__dict__['helper'] = 1",
        "ns = mod.__dict__\n    ns |= {'helper': 1}",
        "import operator\n    operator.setitem(mod.__dict__, 'helper', 1)",
    ],
)
def test_fold23_695_allow_listed_writes_record_their_name(stmt: str) -> None:
    source = FOLD22_T.format(pre="", stmt=stmt)
    assert reason(source) == "mixed-bindings", stmt


# ---------------------------------------------------------------------------
# Fold 24 (the president's re-check at e9c087d9, Y-5 and Y-6): an import of
# the mock module or ``patch``, in any spelling and at any scope, is an alias
# (its readbacks carry the kind), and ``values()``/``items()`` on a namespace
# dict are off THE CLOSED ALLOW-LIST.

FOLD24_PROBES = {
    # Y-5: the file's own import read back through the module or a class.
    "y5-attr-patch-canon": (
        "from unittest.mock import patch\n\n\n",
        f"mod.patch({FOLD22_TARGET}).start()",
    ),
    "y5-attr-mock-as": (
        "from unittest import mock as mk\n\n\n",
        f"mod.mk.patch({FOLD22_TARGET}).start()",
    ),
    "y5-attr-patch-as-object": (
        "from unittest.mock import patch as P\n\n\n",
        "k = 'hel' + 'per'\n    mod.P.object(mod, k, replacement).start()",
    ),
    "y5-attr-import-as": (
        "import unittest.mock as um\n\n\n",
        f"mod.um.patch({FOLD22_TARGET}).start()",
    ),
    "y5-attr-patch-as": (
        "from unittest.mock import patch as P\n\n\n",
        f"mod.P({FOLD22_TARGET}).start()",
    ),
    "y5-getattr-import-as": (
        "import unittest.mock as um\n\n\n",
        f"getattr(mod, 'um').patch({FOLD22_TARGET}).start()",
    ),
    "y5-ns-subscript-import-as": (
        "import unittest.mock as um\n\n\n",
        f"mod.__dict__['um'].patch({FOLD22_TARGET}).start()",
    ),
    "y5-ns-get-import-as": (
        "import unittest.mock as um\n\n\n",
        f"mod.__dict__.get('um').patch({FOLD22_TARGET}).start()",
    ),
    "y5-ns-subscript-patch-as": (
        "from unittest.mock import patch as P\n\n\n",
        f"mod.__dict__['P']({FOLD22_TARGET}).start()",
    ),
    "y5-ns-get-patch-as": (
        "from unittest.mock import patch as P\n\n\n",
        f"mod.__dict__.get('P')({FOLD22_TARGET}).start()",
    ),
    "y5-match-keyword-import-as": (
        "import unittest.mock as um\n\n\n",
        "match mod:\n        case object(um=x):\n"
        f"            x.patch({FOLD22_TARGET}).start()",
    ),
    "y5-class-mock-as": (
        "class K:\n    from unittest import mock as mk\n\n\n",
        f"K.mk.patch({FOLD22_TARGET}).start()",
    ),
    "y5-class-patch-as": (
        "class K:\n    from unittest.mock import patch as P\n\n\n",
        f"K.P({FOLD22_TARGET}).start()",
    ),
    # Y-6: iterating the namespace hands over the file's own sensitive values.
    "y6-items-patch-as": (
        "from unittest.mock import patch as P\n\n\n",
        "[v for kk, v in mod.__dict__.items() if kk == 'P'][0]"
        f"({FOLD22_TARGET}).start()",
    ),
    "y6-items-patch-as-loop": (
        "from unittest.mock import patch as P\n\n\n",
        "for kk, v in mod.__dict__.items():\n        if kk == 'P':\n"
        f"            v({FOLD22_TARGET}).start()",
    ),
    "y6-items-import-as": (
        "import unittest.mock as um\n\n\n",
        "for kk, v in mod.__dict__.items():\n        if kk == 'u' + 'm':\n"
        f"            v.patch({FOLD22_TARGET}).start()",
    ),
    "y6-items-patch-canon-join": (
        "from unittest.mock import patch\n\n\n",
        "for kk, v in mod.__dict__.items():\n        if kk == 'patc' + chr(104):\n"
        f"            v({FOLD22_TARGET}).start()",
    ),
    "y6-values-mock-canon": (
        FOLD23_MOCK,
        "for v in mod.__dict__.values():\n"
        "        if getattr(v, '__name__', '') == 'unittest.' + 'mo' + chr(99) + 'k':\n"
        f"            v.patch({FOLD22_TARGET}).start()",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD24_PROBES))
def test_fold24_695_president_probes_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, stmt = FOLD24_PROBES[case]
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


# The completeness matrix's "import binding read back" rows: every import
# spelling of the mock module or ``patch``, read back by every readback form.
FOLD24_IMPORTS = {
    "from-unittest-import-mock": ("from unittest import mock", "mock", "mock"),
    "from-unittest-import-mock-as": ("from unittest import mock as mk", "mk", "mock"),
    "import-unittest-mock-as": ("import unittest.mock as um", "um", "mock"),
    "import-mock": ("import mock", "mock", "mock"),
    "import-mock-as": ("import mock as mk", "mk", "mock"),
    "from-unittest-mock-import-patch": (
        "from unittest.mock import patch",
        "patch",
        "patch",
    ),
    "from-unittest-mock-import-patch-as": (
        "from unittest.mock import patch as P",
        "P",
        "patch",
    ),
    "from-mock-import-patch": ("from mock import patch", "patch", "patch"),
    "from-mock-import-patch-as": ("from mock import patch as P", "P", "patch"),
}
FOLD24_READBACKS = {
    "attribute": "mod.{N}",
    "getattr": "getattr(mod, '{N}')",
    "ns-subscript": "mod.__dict__['{N}']",
    "ns-get": "mod.__dict__.get('{N}')",
    "match-keyword": "match mod:\n        case object({N}=x):\n            pass\n    x",
    "class-attribute": "K.{N}",
}
FOLD24_MATRIX = sorted(
    (spelling, form) for spelling in FOLD24_IMPORTS for form in FOLD24_READBACKS
)


@pytest.mark.parametrize(("spelling", "form"), FOLD24_MATRIX)
def test_fold24_695_import_bindings_are_aliases(spelling: str, form: str) -> None:
    statement, name, kind = FOLD24_IMPORTS[spelling]
    readback = FOLD24_READBACKS[form].replace("{N}", name)
    use = (
        f"{readback}.patch({FOLD22_TARGET}).start()"
        if kind == "mock"
        else f"{readback}({FOLD22_TARGET}).start()"
    )
    pre = (
        f"class K:\n    {statement}\n\n\n"
        if form == "class-attribute"
        else f"{statement}\n\n\n"
    )
    source = FOLD22_T.format(pre=pre, stmt=use)
    assert reason(source) == "dynamic-scope", (spelling, form)


# Y-6: ``values()`` and ``items()`` are off the list for every kind, whether
# or not the file imports the mock module.
@pytest.mark.parametrize(
    ("kind", "method"),
    sorted((kind, method) for kind in FOLD23_VALUES for method in ("values", "items")),
)
def test_fold24_695_namespace_iteration_fails_closed(kind: str, method: str) -> None:
    pre, value = FOLD23_VALUES[kind]
    source = FOLD22_T.format(pre=pre, stmt=f"x = list({value}.{method}())")
    assert reason(source) == "dynamic-scope", (kind, method)


def test_fold24_695_stdlib_signal_items_fails_closed() -> None:
    # ``multiprocessing/process.py``: the one stdlib file Y-6 costs.
    source = FOLD22_T.format(
        pre="import signal\n\n\n",
        stmt="for name, num in list(signal.__dict__.items()):\n        x = (name, num)",
    )
    assert reason(source) == "dynamic-scope"


@pytest.mark.parametrize(
    ("pre", "stmt"),
    [
        # A plain ``.patch(url)`` with a computed URL in a file that imports
        # ``patch`` under another name, or imports only the mock module.
        (
            "from unittest.mock import patch as P\n\n\n",
            "u = 'http://x'\n    client.patch(u)",
        ),
        ("import unittest.mock as um\n\n\n", "u = 'http://x'\n    client.patch(u)"),
        (FOLD23_MOCK, "u = 'http://x'\n    client.patch(u)"),
        # With a constant URL even beside the canonical ``patch`` import.
        ("from unittest.mock import patch\n\n\n", "client.patch('http://x')"),
        # Direct uses of the import names stay on the list.
        ("from unittest.mock import patch as P\n\n\n", "P('os.getcwd', len).start()"),
        ("from unittest import mock as mk\n\n\n", "m = mk.Mock()\n    m.foo(1)"),
        (
            "import unittest.mock as um\n\n\n",
            "um.patch.object(client, 'other', 1).start()",
        ),
        ("class K:\n    from unittest import mock as mk\n\n\n", "x = 1"),
        # ``keys()`` stays: keys are strings.
        ("from unittest.mock import patch\n\n\n", "x = list(mod.__dict__.keys())"),
        (
            "from unittest.mock import patch as P\n\n\n",
            "x = sorted(mod.__dict__.keys())",
        ),
    ],
)
def test_fold24_695_controls_still_resolve(pre: str, stmt: str) -> None:
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], stmt


def test_fold24_695_canonical_patch_import_makes_any_x_patch_patch() -> None:
    # The A-4 cost: beside ``from unittest.mock import patch``, ``X.patch``
    # is spelled like the readback ``mod.patch``, so a computed target fails
    # closed whatever ``X`` is (0 stdlib and repository test files).
    source = FOLD22_T.format(
        pre="from unittest.mock import patch\n\n\n",
        stmt="u = 'http://x'\n    client.patch(u)",
    )
    assert reason(source) == "dynamic-scope"


# ---------------------------------------------------------------------------
# Fold 25 (Codex 4657695001 at ab49156a): an allow-listed callee is verified
# by binding. ``len`` and ``dict`` must be the builtins (bound nowhere in the
# file, no recorded write of the name), ``operator`` and its writers must come
# from a tracked import of ``operator`` and nothing else.

FOLD25_CODEX = "def len(d):\n    d.update(dict(helper=replacement))\n    return 0\n\n\n"
# One allow-list entry per callee spelled by name: (relied name, imports, use).
FOLD25_ENTRIES = {
    "len": ("len", "", "x = len(mod.__dict__)"),
    "dict-update": ("dict", "", "dict.update(mod.__dict__, {'other': 1})"),
    "dict-setdefault": ("dict", "", "dict.setdefault(mod.__dict__, 'other', 1)"),
    "dict-pop": ("dict", "", "dict.pop(mod.__dict__, 'other', None)"),
    "dict-setitem": ("dict", "", "dict.__setitem__(mod.__dict__, 'other', 1)"),
    "dict-delitem": ("dict", "", "dict.__delitem__(mod.__dict__, 'other')"),
    "dict-ior": ("dict", "", "dict.__ior__(mod.__dict__, {'other': 1})"),
    "operator-setitem": (
        "operator",
        "import operator\n\n\n",
        "operator.setitem(mod.__dict__, 'other', 1)",
    ),
    "operator-delitem": (
        "operator",
        "import operator\n\n\n",
        "operator.delitem(mod.__dict__, 'other')",
    ),
    "operator-ior": (
        "operator",
        "import operator\n\n\n",
        "operator.ior(mod.__dict__, {'other': 1})",
    ),
    "operator-as": (
        "op",
        "import operator as op\n\n\n",
        "op.setitem(mod.__dict__, 'other', 1)",
    ),
    "from-operator-setitem": (
        "setitem",
        "from operator import setitem\n\n\n",
        "setitem(mod.__dict__, 'other', 1)",
    ),
    "from-operator-as": (
        "s",
        "from operator import setitem as s\n\n\n",
        "s(mod.__dict__, 'other', 1)",
    ),
}
# Each shadowing binding form of the relied name ``{N}``.
FOLD25_SHADOWS = {
    "def": "def {N}(*a, **k):\n    return 0\n\n\n",
    "assignment": "{N} = print\n\n\n",
    "import-alias": "from os import getcwd as {N}\n\n\n",
    "parameter": "def shadow({N}):\n    return {N}\n\n\n",
    "for-target": "for {N} in (print,):\n    pass\n\n\n",
    "global": "def shadow():\n    global {N}\n    {N} = print\n\n\n",
    "recorded-write": "def shadow(m):\n    m.{N} = print\n\n\n",
    # Bound only in the scope pass's view (not a syntactic binding position).
    "with-tuple-target": "with open(__file__) as (a, {N}):\n    pass\n\n\n",
    "type-parameter": "def shadow[{N}]():\n    return 0\n\n\n",
}
FOLD25_PROBES = {
    "codex-4657695001": (FOLD25_CODEX, "len(mod.__dict__)"),
    "type-of-namespace": ("", "type(mod.__dict__).update(mod.__dict__, {'other': 1})"),
    "other-receiver": (
        "class U:\n    @staticmethod\n    def update(d, *a):\n"
        "        d.update(dict(helper=replacement))\n\n\n",
        "U.update(mod.__dict__, {'other': 1})",
    ),
    "bare-writer-no-import": ("", "setitem(mod.__dict__, 'other', 1)"),
    "from-other-module": (
        "from os import setitem\n\n\n",
        "setitem(mod.__dict__, 'other', 1)",
    ),
    "other-module-as-operator": (
        "import os as operator\n\n\n",
        "operator.setitem(mod.__dict__, 'other', 1)",
    ),
    **{
        f"{entry}-{shadow}": (
            imports + FOLD25_SHADOWS[shadow].replace("{N}", name),
            use,
        )
        for entry, (name, imports, use) in FOLD25_ENTRIES.items()
        for shadow in FOLD25_SHADOWS
    },
}


@pytest.mark.parametrize("case", sorted(FOLD25_PROBES))
def test_fold25_695_shadowed_allowlist_callees_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, stmt = FOLD25_PROBES[case]
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


# Unshadowed, every entry still resolves.
@pytest.mark.parametrize("entry", sorted(FOLD25_ENTRIES))
def test_fold25_695_verified_callees_still_resolve(entry: str) -> None:
    _name, imports, use = FOLD25_ENTRIES[entry]
    source = FOLD22_T.format(pre=imports, stmt=use)
    assert proof_text(source) == ["def helper(*a):\n    return 1"], entry


# ... and a verified writer still records the name it writes.
@pytest.mark.parametrize(
    ("pre", "stmt"),
    [
        ("", "dict.update(mod.__dict__, {'helper': 1})"),
        ("import operator\n\n\n", "operator.setitem(mod.__dict__, 'helper', 1)"),
        ("from operator import setitem\n\n\n", "setitem(mod.__dict__, 'helper', 1)"),
    ],
)
def test_fold25_695_verified_callees_record_their_name(pre: str, stmt: str) -> None:
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert reason(source) == "mixed-bindings", stmt


# Producers and writers named by spelling over-recognize when shadowed, so
# they stay closed: a shadowed ``vars``/``getattr`` still yields a namespace
# kind; a shadowed ``setattr`` still records its constant name, and the
# module it receives is no sensitive kind (a same-file body's writes on it
# are recorded or fail closed on any receiver); a rebound ``patch`` import
# still counts as ``patch``.
@pytest.mark.parametrize(
    ("pre", "stmt"),
    [
        (
            "def vars(o):\n    return {}\n\n\n",
            "k = 'hel' + 'per'\n    vars(mod)[k] = replacement",
        ),
        (
            "def getattr(o, n):\n    return {}\n\n\n",
            "k = 'hel' + 'per'\n    getattr(mod, '__dict__')[k] = replacement",
        ),
        (
            "def setattr(o, n, v):\n    o.__dict__.update({n: v})\n\n\n",
            "setattr(mod, 'other', replacement)",
        ),
        (
            "def setattr(o, n, v):\n    vars(o)[n] = v\n\n\n",
            "setattr(mod, 'other', replacement)",
        ),
        (
            "from unittest.mock import patch\n\n\npatch = print\n\n\n",
            f"patch({FOLD22_TARGET})",
        ),
    ],
)
def test_fold25_695_shadowed_producers_still_fail_closed(pre: str, stmt: str) -> None:
    source = FOLD22_T.format(pre=pre, stmt=stmt)
    assert reason(source) == "dynamic-scope", stmt


def test_fold25_695_shadowed_setattr_body_writes_are_recorded() -> None:
    source = FOLD22_T.format(
        pre="def setattr(o, n, v):\n    o.helper = v\n\n\n",
        stmt="setattr(mod, 'other', replacement)",
    )
    assert reason(source) == "mixed-bindings"


# ---------------------------------------------------------------------------
# Fold 26 (the president's re-check at 1b4d112f, AA-4): an allow-listed entry
# that relies on a member of a verified stdlib module relies on the member
# too. A recorded write of ``setitem`` (``operator.__dict__.update(setitem=
# evil)``) rebinds what ``operator.setitem(ns, …)`` or ``from operator import
# setitem as s`` calls, so it fails closed.

FOLD26_T = (
    "{pre}def helper(*args):\n    return 1\n\n\n"
    "def replacement(*args):\n    return 2\n\n\n"
    "def evil(d, *args, **kw):\n    return 0\n\n\n"
    "{post}def run(mod, client):\n    {stmt}\n    return helper()\n"
)
FOLD26_OP = "operator.setitem(mod.__dict__, 'other', 1)"
FOLD26_PROBES = {
    # p62 ``ns_update_kw`` (= p61 ``op_monkey_dict_update``).
    "p62-repro": (
        "import operator\n\n\n",
        "operator.__dict__.update(setitem=evil)\n\n\n",
        FOLD26_OP,
    ),
    "dict-update-of-namespace": (
        "import operator\n\n\n",
        "dict.update(operator.__dict__, setitem=evil)\n\n\n",
        FOLD26_OP,
    ),
    "getattr-namespace": (
        "import operator\n\n\n",
        "getattr(operator, '__dict__').update(setitem=evil)\n\n\n",
        FOLD26_OP,
    ),
    "write-in-run": (
        "import operator\n\n\n",
        "",
        f"operator.__dict__.update(setitem=evil)\n    {FOLD26_OP}",
    ),
    "handed-in-module": (
        "import operator\n\n\n",
        "",
        f"mod.OP.__dict__.update(setitem=evil)\n    {FOLD26_OP}",
    ),
    "alias-ior": (
        "import operator as op\n\n\n",
        "op.__dict__.update(ior=evil)\n\n\n",
        "op.ior(mod.__dict__, {'other': 1})",
    ),
    # The generalization: a from-import relies on the member it imports.
    "from-import-alias-member-written-first": (
        "import operator as o2\n\n\n",
        "o2.__dict__.update(setitem=evil)\n\n"
        "from operator import setitem as s\n\n\n",
        "s(mod.__dict__, 'other', 1)",
    ),
    "delitem-member": (
        "import operator\n\n\n",
        "operator.__dict__.update(delitem=evil)\n\n\n",
        "operator.delitem(mod.__dict__, 'other')",
    ),
    "dunder-setitem-member": (
        "import operator\n\n\n",
        "operator.__dict__.update(__setitem__=evil)\n\n\n",
        "operator.__setitem__(mod.__dict__, 'other', 1)",
    ),
}


@pytest.mark.parametrize("case", sorted(FOLD26_PROBES))
def test_fold26_695_rebound_operator_members_keep_their_off_mode_edge(
    tmp_path: Path, case: str
) -> None:
    pre, post, stmt = FOLD26_PROBES[case]
    source = FOLD26_T.format(pre=pre, post=post, stmt=stmt)
    root = _tree(tmp_path, {"a.py": source, "b.py": FOLD19_DECOY})
    off, on = _off_on(root)
    edge = _fold19_edge(off, "a.py")
    assert edge["resolution"] == "ambiguous", case
    assert _fold19_edge(on, "a.py") == edge, case


# Recorded writes of other names, or of another writer member, do not flip
# the entry: only the member the call relies on counts.
@pytest.mark.parametrize(
    ("pre", "post", "stmt"),
    [
        ("import operator\n\n\n", "", FOLD26_OP),
        (
            "import operator\n\n\n",
            "operator.__dict__.update(attrgetter=evil)\n\n\n",
            FOLD26_OP,
        ),
        (
            "import operator\n\n\n",
            "operator.__dict__.update(delitem=evil)\n\n\n",
            FOLD26_OP,
        ),
        ("import operator\n\n\n", "", f"client.other = evil\n    {FOLD26_OP}"),
        (
            "from operator import setitem as s\n\n\n",
            "",
            "client.other = evil\n    s(mod.__dict__, 'other', 1)",
        ),
        (
            "import operator as op\n\n\n",
            "op.__dict__.update(iadd=evil)\n\n\n",
            "op.ior(mod.__dict__, {'other': 1})",
        ),
    ],
)
def test_fold26_695_unrelated_writes_keep_the_entry(
    pre: str, post: str, stmt: str
) -> None:
    source = FOLD26_T.format(pre=pre, post=post, stmt=stmt)
    assert proof_text(source) == ["def helper(*args):\n    return 1"], (post, stmt)
