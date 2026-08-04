import asyncio
from pathlib import Path
from typing import Callable, Optional

from telegram import Bot, InputMediaPhoto, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..config import Settings
from ..handlers.approval_handler import ApprovalHandler, build_approval_keyboard
from ..handlers.creation_handler import (
    build_creation_keyboard, build_creation_final_keyboard, build_mode_keyboard,
)
from ..domain.models.enums import ApprovalStatus
from ..domain.models.post import ComposedPost
from ..utils.logger import get_logger

logger = get_logger(__name__)

# Teto de caracteres de uma mensagem de texto do Telegram (para fatiar a
# legenda completa do preview sem estourar a API).
TELEGRAM_MESSAGE_LIMIT = 4096


class TelegramBotService:
    def __init__(self, settings: Settings, approval_handler: ApprovalHandler):
        self._settings = settings
        self._approval_handler = approval_handler
        self._app: Optional[Application] = None
        self._chat_id = settings.telegram_chat_id
        self._timeout = settings.telegram_approval_timeout

    def register_commands(
        self,
        cmd_start,
        cmd_status,
        cmd_history,
        cmd_schedule,
        cmd_pause,
        cmd_resume,
        cmd_force,
        cmd_metrics,
        on_message: Optional[Callable] = None,
        cmd_criar: Optional[Callable] = None,
        cmd_comandos: Optional[Callable] = None,
        creation_handler=None,
    ) -> None:
        if not self._app:
            raise RuntimeError("Bot not initialized — call start() first")

        self._app.add_handler(CommandHandler("start", cmd_start))
        self._app.add_handler(CommandHandler("status", cmd_status))
        self._app.add_handler(CommandHandler("history", cmd_history))
        self._app.add_handler(CommandHandler("schedule", cmd_schedule))
        self._app.add_handler(CommandHandler("pause", cmd_pause))
        self._app.add_handler(CommandHandler("resume", cmd_resume))
        self._app.add_handler(CommandHandler("force", cmd_force))
        self._app.add_handler(CommandHandler("metrics", cmd_metrics))
        if cmd_comandos is not None:
            self._app.add_handler(CommandHandler("comandos", cmd_comandos))
        if cmd_criar is not None:
            self._app.add_handler(CommandHandler("criar", cmd_criar))
        # Callbacks da criação conversacional (create:*) vêm ANTES do handler de
        # aprovação, filtrados por padrão para não interceptar os botões de aprovação.
        if creation_handler is not None:
            self._app.add_handler(CallbackQueryHandler(creation_handler.handle_callback, pattern=r"^create:"))
        self._app.add_handler(CallbackQueryHandler(self._approval_handler.handle_callback))
        # Mensagens de texto livre (não-comando): pedido de assunto e respostas
        # de redo (HU-BACKEND-01 / HU-BACKEND-04). Registrado por último para não
        # interceptar os comandos acima.
        if on_message is not None:
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    async def start(self) -> None:
        self._app = (
            Application.builder()
            .token(self._settings.telegram_bot_token)
            .build()
        )
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling(drop_pending_updates=True)
        logger.info("Telegram bot started and polling.")

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()
            logger.info("Telegram bot stopped.")

    async def send_preview(self, post: ComposedPost) -> str:
        bot: Bot = self._app.bot
        paths = [Path(p) for p in post.composed_image_paths]

        if len(paths) == 1:
            with open(paths[0], "rb") as f:
                await bot.send_photo(
                    chat_id=self._chat_id,
                    photo=f,
                    caption=self._build_preview_caption(post),
                    parse_mode="Markdown",
                )
        else:
            media_group = []
            for i, path in enumerate(paths):
                with open(path, "rb") as f:
                    caption = self._build_preview_caption(post) if i == 0 else None
                    media_group.append(InputMediaPhoto(media=f.read(), caption=caption, parse_mode="Markdown" if caption else None))
            await bot.send_media_group(chat_id=self._chat_id, media=media_group)

        await self._send_full_caption(post)

        keyboard_msg = await bot.send_message(
            chat_id=self._chat_id,
            text=f"Post `{post.id[:8]}` — {len(paths)} imagem(ns). Escolha uma ação:",
            parse_mode="Markdown",
            reply_markup=build_approval_keyboard(post.id),
        )
        return str(keyboard_msg.message_id)

    async def _send_full_caption(self, post: ComposedPost) -> None:
        """Envia a legenda COMPLETA em mensagem própria, sem truncar.

        Regra de governança: o operador aprova exatamente o texto que será
        publicado — truncar o preview criaria conteúdo publicado sem revisão.
        Texto puro (sem parse_mode) para que markdown gerado pela IA não
        quebre o envio nem forje formatação.
        """
        text = "📝 Legenda completa:\n\n" + (post.caption or "(sem caption)")
        for start in range(0, len(text), TELEGRAM_MESSAGE_LIMIT):
            await self._app.bot.send_message(
                chat_id=self._chat_id,
                text=text[start:start + TELEGRAM_MESSAGE_LIMIT],
            )

    async def await_approval(self, post_id: str, timeout: int | None = None) -> ApprovalStatus:
        timeout = timeout or self._timeout
        future = self._approval_handler.register_pending(post_id)
        try:
            status = await asyncio.wait_for(future, timeout=float(timeout))
            return status
        except asyncio.TimeoutError:
            self._approval_handler.cancel_pending(post_id)
            logger.info("Approval timeout for post %s", post_id)
            return ApprovalStatus.EXPIRED

    async def notify(self, text: str) -> Optional[str]:
        """Envia uma mensagem ao operador e devolve o message_id (quando enviada).

        O id permite vincular uma pergunta a uma resposta específica via reply do
        Telegram — usado pelo fluxo de redo conversacional (HU-BACKEND-04) para
        rotear a resposta ao post certo mesmo com vários pendentes em paralelo.
        """
        if self._app:
            logger.info("DEBUG notify: ANTES do send_message (chat=%s)", self._chat_id)
            import asyncio as _asyncio
            try:
                msg = await _asyncio.wait_for(
                    self._app.bot.send_message(chat_id=self._chat_id, text=text, parse_mode="Markdown"),
                    timeout=15,
                )
            except Exception as _e:
                logger.error("DEBUG notify: send_message FALHOU/HANG: %s: %s", type(_e).__name__, _e)
                return None
            logger.info("DEBUG notify: DEPOIS do send_message id=%s", msg.message_id)
            return str(msg.message_id)
        return None

    async def send_creation_preview(self, chat_id: int, image_path: str, note: str) -> str:
        with open(image_path, "rb") as f:
            msg = await self._app.bot.send_photo(
                chat_id=chat_id, photo=f, caption=f"🎨 {note}",
                reply_markup=build_creation_keyboard(),
            )
        return str(msg.message_id)

    async def send_creation_final_preview(self, post: ComposedPost) -> str:
        path = Path(post.composed_image_paths[0])
        with open(path, "rb") as f:
            await self._app.bot.send_photo(
                chat_id=self._chat_id, photo=f,
                caption=self._build_preview_caption(post), parse_mode="Markdown",
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
            chat_id=chat_id, text="Foto limpa da peça ou banner com texto? (ou responda em texto)",
            reply_markup=build_mode_keyboard(),
        )
        return str(msg.message_id)

    def _build_preview_caption(self, post: ComposedPost) -> str:
        # Só metadados: a legenda vai COMPLETA em mensagem própria
        # (_send_full_caption) — o caption de foto tem teto de 1024 chars.
        cost_str = f"${post.total_cost_usd:.3f}"
        lines = [
            f"📸 *Preview do Post*",
            f"Template: `{post.template_id}`",
            f"Custo: {cost_str}",
            f"Tentativa: {post.attempt}/{post.max_attempts}",
        ]
        return "\n".join(lines)
