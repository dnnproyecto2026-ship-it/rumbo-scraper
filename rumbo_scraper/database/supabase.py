"""Supabase client factory."""

from functools import lru_cache

from supabase import Client, create_client

from rumbo_scraper.settings import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Create and cache a Supabase client using local environment settings."""
    settings.validate_supabase()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )
