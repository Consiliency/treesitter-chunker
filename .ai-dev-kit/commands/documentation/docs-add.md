---
name: docs-add
argument-hint: "[homepage-url] [identifier]"
description: "Add a new documentation source to track. Analyzes the site to determine best strategy."
allowed-tools: Read, Write, Bash(curl:*, npx:*, python3:*, cursor-agent:*, which:*), Task, browser_subagent
---

# Add Documentation Source

Adds a new external documentation source to the tracking system.

## Inputs

- `$1`: Homepage URL (e.g., `https://docs.viperjuice.dev`)
- `$2`: Short identifier (e.g., `example`)

## Workflow

### 1. Analyze the Documentation Site

#### Extract URL Components
Parse `$1` to extract:
- `SCHEME` (http/https)
- `HOST` (e.g., `platform.openai.com`)
- `BASE_DOMAIN` (e.g., `openai.com` - remove first subdomain if present)

```bash
# Example: https://platform.openai.com/docs/api-reference
# → SCHEME=https, HOST=platform.openai.com, BASE_DOMAIN=openai.com
```

#### Check for llms.txt (Expanded Multi-Domain Search)

Search for llms.txt across multiple locations, stopping on first success.
Track all checked URLs for metadata persistence.

**Initialize**: `discovery_llms_txt = { checked_urls: [], successful_url: null }`

**Phase 1: Homepage paths** (current behavior)
```bash
curl -sI "$1/llms.txt" | head -1
curl -sI "$1/llms-full.txt" | head -1
```
Record status in `checked_urls`. If 200, set `successful_url` and skip remaining phases.

**Phase 2: Domain root**
```bash
curl -sI "${SCHEME}://${HOST}/llms.txt" | head -1
curl -sI "${SCHEME}://${HOST}/llms-full.txt" | head -1
curl -sI "${SCHEME}://${HOST}/.well-known/ai.txt" | head -1
```

**Phase 3: Common doc paths**
```bash
curl -sI "${SCHEME}://${HOST}/docs/llms.txt" | head -1
```

**Phase 4: Related subdomains** (extract base_domain)
```bash
curl -sI "https://developers.${BASE_DOMAIN}/llms.txt" | head -1
curl -sI "https://docs.${BASE_DOMAIN}/llms.txt" | head -1
curl -sI "https://api.${BASE_DOMAIN}/llms.txt" | head -1
curl -sI "https://${BASE_DOMAIN}/llms.txt" | head -1
```

**For any HEAD check that returns 200**, verify content exists:
- Spawn `docs-fetch-url` with `purpose: "text"` for that URL
- If `ok=true` and `content` is non-empty, set `successful_url` and stop
- If `ok=false` and `bot_protection.detected=true`:
  - Record `bot_protection_detected = true`
  - If `human_intervention_used=true`, record that as well
  - Continue to next URL

**If all HEAD checks blocked (403/406/429)**, fall back to best-effort fetch for each URL using `docs-fetch-url` with `purpose: "text"`.

**Result**: Store `discovery_llms_txt` for metadata persistence.

**Initialize tracking variables** (at start of discovery):
```
bot_protection_detected = false
human_intervention_used = false
```

Update these flags whenever a `docs-fetch-url` response indicates:
- `bot_protection.detected = true` → set `bot_protection_detected = true`
- `human_intervention_used = true` → set `human_intervention_used = true`

#### Check for robots.txt
```bash
curl -s "${SCHEME}://${HOST}/robots.txt"
```

Parse robots.txt to extract:
- **Sitemaps**: Lines matching `Sitemap: {url}` (case-insensitive)
- **Allowed paths**: Lines matching `Allow: {path}` for User-agent: *
- **Disallowed paths**: Lines matching `Disallow: {path}` for User-agent: *
- **Crawl-delay**: Lines matching `Crawl-delay: {seconds}`

**Initialize**: `discovery_robots_txt = { url, status, sitemaps: [], allowed_paths: [], disallowed_paths: [], crawl_delay: null }`

Example parsing:
```bash
# Extract sitemaps
grep -i "^Sitemap:" robots.txt | sed 's/^[Ss]itemap:\s*//'

# Extract allowed paths for general user agent
awk '/User-agent:\s*\*/,/^$/' robots.txt | grep -i "^Allow:" | sed 's/^[Aa]llow:\s*//'
```

**Use discovered sitemaps**: If sitemaps found in robots.txt, add them to the sitemap check list (see below).

#### Check for GitHub Link
Prefer best-effort fetch (Playwright→curl) so this works even when curl 403s:

1) Fetch homepage HTML via `docs-fetch-url`:
```
subagent_type: "docs-fetch-url"
description: "Fetch homepage HTML"
prompt: |
  Fetch URL.

  Input:
  - url: $1
  - purpose: "html"
  - allow_human_intervention: true
```

Store the JSON output, then set `HOMEPAGE_HTML = content` when `ok=true`.

**Handle bot protection response**:
- If `bot_protection.detected=true`: update `bot_protection_detected = true`
- If `human_intervention_used=true`: update `human_intervention_used = true`
- If intervention succeeded (`ok=true` after intervention), continue with extracted content

2) If `ok=true`, extract GitHub links from `HOMEPAGE_HTML` (simple regex parsing is fine):
- Match `github\\.com/[^"\\s>]+`
- Return up to 5 unique matches

3) If `ok=false` (including after failed intervention), fall back to:
```bash
curl -s "$1" | grep -oP 'github\\.com/[^"'"'"'\\s>]+' | head -5
```

#### Check for Sitemap
**Initialize**: `discovery_sitemap = { url: null, status: null, from_robots_txt: false }`

**Priority order for sitemap URLs**:
1. Sitemaps discovered from robots.txt (if any)
2. `$1/sitemap.xml` (homepage path)
3. `${SCHEME}://${HOST}/sitemap.xml` (domain root)

```bash
# Check each sitemap URL in priority order
curl -sI "{sitemap_url}" | head -1
```

If the HEAD check is blocked (common: 403/406/429) or empty, fall back:

- Spawn `docs-fetch-url` with:
  - `url: {sitemap_url}`
  - `purpose: "text"`
  - `allow_human_intervention: true`

**Handle response**:
- If `ok=true`: Record `discovery_sitemap = { url: {working_url}, status: 200, from_robots_txt: {bool} }`
- If `bot_protection.detected=true`: update `bot_protection_detected = true`
- If `human_intervention_used=true`: update `human_intervention_used = true`
- If `ok=false` after all attempts: continue without sitemap (will rely on crawling)

### 1a. Detect Available Browser Tools

Check which browser tools are available (in priority order):

#### Check for Antigravity browser_subagent
If `browser_subagent` tool is available in your tool list → running in Antigravity IDE

#### Check for cursor-agent CLI
```bash
which cursor-agent
```
If found → can delegate browser tasks to Cursor

#### Check for Playwright (via wrapper)
Check if Chrome debugging endpoint is accessible:

**Verify Chrome debugging endpoint**:
```bash
# Check if Chrome debugging is accessible
curl -s "http://localhost:9222/json/version" > /dev/null 2>&1
CHROME_DEBUGGING_ACCESSIBLE=$?

# If not accessible and auto-launch enabled, attempt launch
if [ $CHROME_DEBUGGING_ACCESSIBLE -ne 0 ] && [ "${AUTO_LAUNCH_CHROME_DEBUG:-false}" = "true" ]; then
    REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    AUTO_LAUNCH_SCRIPT="$REPO_ROOT/.claude/ai-dev-kit/dev-tools/scripts/auto-launch-chrome-debug.sh"
    if [ -f "$AUTO_LAUNCH_SCRIPT" ]; then
        "$AUTO_LAUNCH_SCRIPT" 2>/dev/null || true
        sleep 2
        curl -s "http://localhost:9222/json/version" > /dev/null 2>&1
        CHROME_DEBUGGING_ACCESSIBLE=$?
    fi
fi

# Set playwright_ready based on Chrome debugging status
if [ $CHROME_DEBUGGING_ACCESSIBLE -eq 0 ]; then
    playwright_ready=true
else
    playwright_ready=false
    # Warn user if Chrome not running
    echo "⚠️  Chrome debugging endpoint not accessible"
    echo "   Launch Chrome with: google-chrome --remote-debugging-port=9222"
    echo "   Or use: .claude/ai-dev-kit/dev-tools/scripts/launch-chrome-debug.sh"
    echo "   Or enable auto-launch: export AUTO_LAUNCH_CHROME_DEBUG=true"
fi
```

**Store result as**:
- `available_browser_tool` (one of: antigravity, cursor-cli, playwright, none)
- `playwright_ready` (true/false) - only set if `available_browser_tool == playwright`

### 1b. Detect JavaScript-Rendered Sites

Check if curl returns suspicious response indicating JS rendering:

```bash
# Check response size (JS-rendered sites often return minimal HTML)
CURL_SIZE=$(curl -s "$1" | wc -c)
echo "Response size: $CURL_SIZE bytes"

# Check for JS-required indicators
curl -s "$1" | grep -i "please enable javascript\|noscript\|__NEXT_DATA__\|window.__remixContext" | head -3
```

**JS-rendered indicators**:
- Response < 1KB
- Contains "please enable javascript" or "noscript"
- Contains Next.js/Remix/SPA framework markers
- Only CSS/fonts returned (no text content)

**Store result as**: `js_rendering_detected` (true/false)

### 2. Determine Strategy

**Curl-based strategies are tried first (faster). Browser supplements when needed.**

Priority order (curl-based):
1. `llmstxt` - if llms.txt exists (fastest)
2. `github_raw` - if GitHub repo found with docs
3. `web_sitemap` - if sitemap.xml exists
4. `web_crawl` - standard curl-based crawling

**Browser triggers** (use `browser_crawl` when any occur):
- `js_rendering_detected == true` AND curl returned < 1KB
- Curl gets 403 Forbidden
- Curl returns HTML but few/no navigation links found
- Source has `js_required: true` in registry config

**Browser tool selection** (when browser_crawl triggered):
- If `available_browser_tool == antigravity` → use native browser_subagent
- If `available_browser_tool == cursor-cli` → delegate to cursor-agent
- If `available_browser_tool == playwright` AND `playwright_ready == true` → use Playwright MCP
- If `available_browser_tool == playwright` AND `playwright_ready == false` → warn user; provide Chrome debugging setup instructions; fall back to next available tool or fail gracefully
- If `available_browser_tool == none` → warn user; suggest Playwright setup

If GitHub found, detect framework:
- `fern/docs.yml` -> Fern
- `sidebars.js` -> Docusaurus
- `mint.json` -> Mintlify
- `mkdocs.yml` -> MkDocs
- `SUMMARY.md` -> GitBook

**Fetch fallback order (when browser needed)**: Playwright MCP → curl (via `docs-fetch-url`).

### 3. Gather Information

**Ask user if needed:**
- Full name of the library
- Brief description
- Priority level (high/medium/low)

### 4. Create Registry Entry

Add to `ai-docs/libraries/_registry.json`:

```json
{
  "sources": {
    "{$2}": {
      "name": "{Name}",
      "description": "{Description}",
      "homepage": "$1",
      "strategy": "{detected}",
      "priority": "{user choice or medium}",
      // Strategy-specific config...
    }
  }
}
```

### 5. Create Directory Structure

```bash
mkdir -p ai-docs/libraries/{$2}
```

### 6. Initial Fetch

Run `/ai-dev-kit:docs-update {$2}` to populate documentation.

**If strategy is `browser_crawl`**:
- The discovery agent will use the detected `available_browser_tool`
- Pass `js_required: true` in the browser config if JS rendering was detected
- The agent will automatically select the best available browser tool

### 7. Validate TOON Files

After creating TOON files, validate with official TOON CLI (note: use `--decode`, not `validate`):

```bash
# Validate by attempting decode (fails on invalid TOON)
npx @toon-format/cli --decode ai-docs/libraries/{$2}/_index.toon > /dev/null

# If validation fails, run auto-fix scripts in this order then re-validate
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_comments.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_yaml_lists.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_nested_lists.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_commas.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_pipes.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_multiline.py ai-docs/libraries/{$2}/
python3 .claude/ai-dev-kit/dev-tools/scripts/fix_toon_blank_lines.py ai-docs/libraries/{$2}/

# Re-validate after fixes
npx @toon-format/cli --decode ai-docs/libraries/{$2}/_index.toon > /dev/null

# Also validate the updated root index
npx @toon-format/cli --decode ai-docs/libraries/_index.toon > /dev/null
```

**Critical TOON Rules** (enforced by CLI decoder):
- Do NOT use comments (`# ...`) - TOON CLI doesn't support them
- Do NOT indent tabular array rows incorrectly - rows must be 2-space indented
- Do NOT use YAML-style lists (`- item`) without array declaration (`key[N]{col}:`)
- Do NOT use multiline strings (`key: |`) - use quoted strings with `\n`
- Do NOT use pipe delimiters in inline arrays - use commas
- Do NOT use commas inside quoted strings in tabular arrays - use semicolons
- **Tabular arrays need `[N]` count AND `{cols}` column specification**
- **ALWAYS add a blank line AFTER tabular arrays** to terminate them

### 8. Pass Discovery Metadata to Assembly

Ensure the discovery results are passed to `docs-assemble` for persistence in `.meta.json`:

```json
{
  "discovery": {
    "performed_at": "{ISO timestamp}",
    "llms_txt": "{discovery_llms_txt object}",
    "robots_txt": "{discovery_robots_txt object}",
    "sitemap": "{discovery_sitemap object}",
    "bot_protection_detected": "{from docs-fetch-url response}",
    "human_intervention_used": "{from docs-fetch-url response}"
  }
}
```

### 9. Report

```markdown
## Added Documentation Source: {$2}

**Name**: {Name}
**Homepage**: $1
**Strategy**: {strategy}
**GitHub**: {repo if found}

### Discovery Results
- **llms.txt**: {found at URL / not found} ({N} URLs checked)
- **robots.txt**: {found/not found}
  - Sitemaps: {list or none}
  - Crawl delay: {N seconds or none}
- **Sitemap**: {found at URL / not found}
- **GitHub repo**: {url or not found}
- **Doc framework**: {Fern/Docusaurus/etc or unknown}
- **JS rendering**: {detected/not detected}
- **Browser tool**: {antigravity/cursor-cli/playwright/none}
- **Playwright ready**: {true/false} (only if browser tool is playwright)
- **Bot protection**: {detected/not detected}
- **Human intervention**: {used/not used}

### Initial Crawl
- Pages discovered: {N}
- Sections: {list}
- Estimated tokens: {N}

### Files Created
- ai-docs/libraries/{$2}/_index.toon
- ai-docs/libraries/{$2}/.meta.json
- {N} page summaries

### Usage
- Navigate: @ai-docs/libraries/{$2}/_index.toon
- Full context: @ai-docs/libraries/{$2}/full-context.md
- Update: /ai-dev-kit:docs-update {$2}
```

## Usage

```bash
/ai-dev-kit:docs-add https://docs.boundaryml.com baml
/ai-dev-kit:docs-add https://orm.drizzle.team drizzle
/ai-dev-kit:docs-add https://zod.dev zod
```

## Notes

- Not all sites are easily crawlable
- For problematic sites, suggest they add llms.txt
- Manual configuration may be needed for complex setups
- **Browser automation** is available for JS-rendered sites (one-time setup):
  - Antigravity IDE: Built-in `browser_subagent` (zero config)
  - Cursor: `cursor-agent` CLI or browser MCP (zero config in Cursor)
  - Claude Code: Launch Chrome with debugging: `google-chrome --remote-debugging-port=9222`. Then use the Playwright wrapper: `python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py`
  - **WSL2 users**: See `.claude/ai-dev-kit/dev-tools/mcp/README.md` for Chrome debugging setup
