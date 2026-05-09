"""Internal routes — called by Cloud Scheduler only. Protected by internal secret header."""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from saas.api.deps import verify_internal_secret
from saas.workers.alert_monitor import check_alerts
from saas.workers.batch_scheduler import run_weekly_batch

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
