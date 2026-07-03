import asyncio
import json
from pathlib import Path
from typing import Callable, Awaitable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

from ..config import Settings
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

        self._scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            timezone=settings.scheduler_timezone,
        )

    async def start(self) -> None:
        self._load_templates()
        if self._settings.scheduler_enabled:
            self._scheduler.start()
            logger.info("Scheduler started (timezone: %s)", self._settings.scheduler_timezone)
        else:
            logger.info("Scheduler disabled via config")

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    async def pause(self) -> None:
        if self._scheduler.running:
            self._scheduler.pause()
            logger.info("Scheduler paused")

    async def resume(self) -> None:
        if self._scheduler.running:
            self._scheduler.resume()
            logger.info("Scheduler resumed")

    async def add_job(self, schedule: Schedule) -> str:
        self._schedules[schedule.id] = schedule
        if schedule.enabled and self._scheduler.running:
            self._schedule_job(schedule)
        return schedule.id

    async def remove_job(self, job_id: str) -> None:
        self._schedules.pop(job_id, None)
        try:
            self._scheduler.remove_job(job_id)
        except Exception as exc:
            # Job pode já não existir no scheduler (ex.: nunca agendado por estar
            # desabilitado). Não é fatal, mas logamos para não mascarar falhas
            # reais do jobstore.
            logger.debug("Não foi possível remover job '%s' do scheduler: %s", job_id, exc)

    async def list_jobs(self) -> list[Schedule]:
        return list(self._schedules.values())

    async def update_job(self, job_id: str, schedule: Schedule) -> None:
        await self.remove_job(job_id)
        await self.add_job(schedule)

    def load_schedules_from_file(self, path: Path) -> None:
        if not path.exists():
            logger.warning("Schedule file not found: %s", path)
            return
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        schedules = data if isinstance(data, list) else [data]
        for item in schedules:
            schedule = Schedule.model_validate(item)
            self._schedules[schedule.id] = schedule
            if schedule.enabled and self._scheduler.running:
                self._schedule_job(schedule)
        logger.info("Loaded %d schedule(s) from %s", len(schedules), path)

    def get_templates(self) -> list[PromptTemplate]:
        return list(self._templates.values())

    def _load_templates(self) -> None:
        templates_dir = self._settings.templates_dir
        if not templates_dir.exists():
            logger.warning("Templates directory not found: %s", templates_dir)
            return
        count = 0
        for path in templates_dir.glob("*.json"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                template = PromptTemplate.model_validate(data)
                if template.active:
                    self._templates[template.id] = template
                    count += 1
            except Exception as exc:
                logger.error("Failed to load template %s: %s", path, exc)
        logger.info("Loaded %d active template(s)", count)

    def _schedule_job(self, schedule: Schedule) -> None:
        trigger = CronTrigger.from_crontab(schedule.cron, timezone=schedule.timezone)
        self._scheduler.add_job(
            func=self._run_job,
            trigger=trigger,
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
        active = [t for t in self._templates.values() if t.active]
        if not active:
            return None

        if schedule.template_id and schedule.template_id in self._templates:
            return self._templates[schedule.template_id]

        from ..domain.models.enums import TemplateSelection
        if schedule.template_selection == TemplateSelection.RANDOM:
            import random
            return random.choice(active)
        elif schedule.template_selection in (TemplateSelection.SEQUENTIAL, TemplateSelection.ROUND_ROBIN):
            idx = self._template_index.get(schedule.id, 0)
            template = active[idx % len(active)]
            self._template_index[schedule.id] = idx + 1
            return template

        import random
        return random.choice(active)
