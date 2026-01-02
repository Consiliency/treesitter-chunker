<script setup lang="ts">
import { computed } from 'vue';
import EventRow from './EventRow.vue';

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
  events: AgentEvent[];
}>();

const hasEvents = computed(() => props.events.length > 0);
</script>

<template>
  <div class="timeline">
    <div v-if="!hasEvents" class="empty-state">
      <div class="empty-icon">📊</div>
      <h3>Waiting for events...</h3>
      <p>Events will appear here as agents execute tools and workflows.</p>
    </div>

    <div v-else class="event-list">
      <EventRow v-for="event in events" :key="event.id" :event="event" />
    </div>
  </div>
</template>

<style scoped>
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  color: var(--text-secondary);
  text-align: center;
}

.empty-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}

.empty-state h3 {
  font-size: 1.25rem;
  color: var(--text-primary);
  margin-bottom: 0.5rem;
}

.empty-state p {
  font-size: 0.875rem;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
</style>
