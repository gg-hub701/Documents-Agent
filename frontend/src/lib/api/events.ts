import {
  EXECUTION_EVENT_TYPES,
  type ExecutionEventType,
} from "./events.generated";

const executionEventTypes = new Set<string>(EXECUTION_EVENT_TYPES);

export function isExecutionEventType(value: string): value is ExecutionEventType {
  return executionEventTypes.has(value);
}
