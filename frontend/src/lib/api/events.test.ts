import { describe, expect, it } from "vitest";

import { isExecutionEventType } from "./events";
import type { ExecutionEvent } from "./events.generated";
import type { components } from "./schema";

type Assert<T extends true> = T;
type IsAssignable<From, To> = [From] extends [To] ? true : false;

type GeneratedEventMatchesOpenApi = Assert<
  IsAssignable<ExecutionEvent, NonNullable<components["schemas"]["ExecutionEvent"]>>
>;
type OpenApiEventMatchesGenerated = Assert<
  IsAssignable<NonNullable<components["schemas"]["ExecutionEvent"]>, ExecutionEvent>
>;
type QueuedEventDataIsNarrowed = Assert<
  IsAssignable<
    Extract<ExecutionEvent, { type: "task.queued" }>["data"],
    components["schemas"]["TaskQueuedEventData"]
  >
>;

function assertType<T extends true>(): void {
  void (0 as unknown as T);
}

describe("isExecutionEventType", () => {
  it("keeps the generated SSE union compatible with OpenAPI", () => {
    assertType<GeneratedEventMatchesOpenApi>();
    assertType<OpenApiEventMatchesGenerated>();
    assertType<QueuedEventDataIsNarrowed>();
  });

  it("accepts a type generated from the backend event union", () => {
    expect(isExecutionEventType("task.queued")).toBe(true);
  });

  it("rejects a type outside the generated event union", () => {
    expect(isExecutionEventType("unknown.event")).toBe(false);
  });
});
