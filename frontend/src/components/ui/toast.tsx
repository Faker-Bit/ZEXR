"use client";

import * as React from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle2, Info, TriangleAlert, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";

type ToastTone = "success" | "error" | "info" | "warning";

interface Toast {
  id: number;
  title: string;
  description?: string;
  tone: ToastTone;
}

interface ToastContextValue {
  toast: (input: { title: string; description?: string; tone?: ToastTone }) => void;
  dismiss: (id: number) => void;
}

const ToastContext = React.createContext<ToastContextValue | null>(null);

const ICONS: Record<ToastTone, React.ElementType> = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
  warning: TriangleAlert,
};

const TONES: Record<ToastTone, string> = {
  success: "border-success/40 text-success",
  error: "border-destructive/40 text-destructive",
  info: "border-primary/40 text-primary",
  warning: "border-warning/40 text-warning",
};

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = React.useState<Toast[]>([]);
  const counter = React.useRef(0);

  const dismiss = React.useCallback((id: number) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const toast = React.useCallback<ToastContextValue["toast"]>(
    ({ title, description, tone = "info" }) => {
      counter.current += 1;
      const id = counter.current;
      setToasts((current) => [...current.slice(-3), { id, title, description, tone }]);
      window.setTimeout(() => dismiss(id), 5200);
    },
    [dismiss],
  );

  const value = React.useMemo(() => ({ toast, dismiss }), [toast, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[calc(100%-2rem)] max-w-sm flex-col gap-2"
      >
        <AnimatePresence initial={false}>
          {toasts.map((item) => {
            const Icon = ICONS[item.tone];
            return (
              <motion.div
                key={item.id}
                layout
                initial={{ opacity: 0, y: 16, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, x: 24, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
                className="pointer-events-auto flex items-start gap-3 rounded-xl border bg-popover/95 p-3.5 shadow-lg backdrop-blur"
              >
                <Icon className={cn("mt-0.5 size-4 shrink-0", TONES[item.tone])} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium leading-tight">{item.title}</p>
                  {item.description ? (
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {item.description}
                    </p>
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(item.id)}
                  className="rounded p-0.5 text-muted-foreground transition-colors hover:text-foreground"
                  aria-label="Dismiss"
                >
                  <X className="size-3.5" />
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = React.useContext(ToastContext);
  if (!context) {
    // Rendering outside the provider should never crash a page.
    return { toast: () => undefined, dismiss: () => undefined };
  }
  return context;
}