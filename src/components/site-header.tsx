// ============= Full file contents =============

import { Link } from "@tanstack/react-router";
import { UserRound } from "lucide-react";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5 sm:h-16 sm:px-8">
        <Link
          to="/"
          className="font-display text-sm font-bold uppercase tracking-[0.16em] text-foreground no-underline transition-colors hover:text-primary sm:text-base"
        >
          Chronologicals<span className="text-primary"> of AI</span>
        </Link>
        <div
          aria-disabled="true"
          title="Login coming soon"
          className="flex size-9 cursor-not-allowed items-center justify-center rounded-full border border-border bg-card text-muted-foreground"
        >
          <UserRound size={17} strokeWidth={2} aria-hidden="true" />
        </div>
      </div>
    </header>
  );
}
