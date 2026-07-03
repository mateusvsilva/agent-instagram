from typing import TYPE_CHECKING, Awaitable, Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..services.storage import StorageService
    from ..services.scheduler import SchedulerService

logger = get_logger(__name__)

ForceCallback = Callable[[], Awaitable[None]]

# Quantidade de posts exibidos pelo comando /history.
HISTORY_LIMIT = 10


class CommandHandler:
    def __init__(
        self,
        allowed_chat_ids: list[int],
        storage: "StorageService",
        scheduler: "SchedulerService",
        force_callback: ForceCallback,
        criar_callback: Optional[Callable[[int], Awaitable[None]]] = None,
    ):
        self._allowed_chat_ids = allowed_chat_ids
        self._storage = storage
        self._scheduler = scheduler
        self._force_callback = force_callback
        self._criar_callback = criar_callback

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
        for post in pending:
            lines.append(f"• `{post.id[:8]}` — {post.template_id} (tentativa {post.attempt})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        posts = await self._storage.get_history(limit=HISTORY_LIMIT)
        if not posts:
            await update.message.reply_text("📭 Nenhum post no histórico.")
            return
        lines = [f"📜 *Últimos {len(posts)} posts:*\n"]
        for post in posts:
            ts = post.created_at.strftime("%d/%m %H:%M")
            status_icon = {"published": "✅", "discarded": "❌", "failed": "💥"}.get(
                post.status.value, "⏳"
            )
            lines.append(f"{status_icon} `{post.id[:8]}` — {post.template_id} ({ts})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_schedule(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        jobs = await self._scheduler.list_jobs()
        if not jobs:
            await update.message.reply_text("📅 Nenhum job agendado.")
            return
        lines = [f"📅 *{len(jobs)} job(s) agendado(s):*\n"]
        for sched in jobs:
            icon = "✅" if sched.enabled else "⏸"
            lines.append(f"{icon} `{sched.id}` — `{sched.cron}` ({sched.timezone})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_pause(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await self._scheduler.pause()
        await update.message.reply_text("⏸ Scheduler pausado.")

    async def cmd_resume(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await self._scheduler.resume()
        await update.message.reply_text("▶️ Scheduler retomado.")

    async def cmd_force(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        await update.message.reply_text("⚡ Iniciando geração imediata...")
        try:
            await self._force_callback()
        except Exception as exc:
            await update.message.reply_text(f"❌ Erro: {exc}")

    async def cmd_criar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update) or self._criar_callback is None:
            return
        await self._criar_callback(update.effective_chat.id)

    async def cmd_metrics(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            return
        metrics = await self._storage.get_metrics("30d")
        text = (
            f"📊 *Métricas — últimos 30 dias:*\n\n"
            f"Total de posts: {metrics.total_posts}\n"
            f"Publicados: {metrics.published}\n"
            f"Rejeitados: {metrics.rejected}\n"
            f"Taxa de aprovação: {metrics.approval_rate * 100:.1f}%\n"
            f"Custo total: ${metrics.total_cost_usd:.2f}\n"
            f"Custo médio/post: ${metrics.avg_cost_per_post:.3f}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")
