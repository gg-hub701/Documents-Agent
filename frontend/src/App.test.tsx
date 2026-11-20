// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
} from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import App from './App';

afterEach(() => {
  cleanup();
});

describe('application routes', () => {
  it('renders the privacy page without exposing internal task ids', () => {
    render(
      <MemoryRouter initialEntries={['/privacy']}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', {
        name: '外部 AI 数据处理说明',
      }),
    ).toBeTruthy();
    expect(screen.queryByText(/T\d{2}/)).toBeNull();
    expect(screen.queryByText(/GET \/api/)).toBeNull();
  });

  it('opens the task workspace from the task route', () => {
    render(
      <MemoryRouter initialEntries={['/tasks/example-task']}>
        <App />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole('heading', { name: '任务工作台' }),
    ).toBeTruthy();
    expect(screen.getByText('任务已打开')).toBeTruthy();
    expect(screen.queryByText('example-task')).toBeNull();
  });

  it('keeps the selected workspace view in the application store', async () => {
    const firstRender = render(
      <MemoryRouter initialEntries={['/tasks']}>
        <App />
      </MemoryRouter>,
    );

    fireEvent.click(
      screen.getByRole('radio', { name: '执行时间线' }),
    );
    expect(screen.getByText('暂无执行记录')).toBeTruthy();

    firstRender.unmount();
    render(
      <MemoryRouter initialEntries={['/tasks']}>
        <App />
      </MemoryRouter>,
    );

    expect(screen.getByText('暂无执行记录')).toBeTruthy();
  });
});
