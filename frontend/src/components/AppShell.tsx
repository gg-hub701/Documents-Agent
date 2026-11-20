import type { ReactNode } from 'react';
import { Layout } from 'antd';
import '../styles/shell.css';

export interface AppShellProps {
  sidebar: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

/** 三栏工作台外壳：只负责布局与视觉令牌，不持有业务状态、不产生任何模拟数据 */
export function AppShell({ sidebar, center, right }: AppShellProps) {
  return (
    <Layout className="app-shell" hasSider>
      <aside className="sidebar" aria-label="任务侧栏">
        {sidebar}
      </aside>
      <main className="center-panel">{center}</main>
      <aside className="right-panel" aria-label="结果与验证">
        {right}
      </aside>
    </Layout>
  );
}
