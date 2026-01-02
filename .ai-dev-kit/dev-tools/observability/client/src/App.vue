<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue';
import EventTimeline from './components/EventTimeline.vue';

interface AgentEvent {
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

const events = ref<AgentEvent[]>([]);
const connected = ref(false);
const clientCount = ref(0);
let ws: WebSocket | null = null;

function connect() {
  ws = new WebSocket('ws://localhost:4000/stream');

  ws.onopen = () => {
    connected.value = true;
    console.log('Connected to observability server');
  };

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data);

      if (message.type === 'initial') {
        // Initial batch of recent events
        events.value = message.data || [];
      } else if (message.type === 'event') {
        // New event - prepend to list
        events.value = [message.data, ...events.value].slice(0, 100);
      }
    } catch (e) {
      console.error('Failed to parse message:', e);
    }
  };

  ws.onclose = () => {
    connected.value = false;
    console.log('Disconnected from server, reconnecting in 3s...');
    setTimeout(connect, 3000);
  };

  ws.onerror = (error) => {
    console.error('WebSocket error:', error);
  };
}

// Ping server to keep connection alive
let pingInterval: number;

onMounted(() => {
  connect();
  pingInterval = setInterval(() => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 30000);
});

onUnmounted(() => {
  clearInterval(pingInterval);
  ws?.close();
});
</script>

<template>
  <div class="app">
    <header class="header">
      <h1>ai-dev-kit Observability</h1>
      <div class="status">
        <span :class="['status-dot', connected ? 'connected' : 'disconnected']"></span>
        <span>{{ connected ? 'Connected' : 'Disconnected' }}</span>
      </div>
    </header>

    <main class="main">
      <EventTimeline :events="events" />
    </main>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  background-color: var(--bg-secondary);
  border-bottom: 1px solid var(--bg-tertiary);
}

.header h1 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
}

.status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
  color: var(--text-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.connected {
  background-color: var(--accent-green);
  box-shadow: 0 0 8px var(--accent-green);
}

.status-dot.disconnected {
  background-color: var(--accent-red);
}

.main {
  flex: 1;
  padding: 1rem 2rem;
  overflow-y: auto;
}
</style>
