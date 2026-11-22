"""Tier 2 module resolution for JS/TS (plan sections 9.1-9.3, 9.7, 9.8).

Pure functions over the run's scope facts; no filesystem access. The run's
file set is the facts' display paths (relative to the extraction root, with
``/`` separators).

**Specifiers (9.2, ruling 2.2).** Only relative specifiers (``./``,
``../``) resolve. Bare specifiers, ``#imports``, ``node:``, URLs and
absolute paths give ``external-module``; a path that leaves the root gives
``outside-root``. The candidate list follows TypeScript's order:

1. ``p.js`` -> ``p.ts``, ``p.tsx``, ``p.d.ts``, ``p.js``;
2. ``p.jsx`` -> ``p.tsx``, ``p.d.ts``, ``p.jsx``;
3. ``p.ts``, ``p.tsx``, ``p.d.ts`` -> that file;
4. ``.mjs``, ``.cjs``, ``.mts``, ``.cts`` -> ``unknown-variant``;
5. otherwise ``p.ts``, ``p.tsx``, ``p.d.ts``, ``p.js``, ``p.jsx``, then
   ``p/index.`` with the same five extensions.

A ``.js`` or ``.jsx`` specifier also lists ``p.js/index.<ext>``, the
directory TypeScript tries after the file, so a directory of that name only
adds ambiguity. A JavaScript importer with an explicit ``.js``, ``.jsx``,
``.ts`` or ``.tsx`` extension maps to that exact file only.

The decision: any candidate whose extension this run did not collect (the
language filter), or that lies under a skipped directory, gives
``unknown-variant``; so does a candidate a run file matches only after case
folding and Unicode normalization, since case-insensitive file systems would
find that file. Then more than one existing candidate gives
``ambiguous-extension`` (owner decision O-1 (a)); exactly one is the target,
or ``dts-target`` for a ``.d.ts``; none gives ``module-not-found``.
Specifiers with a ``?``, ``#``, ``%``, ``\\``, an empty segment or a trailing
``/`` fail closed as ``unknown-variant``: toolchains read them differently.

**Exports (9.3).** For name ``x`` in module M: M's explicit export entry (a
local binding, resolved by M's Tier 1 lookup; an import in M is a hop), then
``export { x } from`` hops, then, if ``x`` has no explicit export and is not
``default``, the star exports: exactly one provider is followed, none gives
``export-not-found`` and several give ``star-conflict``. A star source that
cannot be read (any failure) fails the whole lookup closed, because it might
provide ``x``. At most three hops follow the first target module
(``hop-limit``); revisiting a ``(module, name)`` pair is a ``cycle``.

**CommonJS reach.** A module whose own exports object CommonJS code may
write, or one another file of the run may write through a namespace import,
``require`` or ``import()`` (its ``taints``), gives ``commonjs`` wherever a
lookup reaches it; so does every module when some JS/TS file may write any
module's exports (``taint_all``) or is unsupported (its writes are
unknown).
"""

from __future__ import annotations

import logging
import posixpath
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

logger = logging.getLogger(__name__)

# Extensions of the JS family and the language that collects each
# (``chunker.auto.ZeroConfigAPI.EXTENSION_MAP``; a test pins the copy).
JS_EXTENSION_LANGUAGES: Mapping[str, str] = {
    ".ts": "typescript",
    ".tsx": "tsx",
    ".js": "javascript",
    ".jsx": "javascript",
}
# ``chunker.symbol_graph.SKIP_PARTS`` (a test pins the copy).
SKIPPED_DIRECTORIES = frozenset(
    {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "node_modules",
        ".tox",
        ".pytest_cache",
        "build",
        "dist",
        ".eggs",
        "archive",
    }
)
HOP_LIMIT = 3
# Owner decision O-2 ("scope by caller"): the closed, case-sensitive,
# path-based test-file classifier. A file is test code when a basename
# segment between dots is ``test`` or ``spec`` (``svc.test.ts``,
# ``svc.spec.tsx``), or a directory segment is exactly one of
# TEST_DIRECTORIES. A test file any production file reaches is production.
TEST_NAME_SEGMENTS = frozenset({"test", "spec"})
TEST_DIRECTORIES = frozenset({"__tests__", "__mocks__", "test", "tests"})
# Middle segments of a sibling ``<stem>.<segment>.<ext>`` that no resolver
# picks for ``<stem>``. Any other segment may be a platform or module suffix
# (React Native's ``svc.ios.ts``, TypeScript ``moduleSuffixes``) that a
# toolchain resolves before ``svc.ts``, so it fails closed (a closed
# allow-list).
INERT_SUFFIXES = frozenset(
    {
        "test",
        "spec",
        "stories",
        "story",
        "bench",
        "d",
        "types",
        "styles",
        "mock",
        "mocks",
        "fixture",
        "fixtures",
        "e2e",
        "config",
    }
)
_EXTENSIONS = (".ts", ".tsx", ".d.ts", ".js", ".jsx")
_UNCOLLECTED_SUFFIXES = (".mjs", ".cjs", ".mts", ".cts")
_UNREAD_CHARACTERS = frozenset("?#%\\")


def _none(reason: str) -> dict[str, Any]:
    return {"outcome": "none", "reason": reason}


def _extension(path: str) -> str:
    """The collecting extension of a candidate (``.d.ts`` collects as ``.ts``)."""
    return posixpath.splitext(path)[1].lower()


def _fold(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


@dataclass(frozen=True)
class ModuleIndex:
    """The run's JS/TS files, for specifier resolution."""

    paths: frozenset[str]
    folded: Mapping[str, frozenset[str]]
    language_filter: str | None = None
    # Every file of the run, of any language (``package.json`` included).
    run_paths: frozenset[str] = frozenset()
    # Folded directory -> folded names of the JS/TS files in it.
    names: Mapping[str, frozenset[str]] = field(default_factory=dict)
    # JS/TS files collected through a symlink (E5-5).
    symlinks: frozenset[str] = frozenset()

    @classmethod
    def build(
        cls,
        paths: Sequence[str],
        language_filter: str | None,
        run_paths: Sequence[str] = (),
        symlinks: Sequence[str] | set[str] = (),
    ) -> ModuleIndex:
        folded: dict[str, set[str]] = {}
        names: dict[str, set[str]] = {}
        for path in paths:
            folded.setdefault(_fold(path), set()).add(path)
            directory, _, name = _fold(path).rpartition("/")
            names.setdefault(directory, set()).add(name)
        return cls(
            paths=frozenset(paths),
            folded={key: frozenset(value) for key, value in folded.items()},
            language_filter=language_filter.lower() if language_filter else None,
            run_paths=frozenset(run_paths) | frozenset(paths),
            names={key: frozenset(value) for key, value in names.items()},
            symlinks=frozenset(symlinks),
        )

    def suffixed_sibling(self, candidates: Sequence[str]) -> bool:
        """Whether a run file ``<stem>.<segment>.<ext>`` may shadow a
        candidate ``<stem>.<ext>`` under a platform or module suffix."""
        known = {_fold(candidate) for candidate in candidates}
        for candidate in candidates:
            stem = _stem(candidate)
            if stem is None:
                continue
            directory, _, base = _fold(stem).rpartition("/")
            for name in self.names.get(directory, ()):
                if (
                    not name.startswith(base + ".")
                    or f"{directory}/{name}".lstrip("/") in known
                ):
                    continue
                middle = _stem(name[len(base) + 1 :])
                if middle is not None and middle not in INERT_SUFFIXES:
                    return True
        return False

    def collected(self, candidate: str) -> bool:
        language = JS_EXTENSION_LANGUAGES.get(_extension(candidate))
        if language is None:
            return False
        return self.language_filter is None or self.language_filter == language


def _stem(path: str) -> str | None:
    """``path`` without its JS/TS extension (``.d.ts`` counts as one)."""
    lower = path.lower()
    for extension in (".d.ts", ".tsx", ".ts", ".jsx", ".js"):
        if lower.endswith(extension):
            return path[: -len(extension)]
    return None


def is_test_path(path: str) -> bool:
    """Whether a display path names test code by the O-2 classifier."""
    *directories, name = path.split("/")
    if any(part in TEST_DIRECTORIES for part in directories):
        return True
    return any(part in TEST_NAME_SEGMENTS for part in name.split(".")[1:-1])


def is_relative(specifier: str) -> bool:
    return specifier.startswith(("./", "../"))


def _dot_segment(specifier: str) -> bool:
    """A ``.`` or ``..`` segment after the leading ``./`` or ``../`` prefix
    (E5-5, A3/B-3): TypeScript and Node read ``./lib/.`` and ``./x/..`` as
    directories, never as files."""
    rest = specifier
    if rest.startswith("./"):
        rest = rest[2:]
    else:
        while rest.startswith("../"):
            rest = rest[3:]
    return any(part in (".", "..") for part in rest.split("/"))


def candidate_list(
    specifier: str, importer: str, importer_language: str | None
) -> tuple[tuple[str, ...], str | None]:
    """``(candidates, reason)``: the root-relative candidates, or a reason."""
    if specifier in (".", ".."):
        # A directory import of the importer's own or parent directory.
        return (), "unknown-variant"
    if not is_relative(specifier):
        return (), "external-module"
    if (
        _UNREAD_CHARACTERS & set(specifier)
        or specifier.endswith("/")
        or "//" in specifier
        or _dot_segment(specifier)
    ):
        return (), "unknown-variant"
    joined = posixpath.join(posixpath.dirname(importer), specifier)
    base = posixpath.normpath(joined)
    if base == ".." or base.startswith(("../", "/")):
        return (), "outside-root"
    lower = base.lower()
    if lower.endswith(_UNCOLLECTED_SUFFIXES):
        return (), "unknown-variant"
    extension = posixpath.splitext(base)[1]
    if extension.lower() in (".js", ".jsx", ".ts", ".tsx") and extension != (
        extension.lower()
    ):
        # ``./svc.JS``: toolchains disagree on whether it is an extension.
        return (), "unknown-variant"
    explicit = lower.endswith((".js", ".jsx", ".ts", ".tsx"))
    if importer_language == "javascript" and explicit:
        return (base,), None
    if lower.endswith((".ts", ".tsx")):  # ``.d.ts`` included
        return (base,), None
    if lower.endswith(".js"):
        stem = base[:-3]
        files = tuple(f"{stem}{ext}" for ext in (".ts", ".tsx", ".d.ts", ".js"))
        return files + tuple(f"{base}/index{ext}" for ext in _EXTENSIONS), None
    if lower.endswith(".jsx"):
        stem = base[:-4]
        files = tuple(f"{stem}{ext}" for ext in (".tsx", ".d.ts", ".jsx"))
        return files + tuple(f"{base}/index{ext}" for ext in _EXTENSIONS), None
    return (
        tuple(f"{base}{ext}" for ext in _EXTENSIONS)
        + tuple(f"{base}/index{ext}" for ext in _EXTENSIONS)
    ), None


def lenient_targets(
    index: ModuleIndex, specifier: str, importer: str
) -> tuple[str, ...] | None:
    """Every run file a taint specifier may name under any toolchain (E5-4).

    Rejected forms still taint: a query or hash is cut, ``\\`` becomes
    ``/``, percent escapes are decoded (both spellings are tried), empty
    segments collapse, a trailing ``/``, ``.`` or ``..`` means a directory,
    extensions are matched in any case and paths after case folding.
    ``None`` when the target cannot be computed (it leaves the root);
    ``()`` for a bare specifier, which is R12 (treesitter-chunker#702).
    """
    if specifier not in (".", "..") and not specifier.startswith(
        ("./", "../", ".\\", "..\\")
    ):
        return ()
    spellings = {specifier, unquote(specifier)}
    found: list[str] = []
    for spelling in sorted(spellings):
        text = spelling.replace("\\", "/")
        for mark in ("?", "#"):
            text = text.split(mark, 1)[0]
        while "//" in text:
            text = text.replace("//", "/")
        parts = text.split("/")
        directory_only = text.endswith("/") or parts[-1] in (".", "..")
        base = posixpath.normpath(
            posixpath.join(posixpath.dirname(importer), text.rstrip("/") or ".")
        )
        if base == ".." or base.startswith(("../", "/")):
            return None
        bases = [] if directory_only else [base]
        stem = _stem(base)
        if stem is not None:
            bases.append(stem)
        candidates: list[str] = [base]
        for item in bases:
            candidates.extend(f"{item}{ext}" for ext in _EXTENSIONS)
        prefix = "" if base == "." else f"{base}/"
        candidates.extend(f"{prefix}index{ext}" for ext in _EXTENSIONS)
        if stem is not None:
            candidates.extend(f"{stem}/index{ext}" for ext in _EXTENSIONS)
        for candidate in candidates:
            for path in sorted(index.folded.get(_fold(candidate), ())):
                if path not in found:
                    found.append(path)
    return tuple(found)


def existing_candidates(
    index: ModuleIndex, specifier: str, importer: str, language: str | None
) -> tuple[str, ...]:
    """Every run file a specifier may name, exact or after case folding."""
    candidates, _ = candidate_list(specifier, importer, language)
    found: list[str] = []
    for candidate in candidates:
        for path in sorted(index.folded.get(_fold(candidate), ())):
            if path not in found:
                found.append(path)
    return tuple(found)


def resolve_specifier(
    index: ModuleIndex, specifier: str, importer: str, language: str | None
) -> tuple[str | None, str | None]:
    """``(path, None)`` for the one target file, or ``(None, reason)``."""
    if importer in index.symlinks:
        # Node resolves a symlinked file's imports from its real path, tsc
        # from the link (E5-5, A4): toolchains disagree.
        return None, "unknown-variant"
    candidates, reason = candidate_list(specifier, importer, language)
    if reason is not None:
        return None, reason
    requested = posixpath.normpath(
        posixpath.join(posixpath.dirname(importer), specifier)
    )
    if requested in index.run_paths and requested not in candidates:
        # ``./svc.vue`` beside ``svc.vue.ts``: a loader would read the exact
        # file (E5-5).
        return None, "unknown-variant"
    for candidate in candidates:
        if not index.collected(candidate):
            return None, "unknown-variant"
        if any(part in SKIPPED_DIRECTORIES for part in candidate.split("/")):
            return None, "unknown-variant"
        if any(path != candidate for path in index.folded.get(_fold(candidate), ())):
            # A case-insensitive file system would find this file too.
            return None, "unknown-variant"
    existing = [candidate for candidate in candidates if candidate in index.paths]
    if len(existing) > 1 or index.suffixed_sibling(candidates):
        return None, "ambiguous-extension"
    if not existing:
        return None, "module-not-found"
    target = existing[0]
    if target in index.symlinks:
        return None, "unknown-variant"
    directory = target.rpartition("/")[0]
    if directory == requested and (
        f"{directory}/package.json" in index.run_paths
        or index.language_filter is not None
    ):
        # A directory import: TypeScript and Node read the directory's
        # ``package.json`` (``types``, ``main``) before ``index``. It is not
        # read here (R6), and a language filter leaves it uncollected.
        return None, "unknown-variant"
    if target.lower().endswith(".d.ts"):
        return None, "dts-target"
    return target, None


@dataclass(frozen=True)
class ModuleFile:
    """What Tier 2 reads from one JS/TS file's scope facts."""

    path: str
    language: str | None
    supported: bool
    exports: Mapping[str, Any] = field(default_factory=dict)
    stars: tuple[str, ...] = ()
    commonjs: bool = False
    opaque: bool = False


@dataclass(frozen=True)
class ModuleRun:
    """The run's module graph inputs, built once per assembly."""

    index: ModuleIndex
    files: Mapping[str, ModuleFile]
    # Modules whose exports a production file may write (every caller).
    tainted: frozenset[str] = frozenset()
    # Run-wide causes (E5-3) in production files, each with the first file.
    shutoff: Mapping[str, str] = field(default_factory=dict)
    # O-2: taints and run-wide causes that originate in test files apply
    # only to callers in test files.
    test_tainted: frozenset[str] = frozenset()
    test_shutoff: Mapping[str, str] = field(default_factory=dict)
    # Test-classified files no production file reaches.
    test_scope: frozenset[str] = frozenset()

    @property
    def taint_all(self) -> bool:
        return bool(self.shutoff)

    def caller_taints(self, importer: str) -> frozenset[str]:
        """The tainted modules a call from ``importer`` must avoid."""
        if importer in self.test_scope:
            return self.tainted | self.test_tainted
        return self.tainted


def build_module_run(
    facts: Sequence[Mapping[str, Any]], language_filter: str | None
) -> ModuleRun:
    """Index the run's JS/TS files, the tainted modules and the run-wide
    causes (E5-1, E5-3, E5-4), scoped by the caller (O-2)."""
    from .engine import language_family
    from .js_modules import CAUSE_UNPARSED_FILE, CAUSE_UNRESOLVABLE_WRITER

    files: dict[str, ModuleFile] = {}
    taints: list[tuple[str, str]] = []
    edges: dict[str, list[str]] = {}
    ns_uses: list[tuple[str, str | None, str, str, str]] = []
    causes: list[tuple[str, str]] = []
    symlinks: set[str] = set()
    for item in sorted(facts, key=lambda fact: str(fact.get("path") or "")):
        scope = item.get("scope_facts") or {}
        language = scope.get("language")
        if language_family(language) != "js":
            continue
        path = str(item.get("path") or "")
        supported = bool(scope.get("supported"))
        bindings = scope.get("module_bindings") or {}
        if bindings.get("symlink"):
            symlinks.add(path)
        if not supported and not bindings:
            # No text to scan (the file could not be read): its writes are
            # unknown.
            causes.append((CAUSE_UNPARSED_FILE, path))
        for name in bindings.get("shutoff", ()):
            causes.append((str(name), path))
        for specifier in bindings.get("taints", ()):
            taints.append((path, str(specifier)))
        edges[path] = [
            str(specifier)
            for key in ("imports", "taints", "stars")
            for specifier in bindings.get(key, ())
        ]
        for use in bindings.get("ns_uses", ()):
            ns_uses.append((path, language, str(use[0]), str(use[1]), str(use[2])))
        files[path] = ModuleFile(
            path=path,
            language=language,
            supported=supported,
            exports=scope.get("exports") or {} if supported else {},
            stars=tuple(str(spec) for spec in bindings.get("stars", ())),
            commonjs=bool(bindings.get("commonjs")),
            opaque=bool(bindings.get("opaque")) or not supported,
        )
    run_paths = sorted(str(item.get("path") or "") for item in facts)
    index = ModuleIndex.build(sorted(files), language_filter, run_paths, symlinks)
    production = _production_files(index, files, edges, symlinks)
    tainted: dict[bool, set[str]] = {True: set(), False: set()}

    def taint(path: str, specifier: str) -> None:
        targets = None if path in symlinks else lenient_targets(index, specifier, path)
        if targets is None:
            # The written module cannot be computed (E5-4).
            causes.append((CAUSE_UNRESOLVABLE_WRITER, path))
        else:
            tainted[path in production].update(targets)

    for path, specifier in taints:
        taint(path, specifier)
    structural = ModuleRun(index, files)
    for path, language, specifier, member, kind in ns_uses:
        # E5-1 (A2/B-5): ``ns.name`` must be a verified export, and
        # ``ns.f()`` must reach a declaration that never mentions ``this``.
        target, _ = resolve_specifier(index, specifier, path, language)
        verified = False
        if target is not None:
            found = _lookup(structural, target, member, 0, (), None)
            if isinstance(found, _Found):
                outcome = found.outcome
                verified = kind != "call" or (
                    outcome.get("outcome") == "local" and outcome.get("this") is False
                )
        if not verified:
            taint(path, specifier)
    shutoff: dict[bool, dict[str, str]] = {True: {}, False: {}}
    for name, path in causes:
        shutoff[path in production].setdefault(name, path)
    for in_production, found_causes in shutoff.items():
        for name, path in sorted(found_causes.items()):
            logger.info(
                "call resolution: Tier 2 is off for %s (%s in %s, %s)",
                "this run" if in_production else "callers in test files",
                name,
                path,
                "production" if in_production else "test-scoped",
            )
    return ModuleRun(
        index,
        files,
        frozenset(tainted[True]),
        dict(shutoff[True]),
        frozenset(tainted[False]),
        dict(shutoff[False]),
        frozenset(files) - production,
    )


def _production_files(
    index: ModuleIndex,
    files: Mapping[str, ModuleFile],
    edges: Mapping[str, Sequence[str]],
    symlinks: set[str],
) -> frozenset[str]:
    """O-2 promotion: the fixpoint of production files over the import
    graph (static imports, re-exports, literal ``require``/``import()`` and
    taints, each resolved leniently). Every file a production file reaches
    is production, whatever its name. A specifier whose target cannot be
    computed (outside the root, or from a symlinked file) promotes every
    test file, which keeps the result sound."""
    production = {path for path in files if not is_test_path(path)}
    pending = sorted(production)
    while pending:
        path = pending.pop()
        for specifier in edges.get(path, ()):
            targets = (
                None if path in symlinks else lenient_targets(index, specifier, path)
            )
            reached = set(files) if targets is None else set(targets)
            for target in sorted(reached - production):
                production.add(target)
                pending.append(target)
    return frozenset(production)


@dataclass(frozen=True)
class _Found:
    """A lookup that found the name: its result (resolved or ``none``)."""

    outcome: Mapping[str, Any]
    path: str = ""


@dataclass(frozen=True)
class _Unknown:
    """A lookup that cannot tell whether the module provides the name."""

    reason: str


_NOT_FOUND = None


def run_tainted_reason(run: ModuleRun, importer: str | None = None) -> str | None:
    """``run-tainted:<cause>`` for the first run-wide cause that applies to a
    call from ``importer`` (O-2: test-scoped causes apply only to callers in
    test files), or ``None``."""
    from .js_modules import SHUTOFF_CAUSES

    active = dict(run.shutoff)
    if importer is not None and importer in run.test_scope:
        active.update(run.test_shutoff)
    for name in SHUTOFF_CAUSES:
        if name in active:
            return f"run-tainted:{name}"
    return None


def _module_reason(
    run: ModuleRun, path: str, taints: frozenset[str] | None
) -> str | None:
    """Why lookups in module ``path`` fail closed, or ``None``.

    ``taints`` are the tainted modules for the caller (O-2); ``None`` when
    verifying namespace uses, where only the module's own shape counts.
    """
    module = run.files.get(path)
    if module is None or not module.supported or module.opaque:
        return "export-not-found"
    if taints is None:
        return None
    # The run-wide shutoff is checked once, in :func:`resolve_import`.
    if module.commonjs or path in taints:
        return "commonjs"
    return None


def _lookup(
    run: ModuleRun,
    path: str,
    name: str,
    hops: int,
    seen: tuple[tuple[str, str], ...],
    taints: frozenset[str] | None,
) -> _Found | _Unknown | None:
    """Look up export ``name`` in module ``path`` (9.3).

    ``None`` means the module provides no such export.
    """
    if (path, name) in seen:
        return _Unknown("cycle")
    if hops > HOP_LIMIT:
        return _Unknown("hop-limit")
    reason = _module_reason(run, path, taints)
    if reason is not None:
        return _Unknown(reason)
    module = run.files[path]
    seen = (*seen, (path, name))
    entry = module.exports.get(name)
    if entry is not None:
        return _Found(_entry_result(run, module, entry, hops, seen, taints), path)
    if name == "default":
        return _NOT_FOUND
    found: list[_Found] = []
    for specifier in module.stars:
        target, failure = resolve_specifier(run.index, specifier, path, module.language)
        if target is None:
            return _Unknown(failure or "module-not-found")
        result = _lookup(run, target, name, hops + 1, seen, taints)
        if isinstance(result, _Unknown):
            return result
        if result is not None:
            found.append(result)
    if len(found) > 1:
        return _Found(_none("star-conflict"))
    return found[0] if found else _NOT_FOUND


def _entry_result(
    run: ModuleRun,
    module: ModuleFile,
    entry: Mapping[str, Any],
    hops: int,
    seen: tuple[tuple[str, str], ...],
    taints: frozenset[str] | None,
) -> Mapping[str, Any]:
    kind = entry.get("kind")
    if kind == "none":
        return _none(str(entry.get("reason")))
    if kind == "reexport":
        return _follow(
            run,
            module,
            str(entry.get("source")),
            str(entry.get("name")),
            hops + 1,
            seen,
            taints,
        )
    if kind == "local":
        outcome = entry.get("outcome") or {}
        if outcome.get("outcome") == "local":
            return {
                "outcome": "local",
                "path": module.path,
                "local": outcome,
                "this": entry.get("this") is not False,
            }
        if outcome.get("outcome") == "import":
            binding = outcome.get("binding") or {}
            if binding.get("attributes") is not None:
                return _none("unknown-variant")
            if binding.get("form") == "namespace":
                return _none("namespace-export")
            return _follow(
                run,
                module,
                str(binding.get("source")),
                str(binding.get("name")),
                hops + 1,
                seen,
                taints,
            )
        if outcome.get("outcome") == "none":
            return _none(str(outcome.get("reason")))
    return _none("export-not-found")


def _follow(
    run: ModuleRun,
    module: ModuleFile,
    specifier: str,
    name: str,
    hops: int,
    seen: tuple[tuple[str, str], ...],
    taints: frozenset[str] | None,
) -> Mapping[str, Any]:
    target, failure = resolve_specifier(
        run.index, specifier, module.path, module.language
    )
    if target is None:
        return _none(failure or "module-not-found")
    return _result(_lookup(run, target, name, hops, seen, taints))


def _result(found: _Found | _Unknown | None) -> Mapping[str, Any]:
    if found is None:
        return _none("export-not-found")
    if isinstance(found, _Unknown):
        return _none(found.reason)
    return found.outcome


def resolve_import(
    run: ModuleRun,
    importer: str,
    importer_language: str | None,
    binding: Mapping[str, Any],
    member: str | None,
) -> Mapping[str, Any]:
    """Resolve one import binding (9.1) to a proof in its target module.

    Returns ``{"outcome": "local", "path": <target file>, "local": <the
    target's local outcome>, "this": <whether it mentions this>}`` or a
    ``none`` outcome. ``member`` is the property of a namespace member call
    (``ns.f()``); a namespace binding without one, or a named binding with
    one, is not resolved.
    """
    shutoff = run_tainted_reason(run, importer)
    if shutoff is not None:
        return _none(shutoff)
    if binding.get("attributes") is not None:
        return _none("unknown-variant")
    form = binding.get("form")
    if form == "namespace":
        if member is None:
            return _none("non-callable")
        name = member
    elif member is not None:
        return _none("export-not-found")
    else:
        name = str(binding.get("name"))
    target, failure = resolve_specifier(
        run.index, str(binding.get("source")), importer, importer_language
    )
    if target is None:
        return _none(failure or "module-not-found")
    return _result(_lookup(run, target, name, 0, (), run.caller_taints(importer)))
