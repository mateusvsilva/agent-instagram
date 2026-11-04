import asyncio
from pathlib import Path
from typing import Callable, Optional

from telegram import InputMediaPhoto
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ..config import Settings
from ..domain.models.enums import ApprovalStatus
from ..domain.models.post import ComposedPost
from ..handlers.approval_handler import ApprovalHandler, build_approval_keyboard
from ..handlers.creation_handler import build_creation_final_keyboard, build_creation_keyboard, build_mode_keyboard
from ..utils.logger import get_logger

logger = get_logger(__name__)

TELEGRAM_MESSAGE_LIMIT = 4096
NOTIFY_TIMEOUT_SECONDS = 15


class TelegramBotService:
    def __init__(self, settings: Settings, approval_handler: ApprovalHandler):
        self._settings = settings
        self._approval_handler = approval_handler
        self._app: Optional[Application] = None
        self._chat_id = settings.telegram_chat_id
        self._timeout = settings.telegram_approval_timeout

    def register_handlers(
        self,
        commands: dict[str, Callable],
        on_message: Callable,
        on_creation_callback: Callable,
    ) -> None:
        if not self._app:
            raise RuntimeError("Bot not initialized — call start() first")
        for name, callback in commands.items():
            self._app.add_handler(CommandHandler(name, callback))
        self._app.add_handler(CallbackQueryHandler(on_creation_callback, pattern=r"^create:"))
        self._app.add_handler(CallbackQueryHandler(self._approval_handler.handle_callback))
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
        self._app.add_error_handler(self._on_error)

    async def start(self) -> None:
        self._app = Application.builder().token(self._settings.telegram_bot_token).build()
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started and polling.")

    async def stop(self) -> None:
        if not self._app:
            return
        if self._app.updater.running:
            await self._app.updater.stop()
        if self._app.running:
            await self._app.stop()
        await self._app.shutdown()
        logger.info("Telegram bot stopped.")

    async def _on_error(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logger.error("Erro ao processar update do Telegram", exc_info=context.error)
        await self.notify(f"❌ Erro: {type(context.error).__name__}: {context.error}")

    async def send_preview(self, post: ComposedPost) -> str:
        bot = self._app.bot
        paths = [Path(p) for p in post.composed_image_paths]
        caption = self._build_preview_caption(post)

        if len(paths) == 1:
            with paths[0].open("rb") as f:
                await bot.send_photo(chat_id=self._chat_id, photo=f, caption=caption, parse_mode="Markdown")
        else:
            media = [
                InputMediaPhoto(
                    media=path.read_bytes(),
                    caption=caption if i == 0 else None,
                    parse_mode="Markdown" if i == 0 else None,
                )
                for i, path in enumerate(paths)
            ]
            await bot.send_media_group(chat_id=self._chat_id, media=media)

        await self._send_full_caption(post)
        msg = await bot.send_message(
            chat_id=self._chat_id,
            text=f"Post `{post.id[:8]}` — {len(paths)} imagem(ns). Escolha uma ação:",
            parse_mode="Markdown",
            reply_markup=build_approval_keyboard(post.id),
        )
        return str(msg.message_id)

    async def _send_full_caption(self, post: ComposedPost) -> None:
        text = "📝 Legenda completa:\n\n" + (post.caption or "(sem caption)")
        for start in range(0, len(text), TELEGRAM_MESSAGE_LIMIT):
            await self._app.bot.send_message(chat_id=self._chat_id, text=text[start:start + TELEGRAM_MESSAGE_LIMIT])

    async def await_approval(self, post_id: str, timeout: Optional[int] = None) -> ApprovalStatus:
        future = self._approval_handler.register_pending(post_id)
        try:
            return await asyncio.wait_for(future, timeout=float(timeout or self._timeout))
        except asyncio.TimeoutError:
            self._approval_handler.cancel_pending(post_id)
            logger.info("Approval timeout for post %s", post_id)
            return ApprovalStatus.EXPIRED

    async def notify(self, text: str) -> Optional[str]:
        if not self._app:
            return None
        for parse_mode in ("Markdown", None):
            try:
                msg = await asyncio.wait_for(
                    self._app.bot.send_message(chat_id=self._chat_id, text=text, parse_mode=parse_mode),
                    timeout=NOTIFY_TIMEOUT_SECONDS,
                )
                return str(msg.message_id)
            except BadRequest as exc:
                logger.warning("Telegram recusou a mensagem formatada, reenviando como texto: %s", exc)
            except Exception as exc:
                logger.error("Falha ao notificar no Telegram: %s: %s", type(exc).__name__, exc)
                return None
        return None

    async def send_creation_preview(self, chat_id: int, image_path: str, note: str) -> str:
        with open(image_path, "rb") as f:
            msg = await self._app.bot.send_photo(
                chat_id=chat_id, photo=f, caption=f"🎨 {note}", reply_markup=build_creation_keyboard()
            )
        return str(msg.message_id)

    async def send_creation_final_preview(self, post: ComposedPost) -> str:
        with Path(post.composed_image_paths[0]).open("rb") as f:
            await self._app.bot.send_photo(
                chat_id=self._chat_id, photo=f, caption=self._build_preview_caption(post), parse_mode="Markdown"
            )
        await self._send_full_caption(post)
        msg = await self._app.bot.send_message(
            chat_id=self._chat_id,
            text=f"Post `{post.id[:8]}` — escolha uma ação:",
            parse_mode="Markdown",
            reply_markup=build_creation_final_keyboard(),
        )
        return str(msg.message_id)

    async def send_mode_prompt(self, chat_id: int) -> str:
        msg = await self._app.bot.send_message(
            chat_id=chat_id,
            text="Foto limpa da peça ou banner com texto? (ou responda em texto)",
            reply_markup=build_mode_keyboard(),
        )
        return str(msg.message_id)

    @staticmethod
    def _build_preview_caption(post: ComposedPost) -> str:
        return "\n".join([
            "📸 *Preview do Post*",
            f"Template: `{post.template_id}`",
            f"Custo: ${post.total_cost_usd:.3f}",
            f"Tentativa: {post.attempt}/{post.max_attempts}",
        ])
