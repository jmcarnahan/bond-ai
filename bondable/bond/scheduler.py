"""
Job Scheduler Engine - Database-polling scheduler for scheduled agent executions.

Uses SELECT FOR UPDATE SKIP LOCKED for distributed locking across multiple instances.
"""

import logging
import os
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytz
from croniter import croniter
from sqlalchemy.engine import Engine

from bondable.bond.providers.metadata import ScheduledJob, Thread, User
from bondable.rest.utils.auth import create_access_token
from bondable.rest.models.auth import User as RestUser

LOGGER = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 30  # seconds
DEFAULT_MIN_SCHEDULE_INTERVAL_MINUTES = 60  # minimum cron interval allowed
MAX_TIMEOUT_SECONDS = 3600  # 1 hour max timeout


class JobScheduler:
    """
    Database-polling scheduler for executing scheduled jobs.

    Polls the database at a configurable interval for due jobs,
    acquires them with distributed locking, and executes them.
    """

    def __init__(self, metadata, provider, instance_id=None):
        self._metadata = metadata
        self._provider = provider
        self._instance_id = instance_id or str(uuid.uuid4())
        self._stop_event = threading.Event()  # Set when stop is requested
        self._thread = None
        self._poll_interval = int(
            os.getenv("SCHEDULER_POLL_INTERVAL_SECONDS", str(DEFAULT_POLL_INTERVAL))
        )
        self._is_sqlite = None  # Lazy-detected on first poll

    def _detect_sqlite(self):
        """Check if the underlying database is SQLite (which doesn't support FOR UPDATE)."""
        try:
            session = self._metadata.get_db_session()
            engine = session.get_bind()
            dialect_name = getattr(getattr(engine, 'dialect', None), 'name', None)
            is_sqlite = dialect_name == "sqlite"
            session.close()
            if is_sqlite:
                LOGGER.info("SQLite detected — disabling FOR UPDATE SKIP LOCKED")
            return is_sqlite
        except Exception:
            return False

    def start(self):
        """Start the scheduler in a daemon thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        LOGGER.info("JobScheduler started (instance=%s, poll_interval=%ds)",
                     self._instance_id, self._poll_interval)

    def stop(self):
        """Stop the scheduler."""
        LOGGER.info("JobScheduler stopping (instance=%s)...", self._instance_id)
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        LOGGER.info("JobScheduler stopped (instance=%s)", self._instance_id)

    def _run_loop(self):
        """Main polling loop."""
        LOGGER.info("Scheduler loop started, polling every %ds", self._poll_interval)
        retention_check_counter = 0
        while not self._stop_event.is_set():
            try:
                self._poll_and_execute()
            except Exception as e:
                LOGGER.error("Scheduler poll error: %s", e, exc_info=True)

            # T16/T17: Run data retention cleanup once per hour (every ~120 polls at 30s interval)
            retention_check_counter += 1
            if retention_check_counter >= 120:
                retention_check_counter = 0
                try:
                    self._run_data_retention_cleanup()
                except Exception as e:
                    LOGGER.error("Data retention cleanup error: %s", e, exc_info=True)

            # Wait for poll interval or until stop is signaled
            if self._stop_event.wait(timeout=self._poll_interval):
                break  # Stop was requested
        LOGGER.info("Scheduler loop exited")

    def _run_data_retention_cleanup(self):
        """T16/T17: Delete messages and related records older than the retention period.

        Default retention: 90 days, configurable via MESSAGE_RETENTION_DAYS env var.
        Also cleans up expired auth codes and revoked tokens.
        """
        retention_days = int(os.getenv("MESSAGE_RETENTION_DAYS", "90"))
        if retention_days <= 0:
            return  # Retention disabled

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)

        try:
            from bondable.bond.providers.bedrock.BedrockMetadata import BedrockMessage
            session = self._metadata.get_db_session()
            try:
                deleted = session.query(BedrockMessage).filter(
                    BedrockMessage.created_at < cutoff
                ).delete()
                if deleted > 0:
                    session.commit()
                    LOGGER.info("DATA_RETENTION: Deleted %d messages older than %d days", deleted, retention_days)
                else:
                    session.rollback()
            except Exception as e:
                session.rollback()
                LOGGER.error("Error during message retention cleanup: %s", e)
            finally:
                session.close()
        except ImportError:
            pass  # BedrockMessage not available (non-Bedrock provider)

        # Also clean up expired auth codes and revoked tokens
        try:
            from bondable.bond.providers.metadata import AuthCode, RevokedToken
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            session = self._metadata.get_db_session()
            try:
                expired_codes = session.query(AuthCode).filter(
                    AuthCode.expires_at < now - timedelta(minutes=5)
                ).delete()
                expired_tokens = session.query(RevokedToken).filter(
                    RevokedToken.expires_at < now
                ).delete()
                if expired_codes > 0 or expired_tokens > 0:
                    session.commit()
                    LOGGER.info(
                        "DATA_RETENTION: Cleaned %d expired auth codes, %d expired revoked tokens",
                        expired_codes, expired_tokens
                    )
                else:
                    session.rollback()
            except Exception as e:
                session.rollback()
                LOGGER.error("Error during auth cleanup: %s", e)
            finally:
                session.close()
        except ImportError:
            pass

    def _poll_and_execute(self):
        """Poll for due jobs and execute them."""
        if self._is_sqlite is None:
            self._is_sqlite = self._detect_sqlite()

        session = self._metadata.get_db_session()
        try:
            now = datetime.now(timezone.utc).replace(tzinfo=None)

            # Find due jobs: enabled, not running, past their next_run_at
            due_query = (
                session.query(ScheduledJob)
                .filter(
                    ScheduledJob.is_enabled == True,  # noqa: E712
                    ScheduledJob.next_run_at <= now,
                    ScheduledJob.status != "running",
                )
            )
            if not self._is_sqlite:
                due_query = due_query.with_for_update(skip_locked=True)
            jobs = due_query.limit(5).all()

            # Also pick up zombie jobs — use per-job timeout (2x) for detection
            running_query = (
                session.query(ScheduledJob)
                .filter(
                    ScheduledJob.status == "running",
                )
            )
            if not self._is_sqlite:
                running_query = running_query.with_for_update(skip_locked=True)
            running_jobs = running_query.all()
            zombies = [
                j for j in running_jobs
                if j.locked_at and (now - j.locked_at).total_seconds() > (j.timeout_seconds or 300) * 2
            ]

            all_jobs = jobs + zombies

            if not all_jobs:
                LOGGER.debug("Scheduler poll: no due jobs found")
                session.close()
                return

            LOGGER.info("Scheduler poll: found %d due job(s), %d zombie(s)",
                        len(jobs), len(zombies))

            # Mark jobs as running within the same transaction
            for job in all_jobs:
                job.status = "running"
                job.locked_by = self._instance_id
                job.locked_at = now

            # Capture job IDs before closing session (objects become detached)
            job_ids = [(job.id, job.name) for job in all_jobs]

            session.commit()
            session.close()

            # Execute each job with its own session to isolate failures
            for job_id, job_name in job_ids:
                try:
                    self._execute_job_by_id(job_id, job_name)
                except Exception as e:
                    LOGGER.error("Error executing job %s: %s", job_id, e, exc_info=True)
                    self._record_failure_by_id(job_id, str(e))

        except Exception as e:
            LOGGER.error("Error in poll_and_execute: %s", e, exc_info=True)
            try:
                session.rollback()
            except Exception:  # nosec B110 — cleanup must not mask original error
                pass
            try:
                session.close()
            except Exception:  # nosec B110
                pass

    def _execute_job_by_id(self, job_id, job_name):
        """Execute a single scheduled job using its own DB session."""
        LOGGER.info("Executing scheduled job %s (%s)", job_id, job_name)

        session = self._metadata.get_db_session()
        new_thread = None  # B2: Track thread for failure handling
        try:
            # Re-load the job in this session to avoid detached instance issues
            job = session.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not job:
                LOGGER.warning("Job %s disappeared before execution", job_id)
                return

            # Look up user
            user_record = session.query(User).filter(User.id == job.user_id).first()
            if not user_record:
                raise ValueError(f"User {job.user_id} not found")

            # Create JWT for this user (expiry matches job timeout)
            jwt_token = self._create_jwt_for_user(user_record, job.timeout_seconds or 300)

            # Build REST User object
            rest_user = RestUser(
                email=user_record.email,
                name=user_record.name,
                provider=user_record.sign_in_method,
                user_id=user_record.id,
            )

            # B1: Validate agent access BEFORE creating thread
            agent_instance = self._provider.agents.get_agent(agent_id=job.agent_id)
            if not agent_instance:
                raise ValueError(f"Agent {job.agent_id} not found")

            if not self._provider.agents.can_user_access_agent(
                user_id=job.user_id, agent_id=job.agent_id
            ):
                raise PermissionError(
                    f"User {job.user_id} does not have access to agent {job.agent_id}"
                )

            # Create thread for this execution (use job's timezone for readable name)
            job_tz = pytz.timezone(job.timezone or "UTC")
            timestamp = datetime.now(job_tz).strftime("%Y-%m-%d %H:%M")
            thread_name = f"[Scheduled] {job.name} - {timestamp}"
            new_thread = self._provider.threads.create_thread(
                user_id=job.user_id,
                name=thread_name,
            )

            # Set scheduled_job_id on the thread
            thread_record = session.query(Thread).filter(
                Thread.thread_id == new_thread.thread_id,
                Thread.user_id == job.user_id,
            ).first()
            if thread_record:
                thread_record.scheduled_job_id = job.id
                session.commit()

            # Stream response (consume all chunks)
            start_time = time.time()
            chunk_count = 0
            for chunk in agent_instance.stream_response(
                thread_id=new_thread.thread_id,
                prompt=job.prompt,
                attachments=[],
                override_role="user",
                current_user=rest_user,
                jwt_token=jwt_token,
            ):
                chunk_count += 1
            elapsed = time.time() - start_time
            LOGGER.info("Job %s: streamed %d chunks in %.1fs", job.id, chunk_count, elapsed)

            # Re-load job from DB — stream_response() uses the same scoped session
            # internally, which may have expired/detached our job object
            session = self._metadata.get_db_session()
            job = session.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not job:
                LOGGER.error("Job %s disappeared after execution", job_id)
                return

            # Store run status on thread session_state for run history
            self._set_thread_run_status(session, new_thread.thread_id, job.user_id, "completed")

            # Record success
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            job.last_run_at = now
            job.last_run_status = "completed"
            job.last_run_error = None
            job.last_thread_id = new_thread.thread_id
            job.next_run_at = self._compute_next_run(job.schedule, job.timezone or "UTC")
            job.status = "pending"
            job.locked_by = None
            job.locked_at = None
            session.commit()

            LOGGER.info("Scheduled job %s completed successfully (thread=%s)",
                         job.id, new_thread.thread_id)

        except Exception as e:
            LOGGER.error("Scheduled job %s failed: %s", job_id, e, exc_info=True)
            try:
                session.rollback()
            except Exception:  # nosec B110 — cleanup must not mask original error
                pass
            try:
                session.close()
            except Exception:  # nosec B110
                pass
            # Use a fresh session for failure recording — the original session
            # may be in a dirty/expired state after rollback
            self._record_failure_by_id(job_id, str(e), thread_id=new_thread.thread_id if new_thread else None)
            return
        finally:
            try:
                session.close()
            except Exception:  # nosec B110
                pass

    def _set_thread_run_status(self, session, thread_id, user_id, run_status, error=None):
        """Store the scheduled run status in the thread's session_state JSON."""
        try:
            thread_record = session.query(Thread).filter(
                Thread.thread_id == thread_id,
                Thread.user_id == user_id,
            ).first()
            if thread_record:
                state = thread_record.session_state or {}
                state["scheduled_run_status"] = run_status
                if error:
                    state["scheduled_run_error"] = error[:500]
                thread_record.session_state = state
                session.commit()
        except Exception as e:
            LOGGER.warning("Failed to set thread run status: %s", e)

    def _record_failure_by_id(self, job_id, error_msg, thread_id=None):
        """Record a job failure by ID using a fresh session (for detached jobs)."""
        session = self._metadata.get_db_session()
        try:
            job = session.query(ScheduledJob).filter(ScheduledJob.id == job_id).first()
            if not job:
                return

            # Store failed status on thread if one was created
            if thread_id:
                self._set_thread_run_status(
                    session, thread_id, job.user_id, "failed", error=error_msg
                )

            self._record_failure_with_session(job, session, error_msg)
        finally:
            try:
                session.close()
            except Exception:  # nosec B110
                pass

    def _record_failure_with_session(self, job, session, error_msg):
        """Record a job execution failure."""
        try:
            # Re-load job in this session to avoid detached instance issues
            job = session.query(ScheduledJob).filter(ScheduledJob.id == job.id).first()
            if not job:
                return

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            job.last_run_at = now
            job.last_run_status = "failed"
            job.last_run_error = error_msg[:2000] if error_msg else None
            job.next_run_at = self._compute_next_run(job.schedule, job.timezone or "UTC")
            job.status = "pending"
            job.locked_by = None
            job.locked_at = None
            session.commit()
        except Exception as e:
            LOGGER.error("Error recording failure for job %s: %s", job.id if job else "unknown", e)
            try:
                session.rollback()
            except Exception:  # nosec B110
                pass

    def _create_jwt_for_user(self, user_record, timeout_seconds=300):
        """Create a JWT token for a user record.

        The token expiry matches the job's timeout_seconds plus a 5-minute buffer
        to ensure the token remains valid for the entire execution.
        """
        timeout_seconds = max(60, timeout_seconds or 300)  # defensive floor
        jwt_data = {
            "sub": user_record.email,
            "name": user_record.name,
            "provider": user_record.sign_in_method,
            "user_id": user_record.id,
            "iss": "bond-ai",
            "aud": "mcp-server",
        }
        expiry_minutes = max(15, (timeout_seconds // 60) + 5)
        return create_access_token(
            data=jwt_data,
            expires_delta=timedelta(minutes=expiry_minutes),
        )

    @staticmethod
    def _compute_next_run(schedule, tz="UTC"):
        """Compute the next run time from a cron expression."""
        try:
            now = datetime.now(pytz.timezone(tz))
            cron = croniter(schedule, now)
            next_dt = cron.get_next(datetime)
            return next_dt.astimezone(pytz.utc).replace(tzinfo=None)
        except Exception as e:
            LOGGER.warning(
                "Failed to compute next run for schedule '%s' (tz=%s): %s. "
                "Falling back to 1 hour from now.",
                schedule, tz, e,
            )
            return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
