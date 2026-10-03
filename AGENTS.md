<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

- Article explainers and semantic search run as public server functions in `src/lib/explainer.functions.ts` against the owner's external dataset project; the explainer reads/writes the `article_explainers` cache first so the LLM only runs once per article.
- Search queries are embedded with the same model the dataset was built with (bge-small via Hugging Face) so similarity scores match the stored vectors.
