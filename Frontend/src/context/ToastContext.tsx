"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { CheckCircle2, AlertTriangle, Info, XCircle, X } from "lucide-react";

export type ToastType = "success" | "error" | "info" | "warning";

export interface ToastItem {
  id: string;
  type: ToastType;
  title?: string;
  message: string;
}

interface ToastContextType {
  toast: {
    success: (message: string, title?: string) => void;
    error: (message: string, title?: string) => void;
    info: (message: string, title?: string) => void;
    warning: (message: string, title?: string) => void;
  };
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const addToast = useCallback((type: ToastType, message: string, title?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, message, title }]);

    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const toastHelpers = {
    success: (message: string, title?: string) => addToast("success", message, title),
    error: (message: string, title?: string) => addToast("error", message, title),
    info: (message: string, title?: string) => addToast("info", message, title),
    warning: (message: string, title?: string) => addToast("warning", message, title),
  };

  return (
    <ToastContext.Provider value={{ toast: toastHelpers }}>
      {children}
      {/* Floating Toast Portal */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none px-4 md:px-0">
        {toasts.map((item) => (
          <div
            key={item.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-xl backdrop-blur-md transition-all duration-300 animate-in slide-in-from-bottom-5 ${
              item.type === "success"
                ? "border-emerald-500/30 bg-emerald-950/90 text-emerald-100"
                : item.type === "error"
                ? "border-rose-500/30 bg-rose-950/90 text-rose-100"
                : item.type === "warning"
                ? "border-amber-500/30 bg-amber-950/90 text-amber-100"
                : "border-blue-500/30 bg-blue-950/90 text-blue-100"
            }`}
          >
            <span className="mt-0.5 shrink-0">
              {item.type === "success" && <CheckCircle2 size={18} className="text-emerald-400" />}
              {item.type === "error" && <XCircle size={18} className="text-rose-400" />}
              {item.type === "warning" && <AlertTriangle size={18} className="text-amber-400" />}
              {item.type === "info" && <Info size={18} className="text-blue-400" />}
            </span>
            <div className="flex-1 text-xs">
              {item.title && <div className="font-bold text-sm mb-0.5">{item.title}</div>}
              <div className="font-medium leading-relaxed">{item.message}</div>
            </div>
            <button
              onClick={() => removeToast(item.id)}
              className="opacity-70 hover:opacity-100 transition-opacity p-0.5"
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return context.toast;
}
