import asyncio
import json
import random
from pathlib import Path
from typing import Awaitable, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import Settings
from ..domain.models.enums import TemplateSelection
from ..domain.models.schedule import Schedule
from ..domain.models.template import PromptTemplate
from ..utils.logger import get_logger

logger = get_logger(__name__)

JobCallback = Callable[[Schedule, Optional[PromptTemplate]], Awaitable[None]]


class SchedulerService:
    def __init__(self, settings: Settings, job_callback: JobCallback):
        self._settings = settings
        self._job_callback = job_callback
        self._schedules: dict[str, Schedule] = {}
        self._templates: dict[str, PromptTemplate] = {}
        self._template_index: dict[str, int] = {}
        self._scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    def start(self) -> None:
        self._load_templates()
        if not self._settings.scheduler_enabled:
            logger.info("Scheduler disabled via config")
            return
        self._scheduler.start()
        logger.info("Scheduler started (timezone: %s)", self._settings.scheduler_timezone)

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def pause(self) -> None:
        if self._scheduler.running:
            self._scheduler.pause()
            logger.info("Scheduler paused")

    def resume(self) -> None:
        if self._scheduler.running:
            self._scheduler.resume()
            logger.info("Scheduler resumed")

    def list_jobs(self) -> list[Schedule]:
        return list(self._schedules.values())

    def get_templates(self) -> list[PromptTemplate]:
        return list(self._templates.values())

    def load_schedules_from_file(self, path: Path) -> None:
        if not path.exists():
            logger.warning("Schedule file not found: %s", path)
            return
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data if isinstance(data, list) else [data]:
            schedule = Schedule.model_validate(item)
            self._schedules[schedule.id] = schedule
            if schedule.enabled and self._scheduler.running:
                self._schedule_job(schedule)
        logger.info("Loaded %d schedule(s) from %s", len(self._schedules), path)

    def _load_templates(self) -> None:
        templates_dir = self._settings.templates_dir
        if not templates_dir.exists():
            logger.warning("Templates directory not found: %s", templates_dir)
            return
        for path in templates_dir.glob("*.json"):
            try:
                template = PromptTemplate.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.error("Failed to load template %s: %s", path, exc)
                continue
            if template.active:
                self._templates[template.id] = template
        logger.info("Loaded %d active template(s)", len(self._templates))

    def _schedule_job(self, schedule: Schedule) -> None:
        self._scheduler.add_job(
            func=self._run_job,
            trigger=CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone),
            id=schedule.id,
            name=f"post_{schedule.id}",
            kwargs={"schedule_id": schedule.id},
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        logger.info("Scheduled job '%s' with cron '%s'", schedule.id, schedule.cron)

    async def _run_job(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if not schedule or not schedule.enabled:
            return
        template = self._select_template(schedule)
        logger.info("Job triggered: schedule=%s template=%s", schedule_id, template.id if template else "none")
        for attempt in range(1, schedule.max_retries + 1):
            try:
                await self._job_callback(schedule, template)
                return
            except Exception as exc:
                logger.error("Job attempt %d/%d failed: %s", attempt, schedule.max_retries, exc)
                if attempt < schedule.max_retries:
                    await asyncio.sleep(self._settings.scheduler_retry_delay_seconds)

    def _select_template(self, schedule: Schedule) -> Optional[PromptTemplate]:
        if schedule.template_id in self._templates:
            return self._templates[schedule.template_id]
        templates = self.get_templates()
        if not templates:
            return None
        if schedule.template_selection == TemplateSelection.RANDOM:
            return random.choice(templates)
        index = self._template_index.get(schedule.id, 0)
        self._template_index[schedule.id] = index + 1
        return templates[index % len(templates)]
