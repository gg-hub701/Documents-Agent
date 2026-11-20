import type { UserConfig } from 'vite';
import { describe, expect, it } from 'vitest';

import viteConfig from '../vite.config';

describe('Vite development proxy', () => {
  it('routes API and health requests to the local FastAPI server', () => {
    const config = viteConfig as UserConfig;

    expect(config.server?.proxy).toMatchObject({
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    });
  });
});
