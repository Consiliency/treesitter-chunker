# TypeScript MCP Server Template

A starter template for building MCP servers in TypeScript using the official SDK.

## Quick Start

1. **Copy this template**
   ```bash
   cp -r dev-tools/mcp/_templates/typescript dev-tools/mcp/my-server
   ```

2. **Install dependencies**
   ```bash
   cd dev-tools/mcp/my-server
   npm install
   ```

3. **Modify `server.ts`**
   - Update the server name and version
   - Add your tools to the `TOOLS` array
   - Implement tool logic in the `CallToolRequestSchema` handler

4. **Build (optional, for production)**
   ```bash
   npm run build
   ```

5. **Register in `.mcp.json`**
   ```json
   {
     "mcpServers": {
       "my-server": {
         "command": "npx",
         "args": ["ts-node", "dev-tools/mcp/my-server/server.ts"]
       }
     }
   }
   ```

   Or if built:
   ```json
   {
     "mcpServers": {
       "my-server": {
         "command": "node",
         "args": ["dev-tools/mcp/my-server/server.js"]
       }
     }
   }
   ```

## Server Structure

```typescript
// Define your tools
const TOOLS: Tool[] = [
  {
    name: "my_tool",
    description: "What this tool does",
    inputSchema: {
      type: "object",
      properties: {
        param1: { type: "string", description: "..." },
      },
      required: ["param1"],
    },
  },
];

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "my_tool": {
      const { param1 } = args as { param1: string };
      // Your implementation here
      return {
        content: [{ type: "text", text: "result" }],
      };
    }
  }
});
```

## Adding Resources

MCP servers can also expose resources:

```typescript
import {
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

// In server capabilities, add:
// resources: {}

server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: "file:///path/to/resource",
        name: "My Resource",
        mimeType: "text/plain",
      },
    ],
  };
});

server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;
  return {
    contents: [{ uri, text: "Resource content here", mimeType: "text/plain" }],
  };
});
```

## Environment Variables

Access environment variables passed from `.mcp.json`:

```typescript
const allowedPaths = process.env.ALLOWED_PATHS || "./";
const apiKey = process.env.API_KEY;
```

## Resources

- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [MCP Specification](https://spec.modelcontextprotocol.io/)
- [Example Servers](https://github.com/modelcontextprotocol/servers)
