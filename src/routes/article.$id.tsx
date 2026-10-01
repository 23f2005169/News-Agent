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
  return (
    <section aria-labelledby="prerequisites-heading" className="border-t border-border pt-5 lg:border-t-0 lg:pt-0">
      <h2 id="prerequisites-heading" className="font-mono text-xs font-semibold uppercase text-primary">Before you read</h2>
      {prerequisites.length > 0 ? (
        <ul className="mt-5 flex flex-wrap gap-2 lg:flex-col lg:items-start">
          {prerequisites.map((topic) => (
            <li key={topic} className="rounded-sm border border-border bg-card px-3 py-2 text-sm leading-snug text-foreground">{topic}</li>
          ))}
        </ul>
      ) : <p className="mt-5 text-sm leading-relaxed text-muted-foreground">Prerequisite topics will appear here.</p>}
    </section>
  );
}

function Suggestions({ id }: { id: string }) {
  const { data: suggestions } = useSuspenseQuery(suggestionsQuery(id));
  return (
    <section aria-labelledby="suggestions-heading" className="border-t border-border pt-5 lg:border-t-0 lg:pt-0">
      <h2 id="suggestions-heading" className="font-mono text-xs font-semibold uppercase text-primary">Also See</h2>
      {suggestions.length > 0 ? <div className="mt-5 flex flex-col gap-3">
        {suggestions.slice(0, 3).map((suggestion) => (
          <Link
            key={suggestion.id}
            to="/article/$id"
            params={{ id: suggestion.id }}
            className="border-b border-border pb-3 font-display text-base font-semibold leading-snug text-foreground no-underline transition-colors hover:text-primary"
          >
            {suggestion.title}
          </Link>
        ))}
      </div> : <p className="mt-5 text-sm leading-relaxed text-muted-foreground">Related articles will appear here.</p>}
    </section>
  );
}

function Article() {
  const { id } = Route.useParams();
  const { data: item } = useSuspenseQuery(itemQuery(id));
  const paragraphs = item.summary?.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean) ?? [];

  return (
    <>
      <SiteHeader />
      <main className="mx-auto max-w-7xl px-6 pb-28 pt-10 sm:px-8 sm:pt-16">
        {item.subfield_tag && (
          <span className="inline-flex items-center rounded-full bg-primary/12 px-3 py-1 font-mono text-[0.7rem] font-medium uppercase text-primary">
            {item.subfield_tag}
          </span>
        )}
        <h1 className="mt-5 max-w-4xl font-display text-3xl font-bold leading-tight sm:text-5xl">{item.title || "Untitled article"}</h1>
        <div className="mt-10 grid gap-10 border-t border-border pt-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,2.4fr)_minmax(0,1fr)] lg:gap-0 lg:pt-10">
          <aside className="lg:pr-7"><Prerequisites id={id} /></aside>
          <section aria-labelledby="article-heading" className="min-w-0 border-t border-border pt-5 lg:border-x lg:border-t-0 lg:px-10 lg:pt-0">
            <h2 id="article-heading" className="font-mono text-xs font-semibold uppercase text-primary">Article</h2>
            <div className="mt-5 font-serif text-xl leading-relaxed text-foreground sm:text-2xl">
              {paragraphs.length > 0 ? paragraphs.map((paragraph, index) => <p key={index} className="mb-6 whitespace-pre-line last:mb-0">{paragraph}</p>) : <p className="text-muted-foreground">Summary is not available yet.</p>}
            </div>
          </section>
          <aside className="lg:pl-7"><Suggestions id={id} /></aside>
        </div>
        <Link to="/" className="mt-16 inline-block text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:underline">Back to feed</Link>
      </main>
    </>
  );
}
