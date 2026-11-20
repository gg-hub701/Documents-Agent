// Generated from backend/app/api/schemas/events.py. Do not edit.
import type { components } from "./schema";

export const EXECUTION_EVENT_TYPES = [
  "task.queued",
  "task.started",
  "plan.created",
  "clarification.required",
  "job.waiting",
  "job.status",
  "job.blocked",
  "template.diagnosed",
  "conversion.started",
  "conversion.finished",
  "tool.started",
  "tool.finished",
  "validation.finished",
  "artifact.ready",
  "turn.finished",
  "task.finished",
  "heartbeat",
] as const;

export type ExecutionEventType = (typeof EXECUTION_EVENT_TYPES)[number];

export type ExecutionEvent =
  | components["schemas"]["TaskQueuedEvent"]
  | components["schemas"]["TaskStartedEvent"]
  | components["schemas"]["PlanCreatedEvent"]
  | components["schemas"]["ClarificationRequiredEvent"]
  | components["schemas"]["JobWaitingEvent"]
  | components["schemas"]["JobStatusEvent"]
  | components["schemas"]["JobBlockedEvent"]
  | components["schemas"]["TemplateDiagnosedEvent"]
  | components["schemas"]["ConversionStartedEvent"]
  | components["schemas"]["ConversionFinishedEvent"]
  | components["schemas"]["ToolStartedEvent"]
  | components["schemas"]["ToolFinishedEvent"]
  | components["schemas"]["ValidationFinishedEvent"]
  | components["schemas"]["ArtifactReadyEvent"]
  | components["schemas"]["TurnFinishedEvent"]
  | components["schemas"]["TaskFinishedEvent"]
  | components["schemas"]["HeartbeatEvent"];
