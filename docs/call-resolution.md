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
reaches. Without a proof, language family and symbol kind filters can still
remove candidates, and the edge stays `ambiguous`. The pass only removes
candidates from ambiguous edges and preserves all existing resolved and
unresolved edges.
A narrowed edge carries `provenance.call_resolution` and `provenance.call_rules`.

In Python, `structural` skips module-scope and class-body proofs in files
that can bind names dynamically, for example through `exec`, `globals()`,
`sys.modules` or a star import. A mention of `f_locals` can rule out proofs
throughout the file. See the
[Boundary IR specification](interface-boundary-spec.md#call-resolution-extension-experimental)
for the exact rules.

In Python, `imports` also checks for recognized writes to a known module's
globals across the run. A write or an escape, such as passing an imported
module to a helper, can also invalidate that module's own Tier 1 module-scope
proofs. Python can therefore resolve fewer calls in `imports` than in
`structural`. The tool does not detect cross-file closure-cell writes or
writes to a caller's frame locals for Tier 1 proofs. A Tier 1 edge that such
a write makes wrong stays `resolved` in both modes.

## When import proofs are skipped

A run-wide cause indicates that a file can load or change a module whose
identity the tool cannot safely pin down, or that an unreadable file could do
so. The tool skips Tier 2 for affected callers of that language and reports
the cause at INFO level. For example, Python logs
`call resolution: Python Tier 2 is off for this run (dynamic-loader in loader.py, production)`.
The names in the table are the causes shown in the log. The exported graph
does not include these decisions. A write to an identifiable module can
invalidate proofs for just that module or a specific name.

| Cause | Example |
| --- | --- |
| `evaluator` | Running code with Python `exec` or JavaScript `new Function`, or loading Node's `vm`, `repl` or `inspector` modules. |
| `dynamic-loader` | Loading a path chosen at runtime, such as `require(path)` or Python `import_module(name)`. |
| `module-system` | Changing how modules are found or cached, such as changing Python's `sys.path` or using Node's module machinery to change the module cache. In JS/TS, any mention of Node's `process` counts too, because `process.binding`, `process.mainModule` and a search of its keys reach the loader. A few safe uses of the global are exempt, such as reading `process.env` or `process.argv`. Aliases from a static import of `process` that are used the same way are exempt as well. Loading `process` through a `require` call always counts. |
| `module-object` | Exposing a writable namespace, such as accessing a Python function's `__globals__` or handing the CommonJS `module` object to a helper. |
| `unparsed-file` | A collected file that the analyzer cannot read or parse safely. |
| `unresolvable-writer` | A patch or export write whose target cannot be located. |

### Test scoping

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
outside those rules.

### Not yet covered (fixes planned)

| Route | Example | Tracked in |
| --- | --- | --- |
| Python helpers that run source text | Profilers and debuggers such as `cProfile`, `profile`, `bdb`, `pdb` and `breakpoint()`, along with `trace`, `timeit`, `code`, `doctest` and `logging.config.fileConfig`, can run code that changes a binding. `exec` can also leave some function-scope proofs in place. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python helpers that load executable data | `pickle.loads`, `multiprocessing.reduction.ForkingPickler` or `shelve` can run code while loading a payload. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python code run with different globals | `runpy` with `init_globals`, multiprocessing's spawn setup or a loader's `exec_module` can run a fresh instance of a module. A function can also be rebuilt and run with a code object from `compile`, `marshal.loads`, a loader's `get_code` or another function's `__code__`. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python annotation evaluation and builtin changes | `ForwardRef.evaluate`, `typing.evaluate_forward_ref`, `typing.get_type_hints` and `inspect.get_annotations` can evaluate a string annotation. `gettext.install()` can add a builtin, and a custom `sys.displayhook` can change what runs. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python patch helpers obtained from a module | Code can retrieve a module's `patch` value through a computed attribute and use it to replace a target. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python patch calls on other receivers | A `.patch` call can replace a target even when the receiver is a parameter with a name the tool does not recognize. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python heap walking | Code can use `gc.get_referents`, `gc.get_referrers` or `gc.get_objects` to find a namespace, code object or closure cell. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python closure cells and frames across files | Another file can rewrite a closure cell used by an import proof, read its caller's frame locals, or receive a frame or a re-exported `locals` or `vars` function. Frame access can also come through `sys.settrace` or `sys.breakpointhook` installed by another module. | [treesitter-chunker#699](https://github.com/Consiliency/treesitter-chunker/issues/699) |
| Python function-local patcher aliases | A helper can reach a patcher through `locals()`, no-argument `vars()` or a frame-locals proxy. | [treesitter-chunker#707](https://github.com/Consiliency/treesitter-chunker/issues/707) |
| Python imports exposed through a namespace | Passing `globals()` or `locals()` to a helper can let it reach and modify an imported module. | [treesitter-chunker#724](https://github.com/Consiliency/treesitter-chunker/issues/724) |
| Python helpers that return imported modules | Returning an import already counts as exposing it to other code. More precise tracking is planned for which module a helper returns and how the caller uses it. | [treesitter-chunker#706](https://github.com/Consiliency/treesitter-chunker/issues/706) |
| Python format strings that name the main module | A stored template or a literal part of an f-string or t-string can expose `__main__` or `__mp_main__` to a formatting callback. | [treesitter-chunker#714](https://github.com/Consiliency/treesitter-chunker/pull/714) |
| JavaScript access to the calling function and dynamic scope | Code can use a key such as `caller` or `getFunction` to reach a function on the stack, or use a `with` statement to change a lookup. | [treesitter-chunker#718](https://github.com/Consiliency/treesitter-chunker/issues/718) |

### Runtime behavior the source scan can miss

| Route | Example |
| --- | --- |
| Computed names and reflection | `getattr(obj, prefix + suffix)`, walking `dir(obj)` or `inspect.getmembers(obj)` to find a frame member, or finding a key such as `caller` with a pattern like `/^cal+er$/`. This also covers computed lookups for pytest fixture methods, ancestor packages and JS loader methods. |
| Code or names supplied as data | A third-party evaluator runs a downloaded string, a worker sends pickled data to a Python `Connection.recv()`, or a JS program reads `caller` or `getFunction` from JSON. Python bytes `%` templates, runtime-built templates and `string.Template` subclasses with a custom delimiter such as `#` can hide a `__main__` lookup. A formatting callback can also cut `__main__` out of a larger component or receive a name joined across a replacement field. |
| Writes inside a library | `functools.update_wrapper` writes to an object passed to it, or `argparse` populates a supplied namespace. A catch-all `__getattr__` can also supply an annotation hook to `update_wrapper`. Known Python module escapes are tracked in `imports`. |
| Capabilities obtained outside the run | An installed package can re-export Python's `builtins` under another name or hide access to Node's code evaluation APIs. Native extensions and startup hooks such as `sitecustomize` can also change bindings. |
| Patched built-in prototypes | An `Object.prototype` getter named `send`, or a replacement for `EventEmitter.prototype.on`, `once` or `emit`, receives `process` as `this` when code checks `process.send`, calls `process.on(…)` or calls `process.exit()`. The exempt `process` uses are safe unless a built-in prototype is patched. Node's own code makes the same inherited lookups without any `process` token, for example when `new Buffer()` reads `noDeprecation`. |
| `process` reached without its name | A lookup on `globalThis` with a key built at runtime, such as `"pro" + "cess"` or a parameter, finds `process` without spelling it. The same applies to keys read from data. |
| Replacement function bodies | After `f.__code__ = other.__code__`, the edge can still name `f`, the right definition, even though calling it runs different code. |
| Runtime and build flags | Node's `--require`, `--import` or `NODE_OPTIONS` can preload code. Babel plugins and macros can change the code before it runs. |
| Generated files collected as source | A build directory such as `.next/` can be scanned alongside the source. Point extraction at the source directories when analyzing the source program. |

### Routes that need configuration or more program context

| Route | Example |
| --- | --- |
| Python writes across files | Another module changes a closure cell through `cell_contents`, writes a caller's `f_locals` through a frame, or runs `exec(code, mod.__dict__)` against a module it found at runtime. Tier 1 edges can still stay resolved in either mode. |
| Python loading and rebinding | Importing `pkg.X` from another file can replace a binding on `pkg`. A sibling module can inject a builtin, a loader can choose a different module name, and a configured plugin can supply a module at runtime. Pytest path and import settings can also change what a test loads. |
| JS/TS aliases into the run | A bare specifier can refer back into the project through a package self-reference, a workspace symlink or tsconfig `paths`. |
| External resolution settings | A `package.json` `browser` or `exports` map, a bundler alias or extension list, or tsconfig `rootDirs` or `moduleSuffixes` can redirect a source import. A test runner can also supply a mock through its own module mappings. |
| Files missing from the run | A writer in an uncollected `.mjs`, `.cjs`, `.mts` or `.cts` file, or a file omitted by a language filter, can change a module the tool analyzed. |

For the edge format, binding rules and exact list of recognized triggers,
see the [Boundary IR specification](interface-boundary-spec.md#call-resolution-extension-experimental).
