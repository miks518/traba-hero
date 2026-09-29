import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: () => ({
    name: 'Trabahero',
    // Keep in step with the **Version:** line in Documentation.md. These drifted
    // for five minor releases once, so `manifestVersion.test.ts` reads both
    // files and fails if they disagree again.
    description:
      'Scan a job posting for scam signals, then check the employer behind it actually exists. For Filipino job seekers.',
    version: '0.5.0',
    permissions: ['activeTab', 'storage', 'tabs', 'sidePanel'],
    host_permissions: ['<all_urls>', 'http://localhost:8000/*'],
    side_panel: {
      default_path: 'entrypoints/sidepanel/index.html',
    },
    action: {},
  }),
});
