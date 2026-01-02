import { ref, onMounted, onUnmounted } from 'vue';

export interface AgentEvent {
  id: number;
  timestamp: string;
  event_type: string;
  session_id: string;
  agent_name?: string;
  lane_id?: string;
  phase_id?: string;
  task_id?: string;
  payload: Record<string, unknown>;
}

export function useWebSocket(url: string = 'ws://localhost:4000/stream') {
  const events = ref<AgentEvent[]>([]);
  const connected = ref(false);
  let ws: WebSocket | null = null;
  let pingInterval: number | null = null;
  let reconnectTimeout: number | null = null;

  function connect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }

    ws = new WebSocket(url);

    ws.onopen = () => {
      connected.value = true;
      console.log('Connected to observability server');
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        if (message.type === 'initial') {
          events.value = message.data || [];
        } else if (message.type === 'event') {
          events.value = [message.data, ...events.value].slice(0, 100);
        }
      } catch (e) {
        console.error('Failed to parse message:', e);
      }
    };

    ws.onclose = () => {
      connected.value = false;
      console.log('Disconnected from server, reconnecting in 3s...');
      reconnectTimeout = setTimeout(connect, 3000) as unknown as number;
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  function disconnect() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (pingInterval) {
      clearInterval(pingInterval);
      pingInterval = null;
    }
    ws?.close();
    ws = null;
  }

  onMounted(() => {
    connect();

    // Keep connection alive with pings
    pingInterval = setInterval(() => {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000) as unknown as number;
  });

  onUnmounted(() => {
    disconnect();
  });

  return {
    events,
    connected,
    connect,
    disconnect,
  };
}
