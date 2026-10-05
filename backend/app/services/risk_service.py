from typing import Dict, Any, List
from app.core.logging import logger
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

        Each flag insert below is isolated in its own try/except, matching
        the per-item defensive pattern used for flag/chain inserts elsewhere
        in pipeline_service.py. This method is called directly from
        finalize_case() with no try/except of its own — before this, a
        single failed insert (e.g. a schema mismatch, or any other transient
        DB error) would raise uncaught, both losing any other flags this
        call would otherwise have created and crashing case finalization
        entirely. Now one bad insert is logged and skipped; the rest of the
        run's flags still get created and finalize_case() still completes.
        """
        flags_created = []
        chain_result = self.chain_service.reconstruct_case_chain(case_id)

        # flag survey number conflicts
        for conflict in chain_result["conflicts"]:
            try:
                flag = self.flag_repo.create_flag({
                    "case_id": case_id,
                    "flag_type": "Survey Number Conflict",
                    "severity": "high",
                    "description": conflict["detail"],
                    "status": "raised",
                    "source": "structural"
                })
                flags_created.append(flag)
            except Exception as e:
                logger.error(
                    "risk_service.flag_create_failed | case_id=%s flag_type=%s error=%s",
                    case_id, "Survey Number Conflict", e,
                )

        # flag ownership gaps
        for gap in chain_result["gaps"]:
            try:
                flag = self.flag_repo.create_flag({
                    "case_id": case_id,
                    "flag_type": "Ownership Chain Gap",
                    "severity": "high",
                    "description": gap["detail"],
                    "status": "raised",
                    "source": "structural"
                })
                flags_created.append(flag)
            except Exception as e:
                logger.error(
                    "risk_service.flag_create_failed | case_id=%s flag_type=%s error=%s",
                    case_id, "Ownership Chain Gap", e,
                )

        # flag if chain has only one record - insufficient history for due diligence
        if len(chain_result["chain"]) <= 1:
            try:
                flag = self.flag_repo.create_flag({
                    "case_id": case_id,
                    "flag_type": "Insufficient Ownership History",
                    "severity": "medium",
                    "description": "Only one or zero ownership records found for this case — insufficient history to verify a clean chain of title",
                    "status": "raised",
                    "source": "structural"
                })
                flags_created.append(flag)
            except Exception as e:
                logger.error(
                    "risk_service.flag_create_failed | case_id=%s flag_type=%s error=%s",
                    case_id, "Insufficient Ownership History", e,
                )

        return flags_created