from typing import Optional

from supabase import Client, create_client

from app.core.config import get_supabase_key, settings

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(settings.SUPABASE_URL, get_supabase_key())
    return _supabase_client