import { createServerFn } from "@tanstack/react-start";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";

// External read-only dataset: the owner's own Supabase project.
// A publishable key is public by design, so these constants are safe in code.
const DATASET_URL = "https://ysvxlcynxomtmgnlties.supabase.co";
const DATASET_KEY = "sb_publishable_7zOwBVQ9ZMqwyjDehpoDqw_DRy9C7AF";

function publicClient() {
  return createClient(DATASET_URL, DATASET_KEY, {
    auth: { storage: undefined, persistSession: false, autoRefreshToken: false },
  });
}

export const getItems = createServerFn({ method: "GET" }).handler(async () => {
  const { data, error } = await publicClient()
    .from("items")
    .select("id,title,summary,scraped_category,source_type,word_count,published_date")
    .order("published_date", { ascending: false, nullsFirst: false })
    .order("id", { ascending: true });
  if (error) throw new Error("The reading collection could not be loaded.");
  return data ?? [];
});

export const getItem = createServerFn({ method: "GET" })
  .inputValidator((id: string) => z.string().min(1).parse(id))
  .handler(async ({ data: id }) => {
    const { data, error } = await publicClient()
      .from("items")
      .select("id,title,raw_text,scraped_category")
      .eq("id", id)
      .maybeSingle();
    if (error) throw new Error("This article could not be loaded.");
    return data;
  });