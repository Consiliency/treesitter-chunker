---
name: toon-validate
argument-hint: "[path]"
description: "Validate TOON files using official CLI and auto-fix scripts"
allowed-tools: Bash(npx:*, python3:*, find:*)
---

# Validate TOON Files

Validates TOON files using the official `@toon-format/cli` decode command (matches IDE extension),
then runs auto-fix scripts if validation fails.

**IMPORTANT**: The CLI uses `--decode` not `validate` - validation happens by attempting to decode.

## Inputs

- `$1`: Path to validate (file or directory, e.g., `ai-docs/libraries/baml/`)

## Workflow

### 1. Validate with Official CLI

```bash
# For a single file:
npx @toon-format/cli --decode $1 > /dev/null

# For a directory, validate each .toon file:
for f in $(find $1 -name "*.toon"); do
  npx @toon-format/cli --decode "$f" > /dev/null 2>&1 && echo "OK: $f" || echo "FAILED: $f"
done
```

If all validations pass, report success and exit.

### 2. Auto-fix Common Issues

If validation fails, run the auto-fix scripts **in this order**:

```bash
# Order matters - fix structural issues first
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_comments.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_yaml_lists.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_nested_lists.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_commas.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_pipes.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_multiline.py $1/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_blank_lines.py $1/
```

### 3. Re-validate

```bash
for f in $(find $1 -name "*.toon"); do
  npx @toon-format/cli --decode "$f" > /dev/null 2>&1 && echo "OK: $f" || echo "FAILED: $f"
done
```

### 4. Report Results

```markdown
## TOON Validation Results: {$1}

**Status**: {passed/failed}

### Files Checked
- {N} .toon files found
- {N} passed
- {N} failed

### Fixes Applied
- fix_toon_comments.py: {N files or "0"}
- fix_toon_yaml_lists.py: {N files or "0"}
- fix_toon_nested_lists.py: {N files or "0"}
- fix_toon_commas.py: {N files or "0"}
- ...

### Remaining Issues
- {list any unresolved errors or "none"}
```

## Usage

```bash
# Validate a specific library
/documentation:toon-validate ai-docs/libraries/baml/

# Validate all libraries
/documentation:toon-validate ai-docs/libraries/

# Validate a single file
/documentation:toon-validate ai-docs/libraries/_index.toon
```

## Tools Used

- **Official**: `@toon-format/cli --decode` - validates by attempting to decode (same parser as IDE extension)
- **Auto-fix scripts** (in `.claude/ai-dev-kit/dev-tools/scripts/`):
  - `fix_toon_comments.py` - removes comment lines (not supported by CLI)
  - `fix_toon_yaml_lists.py` - converts `- item` to tabular arrays
  - `fix_toon_nested_lists.py` - adds counts to nested lists
  - `fix_toon_commas.py` - fixes commas in tabular array values
  - `fix_toon_pipes.py` - replaces pipe delimiters with commas
  - `fix_toon_multiline.py` - converts `key: |` to quoted strings
  - `fix_toon_blank_lines.py` - removes blank lines within lists

## Common TOON Errors

| Error Message | Cause | Fix Script |
|--------------|-------|------------|
| Missing colon after key | Comment line or raw text | fix_toon_comments.py |
| Expected N tabular rows, got M | Missing indentation or wrong count | fix_toon_yaml_lists.py |
| Expected N values, got M | Commas in values | fix_toon_commas.py |
