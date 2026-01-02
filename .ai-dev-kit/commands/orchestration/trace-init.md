---
name: trace-init
argument-hint: "[spec-id] [--spec-url] [--repo owner/name] [--plan plan.md] [--lane-manifest lane.json]"
description: "Seed branch, issue/PR templates, and trace metadata for a specification."
allowed-tools: ["Bash", "Read", "Agent"]
---

# Trace Initialization

Generate deterministic trace artifacts for a specification and persist them to
`.claude/ai-dev-kit/trace/`.

## Inputs

- `spec-id` (required): Identifier from the spec system (e.g., `SPEC-102`).
- `--spec-url` (optional): Direct URL to the spec for backlinks.
- `--repo` (optional): GitHub `owner/name` slug. When provided and a token is
  available (`AI_DEV_KIT_GITHUB_TOKEN`, `GITHUB_TOKEN`, or `GH_TOKEN`), the
  helper opens an issue and a draft PR.
- `--plan`: Phase/plan documents to receive trace markers.
- `--lane-manifest`: Lane manifest files (Markdown or JSON) to update with trace markers.
- `--offline`: Skip GitHub calls even if a token exists.

## Process

1. Compute deterministic identifiers
   - Branch: `trace/<spec-id-slug>`
   - Issue title: `[<spec-id>] Trace init`
   - PR title: `[<spec-id>] Draft implementation`

2. Generate offline templates
   - Issue template: `.claude/ai-dev-kit/trace/issue.md`
   - PR template: `.claude/ai-dev-kit/trace/pr.md`
   - Branch hint: `.claude/ai-dev-kit/trace/branch.txt`
   - Trace manifest: `.claude/ai-dev-kit/trace/trace.json`

3. Optional GitHub automation
   - If `--repo` and a token are present, create:
     - Issue via `/repos/<repo>/issues`
     - Draft PR via `/repos/<repo>/pulls` (linked to the issue when available)
   - Persist the returned IDs/URLs into `trace.json`.

4. Propagate trace markers
   - Inject a `trace` block into each plan and lane manifest:
     - Markdown: `<!-- trace:start --> ... <!-- trace:end -->`
     - JSON: `{ "trace": { ... } }`

## Example

```bash
python plugins/ai-dev-kit/scripts/trace_init.py SPEC-42 \
  --spec-url https://specs.local/SPEC-42 \
  --repo acme/backend \
  --plan plans/phase-2.md \
  --lane-manifest plans/phase-2-lanes.json
```

Offline mode:

```bash
python plugins/ai-dev-kit/scripts/trace_init.py SPEC-42 --offline
```
