import { describe, expect, it } from 'vitest';

import type { ApiScanResponse } from '../types';
import { mapApiResponse } from './mapApiResponse';

function scanResponse(over: Partial<ApiScanResponse> = {}): ApiScanResponse {
  return {
    valid: true,
    anomalies: [],
    job_summary: '',
    ...over,
  } as ApiScanResponse;
}

describe('mapApiResponse and the request class', () => {
  it('carries the class through unchanged', () => {
    // The class is decided by the backend from the posting's own findings.
    // Dropping it here would leave the panel with a verdict it cannot explain,
    // and defaulting it would invent a class the backend never reached.
    expect(mapApiResponse(scanResponse({ request_class: 'prohibited' })).requestClass).toBe(
      'prohibited',
    );
  });

  it('leaves an absent class absent rather than defaulting to ordinary', () => {
    // `''` on the wire means the scan did not report a class — a reading
    // recorded before the field existed. That is a missing input, not a clean
    // posting.
    expect(mapApiResponse(scanResponse()).requestClass).toBeUndefined();
  });
});
