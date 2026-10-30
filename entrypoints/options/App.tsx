import { useEffect, useState } from 'react';
import { defaultApiBase, getApiBase, initApiBase, setApiBase } from '../sidepanel/lib/apiBase';

/**
 * Settings page. Its only job today is the backend URL — the one value that
 * otherwise forces a rebuild and a Web Store re-review whenever the host moves.
 */
export default function App() {
  const [value, setValue] = useState(getApiBase());
  const [saved, setSaved] = useState(getApiBase());
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'testing' | 'ok' | 'fail'>('idle');

  useEffect(() => {
    initApiBase().then((base) => {
      setValue(base);
      setSaved(base);
    });
  }, []);

  const dirty = value.trim().replace(/\/+$/, '') !== saved;

  async function save() {
    setStatus('saving');
    const next = await setApiBase(value);
    setValue(next);
    setSaved(next);
    setStatus('saved');
  }

  async function reset() {
    const next = await setApiBase('');
    setValue(next);
    setSaved(next);
    setStatus('saved');
  }

  async function test() {
    setStatus('testing');
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 4000);
      const res = await fetch(`${value.trim().replace(/\/+$/, '')}/health`, { signal: controller.signal });
      clearTimeout(timer);
      setStatus(res.ok ? 'ok' : 'fail');
    } catch {
      setStatus('fail');
    }
  }

  return (
    <div className="min-h-screen bg-background text-on-surface p-8">
      <div className="max-w-xl mx-auto">
        <h1 className="text-2xl font-bold text-primary mb-2">Trabahero Settings</h1>
        <p className="text-on-surface-variant mb-8 text-sm">
          Point the extension at a Trabahero backend. Leave blank to use the built-in default.
        </p>

        <label className="block text-sm font-semibold mb-2" htmlFor="backendUrl">
          Backend URL
        </label>
        <input
          id="backendUrl"
          type="url"
          value={value}
          onChange={(e) => { setValue(e.target.value); setStatus('idle'); }}
          spellCheck={false}
          placeholder={defaultApiBase()}
          className="w-full rounded border border-outline bg-surface-container px-3 py-2 text-sm font-mono mb-3"
        />
        <p className="text-xs text-on-surface-variant mb-6">
          Built-in default: <span className="font-mono">{defaultApiBase()}</span>
        </p>

        <div className="flex flex-wrap gap-3 items-center">
          <button
            onClick={save}
            disabled={!dirty || status === 'saving'}
            className="rounded bg-primary text-on-primary px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Save
          </button>
          <button
            onClick={reset}
            className="rounded border border-outline px-4 py-2 text-sm font-semibold"
          >
            Reset to default
          </button>
          <button
            onClick={test}
            disabled={status === 'testing'}
            className="rounded border border-outline px-4 py-2 text-sm font-semibold disabled:opacity-50"
          >
            Test connection
          </button>
        </div>

        <p className="mt-4 text-sm min-h-5">
          {status === 'saved' && <span className="text-secondary">Saved.</span>}
          {status === 'testing' && <span className="text-on-surface-variant">Checking…</span>}
          {status === 'ok' && <span className="text-secondary">Connected — the backend is reachable.</span>}
          {status === 'fail' && <span className="text-error">Could not reach that backend. Check the URL and that it is running.</span>}
        </p>
      </div>
    </div>
  );
}
