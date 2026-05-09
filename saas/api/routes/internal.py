"""Internal routes — called by Cloud Scheduler only. Protected by internal secret header."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from saas.api.deps import verify_internal_secret
from saas.workers.alert_monitor import check_alerts
from saas.workers.batch_scheduler import run_weekly_batch
from saas.workers.verdict_settler import settle_verdicts

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(verify_internal_secret)])


@router.post("/batch/run")
async def trigger_batch(background_tasks: BackgroundTasks) -> dict:
    """Cloud Scheduler calls this every Sunday at 8pm ET."""
    background_tasks.add_task(run_weekly_batch)
    return {"status": "batch_started"}


@router.post("/alerts/check")
async def trigger_alert_check(background_tasks: BackgroundTasks) -> dict:
    """Cloud Scheduler calls this every 5 minutes."""
    background_tasks.add_task(check_alerts)
    return {"status": "alert_check_started"}


@router.post("/verdicts/settle")
async def trigger_verdict_settlement(background_tasks: BackgroundTasks) -> dict:
    """Cloud Scheduler calls this daily to settle 30d and 90d verdict outcomes."""
    background_tasks.add_task(settle_verdicts)
    return {"status": "settlement_started"}
