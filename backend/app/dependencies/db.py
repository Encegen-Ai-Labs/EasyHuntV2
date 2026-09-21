from typing import Optional

import httpx
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.core.config import get_supabase_key, settings

_supabase_client: Optional[Client] = None
_supabase_service_client: Optional[Client] = None


def _client_options() -> SyncClientOptions:
    # postgrest-py and storage3 each build their own httpx.Client with
    # http2=True hardcoded (postgrest/_sync/client.py, storage3/_sync/client.py) —
    # not something supabase-py's public options normally let you turn off,
    # short of handing it a pre-built httpx.Client here, which it will use
    # as-is instead of building its own.
    #
    # That matters because every sync FastAPI dependency (get_current_user,
    # the doc/case/user lookups behind it) runs in its own threadpool worker
    # thread (Starlette's run_in_threadpool), while this Supabase client is a
    # single module-level singleton shared across all of them. Concurrent
    # requests — e.g. the frontend polling GET /documents/{id} — end up
    # issuing requests from different threads over the *same* pooled HTTP/2
    # connection at once. On Windows that races a non-blocking socket read
    # and raises `httpx.ReadError: [WinError 10035] A non-blocking socket
    # operation could not be completed immediately`, which surfaces as a 500
    # on whatever request happened to be sharing that connection at the time
    # — intermittent, and easy to mistake for the request/pipeline itself
    # being slow when it's actually a failed-and-presumably-retried poll.
    # Forcing HTTP/1.1 gives each concurrent request its own connection
    # instead of multiplexing streams over one shared socket, which avoids
    # the race entirely (verified against the live project).
    return SyncClientOptions(httpx_client=httpx.Client(http2=False))


def get_supabase_client() -> Client:
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY, options=_client_options())
    return _supabase_client


def get_supabase_service_client() -> Client:
    global _supabase_service_client
    if _supabase_service_client is None:
        _supabase_service_client = create_client(settings.SUPABASE_URL, get_supabase_key(), options=_client_options())
    return _supabase_service_client