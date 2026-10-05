import { ApiError } from "@/lib/api";

export function ErrorNotice({ error, context }: { error: Error; context?: string }) {
  const forbidden = error instanceof ApiError && error.forbidden;
  return (
    <div role="alert" className="rounded border border-danger-fg/40 bg-danger-bg px-3 py-2 text-[13px] text-danger-fg">
      {context && <strong className="font-semibold">{context}: </strong>}
      {forbidden ? `Not permitted for the current persona — ${error.message}` : error.message}
    </div>
  );
}
