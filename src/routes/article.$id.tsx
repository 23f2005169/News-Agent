// ============= Full file contents =============

import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { getItem } from "@/lib/items.functions";
import { SiteHeader } from "@/components/site-header";

const itemQuery = (id: string) => queryOptions({
  queryKey: ["item", id],
  queryFn: async () => {
    const item = await getItem({ data: id });
    if (!item) throw notFound();
    return item;
  },
});

export const Route = createFileRoute("/article/$id")({
  loader: ({ context, params }) => context.queryClient.ensureQueryData(itemQuery(params.id)),
  head: ({ loaderData }) => {
    const title = loaderData?.title || "Article";
    return { meta: [
      { title: `${title} — Chronologicals of AI` },
      { name: "description", content: `Read ${title} on Chronologicals of AI.` },
      { property: "og:title", content: `${title} — Chronologicals of AI` },
      { property: "og:description", content: `Read ${title} on Chronologicals of AI.` },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary" },
    ] };
  },
  component: Article,
  errorComponent: () => <ArticleMessage message="This article could not be loaded right now." />,
  notFoundComponent: () => <ArticleMessage message="This article was not found." />,
});

function ArticleMessage({ message }: { message: string }) {
  return <><SiteHeader /><main className="mx-auto max-w-[720px] px-6 pb-28 pt-16 sm:px-8"><p className="font-display text-3xl font-bold">{message}</p><Link to="/" className="mt-12 inline-block text-sm font-medium text-primary hover:underline">Back to feed</Link></main></>;
}

// Prerequisites shell: the backend will supply topic/keyword names (not article titles).
// TODO(owner): replace this stub with the real prerequisites fetch.
async function getPrerequisites(_id: string): Promise<string[]> {
  return [];
}

// Suggestions shell: will be filled by semantic search over embeddings (backend).
// TODO(owner): replace this stub with the semantic-search recommendations fetch.
async function getSuggestions(_id: string): Promise<{ id: string; title: string }[]> {
  return [];
}

const prerequisitesQuery = (id: string) => queryOptions({
  queryKey: ["prerequisites", id],
  queryFn: () => getPrerequisites(id),
});

const suggestionsQuery = (id: string) => queryOptions({
  queryKey: ["suggestions", id],
  queryFn: () => getSuggestions(id),
});

function Prerequisites({ id }: { id: string }) {
  const { data: prerequisites } = useSuspenseQuery(prerequisitesQuery(id));
  if (prerequisites.length === 0) return null;
  return (
    <section aria-label="Prerequisites" className="mt-8 rounded-2xl border border-border bg-card p-5">
      <h2 className="font-mono text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">Before you read</h2>
      <div className="mt-3 flex flex-wrap gap-2">
        {prerequisites.map((topic) => (
          <span key={topic} className="inline-flex items-center rounded-full bg-muted px-3 py-1 text-sm text-foreground">
            {topic}
          </span>
        ))}
      </div>
    </section>
  );
}

function Suggestions({ id }: { id: string }) {
  const { data: suggestions } = useSuspenseQuery(suggestionsQuery(id));
  if (suggestions.length === 0) return null;
  return (
    <section aria-label="More like this" className="mt-16 border-t border-border pt-10">
      <h2 className="font-mono text-[0.7rem] font-medium uppercase tracking-wider text-muted-foreground">More like this</h2>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {suggestions.map((suggestion) => (
          <Link
            key={suggestion.id}
            to="/article/$id"
            params={{ id: suggestion.id }}
            className="rounded-2xl border border-border bg-card p-5 font-display text-base font-bold leading-snug text-foreground no-underline transition-colors hover:border-primary/50 hover:text-primary"
          >
            {suggestion.title}
          </Link>
        ))}
      </div>
    </section>
  );
}

function Article() {
  const { id } = Route.useParams();
  const { data: item } = useSuspenseQuery(itemQuery(id));
  const paragraphs = item.raw_text?.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean) ?? [];

  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-[720px] px-6 pb-32 pt-14 sm:px-8 sm:pt-20">
        {item.scraped_category && (
          <span className="inline-flex items-center rounded-full bg-primary/12 px-3 py-1 font-mono text-[0.7rem] font-medium uppercase tracking-wider text-primary">
            {item.scraped_category}
          </span>
        )}
        <h1 className="mt-5 font-display text-[clamp(2.5rem,5vw,3.75rem)] font-bold leading-[1.08] tracking-tight">{item.title || "Untitled article"}</h1>
        <div className="mt-10 border-t border-border pt-10 font-serif text-[1.25rem] leading-[1.8] sm:mt-12 sm:pt-12 sm:text-[1.35rem]">
          {paragraphs.map((paragraph, index) => <p key={index} className="mb-7 whitespace-pre-line last:mb-0">{paragraph}</p>)}
        </div>
        <Link to="/" className="mt-16 inline-block text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:underline">Back to feed</Link>
      </main>
    </>
  );
}
