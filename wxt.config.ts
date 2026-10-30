import { defineConfig } from 'wxt';

// See https://wxt.dev/api/config.html
export default defineConfig({
  modules: ['@wxt-dev/module-react'],
  manifest: (ctx) => {
    // Omit key for Chrome Web Store builds — the store generates its own.
    // Include key only for local development / self-distribution.
    const isStoreBuild = ctx.command === 'build' && ctx.browser === 'chrome';
    return {
      name: 'Trabahero',
      description:
        'Scan a job posting for scam signals, then check the employer behind it actually exists. For Filipino job seekers.',
      version: '0.5.0',
      ...(!isStoreBuild
        ? {
            // Pins the extension ID to hdmdhiojgdoomcjfhbkidbhkifmokkop for local dev.
            key:
              'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAraFxzE/9eT6/cBOuDrnkxao6zMXkuWVzN9JWBNgM+tbqSo0h7BCRSMp5lAZaPI/XM8TKTQUn/6/nkn/FPxCVP97vLrV6aBCPJNIznV4Kx2n2w9upRKjSSUQpKzuO82X1caJ58UafUXzlzOBWohQqBfsyBFWBBg+PKW1IIkR+14VLiSg0PODTnOl6nDGPrjRYYVIxy/A7n4eSv8JJkdTPlxFCo0AL+7+T4dCDAPyr9m9C8DmsX6JYfzPpNCOZE0fOgc3JlWiqVYvkkpWrpL6LCXytNNAOg2Ixhd4xM2BEvTg3SCNg1wq7Poh2JwENi6lP3ozV1WIWcsUpxnNkSM/nQQIDAQAB',
          }
        : {}),
      permissions: ['activeTab', 'storage', 'tabs', 'sidePanel'],
      host_permissions: ['<all_urls>', 'http://localhost:8010/*'],
      side_panel: {
        default_path: 'entrypoints/sidepanel/index.html',
      },
      action: {},
    };
  },
});
