import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'happy-dom',
    // `.agents/` holds agent tooling installed by the Skills CLI, not project
    // tests. Its `.test.cjs` files are Node scripts that vitest collects as
    // suites and then reports as failing, so `npm test` would exit non-zero for
    // reasons that have nothing to do with the code. See .gitignore.
    include: ['**/*.{test,spec}.{ts,tsx}'],
  },
});
