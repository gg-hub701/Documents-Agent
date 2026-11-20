import { ROUTES, STATE_CHANGE_HEADERS } from './routes';
import {
  EXECUTION_EVENT_TYPES,
  type CreateTaskRequest, type CreateTurnRequest, type CursorPage,
  type ErrorResponse, type ExecutionEvent, type TaskDetail, type TaskSummary,
  type UploadRecord,
} from './types';

export class ContractError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = 'ContractError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    ...STATE_CHANGE_HEADERS,
    ...((init.headers as Record<string, string> | undefined) ?? {}),
  };
  const res = await fetch(path, { ...init, headers, credentials: 'same-origin' });
  if (!res.ok) {
    let body: Partial<ErrorResponse> = {};
    try { body = (await res.json()) as ErrorResponse; } catch { /* 保留兜底信息 */ }
    throw new ContractError(res.status, body.code ?? `HTTP_${res.status}`, body.message ?? `请求失败 (${res.status})`, body.request_id);
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return text ? (JSON.parse(text) as T) : (undefined as T);
}

/** 首轮必须先在后端创建任务，拿回真实的 task_id，不能把前端 sessionId 当 task_id 用 */
export function createTask(body: CreateTaskRequest): Promise<TaskDetail> {
  return request<TaskDetail>(ROUTES.tasks, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/** 后续轮次：CreateTurnRequest 使用 base_refs，不是 upload_ids */
export function createTurn(taskId: string, body: CreateTurnRequest, idempotencyKey: string): Promise<TaskDetail> {
  return request<TaskDetail>(ROUTES.turns(taskId), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(body),
  });
}

export function getTaskDetail(taskId: string): Promise<TaskDetail> {
  return request<TaskDetail>(ROUTES.task(taskId));
}

export function listTasks(cursor?: string): Promise<CursorPage<TaskSummary>> {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : '';
  return request<CursorPage<TaskSummary>>(`${ROUTES.tasks}${q}`);
}

export function getUpload(uploadId: string): Promise<UploadRecord> {
  return request<UploadRecord>(ROUTES.upload(uploadId));
}

export function deleteUpload(uploadId: string): Promise<void> {
  return request<void>(ROUTES.upload(uploadId), { method: 'DELETE' });
}

export function uploadFile(file: File): Promise<UploadRecord> {
  const fd = new FormData();
  fd.append('file', file);
  // 不设置 Content-Type，由浏览器生成 multipart boundary
  return request<UploadRecord>(ROUTES.uploads, { method: 'POST', body: fd });
}

export interface EventSubscription {
  close: () => void;
}

/** SSE 订阅：按真实事件名注册，支持 after_event_id / Last-Event-ID 续传 */
export function subscribeEvents(
  taskId: string,
  afterEventId: number,
  onEvent: (event: ExecutionEvent) => void,
  onError: (message: string) => void,
): EventSubscription {
  const source = new EventSource(ROUTES.events(taskId, afterEventId), { withCredentials: true });
  const handler = (raw: Event): void => {
    const ev = raw as MessageEvent<string>;
    try { onEvent(JSON.parse(ev.data) as ExecutionEvent); }
    catch { /* 单个坏事件不中断整条流 */ }
  };
  EXECUTION_EVENT_TYPES.forEach((name) => source.addEventListener(name, handler));
  source.onerror = () => {
    onError('SSE 连接中断，可用 lastEventId 续传');
    source.close();
  };
  return { close: () => source.close() };
}
