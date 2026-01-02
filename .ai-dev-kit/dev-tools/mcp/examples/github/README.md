# GitHub MCP Server

A simple MCP server for GitHub API operations. Demonstrates API wrapper patterns.

## Note

For full-featured GitHub integration, use the official MCP server:

```bash
claude mcp add github -- npx -y @modelcontextprotocol/server-github
```

This example shows how to build custom API wrappers for any service.

## Features

- **list_issues**: List repository issues
- **get_issue**: Get issue details
- **list_prs**: List pull requests
- **get_repo**: Get repository info
- **search_code**: Search code across GitHub

## Configuration

Add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "github-custom": {
      "command": "python3",
      "args": ["dev-tools/mcp/examples/github/server.py"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    }
  }
}
```

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GITHUB_TOKEN` | GitHub personal access token | Recommended |

Without a token, API rate limits (60 requests/hour) apply.

### Creating a Token

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Generate a new token with:
   - `repo` (for private repos)
   - `read:org` (for org repos)
3. Set in your environment:
   ```bash
   export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
   ```

## Usage Examples

```
"List open issues in anthropics/claude-code"
"Get details of issue #42 in my-org/my-repo"
"Show open pull requests in facebook/react"
"Search for 'useState hook' in GitHub code"
```

## Dependencies

```bash
uv pip install mcp
```

Uses Python's built-in `urllib` for HTTP requests (no additional dependencies).

## Extending

To add more GitHub operations:

1. Add a new tool definition in `list_tools()`
2. Implement the handler in `call_tool()`

Example - add comment to issue:

```python
Tool(
    name="add_comment",
    description="Add a comment to an issue",
    inputSchema={
        "type": "object",
        "properties": {
            "owner": {"type": "string"},
            "repo": {"type": "string"},
            "issue_number": {"type": "integer"},
            "body": {"type": "string", "description": "Comment text"},
        },
        "required": ["owner", "repo", "issue_number", "body"],
    },
)

# In call_tool():
elif name == "add_comment":
    endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}/comments"
    result = github_request(endpoint, method="POST", data={"body": body})
    return [TextContent(type="text", text=f"Comment added: {result['html_url']}")]
```

## Rate Limits

- Without token: 60 requests/hour
- With token: 5,000 requests/hour

The server logs warnings when approaching limits.
