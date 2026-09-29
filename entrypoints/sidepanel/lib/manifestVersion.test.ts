// The version a user sees in chrome://extensions, and the one the Chrome Web
// Store listing shows, come from the manifest. Documentation.md carries the
// project's own version. These drifted apart for five minor releases: the docs
// said 0.5.0 while anything loading the extension reported 0.1.0, so the store
// listing and the requirements document disagreed about what was shipping.
//
// This parses both files rather than asserting on literals, because the point
// is that the numbers agree — not that they equal some value written here. A
// literal would need editing on every release, which is the same forgetting.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = resolve(__dirname, '../../..')

const readRoot = (name: string) => readFileSync(resolve(ROOT, name), 'utf-8')

const documentedVersion = () => {
  // Documentation.md's "**Version:**" line. Matched structurally so a
  // reformat of the heading does not read as a version change.
  const match = readRoot('Documentation.md').match(/\*\*Version:\*\*\s*(\S+)/)
  if (!match) throw new Error('Documentation.md has no "**Version:**" line')
  return match[1]
}

describe('extension version', () => {
  it('the manifest reports the version the documentation claims', () => {
    const manifest = readRoot('wxt.config.ts')
    const match = manifest.match(/version:\s*'([^']+)'/)
    if (!match) throw new Error('wxt.config.ts declares no manifest version')

    expect(match[1]).toBe(documentedVersion())
  })

  it('the npm package version matches too', () => {
    // package.json is not published, but a mismatch makes `npm run build`
    // output harder to reason about and is the usual way the two drift apart.
    const pkg = JSON.parse(readRoot('package.json'))

    expect(pkg.version).toBe(documentedVersion())
  })

  it('is a version Chrome will accept', () => {
    // Chrome rejects a manifest whose version is not one to four dot-separated
    // integers, which fails the build only at upload time.
    expect(documentedVersion()).toMatch(/^\d+(\.\d+){0,3}$/)
  })
})

describe('extension description', () => {
  // Chrome caps the manifest description at 132 characters and refuses to load
  // a manifest that exceeds it.
  const MAX = 132

  it('fits within the manifest limit', () => {
    const match = readRoot('wxt.config.ts').match(/description:\s*'([^']+)'/)
    if (!match) throw new Error('wxt.config.ts declares no description')

    expect(match[1].length).toBeLessThanOrEqual(MAX)
  })

  it('names what the extension does and who it is for', () => {
    const match = readRoot('wxt.config.ts').match(/description:\s*'([^']+)'/)
    if (!match) throw new Error('wxt.config.ts declares no description')
    const description = match[1]

    // Both halves matter: a listing that says what to do, and one that says
    // who it is for. The old copy carried neither — "A Universal Visual Job-Scam
    // Detection System" described a thesis title, not a use.
    expect(description).toMatch(/scam/i)
    expect(description).toMatch(/Filipino/i)
  })

  it('is the same string in the npm package', () => {
    const manifest = readRoot('wxt.config.ts')
    const match = manifest.match(/description:\s*'([^']+)'/)
    if (!match) throw new Error('wxt.config.ts declares no description')

    expect(JSON.parse(readRoot('package.json')).description).toBe(match[1])
  })
})
