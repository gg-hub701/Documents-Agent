import type { ExecutionEvent, TaskStatus } from './types';

/**
 * 事件去重与 UI 动作归约。
 * 后端事件是瘦事件：artifact.ready 只给 artifact_id、plan.created 只给 job_count。
 * 因此这里只产出「需要刷新哪个详情」的动作，由上层调用 REST 回查后合并进缓存，
 * 绝不把 data 当成完整领域对象直接渲染（T16 的缓存更新/详情恢复边界）。
 */
export class EventCursor {
  private last: number;

  constructor(initialSeq = 0) {
    this.last = initialSeq;
  }

  get value(): number {
    return this.last;
  }

  accept(event: ExecutionEvent): boolean {
    if (event.seq <= this.last) return false;
    this.last = event.seq;
    return true;
  }
}

export type UiAction =
  | { kind: 'refresh-task' }
  | { kind: 'refresh-job'; jobId: string }
  | { kind: 'refresh-clarification'; clarificationId: string }
  | { kind: 'refresh-artifact'; artifactId: string }
  | { kind: 'refresh-conversion'; source: string; target: string }
  | { kind: 'finished'; status: TaskStatus }
  | { kind: 'heartbeat' }
  | { kind: 'ignore' };

export function toUiAction(event: ExecutionEvent): UiAction {
  switch (event.type) {
    case 'heartbeat':
      return { kind: 'heartbeat' };
    case 'task.queued':
    case 'task.started':
      return { kind: 'refresh-task' };
    case 'plan.created':
      // job_count 只是数量，Job 列表需回查 GET /tasks/{id}
      return { kind: 'refresh-task' };
    case 'clarification.required':
      return { kind: 'refresh-clarification', clarificationId: event.data.clarification_id };
    case 'job.waiting':
    case 'job.status':
    case 'job.blocked':
    case 'tool.started':
    case 'tool.finished':
    case 'validation.finished':
      return event.job_id
        ? { kind: 'refresh-job', jobId: event.job_id }
        : { kind: 'refresh-task' };
    case 'artifact.ready':
      return { kind: 'refresh-artifact', artifactId: event.data.artifact_id };
    case 'conversion.started':
    case 'conversion.finished':
      return { kind: 'refresh-conversion', source: event.data.source_format, target: event.data.target_format };
    case 'turn.finished':
      return { kind: 'refresh-task' };
    case 'task.finished':
      return { kind: 'finished', status: event.data.task_status };
    case 'template.diagnosed':
      return { kind: 'refresh-task' };
    default:
      return { kind: 'ignore' };
  }
}

/** 时间线展示文案：事件本身不携带完整回答正文，正文来自 REST 详情 */
export function describeEvent(event: ExecutionEvent): string {
  switch (event.type) {
    case 'task.queued': return `任务进入队列（第 ${event.data.queue_position} 位）`;
    case 'task.started': return 'Worker 已开始处理';
    case 'plan.created': return `执行计划已建立，共 ${event.data.job_count} 个 Job`;
    case 'clarification.required': return event.data.question;
    case 'job.waiting': return `等待 ${event.data.depends_on.length} 个前驱 Job`;
    case 'job.status': return `Job 状态：${event.data.status}`;
    case 'job.blocked': return event.data.blocked_reason;
    case 'tool.started': return `调用工具 ${event.data.tool_name}`;
    case 'tool.finished': return `工具 ${event.data.tool_name} 执行完成`;
    case 'validation.finished': return `验证 ${event.data.validator}：${event.data.status}`;
    case 'artifact.ready': return '产物已发布，可回查详情';
    case 'turn.finished': return `轮次结束：${event.data.turn_status}`;
    case 'task.finished': return `任务结束：${event.data.task_status}`;
    case 'conversion.started': return `开始转换 ${event.data.source_format} → ${event.data.target_format}`;
    case 'conversion.finished': return `转换完成 ${event.data.source_format} → ${event.data.target_format}`;
    case 'template.diagnosed': return `模板诊断：${event.data.status}`;
    case 'heartbeat': return '心跳';
    default: return '未知事件';
  }
}
