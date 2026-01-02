<script setup lang="ts">
import { computed } from 'vue';

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

const props = defineProps<{
  event: AgentEvent;
}>();

const eventColor = computed(() => {
  const type = props.event.event_type;
  if (type.includes('start')) return 'var(--accent-cyan)';
  if (type.includes('complete') || type.includes('pass')) return 'var(--accent-green)';
  if (type.includes('fail') || type.includes('error')) return 'var(--accent-red)';
  if (type === 'tool_call') return 'var(--accent-orange)';
  return 'var(--text-secondary)';
});

const eventIcon = computed(() => {
  const type = props.event.event_type;
  if (type === 'tool_call') return '🔧';
  if (type.includes('lane')) return '🏊';
  if (type.includes('task')) return '📋';
  if (type.includes('workflow')) return '⚡';
  if (type.includes('verification')) return type.includes('pass') ? '✅' : '❌';
  if (type.includes('research')) return '🔬';
  if (type.includes('error')) return '⚠️';
  return '📍';
});

const formattedTime = computed(() => {
  const date = new Date(props.event.timestamp);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
});

const toolName = computed(() => {
  if (props.event.event_type === 'tool_call') {
    return (props.event.payload.tool_name as string) || 'Unknown Tool';
  }
  return props.event.event_type.replace(/_/g, ' ');
});
</script>

<template>
  <div class="event-row">
    <div class="event-icon">{{ eventIcon }}</div>
    <div class="event-time">{{ formattedTime }}</div>
    <div class="event-type" :style="{ color: eventColor }">
      {{ toolName }}
    </div>
    <div class="event-agent" v-if="event.agent_name">
      {{ event.agent_name }}
    </div>
    <div class="event-lane" v-if="event.lane_id">
      <span class="label">lane:</span>
      {{ event.lane_id }}
    </div>
    <div class="event-task" v-if="event.task_id">
      <span class="label">task:</span>
      {{ event.task_id }}
    </div>
  </div>
</template>

<style scoped>
.event-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  background-color: var(--bg-secondary);
  border-radius: 4px;
  font-size: 0.875rem;
  transition: background-color 0.15s;
}

.event-row:hover {
  background-color: var(--bg-tertiary);
}

.event-icon {
  flex-shrink: 0;
  font-size: 1rem;
}

.event-time {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-family: monospace;
  font-size: 0.75rem;
}

.event-type {
  flex-shrink: 0;
  font-weight: 500;
  text-transform: capitalize;
}

.event-agent {
  flex-shrink: 0;
  color: var(--accent-cyan);
  padding: 0.125rem 0.5rem;
  background-color: rgba(6, 182, 212, 0.1);
  border-radius: 4px;
  font-size: 0.75rem;
}

.event-lane,
.event-task {
  flex-shrink: 0;
  color: var(--text-secondary);
  font-size: 0.75rem;
}

.label {
  opacity: 0.7;
}
</style>
