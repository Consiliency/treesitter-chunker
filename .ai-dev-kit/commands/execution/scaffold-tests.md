---
name: scaffold-tests
description: "Generate test file scaffolds from source files or phase plan, enabling TDD workflow."
args: "[source_files...] | --from-plan <phase-plan.md>"
---

# /ai-dev-kit:scaffold-tests

Generate test scaffolds for source files, creating TODO stubs that the test-engineer agent fills during lane execution.

## Synopsis

```bash
# From explicit source files
/ai-dev-kit:scaffold-tests src/auth/login.py src/auth/session.py

# From phase plan (scans impl task owned files)
/ai-dev-kit:scaffold-tests --from-plan specs/plans/P1-auth.md

# With framework override
/ai-dev-kit:scaffold-tests --framework jest src/components/*.tsx

# Dry run (show what would be generated)
/ai-dev-kit:scaffold-tests --dry-run src/**/*.py

# Force overwrite existing test files
/ai-dev-kit:scaffold-tests --force src/utils.py
```

## Flags

| Flag | Description |
|------|-------------|
| `--from-plan <path>` | Extract source files from phase plan impl tasks |
| `--framework <name>` | Override auto-detected test framework |
| `--output-dir <path>` | Custom test output directory |
| `--dry-run` | Show what would be generated without writing |
| `--force` | Overwrite existing test files |
| `--json` | Output manifest in JSON format |
| `--stub-style <style>` | Use `todo` (default) or `skip` markers |

## Workflow

### Step 1: Detect Test Framework

Read package manifests to identify the test framework:

| Manifest | Detection |
|----------|-----------|
| `pyproject.toml` | `pytest` in dependencies or `[tool.pytest]` section |
| `package.json` | `vitest` or `jest` in devDependencies |
| `go.mod` | Built-in `testing` package |
| `Cargo.toml` | Built-in `cargo test` |
| `pubspec.yaml` | `flutter_test` or `test` in dev_dependencies |

If no manifest found, prompt user or use `--framework` flag.

### Step 2: Gather Source Files

**From explicit arguments**:
```bash
/ai-dev-kit:scaffold-tests src/auth/*.py
```

**From phase plan**:
```bash
/ai-dev-kit:scaffold-tests --from-plan specs/plans/P1-auth.md
```

Extracts files from `Owned Artifacts` column of `impl` task type rows.

### Step 3: Analyze Sources

For each source file:
1. Detect language from extension
2. Parse file to extract public functions, classes, methods
3. Build symbol table with names, types, signatures

Uses heuristics from `skills/test-scaffolding/heuristics/source-analysis.md`.

### Step 4: Generate Scaffolds

For each source file:
1. Determine test file path using naming convention
2. Skip if test file exists (unless `--force`)
3. Apply language template from `skills/test-scaffolding/templates/`
4. Write scaffold with TODO stubs

### Step 5: Return Manifest

Output a manifest of generated files:

```json
{
  "format": "scaffold-manifest/v1",
  "generated_at": "2025-01-15T10:30:00Z",
  "framework": "pytest",
  "generated": [
    {
      "source": "src/auth/login.py",
      "test": "tests/auth/test_login.py",
      "units": ["authenticate", "logout", "UserSession.refresh"],
      "unit_count": 3
    }
  ],
  "skipped": [
    {
      "source": "src/auth/utils.py",
      "reason": "test file exists"
    }
  ],
  "total_units": 12
}
```

## Integration Points

### With `/ai-dev-kit:plan-phase`

When a phase plan is generated, scaffold-tests can auto-populate the `Tests Owned Files` column:

```bash
# After generating phase plan
/ai-dev-kit:scaffold-tests --from-plan specs/plans/P1-feature.md --dry-run
```

### With `/ai-dev-kit:execute-lane`

Lane-lead agent invokes scaffold-tests before test-engineer runs:

1. Check if test files from `Tests Owned Files` exist
2. If missing, run scaffold-tests with impl task sources
3. Commit scaffolds: `chore(P{n}-{lane}): scaffold test files`
4. Log event: `{"event": "scaffold_generated", ...}`

### With `test-engineer` Agent

Test-engineer detects and fills scaffold TODOs:

1. Read test file, detect `# TODO:` or `// TODO:` markers
2. Parse TODO comments for test intent
3. Implement test bodies based on source analysis
4. Remove TODO markers when complete

## Examples

### Python Project

```bash
$ /ai-dev-kit:scaffold-tests src/auth/login.py

Detected framework: pytest
Analyzing: src/auth/login.py

Generated scaffolds:
  tests/auth/test_login.py (3 test stubs)
    - test_authenticate
    - test_logout
    - TestUserSession.test_refresh

Total: 1 file, 3 test stubs
```

### TypeScript Project

```bash
$ /ai-dev-kit:scaffold-tests --framework vitest src/components/Button.tsx

Detected framework: vitest (override)
Analyzing: src/components/Button.tsx

Generated scaffolds:
  src/components/Button.test.tsx (2 test stubs)
    - Button render
    - Button click handler

Total: 1 file, 2 test stubs
```

### From Phase Plan

```bash
$ /ai-dev-kit:scaffold-tests --from-plan specs/plans/P1-auth.md

Extracting sources from phase plan...
Found 5 impl tasks with 8 source files

Detected framework: pytest
Analyzing 8 files...

Generated scaffolds:
  tests/auth/test_login.py (3 stubs)
  tests/auth/test_session.py (4 stubs)
  tests/auth/test_tokens.py (2 stubs)

Skipped:
  tests/auth/test_utils.py (already exists)

Total: 3 files, 9 test stubs
```

## Error Handling

| Error | Behavior |
|-------|----------|
| No package manifest | Prompt for framework or require `--framework` |
| Source file not found | Log warning, continue with others |
| Parse error in source | Log warning, skip file |
| Test file exists | Skip unless `--force` specified |
| No public symbols | Log warning, skip file |

## CLI Implementation

The command is implemented in `ai_dev_kit/scaffold_tests.py` and exposed via:

```bash
ai-dev-kit scaffold-tests [options] [files...]
```

## See Also

- `skills/test-scaffolding/SKILL.md` - Skill definition
- `skills/test-scaffolding/templates/` - Language templates
- `skills/test-scaffolding/heuristics/source-analysis.md` - Extraction heuristics
- `agents/execution/test-engineer.md` - Agent that fills scaffolds
