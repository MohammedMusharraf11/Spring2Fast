"""Supabase client singleton for Spring2Fast.

Replaces the SQLAlchemy/SQLite layer entirely.
All DB operations go through the Supabase Python client using the service role key
so that RLS policies are bypassed for backend-only writes.
"""

from __future__ import annotations

from functools import lru_cache

from supabase import create_client, Client

from app.config import settings


@lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return a cached Supabase client (service role — bypasses RLS)."""
    url = settings.db_url
    key = settings.service_role_key

    if not url or not key:
        raise RuntimeError(
            "Supabase is not configured. "
            "Set DB_URL and SERVICE_ROLE_KEY in your .env file."
        )

    return create_client(url, key)
