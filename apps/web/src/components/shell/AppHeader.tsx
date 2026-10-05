import Link from "next/link";
import { FixtureBanner } from "./FixtureBanner";
import { PersonaSwitcher } from "./PersonaSwitcher";

export function AppHeader() {
  return (
    <header className="border-b border-line bg-surface">
      <FixtureBanner />
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-2.5 md:px-6">
        <Link href="/" className="flex items-baseline gap-3">
          <span className="text-[15px] font-semibold tracking-tight text-ink">Strategic Investigation Platform</span>
          <span className="hidden text-xs text-ink-muted lg:inline">
            Autonomous research · Governed reasoning · Human decisions
          </span>
        </Link>
        <PersonaSwitcher />
      </div>
    </header>
  );
}
