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
      'Scan a job post for scam signals, check the employer exists, and match your skills to it. For Filipino job seekers.',
    // The repository is the only home this project has — no domain, so the
    // listing's homepage is where the source and the setup docs already live.
    homepage_url: 'https://github.com/miks518/traba-hero',
    version: '0.5.0',
    // Pins the extension ID to hdmdhiojgdoomcjfhbkidbhkifmokkop.
    //
    // Without this, Chrome derives an unpacked extension's ID from its absolute
    // folder path — so moving or renaming the project silently changes it, and
    // a CORS allowlist in the backend quietly stops matching, with no error on
    // either side. A public key in the manifest makes the ID permanent instead,
    // and identical on every machine that unpacks this repo, because the key
    // travels with the manifest. The Web Store honours a supplied `key` too, so
    // the ID published to users is this same one and the backend setting is
    // written once rather than again at launch.
    //
    // This is a PUBLIC key: it ships inside every published extension and is
    // readable by anyone. The private half lives outside the repository and is
    // only needed to sign a .crx for self-distribution. Once the Web Store sees
    // a listing with this key, the ID is fixed for the life of that listing.
    key:
      'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAraFxzE/9eT6/cBOuDrnkxao6zMXkuWVzN9JWBNgM+tbqSo0h7BCRSMp5lAZaPI/XM8TKTQUn/6/nkn/FPxCVP97vLrV6aBCPJNIznV4Kx2n2w9upRKjSSUQpKzuO82X1caJ58UafUXzlzOBWohQqBfsyBFWBBg+PKW1IIkR+14VLiSg0PODTnOl6nDGPrjRYYVIxy/A7n4eSv8JJkdTPlxFCo0AL+7+T4dCDAPyr9m9C8DmsX6JYfzPpNCOZE0fOgc3JlWiqVYvkkpWrpL6LCXytNNAOg2Ixhd4xM2BEvTg3SCNg1wq7Poh2JwENi6lP3ozV1WIWcsUpxnNkSM/nQQIDAQAB',
    permissions: ['activeTab', 'storage', 'tabs', 'sidePanel'],
    host_permissions: ['<all_urls>', 'http://localhost:8010/*'],
    side_panel: {
      default_path: 'entrypoints/sidepanel/index.html',
    },
    action: {},
  }),
});
