/**
 * File-based Event Streaming (In-Memory Only)
 * Watches JSONL files from .claude/run-logs/
 * NO DATABASE - streams directly to WebSocket clients
 * Fresh start each time - no persistence
 */

import { watch, existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { homedir } from 'os';
import type { AgentEvent, FilterOptions } from './types';

// In-memory event store (last N events only)
const MAX_EVENTS = 1000;
const events: AgentEvent[] = [];

// Track the last read position for each file
const filePositions = new Map<string, number>();

// Track which files we're currently watching
const watchedFiles = new Set<string>();

// Callback for when new events arrive (for WebSocket broadcasting)
let onEventsReceived: ((events: AgentEvent[]) => void) | null = null;

/**
 * Get the path to the run-logs directory
 */
function getRunLogsDir(): string {
  // Check for project-specific run logs first
  const cwd = process.cwd();
  const projectRunLogs = join(cwd, '.claude', 'run-logs');
  if (existsSync(projectRunLogs)) {
    return projectRunLogs;
  }

  // Fall back to user's .claude directory
  return join(homedir(), '.claude', 'run-logs');
}

/**
 * Get the path to today's events file
 */
function getTodayEventsFile(): string {
  const runLogsDir = getRunLogsDir();
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');

  return join(runLogsDir, `${year}-${month}-${day}.jsonl`);
}

/**
 * Read new events from a JSONL file starting from a given position
 */
function readNewEvents(filePath: string): AgentEvent[] {
  if (!existsSync(filePath)) {
    return [];
  }

  const lastPosition = filePositions.get(filePath) || 0;

  try {
    const content = readFileSync(filePath, 'utf-8');
    const newContent = content.slice(lastPosition);

    // Update position to end of file
    filePositions.set(filePath, content.length);

    if (!newContent.trim()) {
      return [];
    }

    // Parse JSONL - one JSON object per line
    const lines = newContent.trim().split('\n');
    const newEvents: AgentEvent[] = [];

    for (const line of lines) {
      if (!line.trim()) continue;

      try {
        const event = JSON.parse(line) as AgentEvent;
        // Add auto-incrementing ID for UI
        event.id = events.length + newEvents.length + 1;
        newEvents.push(event);
      } catch (error) {
        console.error(`Failed to parse line: ${line.slice(0, 100)}...`, error);
      }
    }

    return newEvents;
  } catch (error) {
    console.error(`Error reading file ${filePath}:`, error);
    return [];
  }
}

/**
 * Add events to in-memory store (keeping last MAX_EVENTS only)
 */
function storeEvents(newEvents: AgentEvent[]): void {
  if (newEvents.length === 0) return;

  // Add to in-memory array
  events.push(...newEvents);

  // Keep only last MAX_EVENTS
  if (events.length > MAX_EVENTS) {
    events.splice(0, events.length - MAX_EVENTS);
  }

  console.log(`Received ${newEvents.length} event(s) (${events.length} in memory)`);

  // Notify subscribers (WebSocket clients)
  if (onEventsReceived) {
    onEventsReceived(newEvents);
  }
}

/**
 * Watch a file for changes and stream new events
 */
function watchFile(filePath: string): void {
  if (watchedFiles.has(filePath)) {
    return; // Already watching
  }

  console.log(`Watching: ${filePath}`);
  watchedFiles.add(filePath);

  // Set file position to END of file - only read NEW events from now on
  if (existsSync(filePath)) {
    const content = readFileSync(filePath, 'utf-8');
    filePositions.set(filePath, content.length);
    console.log(`Positioned at end of file - only new events will be captured`);
  }

  // Watch for changes
  const watcher = watch(filePath, (eventType) => {
    if (eventType === 'change') {
      const newEvents = readNewEvents(filePath);
      storeEvents(newEvents);
    }
  });

  watcher.on('error', (error) => {
    console.error(`Error watching ${filePath}:`, error);
    watchedFiles.delete(filePath);
  });
}

/**
 * Start watching for events
 * @param callback Optional callback to be notified when new events arrive
 */
export function startFileIngestion(callback?: (events: AgentEvent[]) => void): void {
  console.log('Starting file-based event streaming (in-memory only)');

  const runLogsDir = getRunLogsDir();
  console.log(`Reading from ${runLogsDir}`);

  // Set the callback for event notifications
  if (callback) {
    onEventsReceived = callback;
  }

  // Watch today's file
  const todayFile = getTodayEventsFile();
  if (existsSync(todayFile)) {
    watchFile(todayFile);
  } else {
    console.log(`Today's file not found: ${todayFile}`);
    console.log('Will start watching when file is created...');

    // Watch the directory for new files
    if (existsSync(runLogsDir)) {
      watch(runLogsDir, (eventType, filename) => {
        if (filename && filename.endsWith('.jsonl')) {
          const filePath = join(runLogsDir, filename);
          if (!watchedFiles.has(filePath) && existsSync(filePath)) {
            watchFile(filePath);
          }
        }
      });
    }
  }

  // Check for new day's file every hour
  setInterval(() => {
    const newTodayFile = getTodayEventsFile();
    if (!watchedFiles.has(newTodayFile) && existsSync(newTodayFile)) {
      console.log('New day detected, watching new file');
      watchFile(newTodayFile);
    }
  }, 60 * 60 * 1000); // Check every hour

  console.log('File streaming started');
}

/**
 * Get all events currently in memory
 */
export function getRecentEvents(limit: number = 100): AgentEvent[] {
  return events.slice(-limit).reverse();
}

/**
 * Get filter options from in-memory events
 */
export function getFilterOptions(): FilterOptions {
  const sessionIds = new Set<string>();
  const agentNames = new Set<string>();
  const eventTypes = new Set<string>();
  const laneIds = new Set<string>();
  const phaseIds = new Set<string>();

  for (const event of events) {
    if (event.session_id) sessionIds.add(event.session_id);
    if (event.agent_name) agentNames.add(event.agent_name);
    if (event.event_type) eventTypes.add(event.event_type);
    if (event.lane_id) laneIds.add(event.lane_id);
    if (event.phase_id) phaseIds.add(event.phase_id);
  }

  return {
    session_ids: Array.from(sessionIds).slice(0, 100),
    agent_names: Array.from(agentNames).sort(),
    event_types: Array.from(eventTypes).sort(),
    lane_ids: Array.from(laneIds).sort(),
    phase_ids: Array.from(phaseIds).sort(),
  };
}
