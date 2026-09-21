from typing import List, Dict, Any
from app.repositories.base import BaseRepository

# The live Supabase table is "risk_flags", not "flags" — every call site
# below (and app/api/v1/flags.py, which bypasses this repository for two of
# its own reads) was pointed at "flags", a table that doesn't exist in the
# schema, so flag creation/listing/resolution has been silently failing
# (PostgREST 404 "Could not find the table 'public.flags'") regardless of
# how correct the surrounding code looked.
FLAGS_TABLE = "risk_flags"

class FlagRepository(BaseRepository):
    def create_flag(self, flag_data: Dict[str, Any]) -> Dict[str, Any]:
        # Same stray-DEFAULT issue as ownership_chain.document_id and
        # reports.approved_by elsewhere in this codebase (see
        # pipeline_service.py / report_builder_service.py) — except
        # risk_flags has it on *two* columns: document_id and resolved_by
        # both DEFAULT to a UUID that no longer exists in documents/users
        # respectively, which fires an FK violation on every insert that
        # omits either key (verified directly: fixing document_id alone
        # still failed, on resolved_by this time). None of this
        # repository's current callers flag against one specific document
        # or pre-resolve a flag at creation time — default both to null
        # once here instead of repeating this at every call site; either
        # key still wins if flag_data sets it explicitly.
        payload = {"document_id": None, "resolved_by": None, **flag_data}
        return self.insert(FLAGS_TABLE, payload)

    def list_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        return self.select(FLAGS_TABLE, {"case_id": case_id})

    def update_flag(self, flag_id: str, flag_data: Dict[str, Any]) -> Dict[str, Any]:
        results = self.update(FLAGS_TABLE, {"id": flag_id}, flag_data)
        return results[0] if results else None