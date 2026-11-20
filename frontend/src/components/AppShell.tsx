import type { ReactNode } from 'react';
import '../styles/shell.css';

export interface AppShellProps {
  sidebar: ReactNode;
  center: ReactNode;
  right: ReactNode;
}

/** 三栏工作台外壳：只负责布局与视觉令牌，不持有业务状态、不产生任何模拟数据 */
export function AppShell({ sidebar, center, right }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="sidebar">{sidebar}</aside>
      <main className="center-panel">{center}</main>
      <aside className="right-panel">{right}</aside>
    </div>
  );
}
