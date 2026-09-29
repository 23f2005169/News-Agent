import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { queryOptions, useSuspenseQuery } from "@tanstack/react-query";
import { getItem } from "@/lib/items.functions";

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
      { title: `${title} — AI Field Notes` },
      { name: "description", content: `Read ${title} on AI Field Notes.` },
      { property: "og:title", content: `${title} — AI Field Notes` },
      { property: "og:description", content: `Read ${title} on AI Field Notes.` },
      { property: "og:type", content: "article" },
      { name: "twitter:card", content: "summary" },
    ] };
  },
  component: Article,
  errorComponent: () => <ArticleMessage message="This article could not be loaded right now." />,
  notFoundComponent: () => <ArticleMessage message="This article was not found." />,
});

function ArticleMessage({ message }: { message: string }) {
  return <main className="mx-auto max-w-[720px] px-6 pb-28 pt-20 sm:px-8 sm:pt-28"><p className="font-serif text-3xl">{message}</p><Link to="/" className="mt-12 inline-block text-sm text-primary hover:underline">Back to feed</Link></main>;
}

function Article() {
  const { id } = Route.useParams();
  const { data: item } = useSuspenseQuery(itemQuery(id));
  const paragraphs = item.raw_text?.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean) ?? [];

  return (
    <main className="mx-auto max-w-[720px] px-6 pb-32 pt-20 sm:px-8 sm:pt-28">
      {item.scraped_category && <p className="mb-5 text-sm font-medium text-primary">{item.scraped_category}</p>}
      <h1 className="font-serif text-[clamp(2.75rem,5vw,4.25rem)] font-semibold leading-[1.1]">{item.title || "Untitled article"}</h1>
      <div className="mt-10 border-t border-border pt-10 font-serif text-[1.25rem] leading-[1.8] sm:mt-14 sm:pt-12 sm:text-[1.35rem]">
        {paragraphs.map((paragraph, index) => <p key={index} className="mb-7 whitespace-pre-line last:mb-0">{paragraph}</p>)}
      </div>
      <Link to="/" className="mt-16 inline-block text-sm text-primary hover:underline focus-visible:outline-none focus-visible:underline">Back to feed</Link>
    </main>
  );
}