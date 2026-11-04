from typing import TYPE_CHECKING, Awaitable, Callable

from telegram import Update
from telegram.ext import ContextTypes

if TYPE_CHECKING:
    from ..services.scheduler import SchedulerService
    from ..services.storage import StorageService

HISTORY_LIMIT = 10
_STATUS_ICONS = {"published": "✅", "discarded": "❌", "failed": "💥"}


class CommandHandler:
    def __init__(
        self,
        allowed_chat_ids: list[int],
        storage: "StorageService",
        scheduler: "SchedulerService",
        force_callback: Callable[[], Awaitable[None]],
        criar_callback: Callable[[int], Awaitable[None]],
    ):
        self._allowed_chat_ids = allowed_chat_ids
        self._storage = storage
        self._scheduler = scheduler
        self._force_callback = force_callback
        self._criar_callback = criar_callback

    def commands(self) -> dict[str, Callable]:
        return {
            "start": self.cmd_start,
            "criar": self.cmd_criar,
            "status": self.cmd_status,
            "history": self.cmd_history,
            "schedule": self.cmd_schedule,
            "pause": self.cmd_pause,
            "resume": self.cmd_resume,
            "force": self.cmd_force,
            "metrics": self.cmd_metrics,
        }

    def _is_allowed(self, update: Update) -> bool:
        return update.effective_chat is not None and update.effective_chat.id in self._allowed_chat_ids

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await update.message.reply_text(
            "🤖 *Instagram Agent ativo.*\n\n"
            "Comandos disponíveis:\n"
            "/criar — criar uma imagem conversando com a IA\n"
            "/status — posts pendentes\n"
            "/history — últimos posts\n"
            "/schedule — jobs agendados\n"
            "/pause — pausar scheduler\n"
            "/resume — retomar scheduler\n"
            "/force — forçar geração imediata\n"
            "/metrics — métricas de custo e aprovação",
            parse_mode="Markdown",
        )

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        pending = await self._storage.get_pending_posts()
        if not pending:
            await update.message.reply_text("✅ Nenhum post aguardando aprovação.")
            return
        lines = [f"📋 *{len(pending)} post(s) pendente(s):*\n"]
        lines += [f"• `{p.id[:8]}` — `{p.template_id}` (tentativa {p.attempt})" for p in pending]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        posts = await self._storage.get_history(limit=HISTORY_LIMIT)
        if not posts:
            await update.message.reply_text("📭 Nenhum post no histórico.")
            return
        lines = [f"📜 *Últimos {len(posts)} posts:*\n"]
        lines += [
            f"{_STATUS_ICONS.get(p.status.value, '⏳')} `{p.id[:8]}` — `{p.template_id}` "
            f"({p.created_at.strftime('%d/%m %H:%M')})"
            for p in posts
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        jobs = self._scheduler.list_jobs()
        if not jobs:
            await update.message.reply_text("📅 Nenhum job agendado.")
            return
        lines = [f"📅 *{len(jobs)} job(s) agendado(s):*\n"]
        lines += [
            f"{'✅' if s.enabled else '⏸'} `{s.id}` — `{s.cron}` (`{s.timezone}`)" for s in jobs
        ]
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        self._scheduler.pause()
        await update.message.reply_text("⏸ Scheduler pausado.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        self._scheduler.resume()
        await update.message.reply_text("▶️ Scheduler retomado.")

    async def cmd_force(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await update.message.reply_text("⚡ Iniciando geração imediata...")
        await self._force_callback()

    async def cmd_criar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await self._criar_callback(update.effective_chat.id)

    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        m = await self._storage.get_metrics("30d")
        await update.message.reply_text(
            f"📊 *Métricas — últimos 30 dias:*\n\n"
            f"Total de posts: {m.total_posts}\n"
            f"Publicados: {m.published}\n"
            f"Rejeitados: {m.rejected}\n"
            f"Taxa de aprovação: {m.approval_rate * 100:.1f}%\n"
            f"Custo total: ${m.total_cost_usd:.2f}\n"
            f"Custo médio/post: ${m.avg_cost_per_post:.3f}",
            parse_mode="Markdown",
        )
