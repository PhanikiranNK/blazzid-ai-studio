"""Background recovery for abandoned jobs with expired worker leases."""

from __future__ import annotations

import logging
from datetime import datetime

from blazzid_jobs.repository import JobRepository

logger = logging.getLogger("blazzid.worker.recovery")


class JobRecoveryService:
    """Detects and reclaims abandoned processing jobs whose worker lease has expired."""

    def __init__(self, repository: JobRepository) -> None:
        self.repository = repository

    def recover(self, lease_expired_before: datetime) -> list[str]:
        """Scan and recover all jobs whose lease expired before the specified threshold."""
        recovered = self.repository.recover_abandoned_jobs(lease_expired_before)
        if recovered:
            logger.warning("Recovered %d abandoned jobs: %s", len(recovered), recovered)
        return recovered
