"""
Scheduled Jobs Router - API endpoints for managing scheduled agent executions.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Annotated, List

import pytz
from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Query, status

from bondable.bond.config import Config
from bondable.bond.providers.metadata import ScheduledJob, Thread
from bondable.bond.scheduler import MAX_TIMEOUT_SECONDS
from bondable.rest.models.auth import User
from bondable.rest.models.scheduled_jobs import (
    ScheduledJobCreateRequest,
    ScheduledJobResponse,
    ScheduledJobRunResponse,
    ScheduledJobUpdateRequest,
)
from bondable.rest.dependencies.auth import get_current_user

router = APIRouter(prefix="/scheduled-jobs", tags=["Scheduled Jobs"])
LOGGER = logging.getLogger(__name__)

# Minimum schedule interval in minutes — configurable via env var for testing
MIN_SCHEDULE_INTERVAL_MINUTES = int(
    os.getenv("MIN_SCHEDULE_INTERVAL_MINUTES", "60")
)
# Max jobs per user
MAX_JOBS_PER_USER = int(os.getenv("MAX_JOBS_PER_USER", "20"))


def _get_db_session():
    """Get database session from provider."""
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'metadata'):
        return provider.metadata.get_db_session()
    return None


def _validate_min_interval(schedule: str) -> None:
    """Reject cron schedules that fire more frequently than the configured minimum."""
    if MIN_SCHEDULE_INTERVAL_MINUTES <= 0:
        return  # disabled
    try:
        now = datetime.now(pytz.utc)
        cron = croniter(schedule, now)
        first = cron.get_next(datetime)
        second = cron.get_next(datetime)
        gap_minutes = (second - first).total_seconds() / 60
        if gap_minutes < MIN_SCHEDULE_INTERVAL_MINUTES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Schedule too frequent: fires every {int(gap_minutes)} minute(s). "
                       f"Minimum interval is {MIN_SCHEDULE_INTERVAL_MINUTES} minute(s). "
                       f"(Configurable via MIN_SCHEDULE_INTERVAL_MINUTES env var)",
            )
    except HTTPException:
        raise
    except Exception:  # nosec B110 — validation will be caught by croniter.is_valid check
        pass


def _compute_next_run(schedule: str, tz: str = "UTC") -> datetime:
    """Compute the next run time from a cron expression."""
    now = datetime.now(pytz.timezone(tz))
    cron = croniter(schedule, now)
    next_dt = cron.get_next(datetime)
    # Convert to UTC for storage
    return next_dt.astimezone(pytz.utc).replace(tzinfo=None)


def _job_to_response(job: ScheduledJob) -> ScheduledJobResponse:
    """Convert a ScheduledJob ORM object to a response model."""
    return ScheduledJobResponse(
        id=job.id,
        user_id=job.user_id,
        agent_id=job.agent_id,
        name=job.name,
        prompt=job.prompt,
        schedule=job.schedule,
        timezone=job.timezone or "UTC",
        is_enabled=job.is_enabled,
        status=job.status or "pending",
        timeout_seconds=job.timeout_seconds or 300,
        last_run_at=job.last_run_at,
        last_run_status=job.last_run_status,
        last_run_error=job.last_run_error,
        last_thread_id=job.last_thread_id,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("", response_model=List[ScheduledJobResponse])
async def list_scheduled_jobs(
    current_user: Annotated[User, Depends(get_current_user)]
) -> List[ScheduledJobResponse]:
    """List all scheduled jobs for the authenticated user."""
    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        jobs = session.query(ScheduledJob).filter(
            ScheduledJob.user_id == current_user.user_id
        ).order_by(ScheduledJob.created_at.desc()).all()

        return [_job_to_response(job) for job in jobs]
    finally:
        session.close()


@router.post("", response_model=ScheduledJobResponse, status_code=status.HTTP_201_CREATED)
async def create_scheduled_job(
    request: ScheduledJobCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
) -> ScheduledJobResponse:
    """Create a new scheduled job."""
    # Validate timezone
    try:
        pytz.timezone(request.timezone)
    except pytz.exceptions.UnknownTimeZoneError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid timezone: {request.timezone}"
        )

    # Validate timeout bounds
    if request.timeout_seconds < 60:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="timeout_seconds must be at least 60"
        )
    if request.timeout_seconds > MAX_TIMEOUT_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"timeout_seconds must be at most {MAX_TIMEOUT_SECONDS}"
        )

    # Validate cron expression
    if not croniter.is_valid(request.schedule):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid cron expression: {request.schedule}"
        )

    # Validate minimum schedule interval
    _validate_min_interval(request.schedule)

    # Validate agent access
    config = Config.config()
    provider = config.get_provider()
    if provider and hasattr(provider, 'agents'):
        try:
            # Reject scheduling the default (Home) agent
            agent_record = provider.agents.get_agent_record(request.agent_id)
            if agent_record and agent_record.is_default:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="The default Home agent cannot be used for scheduled jobs"
                )

            if not provider.agents.can_user_access_agent(
                user_id=current_user.user_id, agent_id=request.agent_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Agent not found or access denied"
                )
        except HTTPException:
            raise
        except Exception as e:
            LOGGER.warning("Agent access check failed for agent %s: %s", request.agent_id, e)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agent not found or access denied"
            )

    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        # Enforce per-user job limit
        existing_count = session.query(ScheduledJob).filter(
            ScheduledJob.user_id == current_user.user_id
        ).count()
        if existing_count >= MAX_JOBS_PER_USER:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Maximum of {MAX_JOBS_PER_USER} scheduled jobs per user"
            )

        next_run = _compute_next_run(request.schedule, request.timezone)

        job = ScheduledJob(
            id=str(uuid.uuid4()),
            user_id=current_user.user_id,
            agent_id=request.agent_id,
            name=request.name,
            prompt=request.prompt,
            schedule=request.schedule,
            timezone=request.timezone,
            is_enabled=request.is_enabled,
            status="pending",
            timeout_seconds=request.timeout_seconds,
            next_run_at=next_run,
        )
        session.add(job)
        session.commit()
        session.refresh(job)

        LOGGER.info("Created scheduled job %s for user %s", job.id, current_user.user_id)
        return _job_to_response(job)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        LOGGER.error("Error creating scheduled job: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create scheduled job")
    finally:
        session.close()


@router.get("/{job_id}", response_model=ScheduledJobResponse)
async def get_scheduled_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
) -> ScheduledJobResponse:
    """Get a single scheduled job."""
    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        job = session.query(ScheduledJob).filter(
            ScheduledJob.id == job_id,
            ScheduledJob.user_id == current_user.user_id
        ).first()

        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")

        return _job_to_response(job)
    finally:
        session.close()


@router.put("/{job_id}", response_model=ScheduledJobResponse)
async def update_scheduled_job(
    job_id: str,
    request: ScheduledJobUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)]
) -> ScheduledJobResponse:
    """Update a scheduled job."""
    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        job = session.query(ScheduledJob).filter(
            ScheduledJob.id == job_id,
            ScheduledJob.user_id == current_user.user_id
        ).first()

        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")

        # Validate timezone if provided
        if request.timezone is not None:
            try:
                pytz.timezone(request.timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid timezone: {request.timezone}"
                )

        # Validate timeout bounds if provided
        if request.timeout_seconds is not None and request.timeout_seconds < 60:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="timeout_seconds must be at least 60"
            )
        if request.timeout_seconds is not None and request.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"timeout_seconds must be at most {MAX_TIMEOUT_SECONDS}"
            )

        # Validate new cron expression if provided
        if request.schedule is not None:
            if not croniter.is_valid(request.schedule):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid cron expression: {request.schedule}"
                )
            # Only enforce min interval when the schedule is actually changing
            if request.schedule != job.schedule:
                _validate_min_interval(request.schedule)

        # Apply updates
        if request.name is not None:
            job.name = request.name
        if request.prompt is not None:
            job.prompt = request.prompt
        if request.schedule is not None:
            job.schedule = request.schedule
        if request.timezone is not None:
            job.timezone = request.timezone
        if request.is_enabled is not None:
            job.is_enabled = request.is_enabled
        if request.timeout_seconds is not None:
            job.timeout_seconds = request.timeout_seconds

        # Recompute next_run_at if schedule or timezone changed
        if request.schedule is not None or request.timezone is not None:
            job.next_run_at = _compute_next_run(
                job.schedule,
                job.timezone or "UTC"
            )

        session.commit()
        session.refresh(job)

        LOGGER.info("Updated scheduled job %s", job_id)
        return _job_to_response(job)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        LOGGER.error("Error updating scheduled job: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update scheduled job")
    finally:
        session.close()


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scheduled_job(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)]
):
    """Delete a scheduled job."""
    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        job = session.query(ScheduledJob).filter(
            ScheduledJob.id == job_id,
            ScheduledJob.user_id == current_user.user_id
        ).first()

        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")

        if job.status == "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete a running job. Wait for it to finish or disable it first."
            )

        session.delete(job)
        session.commit()

        LOGGER.info("Deleted scheduled job %s", job_id)
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        LOGGER.error("Error deleting scheduled job: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete scheduled job")
    finally:
        session.close()


@router.get("/{job_id}/runs", response_model=List[ScheduledJobRunResponse])
async def list_job_runs(
    job_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> List[ScheduledJobRunResponse]:
    """List past run threads for a scheduled job."""
    session = _get_db_session()
    if session is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database not available")

    try:
        # Verify job ownership
        job = session.query(ScheduledJob).filter(
            ScheduledJob.id == job_id,
            ScheduledJob.user_id == current_user.user_id
        ).first()

        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found")

        # Query threads associated with this job
        threads = session.query(Thread).filter(
            Thread.scheduled_job_id == job_id
        ).order_by(Thread.created_at.desc()).offset(offset).limit(limit).all()

        runs = []
        for thread in threads:
            # Read run status from thread's session_state JSON
            thread_status = None
            session_state = thread.session_state or {}
            if isinstance(session_state, dict):
                thread_status = session_state.get("scheduled_run_status")

            runs.append(ScheduledJobRunResponse(
                thread_id=thread.thread_id,
                thread_name=thread.name or "",
                created_at=thread.created_at,
                status=thread_status,
            ))

        return runs
    finally:
        session.close()
