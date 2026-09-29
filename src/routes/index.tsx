import { useState } from "react";
import { createFileRoute, Link } from "@tanstack/react-router";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
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
    { title: "AI Field Notes — Research, tools and releases" },
    { name: "description", content: "A quiet reading feed for AI research, tools and releases." },
    { property: "og:title", content: "AI Field Notes — Research, tools and releases" },
    { property: "og:description", content: "A quiet reading feed for AI research, tools and releases." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ] }),
  loader: ({ context }) => context.queryClient.ensureQueryData(itemsQuery),
  component: Feed,
  errorComponent: () => <main className="mx-auto max-w-[720px] px-6 py-24"><h1 className="font-serif text-4xl">AI Field Notes</h1><p className="mt-8 text-muted-foreground">The feed could not be loaded right now. Please try again later.</p></main>,
  notFoundComponent: () => <main className="mx-auto max-w-[720px] px-6 py-24"><p>Page not found.</p></main>,
});

function Feed() {
  const { data: items } = useSuspenseQuery(itemsQuery);
  const [source, setSource] = useState<Source>("all");
  const visible = source === "all" ? items : items.filter((item) => item.source_type?.toLowerCase() === source);

  return (
    <main className="mx-auto max-w-[720px] px-6 pb-28 pt-20 sm:px-8 sm:pt-28">
      <h1 className="font-serif text-[clamp(3.25rem,6vw,4.75rem)] font-semibold leading-[1.06]">AI Field Notes</h1>
      <p className="mt-4 text-base leading-relaxed text-muted-foreground">A reading feed for AI research, tools and releases.</p>

      <div className="mt-14 flex items-center gap-7 border-b border-border pb-3" aria-label="Filter by source">
        {filters.map((filter) => <Button key={filter.value} variant="filter" data-active={source === filter.value} aria-pressed={source === filter.value} onClick={() => setSource(filter.value)}>{filter.label}</Button>)}
      </div>

      {visible.length === 0 ? (
        <p className="py-14 text-sm leading-relaxed text-muted-foreground">{items.length === 0 ? "No articles yet." : `No ${source === "arxiv" ? "ArXiv" : "GitHub"} articles yet.`}</p>
      ) : (
        <div>
          {visible.map((item) => (
            <article key={item.id} className="border-b border-border py-9 first:pt-10 sm:py-11">
              {item.scraped_category && <p className="mb-3 text-sm font-medium text-primary">{item.scraped_category}</p>}
              <h2 className="font-serif text-[1.75rem] font-semibold leading-[1.18] sm:text-[2rem]">
                <Link to="/article/$id" params={{ id: item.id }} className="transition-colors hover:text-primary focus-visible:text-primary focus-visible:outline-none focus-visible:underline">{item.title || "Untitled article"}</Link>
              </h2>
              {item.summary && <p className="mt-4 text-[0.975rem] leading-[1.75] text-foreground/80">{item.summary}</p>}
              <p className="mt-5 text-[0.8rem] text-muted-foreground">
                {item.source_type?.toLowerCase() === "arxiv" ? "arXiv" : item.source_type?.toLowerCase() === "github" ? "GitHub" : item.source_type || "Unknown source"}
                <span aria-hidden="true" className="px-2">·</span>
                {Math.max(1, Math.round((item.word_count ?? 0) / 200))} min read
              </p>
            </article>
          ))}
        </div>
      )}
    </main>
  );
}