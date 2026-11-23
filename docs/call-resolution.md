# Call resolution

Use `--call-resolution` with `boundary` or `symbols extract`. The Python
APIs `extract_boundary_ir` and `extract_symbol_graph` take the same values
through `call_resolution`. An extraction run is the set of files the tool
collects under the selected root and filters.

## Choose a mode

| Mode | What it does |
| --- | --- |
| `name` (default) | Uses the existing name-based heuristic. Explicitly choosing `name` produces the same output as omitting the option. |
| `structural` (experimental, Tier 1) | Uses scope to narrow ambiguous calls to bare names. For Python, a call can resolve to a single unconditional, undecorated `def` or `class` that the caller's scope selects. For JavaScript, TypeScript and TSX, a lexical declaration can prove the target. At the top level of a script, other files in the run must also be clear of possible declarations of the same global. |
| `imports` (experimental, Tier 2) | Also follows supported import bindings, such as a relative ES import in JS/TS or `from m import f` and `m.f()` in Python. The import must identify one file in the run and lead to one proven definition. |

**A binding must prove the target.** The experimental modes can resolve an
ambiguous edge only when a binding proves which existing candidate the call
reaches. Filtering by language or symbol kind can narrow the list but cannot
prove a target. When the lookup has no proof it returns `none(reason)`
internally and keeps the name-mode edge for that lookup. The exported graph
keeps its usual resolution statuses. The pass only removes candidates from
ambiguous edges and preserves all existing resolved and unresolved edges.
A narrowed edge carries `provenance.call_resolution` and `provenance.call_rules`.

In Python, `imports` also checks for recognized writes to a known module's
globals across the run. A write or an escape, such as passing an imported
module to a helper, can also invalidate that module's own Tier 1 module-scope
proofs. Python can therefore resolve fewer calls in `imports` than in
`structural`. Cross-file closure-cell writes and writes to a caller's frame
locals can invalidate a Tier 1 proof in either mode.

## When import proofs are skipped

A run-wide cause indicates that a file can load or change a module whose
identity the tool cannot safely pin down, or that an unreadable file could do
so. The tool skips Tier 2 for affected callers of that language and logs the
cause. A skipped lookup can report a reason such as
`none(run-tainted:dynamic-loader)`. A write to an identifiable module can
instead invalidate only that module or a specific name.

| Cause | Example |
| --- | --- |
| `evaluator` | Running code with Python `exec` or JavaScript `new Function`. |
| `dynamic-loader` | Loading a path chosen at runtime, such as `require(path)` or Python `import_module(name)`. |
| `module-system` | Changing how modules are found or cached, such as changing Python's `sys.path` or using Node's module machinery to change the module cache. |
| `module-object` | Exposing a writable namespace, such as accessing a Python function's `__globals__` or handing the CommonJS `module` object to a helper. |
| `unparsed-file` | A collected file that the analyzer cannot read or parse safely. |
| `unresolvable-writer` | A patch or export write whose target cannot be located. |

### Test scoping (O-2)

A cause in production code affects production and test callers. A cause in a
test-only file affects test callers. The same scoping applies to tracked
module writes and escapes. The classifier uses fixed path patterns, such as
`test_*.py`, `*_test.py` and `conftest.py` in Python, or `.test.` and
`.spec.` in JS/TS. Both recognize `test/` and `tests/`, and JS/TS also
recognizes `__tests__/` and `__mocks__/`.

A test-named file reachable from production through recognized imports or
loads counts as production, including through intermediate files. A directory
symlink under the root can cause every test file to count as production. In
JS/TS, the tool also takes that precaution if a production file uses a path
it cannot locate, such as a `#` package import or a `file:` URL. A test entry
point loaded solely by external configuration can still be misclassified.
The [Boundary IR specification](interface-boundary-spec.md#call-resolution-extension-experimental)
describes the exact rules.

## Known limits

The proofs depend on the collected source and the binding and loading rules
the tool models. A resolved edge can be wrong when runtime behavior falls
outside those rules. The design record calls the first group class (b) and
the second class (c).

### Runtime behavior the source scan can miss (b)

| Route | Example |
| --- | --- |
| Computed names and reflection | `getattr(obj, prefix + suffix)`, walking `dir(obj)` or `inspect.getmembers(obj)` to find a frame member, or finding a JS stack key with a pattern like `/^cal+er$/`. This also covers computed lookups for pytest fixture methods, ancestor packages and JS loader methods. |
| Code or names supplied as data | A third-party evaluator runs a downloaded string, a worker sends pickled data to a Python `Connection.recv()`, or a JS program reads a stack key from JSON. Python bytes `%` templates, runtime-built templates and `string.Template` subclasses with a custom delimiter such as `#` can hide a `__main__` lookup. |
| Writes inside a library | `functools.update_wrapper` writes to an object passed to it, or `argparse` populates a supplied namespace. A catch-all `__getattr__` can also supply an annotation hook to `update_wrapper`. Known Python module escapes are tracked in `imports`. |
| Capabilities obtained outside the run | An installed package re-exports Python's `builtins` or Node's `vm` under another name. Native extensions and startup hooks such as `sitecustomize` can also change bindings. |
| Replacement function bodies | After `f.__code__ = other.__code__`, a reference can still name `f` while calling it runs a different body. The analyzer tracks definition targets. |
| Runtime and build flags | Node's `--require`, `--import` or `NODE_OPTIONS` can preload code. Babel plugins and macros can change the code before it runs. |
| Generated files collected as source | A build directory such as `.next/` can be scanned alongside the source. Point extraction at the source directories when analyzing the source program. |

### Routes that need configuration or more program context (c)

| Route | Example |
| --- | --- |
| Python writes across files | Another module changes a closure cell through `cell_contents`, writes a caller's `f_locals` through a frame, or runs `exec(code, mod.__dict__)` against a module it found at runtime. A run-wide cause disables Tier 2, and Tier 1 proofs can still survive these writes in `imports`. |
| Python loading and rebinding | Importing `pkg.X` from another file can replace a binding on `pkg`. A sibling module can inject a builtin, a loader can choose a different module name, and a helper or configured plugin can supply a module through a call result. Pytest path and import settings can also change what a test loads. |
| JS/TS aliases into the run | A bare specifier can refer back into the project through a package self-reference, a workspace symlink or tsconfig `paths`. |
| External resolution settings | A `package.json` `browser` or `exports` map, a bundler alias or extension list, or tsconfig `rootDirs` or `moduleSuffixes` can redirect a source import. A test runner can also supply a mock through its own module mappings. |
| Files missing from the run | A writer in an uncollected `.mjs`, `.cjs`, `.mts` or `.cts` file, or a file omitted by a language filter, can change a module the tool analyzed. |

For the edge format, binding rules and exact list of recognized triggers,
see the [Boundary IR specification](interface-boundary-spec.md#call-resolution-extension-experimental).
