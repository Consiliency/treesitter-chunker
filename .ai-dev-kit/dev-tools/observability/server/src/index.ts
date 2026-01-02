/**
 * Observability Server for ai-dev-kit
 * WebSocket-based real-time event streaming
 */

import type { AgentEvent } from './types';
import { startFileIngestion, getRecentEvents, getFilterOptions } from './file-ingest';

// Store WebSocket clients
const wsClients = new Set<unknown>();

// Start file-based ingestion (reads from .claude/run-logs/)
// Pass a callback to broadcast new events to connected WebSocket clients
startFileIngestion((events) => {
  // Broadcast each event to all connected WebSocket clients
  events.forEach((event) => {
    const message = JSON.stringify({ type: 'event', data: event });
    wsClients.forEach((client: any) => {
      try {
        client.send(message);
      } catch (err) {
        // Client disconnected, remove from set
        wsClients.delete(client);
      }
    });
  });
});

// Create Bun server with HTTP and WebSocket support
const server = Bun.serve({
  port: 4000,

  async fetch(req: Request) {
    const url = new URL(req.url);

    // Handle CORS
    const headers = {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type',
    };

    // Handle preflight
    if (req.method === 'OPTIONS') {
      return new Response(null, { headers });
    }

    // GET /health - Health check
    if (url.pathname === '/health' && req.method === 'GET') {
      return new Response(JSON.stringify({ status: 'ok', clients: wsClients.size }), {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // GET /events/filter-options - Get available filter options
    if (url.pathname === '/events/filter-options' && req.method === 'GET') {
      const options = getFilterOptions();
      return new Response(JSON.stringify(options), {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // GET /events/recent - Get recent events
    if (url.pathname === '/events/recent' && req.method === 'GET') {
      const limit = parseInt(url.searchParams.get('limit') || '100');
      const events = getRecentEvents(limit);
      return new Response(JSON.stringify(events), {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // GET /events/by-agent/:agentName - Get events for specific agent
    if (url.pathname.startsWith('/events/by-agent/') && req.method === 'GET') {
      const agentName = decodeURIComponent(url.pathname.split('/')[3]);
      const limit = parseInt(url.searchParams.get('limit') || '100');

      if (!agentName) {
        return new Response(
          JSON.stringify({
            error: 'Agent name is required',
          }),
          {
            status: 400,
            headers: { ...headers, 'Content-Type': 'application/json' },
          }
        );
      }

      const allEvents = getRecentEvents(limit);
      const agentEvents = allEvents.filter((e) => e.agent_name === agentName);

      return new Response(JSON.stringify(agentEvents), {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // GET /events/by-lane/:laneId - Get events for specific lane
    if (url.pathname.startsWith('/events/by-lane/') && req.method === 'GET') {
      const laneId = decodeURIComponent(url.pathname.split('/')[3]);
      const limit = parseInt(url.searchParams.get('limit') || '100');

      if (!laneId) {
        return new Response(
          JSON.stringify({
            error: 'Lane ID is required',
          }),
          {
            status: 400,
            headers: { ...headers, 'Content-Type': 'application/json' },
          }
        );
      }

      const allEvents = getRecentEvents(limit);
      const laneEvents = allEvents.filter((e) => e.lane_id === laneId);

      return new Response(JSON.stringify(laneEvents), {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
    }

    // WebSocket upgrade
    if (url.pathname === '/stream') {
      const success = server.upgrade(req);
      if (success) {
        return undefined;
      }
    }

    // Default response
    return new Response('ai-dev-kit Observability Server', {
      headers: { ...headers, 'Content-Type': 'text/plain' },
    });
  },

  websocket: {
    open(ws) {
      console.log('WebSocket client connected');
      wsClients.add(ws);

      // Send recent events on connection
      const events = getRecentEvents(50);
      ws.send(JSON.stringify({ type: 'initial', data: events }));
    },

    message(ws, message) {
      // Handle ping/pong for keep-alive
      try {
        const data = JSON.parse(message.toString());
        if (data.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
        }
      } catch {
        // Ignore parse errors
      }
    },

    close(ws) {
      console.log('WebSocket client disconnected');
      wsClients.delete(ws);
    },

    error(ws, error) {
      console.error('WebSocket error:', error);
      wsClients.delete(ws);
    },
  },
});

console.log(`Server running on http://localhost:${server.port}`);
console.log(`WebSocket endpoint: ws://localhost:${server.port}/stream`);
console.log(`Health check: http://localhost:${server.port}/health`);
