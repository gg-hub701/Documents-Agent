/**
 * 契约适配层。T04 (PR #10) 已合并，前端类型唯一来源是生成的
 * `schema.d.ts` (openapi-typescript) 与 `events.generated.ts`。
 * 本文件只做别名收敛与前端辅助类型，不重复定义任何 DTO、枚举或 SSE 事件；
 * 契约变更后重新导出 backend/openapi.json 并重新生成这两个文件即可。
 *
 * 注意两个游标不是一回事：
 * - `seq`：轮次内事件序号，用于 UI 去重（EventCursor）
 * - `event_id`：execution_events 持久化主键，用于 SSE 断线续传的 after_event_id 参数
 *
 * SSE 事件是「瘦事件 + ID 引用」，data 里不含完整对象；
 * 前端必须按 ID 回查 REST 详情，不得把 data 当作完整领域对象渲染。
 */
import type { components } from './schema';
import { EXECUTION_EVENT_TYPES } from './events.generated';
import type { ExecutionEvent, ExecutionEventType } from './events.generated';
import { isExecutionEventType } from './events';

export { EXECUTION_EVENT_TYPES, isExecutionEventType };
export type { ExecutionEvent, ExecutionEventType };

export type Schemas = components['schemas'];
export type UUID = string;
export type ISODateTime = string;

export type TaskStatus = Schemas['TaskStatus'];
export type TurnStatus = Schemas['TurnStatus'];
export type JobStatus = Schemas['JobStatus'];
export type DependencyState = Schemas['DependencyState'];
export type UploadStatus = Schemas['UploadStatus'];
export type ArtifactState = Schemas['ArtifactState'];
export type FileRole = Schemas['FileRole'];
export type SupportedFormat = Schemas['SupportedFormat'];
export type JobType = Schemas['JobType'];
export type TaskKind = Schemas['TaskKind'];

export type CreateTaskRequest = Schemas['CreateTaskRequest'];
export type CreateTurnRequest = Schemas['CreateTurnRequest'];
export type UploadRecord = Schemas['UploadRecord'];
export type TaskSummary = Schemas['TaskSummary'];
export type TaskDetail = Schemas['TaskDetail'];
export type ErrorResponse = Schemas['ErrorResponse'];
export type EventPreview = Schemas['EventPreview'];
export type TaskListPage = Schemas['CursorPage_TaskSummary_'];

/** 前端分页容器：保持与后端 CursorPage 形状一致 */
export interface CursorPage<T> {
  items: T[];
  next_cursor: string | null;
  has_more: boolean;
}
