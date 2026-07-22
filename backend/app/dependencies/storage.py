from typing import Optional

from supabase import Client

from app.dependencies.db import get_supabase_client


class StorageService:
    def __init__(self, supabase_client: Optional[Client] = None):
        self.client = supabase_client or get_supabase_client()

    def get_bucket(self, bucket_name: str):
        return self.client.storage.from_(bucket_name)


def get_storage_service() -> StorageService:
    return StorageService()
