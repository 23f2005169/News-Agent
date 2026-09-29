CREATE TABLE public.items (
  id text PRIMARY KEY,
  title text,
  summary text,
  raw_text text,
  scraped_category text,
  source_type text,
  word_count integer,
  published_date timestamptz
);
GRANT SELECT ON public.items TO anon, authenticated;
GRANT ALL ON public.items TO service_role;
ALTER TABLE public.items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone can read items" ON public.items FOR SELECT TO anon, authenticated USING (true);