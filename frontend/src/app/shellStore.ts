import { create } from 'zustand';

export const WORKSPACE_VIEWS = [
  'conversation',
  'timeline',
  'results',
] as const;

export type WorkspaceView = (typeof WORKSPACE_VIEWS)[number];

interface ShellState {
  activeView: WorkspaceView;
  setActiveView: (activeView: WorkspaceView) => void;
}

export function isWorkspaceView(value: unknown): value is WorkspaceView {
  return (
    typeof value === 'string' &&
    WORKSPACE_VIEWS.includes(value as WorkspaceView)
  );
}

export const useShellStore = create<ShellState>((set) => ({
  activeView: 'conversation',
  setActiveView: (activeView) => set({ activeView }),
}));
