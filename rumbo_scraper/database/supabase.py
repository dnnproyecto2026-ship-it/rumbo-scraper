"""Supabase client factory and shared read helpers."""

from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from rumbo_scraper.settings import settings

PAGE_SIZE = 1000


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Create and cache a Supabase client using local environment settings."""
    settings.validate_supabase()
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
    )


def select_all(query: Any, size: int = PAGE_SIZE) -> list[dict[str, Any]]:
    """Read every row of a query, not just the first page.

    PostgREST caps an unbounded select at 1000 rows and reports nothing about
    the rows it withheld. A loader that reads its existing records through that
    cap believes the ones past it do not exist and inserts them again, so the
    table grows silently on every run. Reading in pages is the only way the
    synchronisation can see what it is comparing against.
    """
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        response = query.range(offset, offset + size - 1).execute()
        page = getattr(response, "data", None)
        if not isinstance(page, list):
            raise RuntimeError("Supabase devolvió una respuesta sin datos.")
        rows.extend(page)
        if len(page) < size:
            return rows
        offset += size
