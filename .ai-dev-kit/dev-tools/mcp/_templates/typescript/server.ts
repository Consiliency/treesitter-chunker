#!/usr/bin/env npx ts-node
/**
 * MCP Server Template (TypeScript)
 *
 * A starter template for building Model Context Protocol servers.
 * Uses the official MCP TypeScript SDK.
 *
 * Usage:
 *    1. Copy this directory to dev-tools/mcp/your-server-name/
 *    2. Install dependencies: npm install
 *    3. Modify the tools below to implement your functionality
 *    4. Register in .mcp.json
 *
 * For more information, see:
 *    - MCP SDK: https://github.com/modelcontextprotocol/typescript-sdk
 *    - MCP Spec: https://spec.modelcontextprotocol.io/
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";

// Create the MCP server instance
const server = new Server(
  {
    name: "your-server-name",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define available tools
const TOOLS: Tool[] = [
  {
    name: "example_tool",
    description:
      "An example tool that echoes input. Replace with your implementation.",
    inputSchema: {
      type: "object",
      properties: {
        message: {
          type: "string",
          description: "The message to echo back",
        },
      },
      required: ["message"],
    },
  },
  // Add more tools here...
];

// Handle list_tools request
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: TOOLS };
});

// Handle call_tool request
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case "example_tool": {
      const message = (args as { message: string }).message;
      return {
        content: [{ type: "text", text: `Echo: ${message}` }],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});

// Run the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("MCP Server running on stdio");
}

main().catch(console.error);
