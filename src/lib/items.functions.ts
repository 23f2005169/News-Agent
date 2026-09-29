import { createServerFn } from "@tanstack/react-start";
import { createClient } from "@supabase/supabase-js";
import { z } from "zod";
import type { Database } from "@/integrations/supabase/types";

function publicClient() {
  const url = process.env["SUPABASE_URL"];
  const key = process.env["SUPABASE_PUBLISHABLE_KEY"];
  if (!url || !key) throw new Error("The reading collection is unavailable.");
  return createClient<Database>(url, key, {
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