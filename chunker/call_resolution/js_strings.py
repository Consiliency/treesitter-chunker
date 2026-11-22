"""Exact decoding of ECMAScript string literals (plan section 9.1, Tier 2).

Module specifiers and quoted import/export names (``import {"a-b" as x}``,
``export {x as "y"}``) are compared by their string value, never by their
source text: ``"./svc"`` and ``"./\\x73vc"`` name the same module, and
``"t"`` and ``"\\u0074"`` the same export. :func:`decode_string_literal`
returns that value exactly as ECMAScript defines it for module code (which
is always strict), or ``None`` when the literal is not one it decodes
exactly. Every caller fails closed on ``None``.

Decoded (ECMAScript 2025, 12.9.4 String Literals):

- ``\\'``, ``\\"``, ``\\\\`` and every other non-escape character after a
  backslash stand for that character (``NonEscapeCharacter``);
- ``\\b``, ``\\f``, ``\\n``, ``\\r``, ``\\t`` and ``\\v``;
- ``\\0`` not followed by a decimal digit;
- ``\\xHH``, ``\\uHHHH`` and ``\\u{H...}`` up to ``10FFFF``;
- a backslash before a line terminator (LF, CR, CRLF, U+2028, U+2029) is a
  line continuation and stands for nothing.

``None`` (fail closed):

- a legacy octal escape (``\\1``, ``\\01``) or ``\\8``/``\\9``, which are
  syntax errors in strict code;
- a malformed ``\\x`` or ``\\u`` escape, or a code point past ``10FFFF``;
- an unescaped LF or CR inside the literal;
- a value that is not well-formed Unicode (a lone surrogate): a module
  export name must be well formed (``IsStringWellFormedUnicode``), and no
  file path holds one;
- anything that is not a ``'...'`` or ``"..."`` literal.
"""

from __future__ import annotations

from typing import Any

_SIMPLE_ESCAPES = {
    "b": "\b",
    "f": "\f",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "v": "\v",
}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_LINE_TERMINATORS = frozenset("\n\r  ")


def _hex(text: str, start: int, count: int) -> int | None:
    digits = text[start : start + count]
    if len(digits) != count or not set(digits) <= _HEX_DIGITS:
        return None
    return int(digits, 16)


def decode_js_string(raw: str) -> str | None:
    """The value of the string literal ``raw`` (quotes included), or ``None``."""
    if len(raw) < 2 or raw[0] not in "'\"" or raw[-1] != raw[0]:
        return None
    return _decode_body(raw[1:-1], raw[0], template=False)


def cook_template(node: Any, source: bytes) -> list[str] | None:
    """The cooked text of each literal part of a tree-sitter
    ``template_string`` (between substitutions), or ``None`` when a part
    does not cook exactly. Template parts follow the string escapes, except
    that raw line terminators are allowed (CR and CRLF cook to LF)."""
    if node is None or node.type != "template_string":
        return None
    try:
        raw = source[node.start_byte : node.end_byte].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if len(raw) < 2 or raw[0] != "`" or raw[-1] != "`":
        return None
    # The raw text between substitutions, one entry per literal part.
    pieces: list[str] = []
    cursor = node.start_byte + 1
    for part in node.named_children:
        if part.type == "template_substitution":
            pieces.append(source[cursor : part.start_byte].decode("utf-8", "replace"))
            cursor = part.end_byte
    pieces.append(source[cursor : node.end_byte - 1].decode("utf-8", "replace"))
    parts: list[str] = []
    for text in pieces:
        cooked = _decode_body(text, "`", template=True)
        if cooked is None:
            return None
        parts.append(cooked)
    return parts


def decode_js_string_sloppy(raw: str) -> str | None:
    """The value ``raw`` has in sloppy (script) code, for name matching:
    legacy octal escapes and ``\\8``/``\\9`` decode, and a lone surrogate
    is kept as it is. ``None`` only for a malformed literal."""
    if len(raw) < 2 or raw[0] not in "'\"" or raw[-1] != raw[0]:
        return None
    return _decode_body(raw[1:-1], raw[0], template=False, sloppy=True)


def _decode_body(
    body: str, quote: str, *, template: bool, sloppy: bool = False
) -> str | None:
    if template:
        body = body.replace("\r\n", "\n").replace("\r", "\n")
    units: list[int] = []
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if char in "\n\r" and not template:
            return None
        if char == quote:
            # An unescaped closing quote inside the body: not one literal.
            return None
        if char != "\\":
            code = ord(char)
            if code > 0xFFFF:
                code -= 0x10000
                units.extend((0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
            else:
                units.append(code)
            index += 1
            continue
        index += 1
        if index >= length:
            return None
        escape = body[index]
        if escape in _LINE_TERMINATORS:
            # A line continuation; CRLF counts as one terminator.
            index += 2 if body[index : index + 2] == "\r\n" else 1
            continue
        if escape in _SIMPLE_ESCAPES:
            units.append(ord(_SIMPLE_ESCAPES[escape]))
            index += 1
            continue
        if escape == "0" and (
            index + 1 >= length or body[index + 1] not in "0123456789"
        ):
            units.append(0)
            index += 1
            continue
        if escape in "0123456789" and sloppy:
            if escape in "89":
                units.append(ord(escape))
                index += 1
                continue
            digits = escape
            limit = 3 if escape in "0123" else 2
            while len(digits) < limit and body[
                index + len(digits) : index + len(digits) + 1
            ] in tuple("01234567"):
                digits += body[index + len(digits)]
            units.append(int(digits, 8))
            index += len(digits)
            continue
        if escape in "0123456789":
            # Legacy octal, \8 and \9: syntax errors in strict (module) code.
            return None
        if escape == "x":
            value = _hex(body, index + 1, 2)
            if value is None:
                return None
            units.append(value)
            index += 3
            continue
        if escape == "u":
            if body[index + 1 : index + 2] == "{":
                close = body.find("}", index + 2)
                digits = body[index + 2 : close] if close >= 0 else ""
                if not digits or not set(digits) <= _HEX_DIGITS:
                    return None
                value = int(digits, 16)
                if value > 0x10FFFF:
                    return None
                if value > 0xFFFF:
                    value -= 0x10000
                    units.extend((0xD800 + (value >> 10), 0xDC00 + (value & 0x3FF)))
                else:
                    units.append(value)
                index = close + 1
                continue
            value = _hex(body, index + 1, 4)
            if value is None:
                return None
            units.append(value)
            index += 5
            continue
        # NonEscapeCharacter, including the quotes and the backslash itself.
        code = ord(escape)
        if code > 0xFFFF:
            code -= 0x10000
            units.extend((0xD800 + (code >> 10), 0xDC00 + (code & 0x3FF)))
        else:
            units.append(code)
        index += 1
    if sloppy:
        return "".join(chr(unit) for unit in units)
    return _well_formed(units)


def _well_formed(units: list[int]) -> str | None:
    """Join UTF-16 code units; ``None`` if any surrogate is unpaired."""
    chars: list[str] = []
    index = 0
    while index < len(units):
        unit = units[index]
        if 0xD800 <= unit <= 0xDBFF:
            low = units[index + 1] if index + 1 < len(units) else -1
            if not 0xDC00 <= low <= 0xDFFF:
                return None
            chars.append(chr(0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00)))
            index += 2
            continue
        if 0xDC00 <= unit <= 0xDFFF:
            return None
        chars.append(chr(unit))
        index += 1
    return "".join(chars)


def decode_string_literal(node: Any, source: bytes) -> str | None:
    """The value of a tree-sitter ``string`` node, or ``None`` (fail closed)."""
    if node is None or node.type != "string":
        return None
    try:
        raw = source[node.start_byte : node.end_byte].decode("utf-8")
    except UnicodeDecodeError:
        return None
    return decode_js_string(raw)


def module_export_name(node: Any, source: bytes) -> str | None:
    """A ``ModuleExportName``: an identifier's spelling or a string's value.

    Identifiers are compared by their source spelling: a file that spells
    any name with a Unicode escape is not analyzed at all (section 5.3).
    """
    if node is None:
        return None
    if node.type == "string":
        return decode_string_literal(node, source)
    if node.type in ("identifier", "property_identifier", "type_identifier"):
        try:
            return source[node.start_byte : node.end_byte].decode("utf-8")
        except UnicodeDecodeError:
            return None
    return None
