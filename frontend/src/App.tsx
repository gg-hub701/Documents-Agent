import { useState } from 'react';
import { AppShell } from './components/AppShell';
import { EXECUTION_EVENT_TYPES } from './lib/api/types';

type View = 'conversation' | 'timeline' | 'results';

const VIEWS: { id: View; label: string; hint: string }[] = [
  { id: 'conversation', label: '对话', hint: 'T23 对话与指令输入' },
  { id: 'timeline', label: '执行时间线', hint: 'T65 Job DAG 时间线' },
  { id: 'results', label: '结果与验证', hint: 'T24 / T68 预览与血缘' },
];

/**
 * T05 三栏应用外壳与状态骨架。
 * 这里刻意不产生任何模拟任务、模拟回答或模拟产物：
 * 后端 Agent 编排（T17/T18/T19/T62）尚未实现时，前端不得伪造结果或宣称任务成功。
 */
export default function App() {
  const [activeView, setActiveView] = useState<View>('conversation');

  return (
    <AppShell
      sidebar={
        <>
          <div className="shell-brand">
            <span className="shell-brand-mark">D</span>
            <span>DocAgent<br /><span className="shell-brand-sub">文档智能工作台</span></span>
          </div>
          <div className="shell-body">
            <div className="shell-section-title">任务导航</div>
            {VIEWS.map((v) => (
              <div
                key={v.id}
                className={`shell-nav-item ${activeView === v.id ? 'active' : ''}`}
                onClick={() => setActiveView(v.id)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setActiveView(v.id); }}
              >
                {v.label}
              </div>
            ))}
            <div className="shell-section-title" style={{ marginTop: 18 }}>历史任务</div>
            <div className="shell-empty">任务列表由 GET /api/v1/tasks 提供（T14），当前骨架不加载真实数据。</div>
          </div>
          <div className="shell-footer">
            契约对齐：{EXECUTION_EVENT_TYPES.length} 个 SSE 事件类型 · 瘦事件需按 ID 回查详情
          </div>
        </>
      }
      center={
        <>
          <div className="panel-header">
            <span className="panel-title">新建任务</span>
            <span className="tag">T05 骨架</span>
            <span className="panel-subtitle">当前视图：{VIEWS.find((v) => v.id === activeView)?.label}</span>
          </div>
          <div className="panel-content">
            <div className="panel-placeholder">
              <div>
                <strong>{VIEWS.find((v) => v.id === activeView)?.hint}</strong>
                <span>
                  指令输入、消息渲染、SSE 客户端与事件缓存由后续任务接入。<br />
                  真实回答来自 REST 任务详情，SSE 事件只包含 ID 引用，不包含回答正文。
                </span>
              </div>
            </div>
          </div>
        </>
      }
      right={
        <>
          <div className="panel-header"><span className="panel-title">结果与验证</span></div>
          <div className="panel-content">
            <div className="panel-placeholder">
              <div>
                <strong>暂无可发布产物</strong>
                <span>产物仅在后端验证通过并发布后出现；<br />staged / failed / blocked 文件不会显示。</span>
              </div>
            </div>
          </div>
        </>
      }
    />
  );
}
