---
name: specs-find
argument-hint: "[--extra ../other-repo]"
description: "Discover specs across repos and emit a JSON/TOON manifest with IDs, titles, and links."
allowed-tools: Read, Glob, Grep
---

# Find Specifications

Discover specifications in `specs/` and `specs/external-requests/` across the current repository and optional sibling repositories. Outputs a normalized manifest (JSON or TOON) containing spec IDs, titles, links, and traceability metadata.

## Usage

```
/ai-dev-kit:specs-find
/ai-dev-kit:specs-find --extra ../platform-contracts
/ai-dev-kit:specs-find --extra ../platform-contracts --extra ../mobile-app
```

Under the hood, this uses the CLI helper:

```
ai-dev-kit specs-find --root . --extra ../platform-contracts --format toon
```

## What It Scans

- `specs/` (all markdown specs, excluding `specs/templates/`)
- `specs/external-requests/` for cross-repo request specs (REQ-*)
- Additional repositories passed via `--extra` (must contain `specs/`)

## Output Contract

- `format`: `spec-manifest/v1`
- `generated_at`: ISO-8601 UTC timestamp
- `sources[]`: repositories included (name + absolute path)
- `specs[]`: sorted by repo → path → spec ID
  - `id`: Spec identifier (e.g., `REQ-NOTIFY-001`)
  - `title`: Heading text after the ID
  - `source_repo`: Repository name (directory name)
  - `path`: Path relative to repo root
  - `link`: Path plus heading anchor (for contextual loading)
  - `hash`: SHA-256 of the file content (traceability)

## Sample Manifest (JSON)

```json
{
  "format": "spec-manifest/v1",
  "generated_at": "2025-01-05T18:07:52.123456+00:00",
  "sources": [
    {"repository": "ai-dev-kit", "root": "/workspace/ai-dev-kit"},
    {"repository": "platform-contracts", "root": "/workspace/platform-contracts"}
  ],
  "specs": [
    {
      "id": "REQ-NOTIFY-001",
      "title": "Email Sending Endpoint",
      "source_repo": "ai-dev-kit",
      "path": "specs/external-requests/notify.md",
      "link": "specs/external-requests/notify.md#req-notify-001-email-sending-endpoint",
      "hash": "c4b68f4c9b8d7a1c0c8bc8a6c5b01db4c8b63452b4c83502f4b1b5a6d0f1c111"
    },
    {
      "id": "REQ-AUTH-104",
      "title": "Device Login Contract",
      "source_repo": "platform-contracts",
      "path": "specs/auth/device-login.md",
      "link": "specs/auth/device-login.md#req-auth-104-device-login-contract",
      "hash": "db587c0b57714b203ea5e41dbf3fc3fd2bdbeb2b7f1cb201b8f3f9df3ff11000"
    }
  ]
}
```

## Sample Manifest (TOON)

```
spec_manifest:
  format: spec-manifest/v1
  generated_at: 2025-01-05T18:07:52.123456+00:00
  sources[2]{repository|root}
  sources[0]{ai-dev-kit|/workspace/ai-dev-kit}
  sources[1]{platform-contracts|/workspace/platform-contracts}
  specs[2]{id|title|source_repo|path|link|hash}
  specs[0]{REQ-NOTIFY-001|Email Sending Endpoint|ai-dev-kit|specs/external-requests/notify.md|specs/external-requests/notify.md#req-notify-001-email-sending-endpoint|c4b68f4c9b8d7a1c0c8bc8a6c5b01db4c8b63452b4c83502f4b1b5a6d0f1c111}
  specs[1]{REQ-AUTH-104|Device Login Contract|platform-contracts|specs/auth/device-login.md|specs/auth/device-login.md#req-auth-104-device-login-contract|db587c0b57714b203ea5e41dbf3fc3fd2bdbeb2b7f1cb201b8f3f9df3ff11000}
```

## Workflow

1. Load repositories: current repo + any `--extra` sibling repos
2. Walk `specs/` (excluding `specs/templates/`) for `*.md` files
3. Parse headings with IDs (e.g., `## REQ-NOTIFY-001: Email Sending Endpoint`)
4. Build anchors from ID + title, compute file hash, and normalize paths
5. Emit manifest in JSON or TOON format

## Tips

- Keep spec IDs stable; they are used for cross-repo traceability.
- Use `--format toon` for compact embedding in prompts.
- For mono-repo setups, omit `--extra`; everything under `specs/` is discovered automatically.
