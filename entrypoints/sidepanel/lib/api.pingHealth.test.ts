import { afterEach, describe, expect, it, vi } from 'vitest';
import { pingHealth } from './api';

// pingHealth IS the lib/api boundary this suite mocks everywhere else, so
// these tests stub globalThis.fetch to pin its own contract: reachability is
// "the backend answered at all", not "the answer was 2xx". A 429 from the
// backend proves it parsed and answered the request - rendering the offline
// banner for that would tell every user behind a shared NAT the server is
// down precisely when it is up and rate-limiting them.
const fetchMock = vi.fn();

describe('pingHealth', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it('resolves true for a 200', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(pingHealth()).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/health$/);
  });

  it('resolves true for a 429 - a rate-limited backend is an up backend', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 429 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(pingHealth()).resolves.toBe(true);
  });

  it('resolves true for a 5xx - a failing backend is still reachable', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 502 }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(pingHealth()).resolves.toBe(true);
  });

  it('resolves false when fetch rejects - no answer means unreachable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(pingHealth()).resolves.toBe(false);
  });
});
