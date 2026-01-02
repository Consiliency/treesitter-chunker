---
name: docs-update
argument-hint: "[source|--all] [--force]"
description: "Update external documentation using the discover -> summarize -> assemble pipeline. Detects changes and updates only what's needed."
allowed-tools: Read, Write, Bash(curl:*, which:*, cursor-agent:*, python3:*), Task, browser_subagent
---

# Update External Documentation

Orchestrates the documentation update pipeline using specialized sub-agents.

## CRITICAL: Agent Invocation

You MUST use the **Task tool** with `subagent_type` to spawn agents. DO NOT manually implement what agents do - SPAWN the agents.

**Task tool parameters:**

- `subagent_type`: Agent name (e.g., `"docs-discover-llmstxt"`)
- `prompt`: Structured prompt with all inputs
- `description`: Short description (3-5 words)
- `run_in_background`: `false` for sequential, `true` for parallel
- `model`: Optional, defaults to agent's configured model

**Available agents:**

| Agent | subagent_type | Purpose |
|-------|---------------|---------|
| Discovery (llms.txt) | `docs-discover-llmstxt` | Detect changes in llms.txt sources |
| Discovery (GitHub) | `docs-discover-github` | Detect changes in GitHub-hosted docs |
| Discovery (Web) | `docs-discover-web` | Crawl websites for doc pages |
| Discovery (Browser) | `docs-discover-browser` | JS-rendered sites via browser automation |
| Summarizer | `docs-summarize-page` | Summarize a single page to TOON |
| Assembler | `docs-assemble` | Build final index structure |

## Pipeline

```
+----------------+     +----------------+     +----------------+
|   Discover     |---->|   Summarize    |---->|   Assemble     |
|  (1 agent)     |     | (N parallel)   |     |  (1 agent)     |
+----------------+     +----------------+     +----------------+
```

## Inputs

- `$1`: Source identifier (e.g., `baml`) or `--all` for all sources
- `--force`: Skip change detection, re-process everything

## Workflow

### 1. Load Registry

```
@ai-docs/libraries/_registry.json
```

Determine which sources to process based on `$1`.

### 2. For Each Source

#### 2a. Check Cached Discovery URLs

Before spawning discovery, check if `.meta.json` contains cached discovery results:

```
@ai-docs/libraries/{source_id}/.meta.json
```

**If `discovery.llms_txt.successful_url` exists** (for llmstxt strategy):
1. Verify the URL still works: `curl -sI "{successful_url}" | head -1`
2. If 200: Use cached URL directly, skip discovery phase
3. If fails: Proceed to full discovery

**If `discovery.sitemap.url` exists** (for web_sitemap strategy):
1. Verify the sitemap URL still works
2. If 200: Pass to discovery agent as `discovery_context.sitemap.url`
3. This avoids re-probing for sitemap location

**If `discovery.robots_txt.sitemaps` exists**:
1. Pass to discovery agent as `discovery_context.robots_txt.sitemaps`
2. Discovery agent will check these before default paths

**Pass cached context to discovery agent:**
```json
{
  "discovery_context": {
    "sitemap": {"url": "{cached sitemap url if valid}"},
    "robots_txt": {
      "sitemaps": ["{cached sitemaps}"],
      "allowed_paths": ["{cached allowed}"],
      "disallowed_paths": ["{cached disallowed}"],
      "crawl_delay": "{cached delay}"
    }
  }
}
```

#### 2a.1. Build Fallback Chain

Before spawning discovery, construct a fallback chain from the registry strategy configuration:

1. Read the strategy entry from `registry.strategies[source.strategy]`
2. Extract `supplements` array (e.g., `["web_sitemap", "browser_crawl"]`)
3. Build ordered fallback chain: `[primary_strategy, ...supplements]`
4. Extract `triggers` object for failure detection

**Example for llmstxt strategy:**
```json
{
  "fallback_chain": ["llmstxt", "web_sitemap", "browser_crawl"],
  "triggers": {
    "blocked_status_codes": [404, 403, 301],
    "response_size_threshold": 512,
    "error_patterns": ["<!DOCTYPE", "<html", "404", "Not Found"]
  },
  "attempt": 1,
  "previous_failures": []
}
```

**Pre-validation (optional optimization):**
For llmstxt strategy, do a quick HEAD check before spawning:
```bash
curl -sI "{llms_txt_url}" 2>/dev/null | head -1
```
If response is 404/403/301, immediately advance to next strategy in chain.

#### 2b. Spawn Discovery Agent (with Fallback)

Select agent based on `source.strategy`:

| Strategy | subagent_type |
|----------|---------------|
| `llmstxt` | `docs-discover-llmstxt` |
| `github_raw`, `docusaurus`, `mintlify`, `gitbook` | `docs-discover-github` |
| `web_sitemap`, `web_crawl` | `docs-discover-web` |
| `browser_crawl` | `docs-discover-browser` |

**Verify Playwright (via wrapper)** (before browser operations):
- If strategy is `browser_crawl` or browser fallback may be needed:
  1. Check if Chrome debugging endpoint is accessible:
     ```bash
     curl -s "http://localhost:9222/json/version" > /dev/null 2>&1
     ```
  2. If not accessible and `AUTO_LAUNCH_CHROME_DEBUG=true`:
     - Attempt auto-launch: `.claude/ai-dev-kit/dev-tools/scripts/auto-launch-chrome-debug.sh`
     - Wait 2-3 seconds, then re-check
  3. Set `playwright_ready` (true/false) based on Chrome debugging status
  4. If `playwright_ready=false`, warn user and provide setup instructions

**Automatic browser fallback**: If `docs-discover-web` fails with:
- Empty response (< 1KB)
- 403 Forbidden
- Few/no navigation links found

AND browser tools are available, automatically retry with `docs-discover-browser`.

**Use Task tool:**

```
subagent_type: "docs-discover-llmstxt"  # or appropriate type
description: "Discover {source_id} docs"
prompt: |
  Discover documentation changes.

  Input:
  - source_id: {id}
  - config: {JSON of source config from registry}
  - existing_meta: {JSON of .meta.json contents, or null if first run}
  - discovery_context: {JSON from step 2a - cached URLs and robots.txt info, or null}
  - playwright_ready: {true/false} (if browser strategy, include Chrome debugging status)
  - fallback_context: {JSON from step 2a.1 - chain, triggers, attempt number}

  Return: JSON change report with new/changed/unchanged/deleted pages
```

Wait for agent to complete before proceeding.

**Fallback Logic (after discovery returns):**

Evaluate discovery result against `triggers`:

1. **Check for failure conditions:**
   - Discovery returned `ok: false` or `error` field
   - HTTP status in `triggers.blocked_status_codes` (404, 403, 301)
   - Response size < `triggers.response_size_threshold` (512 bytes)
   - Content matches any `triggers.error_patterns` (HTML error pages)
   - Empty or near-empty `pages` array (< 3 pages for established sources)

2. **If failure detected AND fallback_chain has remaining strategies:**
   ```
   Log: "{source_id}: {strategy} failed ({reason}), trying {next_strategy}..."

   previous_failures.push({
     strategy: current_strategy,
     reason: failure_reason,
     timestamp: now
   })

   current_strategy = fallback_chain.shift()
   attempt++

   GOTO step 2b (respawn with new strategy)
   ```

3. **If all fallbacks exhausted:**
   ```
   Log: "{source_id}: All strategies failed"
   Report: List all attempted strategies and their failure reasons
   Skip to next source
   ```

4. **On success:**
   ```
   Log: "{source_id}: Discovered {n} pages via {strategy}"
   If strategy != primary: Log: "(fallback from {primary})"

   Store successful strategy in discovery report for .meta.json
   ```

**Note**: If using cached `discovery_context`, the discovery agent will skip URL probing and use the pre-validated URLs directly, significantly speeding up updates.

#### 2c. Check for Updates

If discovery reports no changes and `--force` not set:
```
{source}: No changes detected
   Last checked: {timestamp}
```
Skip to next source.

#### 2d. Fetch Changed Content

For sources requiring content fetch:

Prefer best-effort fetch (Playwright→curl) for normal websites; keep curl for raw GitHub.

Heuristic:
- Use curl directly for `raw.githubusercontent.com` (fast/reliable).
- Otherwise, fetch via `docs-fetch-url(url=page.url, purpose="html")` and use returned `content`.
- If `docs-fetch-url` returns `ok=false`, fall back to the original curl behavior.

Example (conceptual):
```
subagent_type: "docs-fetch-url"
description: "Fetch page content"
prompt: |
  Fetch URL.

  Input:
  - url: {page.url}
  - purpose: "html"
```

#### 2e. Parallel Summarization

For each page needing summarization, **use Task tool with `run_in_background: true`**:

```
subagent_type: "docs-summarize-page"
description: "Summarize {page_path}"
run_in_background: true
prompt: |
  Summarize this documentation page.

  Input:
  - source_id: {id}
  - page_path: {path}
  - section: {section}
  - title: {title if known}
  - content: |
      {fetched page content}
  - source_url: {url}
  - content_hash: {sha256 hash}

  Return: TOON-formatted page summary (Strict adherence to compact list format and quoted strings required)
```

**Parallelization:**

- Spawn up to 5 agents concurrently using `run_in_background: true`
- Use `AgentOutputTool` to collect results from background agents
- Wait for batch to complete, then start next batch
- Track successes and failures

#### 2f. Assembly

Once all summarization complete, **use Task tool**:

```
subagent_type: "docs-assemble"
description: "Assemble {source_id} docs"
prompt: |
  Assemble documentation structure from page summaries.

  Input:
  - source_id: {id}
  - source_config: {JSON of registry config}
  - new_summaries:
      {Array of TOON content from summarization agents}
  - change_report: {JSON from discovery agent}
  - output_base: ai-docs/libraries/{id}

  Action: Write all index files, page files, full-context.md, and .meta.json
```

Wait for assembly to complete.

**Note**: The docs-assemble agent automatically runs TOON validation and auto-fix tools after writing files. Verify the completion report shows "Validation: passed" or lists fixes applied.

### 3. Update Root Index

After all sources processed, regenerate:
```
@ai-docs/libraries/_index.toon
```

Update library entries with new page counts and timestamps.

### 4. Summary Report

```markdown
## Documentation Update Summary

| Source | Status | Pages | Changed | Strategy | Linting |
|--------|--------|-------|---------|----------|---------|
| baml | Updated | 47 | 5 | github_raw | Passed |
| mcp | No changes | 28 | 0 | llmstxt | - |
| antigravity-ide | Updated | 40 | 40 | web_crawl | Fixed |

### baml Changes
- NEW: guide/new-feature
- UPDATED: reference/types, reference/function
- DELETED: guide/deprecated-api

### TOON Linting
- baml: Passed validation
- antigravity-ide: Auto-fixed 3 issues (comments; commas; indentation)

### Errors
- anthropic-sdk: Failed to fetch llms.txt (404)

### Next Steps
- Reference docs: @ai-docs/libraries/baml/_index.toon
- Full context: @ai-docs/libraries/baml/full-context.md
```

## Usage

```bash
# Update all tracked sources
/ai-dev-kit:docs-update --all

# Update specific source
/ai-dev-kit:docs-update baml

# Force full refresh (ignore change detection)
/ai-dev-kit:docs-update baml --force
```

## Error Handling

- **Discovery failure (with fallback)**:
  1. Check if `strategy.supplements` defines fallback strategies
  2. If available: Attempt each fallback in order, logging each attempt
  3. Only skip source after ALL strategies in fallback chain exhausted
  4. Report final status showing which strategies were attempted:
     ```
     anthropic-sdk: FAILED
       - llmstxt: 404 Not Found
       - web_sitemap: No sitemap.xml found
       - browser_crawl: Skipped (no browser available)
     ```
- **Discovery failure (no fallback)**: Log, skip source, continue with others
- **Summarization failure**: Log failed page, continue with others
- **Assembly failure**: Report error, partial state may exist
- Always report what succeeded and what failed, including successful fallbacks:
  ```
  react: Updated via web_sitemap (fallback from llmstxt)
    - llmstxt: 404 Not Found
    - web_sitemap: SUCCESS (150 pages)
  ```
