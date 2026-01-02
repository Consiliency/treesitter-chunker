# Recommend Skills Command

> Analyze project stack and recommend skills for AI-assisted development

## Usage

```
/ai-dev-kit:recommend-skills [options]
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `--output` | Write report to file | Console |
| `--auto-activate` | Activate recommended generic skills | `false` |
| `--scaffold` | Create project-specific skills in target repo | `false` |
| `--format` | Output format: `markdown`, `json` | `markdown` |

## Examples

### Report Only (Default)

```bash
/ai-dev-kit:recommend-skills
```

Generates a report showing:
- Detected stack (languages, frameworks, databases)
- Recommended generic skills
- Scaffoldable project-specific skills

### Auto-Activate Generic Skills

```bash
/ai-dev-kit:recommend-skills --auto-activate
```

Detects stack and activates matching generic skills:
- `baml-integration` if BAML detected
- `supabase-patterns` if Supabase detected
- `schema-alignment` if ORM detected
- etc.

### Scaffold Project-Specific Skills

```bash
/ai-dev-kit:recommend-skills --scaffold
```

Creates project-specific skills in `.claude/skills/`:
- `{project}-research/` if research patterns detected
- `{project}-domain/` if rich domain models detected
- `{project}-testing/` if custom test patterns detected

### Full Setup

```bash
/ai-dev-kit:recommend-skills --auto-activate --scaffold --output=skill-report.md
```

## Workflow

### Step 1: Detect Stack

Invoke the `library-detection` skill:

```markdown
Read and execute: plugins/ai-dev-kit/skills/library-detection/SKILL.md

Returns:
- languages: [typescript, python]
- frameworks: [next.js, fastapi]
- databases: [postgresql]
- test_frameworks: [vitest, pytest]
- build_tools: [vite, uv]
```

### Step 2: Match Recommendations

Load recommendations from stack-analyzer skill:

```markdown
Read: plugins/ai-dev-kit/skills/stack-analyzer/config/recommendations.yaml

Match detected stack against:
- activate_skills: Generic skills to activate
- scaffold_templates: Project-specific skills to create
```

### Step 3: Generate Report

```markdown
# Skill Recommendations for {project}

## Detected Stack

| Category | Detected |
|----------|----------|
| Languages | TypeScript, Python |
| Frameworks | Next.js, FastAPI |
| Database | PostgreSQL (Supabase) |
| ORM | SQLAlchemy |
| Testing | Vitest, Pytest |
| AI/ML | BAML |

## Generic Skills (in plugin)

| Skill | Reason | Status |
|-------|--------|--------|
| baml-integration | BAML files in baml_src/ | Recommended |
| supabase-patterns | Supabase dependency | Recommended |
| schema-alignment | SQLAlchemy + Alembic | Recommended |

## Project-Specific Skills (scaffoldable)

| Template | Trigger | Output |
|----------|---------|--------|
| project-research | 3 research agents found | .claude/skills/{project}-research/ |
| project-domain | 12 models in src/models/ | .claude/skills/{project}-domain/ |

## Actions

Run with `--auto-activate` to activate generic skills.
Run with `--scaffold` to create project-specific skills.
```

### Step 4: Activate Skills (if --auto-activate)

Mark recommended skills as active in project config:

```markdown
For each recommended skill:
  Log: "Activating skill: {skill_name}"

Skills activated. They will be loaded in future sessions.
```

### Step 5: Scaffold Skills (if --scaffold)

Create project-specific skills from templates:

```markdown
For each scaffold candidate:
  1. Copy template from plugins/ai-dev-kit/skills/stack-analyzer/templates/{template}/
  2. Place in .claude/skills/{project}-{template}/
  3. Add generation header to SKILL.md
  4. Replace {project} placeholders with actual project name

Created:
- .claude/skills/book-vetting-research/SKILL.md
- .claude/skills/book-vetting-domain/SKILL.md
```

### Step 6: Update Manifest

Create or update `.claude/skills/_generated.json`:

```json
{
  "generated_by": "ai-dev-kit:recommend-skills",
  "generated_at": "2025-12-24T10:00:00Z",
  "plugin_version": "1.0.0",
  "skills_created": [
    {
      "path": ".claude/skills/book-vetting-research/",
      "template": "project-research",
      "created_at": "2025-12-24T10:00:00Z"
    }
  ],
  "cleanup_instructions": "These files persist after plugin uninstall. Delete if no longer needed."
}
```

## Output Format

Begin with a short control-plane reminder that Claude Code (ai-dev-kit plugin) orchestrates the workflow.
Encourage delegation to other agents via `/ai-dev-kit:delegate <provider> "<task>"` when they are better suited.

### Console Output (Default)

```
Stack Analysis for: book-vetting

Detected:
  Languages:  TypeScript, Python
  Frameworks: Next.js 14, FastAPI
  Database:   PostgreSQL (Supabase)
  AI/ML:      BAML

Recommended Generic Skills:
  ✓ baml-integration     BAML files detected
  ✓ supabase-patterns    Supabase dependency
  ✓ schema-alignment     SQLAlchemy + Alembic

Scaffoldable Project Skills:
  → project-research     3 research agents found
  → project-domain       12 models detected

Run with --auto-activate to activate generic skills.
Run with --scaffold to create project-specific skills.
```

### JSON Output (--format=json)

```json
{
  "project": "book-vetting",
  "detected_stack": {
    "languages": ["typescript", "python"],
    "frameworks": [
      {"name": "next.js", "version": "14.x"},
      {"name": "fastapi", "version": "0.100.x"}
    ],
    "databases": ["postgresql"],
    "ai_ml": ["baml"]
  },
  "recommended_skills": [
    {
      "skill": "baml-integration",
      "reason": "BAML files detected in baml_src/",
      "status": "recommended"
    }
  ],
  "scaffold_candidates": [
    {
      "template": "project-research",
      "trigger": "3 research agents found",
      "output_path": ".claude/skills/book-vetting-research/"
    }
  ]
}
```

## Integration

### With /ai-dev-kit:setup

This command runs automatically during brownfield setup:

```markdown
/ai-dev-kit:setup

Step 3: Skill Recommendation
Running: /ai-dev-kit:recommend-skills

[Stack analysis output]

? Activate recommended skills? [y/N] y
  ✓ Activated: baml-integration
  ✓ Activated: supabase-patterns

? Scaffold project-specific skills? [y/N] y
  ✓ Created: .claude/skills/book-vetting-research/
```

### With /ai-dev-kit:quickstart-codebase

Also runs as part of comprehensive onboarding:

```markdown
/ai-dev-kit:quickstart-codebase

[Other onboarding steps...]

Step: Skill Recommendations
[recommend-skills output]
```

## Error Handling

### No Stack Detected

```markdown
No package manifests found.

Ensure the project has:
- package.json (Node.js)
- pyproject.toml (Python)
- go.mod (Go)
- Cargo.toml (Rust)

Or specify manually: /ai-dev-kit:recommend-skills --stack="python,fastapi,postgresql"
```

### Template Not Found

```markdown
Template 'project-research' not found.

Expected: plugins/ai-dev-kit/skills/stack-analyzer/templates/project-research/

Check plugin installation: /ai-dev-kit:validate
```

## Best Practices

1. **Run early**: Run during project onboarding for best results
2. **Review before scaffolding**: Check recommendations before creating project skills
3. **Customize after creation**: Edit scaffolded skills for project-specific needs
4. **Track manifest**: Commit `.claude/skills/_generated.json` for team visibility
5. **Re-run after changes**: Re-run when adding new dependencies
