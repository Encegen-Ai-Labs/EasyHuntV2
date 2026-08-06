from typing import Dict, Any, List
from app.repositories.flag_repo import FlagRepository
from app.services.chain_service import ChainReconstructionService


class RiskFlaggingService:
    def __init__(self, flag_repo: FlagRepository, chain_service: ChainReconstructionService):
        self.flag_repo = flag_repo
        self.chain_service = chain_service

    def run_case_level_checks(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Runs risk checks that need the FULL case picture (multiple documents),
        not just a single document's extraction. Call this after all documents
        in a case have been processed.
        """
        flags_created = []
        chain_result = self.chain_service.reconstruct_case_chain(case_id)

        # flag survey number conflicts
        for conflict in chain_result["conflicts"]:
            flag = self.flag_repo.create_flag({
                "case_id": case_id,
                "flag_type": "Survey Number Conflict",
                "severity": "high",
                "description": conflict["detail"],
                "status": "raised"
            })
            flags_created.append(flag)

        # flag ownership gaps
        for gap in chain_result["gaps"]:
            flag = self.flag_repo.create_flag({
                "case_id": case_id,
                "flag_type": "Ownership Chain Gap",
                "severity": "high",
                "description": gap["detail"],
                "status": "raised"
            })
            flags_created.append(flag)

        # flag if chain has only one record - insufficient history for due diligence
        if len(chain_result["chain"]) <= 1:
            flag = self.flag_repo.create_flag({
                "case_id": case_id,
                "flag_type": "Insufficient Ownership History",
                "severity": "medium",
                "description": "Only one or zero ownership records found for this case — insufficient history to verify a clean chain of title",
                "status": "raised"
            })
            flags_created.append(flag)

        return flags_created