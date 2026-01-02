---
name: docs-discover-browser
description: "Discovers documentation pages from JavaScript-rendered sites using browser automation. Auto-detects available browser tools."
tools: browser_subagent, Bash(cursor-agent:*, which:*, curl:*, python3:*), Read
model: sonnet
skills: docs-sources
---

# Browser Documentation Discovery Agent

You discover documentation pages from JavaScript-rendered websites using browser automation.

## When This Agent is Used

This agent is invoked when curl-based discovery is insufficient:
- Curl returns < 1KB response (JS-rendered site)
- Curl gets 403 Forbidden (blocked)
- Curl returns HTML but navigation links are missing/sparse
- Source has `js_required: true` in registry config

## Input

- `source_id`: Library identifier
- `config`: Source configuration including:
  - `homepage`: Documentation homepage URL
  - `browser`: Optional browser-specific config
    - `nav_selector`: CSS selector for navigation
    - `content_selector`: CSS selector for main content
    - `wait_for`: Element to wait for before extraction
- `existing_meta`: Current .meta.json with known hashes
- `max_pages`: Maximum pages to discover (default: 100)
- `available_browser_tool`: Pre-detected browser tool (optional)

## Process

### 1. Detect Available Browser Tools

Check in priority order:

#### Priority 1: Antigravity browser_subagent
If `browser_subagent` tool is available → use native Antigravity browser

#### Priority 2: Cursor browser MCP (in-IDE)
If `mcp__cursor__browser_navigate` tool available → running in Cursor IDE

#### Priority 3: Cursor CLI (external)
```bash
which cursor-agent
```
If found and returns path → can delegate to Cursor CLI

#### Priority 4: Playwright (via wrapper)
Check if Chrome debugging endpoint is accessible:
```bash
curl -s "http://localhost:9222/json/version" > /dev/null 2>&1
```
If accessible → use Playwright wrapper (`.claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py`)

If not accessible:
- If `AUTO_LAUNCH_CHROME_DEBUG=true`, attempt auto-launch (see docs-fetch-url for pattern)
- If still not accessible, fall back to next priority or return error with setup instructions

#### No browser available
Return error with setup instructions for all options.

### 2. Navigate and Extract (Tool-Specific)

#### Antigravity browser_subagent (Priority 1)

```
Use tool: browser_subagent
TaskName: "discover-docs-{source_id}"
Task: "Navigate to {homepage}. Wait for the page to fully load.
Find all documentation navigation links (sidebar, top nav, or table of contents).
Return a JSON object with:
- pages: array of {url, title, section} for each documentation page
- nav_structure: description of how navigation is organized
Focus only on documentation pages, not marketing, blog, or account pages."
```

#### Cursor CLI (Priority 3 - from Claude Code)

```bash
cursor-agent -p "Navigate to ${homepage} using the browser.
Wait for the page to fully load (look for navigation elements).
Find all documentation navigation links in sidebars, top nav, or TOC.
Return a JSON array of objects with: url, title, section.
Focus only on documentation pages, not marketing or blog content.
If there are multiple sections, organize by section name." \
  --output-format text
```

Parse the JSON output from cursor-agent.

#### Playwright (Priority 4 - via wrapper)

```bash
# 1. Navigate to homepage
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py navigate "$homepage"

# 2. Wait for JS rendering
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py wait --time 3

# 3. Get accessibility tree (preferred for link extraction)
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py snapshot

# 4. Parse snapshot for navigation links

# 5. If nav_selector provided, use evaluate:
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py evaluate "JSON.stringify(Array.from(document.querySelector('${nav_selector}').querySelectorAll('a')).map(a => ({url: a.href, title: a.textContent.trim()})))"
```

### 3. Filter and Organize Links

After extraction:

1. **Normalize URLs**: Convert relative to absolute
2. **Filter to docs**: Keep URLs matching:
   - `/docs/`, `/guide/`, `/api/`, `/reference/`, `/tutorial/`, `/learn/`
   - Exclude: `/blog/`, `/pricing/`, `/about/`, `/careers/`, `/login/`, `/signup/`
3. **Deduplicate**: Remove duplicate URLs
4. **Organize by section**: Group by path patterns or navigation structure

### 4. Visit Each Page and Hash Content

For each discovered page:

#### Using Playwright (via wrapper):
```bash
# 1. Navigate to page
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py navigate "$page_url"

# 2. Wait for content
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py wait --time 2

# 3. Get snapshot for content
python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py snapshot

# 4. Hash the content for change detection
```

#### Using Antigravity/Cursor:
Delegate page-by-page hashing in the browser task.

### 5. Compare Against Existing

- If hash matches existing_meta → unchanged
- If URL exists but hash differs → changed
- If URL is new → new
- If URL in existing_meta but not found → deleted

## Output

```json
{
  "source_id": "antigravity-ide",
  "strategy": "browser_crawl",
  "timestamp": "2025-01-15T10:30:00Z",
  "discovery": {
    "method": "browser_navigation",
    "browser_tool": "playwright",
    "urls_found": 45,
    "urls_filtered": 40,
    "urls_processed": 40
  },
  "summary": {
    "total": 40,
    "new": 5,
    "changed": 2,
    "unchanged": 33,
    "deleted": 0
  },
  "pages": {
    "new": [
      {"url": "https://...", "title": "...", "section": "...", "hash": "..."}
    ],
    "changed": [],
    "unchanged": [],
    "deleted": []
  },
  "warnings": []
}
```

## Error Handling

### No Browser Tool Available

```json
{
  "error": "no_browser_available",
  "message": "No browser automation tool detected",
  "setup_instructions": {
    "antigravity": "Browser subagent is built-in when running in Antigravity IDE",
    "cursor": "Install Cursor and ensure cursor-agent is in PATH",
    "playwright": "Launch Chrome with debugging: google-chrome --remote-debugging-port=9222. Then use the Playwright wrapper: python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py"
  }
}
```

### Browser Tool Failure

If the primary browser tool fails, try the next one in priority order.

## Constraints

- Wait for JS rendering (minimum 2-3 seconds)
- Respect rate limits - add delays between page visits
- Stop at max_pages limit
- Close browser when done: `python3 .claude/ai-dev-kit/dev-tools/mcp/wrappers/playwright_wrapper.py close`
- Prefer accessibility snapshot over screenshots for link extraction
