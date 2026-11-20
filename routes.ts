/** /api/v1 路由集中定义：契约唯一来源是 backend/openapi.json，禁止在组件里硬编码路径 */
export const API_BASE = '/api/v1';

/** 所有状态变更请求必须携带（README 安全约定） */
export const STATE_CHANGE_HEADERS: Readonly<Record<string, string>> = {
  'X-Doc-Agent-Request': '1',
};

const enc = (id: string): string => encodeURIComponent(id);

export const ROUTES = {
  health: '/health',
  tasks: `${API_BASE}/tasks`,
  task: (taskId: string) => `${API_BASE}/tasks/${enc(taskId)}`,
  turns: (taskId: string) => `${API_BASE}/tasks/${enc(taskId)}/turns`,
  events: (taskId: string, afterEventId = 0) =>
    `${API_BASE}/tasks/${enc(taskId)}/events?after_event_id=${Math.max(0, Math.trunc(afterEventId))}`,
  uploads: `${API_BASE}/uploads`,
  upload: (uploadId: string) => `${API_BASE}/uploads/${enc(uploadId)}`,
} as const;

/** 分享短链不属于当前后端契约，前端不要调用不存在的 /api/v1/shares */
export const CONTRACT_NOTES = {
  missingEndpoints: ['/api/v1/shares'],
  sseHasNoTextDelta: true,
  eventsAreThin: true,
} as const;
