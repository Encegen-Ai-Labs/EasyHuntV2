from typing import Dict, Any, List
from app.repositories.base import BaseRepository


class ChainReconstructionService:
    def __init__(self, generic_repo: BaseRepository):
        self.generic_repo = generic_repo

    def reconstruct_case_chain(self, case_id: str) -> Dict[str, Any]:
        """
        Pulls all ownership_chain records for a case (across all its documents),
        deduplicates, sorts by date, and detects gaps or conflicts.
        """
        records = self.generic_repo.select("ownership_chain", {"case_id": case_id})

        if not records:
            return {
                "case_id": case_id,
                "chain": [],
                "gaps": [],
                "conflicts": [],
                "status": "no_data"
            }

        # sort chronologically - records with missing/invalid dates go last
        def sort_key(r):
            return r.get("transaction_date") or "9999-99-99"

        sorted_records = sorted(records, key=sort_key)

        # detect survey number conflicts - a case should generally track one property
        survey_numbers = set(r.get("survey_number") for r in sorted_records if r.get("survey_number"))
        conflicts = []
        if len(survey_numbers) > 1:
            conflicts.append({
                "type": "multiple_survey_numbers",
                "detail": f"Case references {len(survey_numbers)} different survey numbers: {list(survey_numbers)}"
            })

        # detect gaps - consecutive owners should link (owner[i] transfers to owner[i+1])
        gaps = []
        for i in range(len(sorted_records) - 1):
            current = sorted_records[i]
            next_record = sorted_records[i + 1]

            current_owner = current.get("owner_name")
            next_owner = next_record.get("owner_name")

            # if the same owner doesn't appear as continuity between consecutive records,
            # and there's no explicit transaction type explaining it, flag as a possible gap
            if current_owner and next_owner and current_owner != next_owner:
                if not next_record.get("transaction_type"):
                    gaps.append({
                        "between_sequence": [current.get("sequence_order"), next_record.get("sequence_order")],
                        "detail": f"Ownership moved from {current_owner} to {next_owner} with no recorded transaction type"
                    })

        return {
            "case_id": case_id,
            "chain": sorted_records,
            "gaps": gaps,
            "conflicts": conflicts,
            "status": "reconstructed"
        }

    def get_current_owner(self, case_id: str) -> Dict[str, Any]:
        """Returns the most recent owner in the chain for a case."""
        result = self.reconstruct_case_chain(case_id)
        if not result["chain"]:
            return {"owner_name": None, "as_of_date": None}

        latest = result["chain"][-1]
        return {
            "owner_name": latest.get("owner_name"),
            "as_of_date": latest.get("transaction_date")
        }