"""Supabase configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SupabaseConfig:
    url: str
    service_key: str


def get_supabase_config() -> Optional[SupabaseConfig]:
    """Read Supabase connection settings from the environment."""
    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not service_key:
        return None
    return SupabaseConfig(url=url, service_key=service_key)


def get_supabase_client():
    """Create a Supabase client when credentials are available."""
    config = get_supabase_config()
    if config is None:
        return None

    from supabase import create_client

    return create_client(config.url, config.service_key)