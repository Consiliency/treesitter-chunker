/**
 * Event types for ai-dev-kit observability
 */

export interface AgentEvent {
  id?: number;
  timestamp: string;
  event_type: EventType;
  session_id: string;
  agent_name?: string;
  lane_id?: string;
  phase_id?: string;
  task_id?: string;
  payload: Record<string, unknown>;
}

export type EventType =
  | 'tool_call'
  | 'workflow_start'
  | 'workflow_complete'
  | 'lane_start'
  | 'lane_complete'
  | 'task_start'
  | 'task_complete'
  | 'verification_pass'
  | 'verification_fail'
  | 'research_synthesis'
  | 'agent_start'
  | 'agent_end'
  | 'error';

export interface FilterOptions {
  session_ids: string[];
  agent_names: string[];
  event_types: string[];
  lane_ids: string[];
  phase_ids: string[];
}

export interface WebSocketMessage {
  type: 'event' | 'initial' | 'ping' | 'pong';
  data?: AgentEvent | AgentEvent[];
}
