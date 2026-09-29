// ============= Full file contents =============

import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { Bookmark } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/site-header";
import { getItems } from "@/lib/items.functions";

const itemsQuery = queryOptions({ queryKey: ["items"], queryFn: () => getItems() });
type Source = "all" | "arxiv" | "github";
const filters: { label: string; value: Source }[] = [
  { label: "All", value: "all" },
  { label: "ArXiv", value: "arxiv" },
  { label: "GitHub", value: "github" },
];

export const Route = createFileRoute("/")({
  head: () => ({ meta: [
    { title: "Chronologicals of AI — Research, tools and releases" },
    { name: "description", content: "A living feed of AI research, tools and releases." },
    { property: "og:title", content: "Chronologicals of AI — Research, tools and releases" },
    { property: "og:description", content: "A living feed of AI research, tools and releases." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  loader: ({ context }) => context.queryClient.ensureQueryData(itemsQuery),
  component: Feed,
  errorComponent: () => <main className="mx-auto max-w-[720px] px-6 py-24"><h1 className="font-display text-4xl font-bold">Chronologicals of AI</h1><p className="mt-8 text-muted-foreground">The feed could not be loaded right now. Please try again later.</p></main>,
  notFoundComponent: () => <main className="mx-auto max-w-[720px] px-6 py-24"><p>Page not found.</p></main>,
});

function Tag({ label, tone }: { label: string; tone: "accent" | "neutral" }) {
  return (
    <span
      className={
        tone === "accent"
          ? "inline-flex items-center gap-1.5 rounded-full bg-primary/12 px-2.5 py-1 font-mono text-[0.68rem] font-medium uppercase tracking-wider text-primary"
          : "inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 font-mono text-[0.68rem] font-medium uppercase tracking-wider text-muted-foreground"
      }
    >
      {tone === "accent" && <Bookmark size={11} strokeWidth={2.25} aria-hidden="true" />}
      {label}
    </span>
  );
}

function Feed() {
  const { data: items } = useSuspenseQuery(itemsQuery);
  const [source, setSource] = useState<Source>("all");
  const visible = source === "all" ? items : items.filter((item) => item.source_type?.toLowerCase() === source);

  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-6xl px-5 pb-28 sm:px-8">
        <section className="pt-14 sm:pt-20">
          <h1 className="font-display text-[clamp(2.75rem,6vw,4.5rem)] font-bold leading-[1.02] tracking-tight">
            Chronologicals<span className="text-primary"> of AI</span>
          </h1>
          <p className="mt-4 max-w-xl text-base leading-relaxed text-muted-foreground sm:text-lg">
            Everything worth reading in AI, newest first — research, tools and releases.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-2.5" aria-label="Filter by source">
            {filters.map((filter) => (
              <Button
                key={filter.value}
                variant="filter"
                data-active={source === filter.value}
                aria-pressed={source === filter.value}
                onClick={() => setSource(filter.value)}
              >
                {filter.label}
              </Button>
            ))}
            <span className="ml-auto font-mono text-xs uppercase tracking-wider text-muted-foreground">
              {visible.length} {visible.length === 1 ? "entry" : "entries"}
            </span>
          </div>
        </section>

        {visible.length === 0 ? (
          <p className="py-16 text-sm leading-relaxed text-muted-foreground">{items.length === 0 ? "No articles yet." : `No ${source === "arxiv" ? "ArXiv" : "GitHub"} articles yet.`}</p>
        ) : (
          <div className="mt-8 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {visible.map((item) => (
              <article key={item.id}>
                <Link
                  to="/article/$id"
                  params={{ id: item.id }}
                  className="group flex h-full flex-col rounded-2xl border border-border bg-card p-6 no-underline transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-[0_14px_36px_-16px_color-mix(in_oklab,var(--primary)_38%,transparent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex flex-wrap gap-2">
                    {item.scraped_category && <Tag label={item.scraped_category} tone="accent" />}
                    <Tag label={item.source_type || "source"} tone="neutral" />
                  </div>
                  <h2 className="mt-4 font-display text-xl font-bold leading-snug tracking-tight text-foreground transition-colors group-hover:text-primary">
                    {item.title || "Untitled article"}
                  </h2>
                  {item.summary && (
                    <p className="mt-3 line-clamp-4 text-[0.9rem] leading-relaxed text-foreground/75">
                      {item.summary}
                    </p>
                  )}
                  <p className="mt-auto pt-5 text-xs font-medium tracking-wide text-muted-foreground">
                    {item.source_type?.toLowerCase() === "arxiv" ? "arXiv" : item.source_type?.toLowerCase() === "github" ? "GitHub" : item.source_type || "Unknown source"}
                    <span aria-hidden="true" className="px-1.5 text-primary">·</span>
                    {Math.max(1, Math.round((item.word_count ?? 0) / 200))} min read
                  </p>
                </Link>
              </article>
            ))}
          </div>
        )}
      </main>
    </>
  );
}
