// The Chrome Web Store rejected version 0.5.0 for "Requesting but not using:
// tabs" (violation dated 5 November 2026). It was right: `tabs` is only needed
// to read a tab's url, title, or favIconUrl for pages the extension has no host
// permission for, and this manifest asks for `<all_urls>`. Everything else the
// code does with the tabs API — query, getZoom, captureVisibleTab, sendMessage —
// works without it.
//
// The list below is pinned on purpose. Every permission is a line in the
// store's permission review, and an accidentally added one is a rejection that
// costs a review cycle. Adding a permission for a real feature means editing
// this list too, which is the moment to ask whether the store will agree it is
// used.
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const ROOT = resolve(__dirname, '../../..')

const declaredPermissions = () => {
  const match = readFileSync(resolve(ROOT, 'wxt.config.ts'), 'utf-8').match(
    /permissions:\s*\[([^\]]*)\]/,
  )
  if (!match) throw new Error('wxt.config.ts declares no permissions array')
  return match[1]
    .split(',')
    .map((entry) => entry.trim().replace(/^'|'$/g, ''))
    .filter(Boolean)
}

describe('manifest permissions', () => {
  it('requests only the permissions the store has seen justified', () => {
    // storage: settings and the backend-url override; sidePanel: the panel
    // itself; activeTab: page access granted when the action is clicked.
    expect(declaredPermissions()).toEqual(['activeTab', 'storage', 'sidePanel'])
  })

  it('does not request `tabs`, which `<all_urls>` already covers', () => {
    expect(declaredPermissions()).not.toContain('tabs')
  })
})
