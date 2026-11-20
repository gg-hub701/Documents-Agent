import {
  ConfigProvider,
  Segmented,
  Tag,
} from 'antd';
import { QueryClientProvider } from '@tanstack/react-query';
import {
  Link,
  Navigate,
  Route,
  Routes,
  useParams,
} from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { PrivacyPage } from './app/PrivacyPage';
import { queryClient } from './app/queryClient';
import {
  isWorkspaceView,
  useShellStore,
  type WorkspaceView,
} from './app/shellStore';
import { appTheme } from './app/theme';

const VIEW_OPTIONS: { label: string; value: WorkspaceView }[] = [
  { label: '对话', value: 'conversation' },
  { label: '执行时间线', value: 'timeline' },
  { label: '结果与验证', value: 'results' },
];

const VIEW_CONTENT: Record<
  WorkspaceView,
  { emptyTitle: string; emptyDescription: string }
> = {
  conversation: {
    emptyTitle: '等待任务指令',
    emptyDescription: '新建任务后，对话和回答会显示在这里。',
  },
  timeline: {
    emptyTitle: '暂无执行记录',
    emptyDescription: '任务开始后，执行步骤和状态会显示在这里。',
  },
  results: {
    emptyTitle: '暂无可发布产物',
    emptyDescription: '验证通过并发布的结果会显示在这里。',
  },
};

function WorkspacePage({ taskId }: { taskId?: string }) {
  const activeView = useShellStore((state) => state.activeView);
  const setActiveView = useShellStore((state) => state.setActiveView);
  const content = VIEW_CONTENT[activeView];

  return (
    <AppShell
      sidebar={
        <>
          <Link className="shell-brand" to="/tasks">
            <span className="shell-brand-mark">D</span>
            <span>
              DocAgent
              <br />
              <span className="shell-brand-sub">文档智能工作台</span>
            </span>
          </Link>
          <nav className="shell-body" aria-label="主要导航">
            <Link
              className={`shell-nav-item ${taskId ? '' : 'active'}`}
              to="/tasks"
            >
              任务工作台
            </Link>
            <Link className="shell-nav-item" to="/privacy">
              隐私说明
            </Link>
            <div className="shell-section-title shell-section-spaced">
              当前任务
            </div>
            <div className="shell-empty">
              {taskId ? '任务已打开' : '暂无进行中的任务'}
            </div>
          </nav>
          <div className="shell-footer">
            本地处理 · 数据保存在本机
          </div>
        </>
      }
      center={
        <>
          <div className="panel-header">
            <h1 className="panel-title">
              {taskId ? '任务工作台' : '新建任务'}
            </h1>
            <Tag color="blue">本地工作台</Tag>
            <Segmented
              className="workspace-switcher"
              options={VIEW_OPTIONS}
              value={activeView}
              onChange={(value) => {
                if (isWorkspaceView(value)) setActiveView(value);
              }}
            />
          </div>
          <div className="panel-content">
            <div className="panel-placeholder">
              <div>
                <strong>{content.emptyTitle}</strong>
                <span>{content.emptyDescription}</span>
              </div>
            </div>
          </div>
        </>
      }
      right={
        <>
          <div className="panel-header">
            <h2 className="panel-title">结果与验证</h2>
          </div>
          <div className="panel-content">
            <div className="panel-placeholder">
              <div>
                <strong>暂无可发布产物</strong>
                <span>验证通过并发布的结果会显示在这里。</span>
              </div>
            </div>
          </div>
        </>
      }
    />
  );
}

function TaskWorkspacePage() {
  const { taskId } = useParams<{ taskId: string }>();
  return <WorkspacePage taskId={taskId} />;
}

export default function App() {
  return (
    <ConfigProvider theme={appTheme}>
      <QueryClientProvider client={queryClient}>
        <Routes>
          <Route path="/" element={<Navigate replace to="/tasks" />} />
          <Route path="/tasks" element={<WorkspacePage />} />
          <Route path="/tasks/:taskId" element={<TaskWorkspacePage />} />
          <Route path="/privacy" element={<PrivacyPage />} />
          <Route path="*" element={<Navigate replace to="/tasks" />} />
        </Routes>
      </QueryClientProvider>
    </ConfigProvider>
  );
}
