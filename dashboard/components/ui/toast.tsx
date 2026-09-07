'use client';

/** Minimal toast system (veloura-styled, a11y-live). */

import { createContext, useCallback, useContext, useRef, useState } from 'react';
import { Check, CircleAlert, Sparkles } from 'lucide-react';

type ToastKind = 'success' | 'error' | 'info';
interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

interface ToastApi {
  push: (message: string, kind?: ToastKind) => void;
}

const ToastContext = createContext<ToastApi>({ push: () => {} });

export function useToast(): ToastApi {
  return useContext(ToastContext);
}

const KIND_STYLES: Record<ToastKind, string> = {
  success: 'border-veloura-success/40 text-veloura-success',
  error: 'border-veloura-danger/40 text-veloura-danger',
  info: 'border-veloura-lavender/40 text-veloura-lavender',
};

const KIND_ICONS: Record<ToastKind, React.ReactNode> = {
  success: <Check size={15} strokeWidth={2.2} />,
  error: <CircleAlert size={15} strokeWidth={2.2} />,
  info: <Sparkles size={15} strokeWidth={2.2} />,
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const push = useCallback((message: string, kind: ToastKind = 'info') => {
    const id = nextId.current++;
    setToasts((t) => [...t.slice(-3), { id, kind, message }]);
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 4200);
  }, []);

  return (
    <ToastContext.Provider value={{ push }}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-6 right-6 z-50 flex flex-col gap-2"
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`veloura-card pointer-events-auto flex min-h-[44px] items-center gap-3 px-4 py-3 text-sm animate-fade-in ${KIND_STYLES[t.kind]}`}
          >
            <span aria-hidden className="shrink-0">{KIND_ICONS[t.kind]}</span>
            <span className="text-veloura-text">{t.message}</span>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
