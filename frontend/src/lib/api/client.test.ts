import { afterEach, describe, expect, it, vi } from 'vitest';

import { createTask, subscribeEvents } from './client';
import type { CreateTaskRequest, TaskDetail } from './types';

const taskBody: CreateTaskRequest = {
  instruction: '读取文件并总结',
  upload_ids: [],
};

const taskDetail = {
  task_id: '4d7f0c4c-39ca-47da-8c49-f17d5a0f6618',
} as TaskDetail;

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('createTask', () => {
  it('sends the idempotency key for retry-safe task creation', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(taskDetail), {
        status: 202,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const createTaskWithKey = createTask as (
      body: CreateTaskRequest,
      idempotencyKey: string,
    ) => Promise<TaskDetail>;

    await createTaskWithKey(taskBody, 'create-task-key-1');

    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      'Idempotency-Key': 'create-task-key-1',
      'X-Doc-Agent-Request': '1',
    });
  });
});

describe('subscribeEvents', () => {
  it('keeps the EventSource open so the browser can reconnect after an error', () => {
    const close = vi.fn();

    class FakeEventSource {
      static instance: FakeEventSource;

      onerror: ((event: Event) => void) | null = null;

      readonly close = close;

      readonly addEventListener = vi.fn();

      constructor(
        readonly url: string,
        readonly options?: EventSourceInit,
      ) {
        FakeEventSource.instance = this;
      }
    }

    vi.stubGlobal(
      'EventSource',
      FakeEventSource as unknown as typeof EventSource,
    );
    const onError = vi.fn();

    subscribeEvents(
      taskDetail.task_id,
      7,
      vi.fn(),
      onError,
    );
    FakeEventSource.instance.onerror?.(new Event('error'));

    expect(onError).toHaveBeenCalledWith(
      'SSE 连接中断，将自动尝试续传',
    );
    expect(close).not.toHaveBeenCalled();
  });
});
