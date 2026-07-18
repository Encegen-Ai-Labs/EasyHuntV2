from typing import Dict, Any, List, Optional
from supabase import Client, create_client
from app.core.config import get_supabase_key, settings

class BaseRepository:
    def __init__(self, supabase_client: Optional[Client] = None):
        # Allow client injection, fallback to global settings
        self.client: Client = supabase_client or create_client(settings.SUPABASE_URL, get_supabase_key())

    def select(self, table: str, query_filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        builder = self.client.table(table).select("*")
        if query_filters:
            for key, val in query_filters.items():
                builder = builder.eq(key, val)
        response = builder.execute()
        return response.data

    def select_one(self, table: str, query_filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        results = self.select(table, query_filters)
        return results[0] if results else None

    def insert(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        response = self.client.table(table).insert(data).execute()
        if not response.data:
            raise Exception(f"Insert failed on table {table}")
        return response.data[0]

    def update(self, table: str, query_filters: Dict[str, Any], data: Dict[str, Any]) -> List[Dict[str, Any]]:
        builder = self.client.table(table).update(data)
        for key, val in query_filters.items():
            builder = builder.eq(key, val)
        response = builder.execute()
        return response.data

    def delete(self, table: str, query_filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        builder = self.client.table(table).delete()
        for key, val in query_filters.items():
            builder = builder.eq(key, val)
        response = builder.execute()
        return response.data