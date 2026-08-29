import React, { useState, useRef } from 'react';
import { testTextModel } from '../lib/api';
import { Icon, ToastContainer, useToastManager } from '../components/common';

export function ModelTestView() {
  const [text, setText] = useState('');
  const [response, setResponse] = useState('');
  const [modelName, setModelName] = useState('');
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const { toasts, showToast, removeToast } = useToastManager();

  const handleSend = async () => {
    if (!text.trim()) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setResponse('');
    try {
      const data = await testTextModel(text, controller.signal);
      setResponse(data.raw_output);
      setModelName(data.model);
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return;
      showToast(e instanceof Error ? e.message : 'Request failed', 'error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-container-padding bg-background flex flex-col gap-stack-md">
      <ToastContainer toasts={toasts} onRemove={removeToast} />

      <div className="flex flex-col gap-2">
        <h2 className="text-headline-sm font-headline text-on-surface">Model Test</h2>
        <p className="text-body-sm text-on-surface-variant">
          Send a prompt to your LM Studio model and see the raw response.
        </p>
      </div>

      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Type a message..."
        rows={4}
        className="w-full rounded-lg bg-surface-container p-3 text-body-sm text-on-surface border border-outline-variant/20 resize-none focus:outline-none focus:border-secondary"
      />

      <button
        onClick={handleSend}
        disabled={loading || !text.trim()}
        className="w-full tactile-btn-gold py-3 rounded-lg font-headline-md text-base flex items-center justify-center gap-2 disabled:opacity-70 active:translate-y-[1px]"
      >
        <Icon name="smart_toy" />
        {loading ? 'Waiting for response...' : 'Send'}
      </button>

      {loading && (
        <div className="w-full h-1 bg-surface-container-highest overflow-hidden rounded-full">
          <div className="w-full h-full bg-secondary animate-loading-bar rounded-full" />
        </div>
      )}

      {response && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <Icon name="smart_toy" className="text-sm text-secondary" />
            <span className="text-label-sm text-on-surface-variant">Raw Response{modelName ? ` (${modelName})` : ''}</span>
          </div>
          <div className="rounded-lg bg-surface-container p-3 border border-outline-variant/20 text-body-sm text-on-surface whitespace-pre-wrap max-h-96 overflow-y-auto">
            {response}
          </div>
        </div>
      )}
    </div>
  );
}

export default ModelTestView;
