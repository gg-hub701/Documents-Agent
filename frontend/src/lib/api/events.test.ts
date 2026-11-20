import { describe, expect, it } from "vitest";

import { isExecutionEventType } from "./events";

describe("isExecutionEventType", () => {
  it("accepts a type generated from the backend event union", () => {
    expect(isExecutionEventType("task.queued")).toBe(true);
  });

  it("rejects a type outside the generated event union", () => {
    expect(isExecutionEventType("unknown.event")).toBe(false);
  });
});
