"use client";

import { type ReactNode, useEffect, useRef } from "react";

/** Right-hand side sheet using the native <dialog> element (focus trapping and Escape for free). */
export function Drawer({
  open,
  onClose,
  onBack,
  title,
  eyebrow,
  children,
}: {
  open: boolean;
  onClose: () => void;
  /** When set, shows a Back button (e.g. return from a source to the claim that cited it). */
  onBack?: () => void;
  title: ReactNode;
  eyebrow?: ReactNode;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      if (typeof el.showModal === "function") el.showModal();
      else el.setAttribute("open", "");
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        // Escape: let React state drive closing so programmatic closes never cascade.
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      aria-labelledby="drawer-title"
      className="fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-dvh w-full max-w-[min(760px,100vw)] border-l border-line bg-surface p-0 text-ink shadow-2xl backdrop:bg-black/30"
    >
      {open && (
        <div className="flex h-full flex-col">
          <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-3">
            <div className="min-w-0">
              {eyebrow && <div className="mb-1">{eyebrow}</div>}
              <h2 id="drawer-title" className="text-[15px] font-semibold leading-snug">
                {title}
              </h2>
            </div>
            <div className="flex shrink-0 gap-2">
            {onBack && (
              <button
                type="button"
                onClick={onBack}
                className="rounded border border-line px-2 py-1 text-xs text-ink-muted hover:bg-surface-muted"
              >
                <span aria-hidden="true">←</span> Back
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="rounded border border-line px-2 py-1 text-xs text-ink-muted hover:bg-surface-muted"
            >
              Close <span aria-hidden="true">✕</span>
            </button>
            </div>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
        </div>
      )}
    </dialog>
  );
}
