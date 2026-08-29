import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Icon } from './Icon';
import type { IconName } from './Icon';

export type ToastType = 'error' | 'success' | 'info';

export interface ToastItem {
  id: number;
  message: string;
  type: ToastType;
}

interface ToastContainerProps {
  toasts: ToastItem[];
  onRemove: (id: number) => void;
}

const TYPE_STYLES: Record<ToastType, { container: string; icon: IconName }> = {
  error: {
    container: 'bg-error-container text-on-error-container border-error/30',
    icon: 'warning',
  },
  success: {
    container: 'bg-secondary-container text-on-secondary-container border-secondary/30',
    icon: 'check_circle',
  },
  info: {
    container: 'bg-surface-container-high text-on-surface border-outline-variant/30',
    icon: 'info',
  },
};

function ToastItemView({ item, onDone }: { item: ToastItem; onDone: () => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(onDone, 250);
    }, 3000);
    return () => clearTimeout(timer);
  }, [onDone]);

  const style = TYPE_STYLES[item.type];

  return (
    <div
      className={`px-4 py-3 rounded-xl border shadow-lg text-body-sm flex items-center gap-3 transition-all duration-250 ${
        exiting ? 'opacity-0 -translate-x-4' : 'opacity-100 translate-x-0'
      } ${style.container}`}
    >
      <Icon name={style.icon} className="text-lg shrink-0" />
      <span>{item.message}</span>
      <button onClick={onDone} className="ml-auto shrink-0 opacity-60 hover:opacity-100 transition-opacity">
        <Icon name="close" className="text-sm" />
      </button>
    </div>
  );
}

export function ToastContainer({ toasts, onRemove }: ToastContainerProps) {
  return (
    <div className="fixed top-4 left-4 z-[100] flex flex-col gap-2 max-w-xs pointer-events-none">
      {toasts.map((item) => (
        <div key={item.id} className="pointer-events-auto animate-slide-in">
          <ToastItemView item={item} onDone={() => onRemove(item.id)} />
        </div>
      ))}
    </div>
  );
}

export function useToastManager() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const idRef = useRef(0);

  const showToast = useCallback((message: string, type: ToastType) => {
    const id = ++idRef.current;
    setToasts((prev) => [...prev, { id, message, type }]);
    return id;
  }, []);

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return { toasts, showToast, removeToast };
}
