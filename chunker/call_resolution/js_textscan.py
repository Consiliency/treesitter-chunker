"""The text scan of a JS/TS file the parser cannot read (E5-3, PR 5 fold 8).

A file whose tree has errors gets no scope analysis. Its ``module_bindings``
come from this scan instead, which is sound by construction rather than by
pattern:

1. **Lexing.** A lexer finds every comment, string, template, regular
   expression, identifier, number and punctuator, respecting quotes,
   escapes, comments and template substitutions (nested templates
   included). A ``/`` starts a regular expression only where an expression
   can start (after an operator, an opening bracket, a comma or one of the
   keywords in :data:`_REGEX_AFTER`). Identifier escapes (``\\u0072equire``)
   are decoded; strings are decoded with :func:`js_strings.decode_js_string_sloppy`
   and template parts cooked like the parsed path does. Anything the lexer
   cannot delimit or decode with certainty (an unterminated literal or
   comment, a stray backslash, an undecodable escape, JSX text that opens a
   quote) makes the file an ``unparsed-file`` cause.
2. **Loader spellings.** ``require`` is exempt only as a complete literal
   call, ``require(<one string or substitution-free template>)``, whose
   decoded value taints its target leniently, or as ``typeof require``.
   ``import`` is exempt as a static import or export (its specifier is
   always a literal, tainted by step 3), as ``import(<one literal>)`` (a
   taint), and as an ``import.meta`` plain read; ``import.meta.glob`` makes
   the file's targets uncomputable. ``module`` is exempt as
   ``module.exports`` or ``typeof module``; ``exports`` writes only the
   file's own exports object, which is already opaque and CommonJS here.
   Every other occurrence of a loader spelling is a run-wide cause:
   ``createRequire``, ``mainModule``, ``getBuiltinModule`` (also inside a
   string), ``eval``, ``Function``, ``execScript``, a ``.constructor``
   property or ``'constructor'`` key, a timer called with something other
   than a name or a function, and any ``require``/``import(``/``module``
   use outside the forms above (a concatenation, a template with
   ``${``, a second argument, an identifier argument).
3. **Relative literals.** Every decoded string or substitution-free
   template whose value is relative (``./``, ``../``, ``.``, ``..``, or the
   backslash forms) taints its target leniently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .js_strings import _decode_body, decode_js_string_sloppy

CAUSE_EVALUATOR = "evaluator"
CAUSE_DYNAMIC_LOADER = "dynamic-loader"
CAUSE_MODULE_SYSTEM = "module-system"
CAUSE_MODULE_OBJECT = "module-object"
CAUSE_UNPARSED_FILE = "unparsed-file"

_MODULE_SYSTEM_NAMES = ("createRequire", "mainModule", "getBuiltinModule")
_MODULE_SPECIFIERS = frozenset({"module", "node:module"})
_EVALUATORS = frozenset({"eval", "Function", "execScript"})
_TIMERS = frozenset({"setTimeout", "setInterval"})
_IMPORT_META_READS = frozenset(
    {"url", "dirname", "filename", "resolve", "env", "main", "hot"}
)
_IMPORT_META_LOADERS = frozenset({"glob", "globEager"})
# Keywords after which ``/`` starts a regular expression.
_REGEX_AFTER = frozenset(
    {
        "return",
        "typeof",
        "instanceof",
        "in",
        "of",
        "new",
        "delete",
        "void",
        "throw",
        "case",
        "do",
        "else",
        "yield",
        "await",
    }
)
# Punctuators after which an expression (so a regular expression) follows.
_EXPRESSION_AFTER = frozenset("(,=:[!&|?{};+-*%<>~^")


class _UncertainError(Exception):
    """The lexer cannot delimit or decode a token with certainty."""


@dataclass(frozen=True)
class _Token:
    kind: str  # ident, string, template, regex, number, punct
    value: str | None
    # A template with a ``${`` substitution is never one complete literal.
    complete: bool = True


class _Lexer:
    def __init__(self, text: str) -> None:
        self.text = text
        self.tokens: list[_Token] = []

    def run(self) -> list[_Token]:
        index = 0
        if self.text.startswith("#!"):
            index = self._line_end(0)
        index = self._code(index, inside_template=False)
        if index != len(self.text):
            raise _UncertainError("unbalanced braces")
        return self.tokens

    def _line_end(self, index: int) -> int:
        while index < len(self.text) and self.text[index] not in "\n\r  ":
            index += 1
        return index

    def _regex_allowed(self) -> bool:
        if not self.tokens:
            return True
        last = self.tokens[-1]
        if last.kind == "punct":
            return last.value in _EXPRESSION_AFTER
        if last.kind == "ident":
            return last.value in _REGEX_AFTER
        return False

    def _code(self, index: int, *, inside_template: bool) -> int:
        """Lex code from ``index``; in a template substitution, stop after the
        ``}`` that closes it and return the index after it."""
        text = self.text
        depth = 0
        while index < len(text):
            char = text[index]
            if char in " \t\n\r\f\v ﻿  ":
                index += 1
            elif text.startswith("//", index):
                index = self._line_end(index)
            elif text.startswith("/*", index):
                end = text.find("*/", index + 2)
                if end < 0:
                    raise _UncertainError("unterminated comment")
                index = end + 2
            elif char in "'\"":
                index = self._string(index)
            elif char == "`":
                index = self._template(index)
            elif char == "/" and self._regex_allowed():
                index = self._regex(index)
            elif char.isdigit() or (
                char == "." and index + 1 < len(text) and text[index + 1].isdigit()
            ):
                end = index + 1
                while end < len(text) and (text[end].isalnum() or text[end] in "._"):
                    end += 1
                self.tokens.append(_Token("number", text[index:end]))
                index = end
            elif char.isalpha() or char in "_$\\" or ord(char) > 127:
                index = self._identifier(index)
            elif char == "{":
                depth += 1
                self.tokens.append(_Token("punct", char))
                index += 1
            elif char == "}":
                if inside_template and depth == 0:
                    return index + 1
                depth -= 1
                if depth < 0:
                    raise _UncertainError("unbalanced braces")
                self.tokens.append(_Token("punct", char))
                index += 1
            elif text.startswith("?.", index) and not (
                index + 2 < len(text) and text[index + 2].isdigit()
            ):
                self.tokens.append(_Token("punct", "."))
                index += 2
            else:
                self.tokens.append(_Token("punct", char))
                index += 1
        if inside_template:
            raise _UncertainError("unterminated template substitution")
        return index

    def _identifier(self, index: int) -> int:
        text = self.text
        chars: list[str] = []
        while index < len(text):
            char = text[index]
            if char == "\\":
                if not text.startswith("\\u", index):
                    raise _UncertainError("stray backslash")
                if text.startswith("\\u{", index):
                    close = text.find("}", index)
                    digits = text[index + 3 : close] if close > 0 else ""
                    width = close + 1 - index
                else:
                    digits = text[index + 2 : index + 6]
                    width = 6
                    if len(digits) != 4:
                        raise _UncertainError("bad identifier escape")
                try:
                    value = int(digits, 16)
                except ValueError as exc:
                    raise _UncertainError("bad identifier escape") from exc
                if value > 0x10FFFF or 0xD800 <= value <= 0xDFFF:
                    raise _UncertainError("bad identifier escape")
                chars.append(chr(value))
                index += width
            elif char.isalnum() or char in "_$" or ord(char) > 127:
                if char in " ﻿  ":
                    break
                chars.append(char)
                index += 1
            else:
                break
        self.tokens.append(_Token("ident", "".join(chars)))
        return index

    def _string(self, index: int) -> int:
        text = self.text
        quote = text[index]
        end = index + 1
        while end < len(text):
            char = text[end]
            if char == "\\":
                end += 3 if text.startswith("\r\n", end + 1) else 2
                continue
            if char == quote:
                value = decode_js_string_sloppy(text[index : end + 1])
                if value is None:
                    raise _UncertainError("undecodable string")
                self.tokens.append(_Token("string", value))
                return end + 1
            if char in "\n\r":
                raise _UncertainError("unterminated string")
            end += 1
        raise _UncertainError("unterminated string")

    def _template(self, index: int) -> int:
        text = self.text
        parts: list[str] = []
        start = index + 1
        end = start
        complete = True
        while end < len(text):
            char = text[end]
            if char == "\\":
                end += 2
                continue
            if char == "`":
                parts.append(text[start:end])
                break
            if text.startswith("${", end):
                parts.append(text[start:end])
                complete = False
                end = self._code(end + 2, inside_template=True)
                start = end
                continue
            end += 1
        else:
            raise _UncertainError("unterminated template")
        cooked: list[str] = []
        for part in parts:
            value = _decode_body(part, "`", template=True, sloppy=True)
            if value is None:
                raise _UncertainError("undecodable template")
            cooked.append(value)
        self.tokens.append(
            _Token(
                "template", "".join(cooked) if complete else "\0".join(cooked), complete
            )
        )
        return end + 1

    def _regex(self, index: int) -> int:
        text = self.text
        end = index + 1
        in_class = False
        while end < len(text):
            char = text[end]
            if char in "\n\r":
                raise _UncertainError("unterminated regular expression")
            if char == "\\":
                end += 2
                continue
            if char == "[":
                in_class = True
            elif char == "]":
                in_class = False
            elif char == "/" and not in_class:
                end += 1
                while end < len(text) and (text[end].isalnum() or text[end] == "$"):
                    end += 1
                self.tokens.append(_Token("regex", None))
                return end
            end += 1
        raise _UncertainError("unterminated regular expression")


def _relative(value: str) -> bool:
    return value in (".", "..") or value.startswith(("./", "../", ".\\", "..\\"))


def _literal(token: _Token | None) -> str | None:
    if token is None or token.kind not in ("string", "template") or not token.complete:
        return None
    return token.value


def scan(source: bytes) -> dict[str, Any]:
    """``{"taints", "shutoff", "uncomputable"}`` for an unparsed file."""
    text = source.decode("utf-8", errors="replace")
    taints: set[str] = set()
    shutoff: set[str] = set()
    uncomputable = False
    try:
        tokens = _Lexer(text).run()
    except _UncertainError:
        return {
            "taints": [],
            "shutoff": [CAUSE_UNPARSED_FILE],
            "uncomputable": False,
        }

    def at(position: int) -> _Token | None:
        return tokens[position] if 0 <= position < len(tokens) else None

    def punct(position: int, value: str) -> bool:
        token = at(position)
        return token is not None and token.kind == "punct" and token.value == value

    def ident(position: int, value: str | None = None) -> bool:
        token = at(position)
        return (
            token is not None
            and token.kind == "ident"
            and (value is None or token.value == value)
        )

    def literal_call(position: int) -> str | None:
        """The value of ``<loader>( <one literal> )`` at ``position``."""
        if not (punct(position + 1, "(") and punct(position + 3, ")")):
            return None
        return _literal(at(position + 2))

    def load(value: str) -> None:
        if value in _MODULE_SPECIFIERS:
            shutoff.add(CAUSE_MODULE_SYSTEM)
        else:
            taints.add(value)

    for position, token in enumerate(tokens):
        if token.kind in ("string", "template"):
            parts = (token.value or "").split("\0")
            if any(name in part for part in parts for name in _MODULE_SYSTEM_NAMES):
                shutoff.add(CAUSE_MODULE_SYSTEM)
            value = _literal(token)
            if value is None:
                continue
            if value in _MODULE_SPECIFIERS:
                shutoff.add(CAUSE_MODULE_SYSTEM)
            elif value == "constructor":
                shutoff.add(CAUSE_EVALUATOR)
            elif _relative(value):
                taints.add(value)
            continue
        if token.kind != "ident":
            continue
        name = token.value or ""
        member = punct(position - 1, ".")
        typeof = ident(position - 1, "typeof")
        if name == "require":
            value = literal_call(position)
            if value is not None:
                load(value)
            elif not typeof:
                shutoff.add(CAUSE_DYNAMIC_LOADER)
        elif name == "import" and not member:
            if punct(position + 1, "("):
                value = literal_call(position)
                if value is None:
                    shutoff.add(CAUSE_DYNAMIC_LOADER)
                else:
                    load(value)
            elif punct(position + 1, ".") and ident(position + 2, "meta"):
                prop = at(position + 4)
                prop_name = prop.value if prop is not None else None
                if not punct(position + 3, ".") or not ident(position + 4):
                    shutoff.add(CAUSE_DYNAMIC_LOADER)
                elif prop_name in _IMPORT_META_LOADERS:
                    uncomputable = True
                elif prop_name not in _IMPORT_META_READS:
                    shutoff.add(CAUSE_DYNAMIC_LOADER)
        elif name == "module" and not member:
            if not (
                typeof or (punct(position + 1, ".") and ident(position + 2, "exports"))
            ):
                shutoff.add(CAUSE_MODULE_OBJECT)
        elif name in _MODULE_SYSTEM_NAMES:
            shutoff.add(CAUSE_MODULE_SYSTEM)
        elif name in _EVALUATORS or (name == "constructor" and member):
            shutoff.add(CAUSE_EVALUATOR)
        elif name in _TIMERS and punct(position + 1, "("):
            first = at(position + 2)
            safe = first is not None and (
                (
                    first.kind == "ident"
                    and (punct(position + 3, ",") or punct(position + 3, ")"))
                )
                or (first.kind == "ident" and first.value in ("function", "async"))
                or (first.kind == "punct" and first.value == "(")
            )
            if not safe:
                shutoff.add(CAUSE_EVALUATOR)
    if shutoff:
        shutoff.add(CAUSE_UNPARSED_FILE)
    return {
        "taints": sorted(taints),
        "shutoff": sorted(shutoff),
        "uncomputable": uncomputable,
    }
