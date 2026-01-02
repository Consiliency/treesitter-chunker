# Check Schema Command

> Detect drift between database schema and code data models

## Usage

```
/ai-dev-kit:check-schema [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--tables` | Comma-separated list of tables to check | All |
| `--severity` | Minimum severity to report: `low`, `medium`, `high` | `low` |
| `--output` | Write report to file | Console |
| `--auto-fix` | Generate fix suggestions | `false` |
| `--format` | Output format: `markdown`, `json` | `markdown` |

## Examples

### Full Check

```bash
/ai-dev-kit:check-schema
```

Checks all tables for drift between database and models.

### Check Specific Tables

```bash
/ai-dev-kit:check-schema --tables=users,orders,products
```

### High Severity Only

```bash
/ai-dev-kit:check-schema --severity=high
```

Only reports HIGH severity issues (missing required columns, etc.)

### With Fix Suggestions

```bash
/ai-dev-kit:check-schema --auto-fix --output=schema-report.md
```

Generates report with suggested fixes for each issue.

## Workflow

### Step 1: Detect Database Stack

Identify ORM and database technology:

```markdown
Check for:
- alembic.ini → SQLAlchemy + Alembic
- prisma/schema.prisma → Prisma
- manage.py + migrations/ → Django
- supabase/migrations/ → Supabase (PostgreSQL)
```

### Step 2: Extract Database Schema

Read schema from migrations or live database:

```markdown
# From Alembic migrations
Parse alembic/versions/*.py to reconstruct schema

# From Prisma
Parse prisma/schema.prisma

# From live database (if accessible)
Query information_schema
```

### Step 3: Extract Code Models

Parse ORM model definitions:

```markdown
# SQLAlchemy
Find classes inheriting from Base
Extract __tablename__, Column definitions

# Prisma
Parse model definitions from schema.prisma

# Also check:
- Pydantic models
- TypeScript interfaces
- BAML type definitions
```

### Step 4: Compare and Report

Run drift detection:

```markdown
For each table:
  For each column in DB:
    Check: Exists in model?
    Check: Types match?
    Check: Nullable matches?
    Check: Default matches?

  For each column in model:
    Check: Exists in DB?

Generate report with issues.
```

### Step 5: Generate Fixes (if --auto-fix)

```markdown
For each issue:
  Generate appropriate fix:
  - Missing column → Add to model or generate migration
  - Type mismatch → Suggest type change
  - Missing migration → Generate alembic revision
```

## Output

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Console Output

```
Schema Alignment Check

Database: PostgreSQL (Supabase)
ORM: SQLAlchemy 2.0

Summary:
  HIGH:   2 issues
  MEDIUM: 3 issues
  LOW:    5 issues

Issues:

[HIGH] MISSING_IN_MODEL
  Table: curation_jobs
  Column: retry_count (INTEGER NOT NULL DEFAULT 0)
  Model: src/models/curation_job.py:CurationJob

  Fix:
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

[MEDIUM] TYPE_MISMATCH
  Table: books
  Column: isbn (VARCHAR(13))
  Model: src/models/book.py:Book.isbn → str (unbounded)

  Fix:
    isbn: Mapped[str] = mapped_column(String(13))

[LOW] MISSING_MIGRATION
  Model: User.preferences (JSONB)
  Migration: Not found

  Fix:
    alembic revision --autogenerate -m "add user preferences"
```

### JSON Output

```json
{
  "database": "postgresql",
  "orm": "sqlalchemy",
  "summary": {
    "high": 2,
    "medium": 3,
    "low": 5
  },
  "issues": [
    {
      "type": "MISSING_IN_MODEL",
      "severity": "HIGH",
      "table": "curation_jobs",
      "column": "retry_count",
      "db_type": "INTEGER",
      "nullable": false,
      "default": "0",
      "model_location": "src/models/curation_job.py:CurationJob",
      "fix": "retry_count: Mapped[int] = mapped_column(Integer, default=0)"
    }
  ]
}
```

## Issue Types

| Type | Severity | Description |
|------|----------|-------------|
| `MISSING_IN_MODEL` | HIGH | Column in DB not in model |
| `MISSING_IN_DB` | MEDIUM | Column in model not in DB |
| `TYPE_MISMATCH` | MEDIUM | Column types don't match |
| `NULLABLE_MISMATCH` | LOW | Nullable constraint differs |
| `DEFAULT_MISMATCH` | LOW | Default values differ |
| `NAMING_DRIFT` | LOW | Naming convention differs |
| `MISSING_MIGRATION` | LOW | Model change without migration |
| `FK_MISMATCH` | MEDIUM | Foreign key relationship differs |

## Severity Escalation

Default severity can be escalated:

| Issue | Escalate If | New Severity |
|-------|------------|--------------|
| MISSING_IN_MODEL | Column is NOT NULL | HIGH → CRITICAL |
| TYPE_MISMATCH | Could cause data loss | MEDIUM → HIGH |
| MISSING_MIGRATION | Production branch | LOW → MEDIUM |

## Integration

### With /ai-dev-kit:execute-lane

Runs as pre-flight check for database lanes:

```markdown
Lane: SL-DB (Database Schema)

Pre-flight checks:
  ✓ Git worktree clean
  ✗ Schema alignment failed
    - 2 HIGH severity issues

Recommendation: Run /ai-dev-kit:check-schema --auto-fix
```

### With /ai-dev-kit:plan-phase

Runs during phase planning:

```markdown
Planning Phase P1...

Schema Alignment: ⚠️ 3 issues detected
- 1 missing migration
- 2 type mismatches

Added to SL-DB lane:
- Task: Resolve schema alignment issues
```

### CI Integration

Add to CI pipeline:

```yaml
# .github/workflows/schema-check.yml
- name: Check schema alignment
  run: |
    claude --skill schema-alignment \
           --output schema-report.md \
           --severity medium

- name: Fail on HIGH issues
  run: |
    if grep -q '"severity": "HIGH"' schema-report.json; then
      echo "HIGH severity schema issues found"
      exit 1
    fi
```

## Best Practices

1. **Run before PRs**: Check schema alignment before merging
2. **Include in lane**: Add schema check to database swim lanes
3. **Fix incrementally**: Address HIGH issues first, then MEDIUM
4. **Document exceptions**: If drift is intentional, document why
5. **Automate checks**: Add to CI for continuous monitoring

## Related

- `schema-alignment` skill - Full skill documentation
- `/ai-dev-kit:recommend-skills` - Enable schema-alignment skill
- Cookbook: `plugins/ai-dev-kit/skills/schema-alignment/cookbook/`
