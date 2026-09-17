import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: () => ({
    name: 'Trabahero',
    description: 'A Universal Visual Job-Scam Detection System for Filipino Job Seekers.',
    version: '0.1.0',
    permissions: ['activeTab', 'storage', 'tabs', 'sidePanel'],
    host_permissions: ['<all_urls>', `${import.meta.env.WXT_API_BASE}/*`],
    side_panel: {
      default_path: 'entrypoints/sidepanel/index.html',
    },
    action: {},
  }),
});
