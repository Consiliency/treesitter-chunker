/**
 * Event type to color mapping for consistent visualization
 */

export const eventColors: Record<string, string> = {
  tool_call: 'var(--accent-orange)',
  workflow_start: 'var(--accent-cyan)',
  workflow_complete: 'var(--accent-green)',
  lane_start: 'var(--accent-cyan)',
  lane_complete: 'var(--accent-green)',
  task_start: 'var(--accent-cyan)',
  task_complete: 'var(--accent-green)',
  verification_pass: 'var(--accent-green)',
  verification_fail: 'var(--accent-red)',
  research_synthesis: 'var(--accent-yellow)',
  agent_start: 'var(--accent-cyan)',
  agent_end: 'var(--text-secondary)',
  error: 'var(--accent-red)',
};

export const eventIcons: Record<string, string> = {
  tool_call: '🔧',
  workflow_start: '⚡',
  workflow_complete: '✅',
  lane_start: '🏊',
  lane_complete: '🏁',
  task_start: '📋',
  task_complete: '✓',
  verification_pass: '✅',
  verification_fail: '❌',
  research_synthesis: '🔬',
  agent_start: '🤖',
  agent_end: '👋',
  error: '⚠️',
};

export function getEventColor(eventType: string): string {
  return eventColors[eventType] || 'var(--text-secondary)';
}

export function getEventIcon(eventType: string): string {
  return eventIcons[eventType] || '📍';
}

export function useEventColors() {
  return {
    eventColors,
    eventIcons,
    getEventColor,
    getEventIcon,
  };
}
