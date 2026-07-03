"""Estado conversacional para mensagens de texto livre do operador.

Cobre dois fluxos novos:
- HU-BACKEND-01: "poste sobre X" — mensagem livre que vira um pedido de assunto.
- HU-BACKEND-04: ao clicar 🔄, o agente PERGUNTA o que mudar e aguarda a resposta
  do operador (texto livre) antes de regenerar.

A mecânica é a mesma do `ApprovalHandler`: futures registradas por chave e
resolvidas quando a resposta chega. O roteamento da resposta ao post correto
usa o reply nativo do Telegram (a pergunta tem um message_id; a resposta que
faz reply a ela carrega `reply_to_message`), de forma que vários posts possam
aguardar ajuste em paralelo (ex.: post agendado + `/force`) sem que a resposta
de um vá para o outro. Quando há exatamente uma pergunta pendente, uma resposta
sem reply explícito ainda é aceita por conveniência; com várias pendentes e sem
reply, a mensagem não é roteada às cegas — o operador é orientado a responder à
pergunta específica.
"""
import asyncio
from typing import Awaitable, Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from ..utils.logger import get_logger

logger = get_logger(__name__)

# Recebe o assunto livre digitado pelo operador e dispara o pipeline.
SubjectCallback = Callable[[str], Awaitable[None]]


class ConversationHandler:
    def __init__(self, allowed_chat_ids: list[int], subject_callback: SubjectCallback, creation_service=None):
        self._allowed_chat_ids = allowed_chat_ids
        self._subject_callback = subject_callback
        self._creation_service = creation_service
        # Futures aguardando a resposta de uma pergunta de redo, por post_id.
        self._pending_answers: dict[str, asyncio.Future] = {}
        # message_id da pergunta de redo -> post_id, para rotear a resposta certa
        # quando o operador faz reply nela (suporta vários pendentes em paralelo).
        self._question_to_post: dict[str, str] = {}

    def register_answer(self, post_id: str) -> asyncio.Future:
        """Registra a espera pela resposta do operador a uma pergunta de redo."""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_answers[post_id] = future
        return future

    def link_question(self, post_id: str, question_message_id: Optional[str]) -> None:
        """Vincula o message_id da pergunta enviada ao post, para roteamento por reply."""
        if question_message_id is not None:
            self._question_to_post[question_message_id] = post_id

    def cancel_answer(self, post_id: str) -> None:
        future = self._pending_answers.pop(post_id, None)
        if future and not future.done():
            future.cancel()
        self._forget_question(post_id)

    def _forget_question(self, post_id: str) -> None:
        for msg_id, pid in list(self._question_to_post.items()):
            if pid == post_id:
                del self._question_to_post[msg_id]

    @property
    def _has_pending_answer(self) -> bool:
        return any(not f.done() for f in self._pending_answers.values())

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat is None or update.effective_chat.id not in self._allowed_chat_ids:
            return  # mesma regra de autorização dos demais comandos
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        if not text:
            return

        # Sessão de criação ativa tem prioridade: o texto livre é o brief/feedback.
        if self._creation_service is not None and self._creation_service.has_active_session(update.effective_chat.id):
            await self._creation_service.handle_text(update.effective_chat.id, text)
            return

        # 1) Resposta a uma pergunta de redo? Resolve o post-alvo sem adivinhar.
        post_id = self._resolve_answer_target(update)
        if post_id is not None:
            future = self._pending_answers.pop(post_id, None)
            self._forget_question(post_id)
            if future and not future.done():
                future.set_result(text)
                logger.info("Resposta de redo recebida para post %s: %.60s", post_id, text)
            return

        # 1b) Há perguntas pendentes, mas a mensagem não dá para roteá-la com
        # segurança (várias abertas e sem reply explícito). Não roteia às cegas
        # nem trata como novo assunto — orienta o operador.
        if self._has_pending_answer:
            await update.message.reply_text(
                "❓ Há mais de um post aguardando ajuste. Responda *à pergunta* do post "
                "específico usando o recurso de responder (reply) do Telegram.",
                parse_mode="Markdown",
            )
            return

        # 2) Caso contrário, é um pedido de assunto livre ("poste sobre X").
        subject = self._extract_subject(text)
        if not subject:
            return
        logger.info("Pedido de assunto via Telegram: %.80s", subject)
        await update.message.reply_text(f"📝 Entendi! Vou gerar um post sobre: *{subject}*", parse_mode="Markdown")
        await self._subject_callback(subject)

    def _resolve_answer_target(self, update: Update) -> Optional[str]:
        """Decide a qual post pendente esta mensagem responde.

        Prioriza o reply explícito (message_id da pergunta). Sem reply, só aceita
        quando há exatamente uma pergunta pendente — evita o misroteamento que
        ocorria ao escolher cegamente a "mais antiga".
        """
        reply = update.message.reply_to_message if update.message else None
        if reply is not None:
            target = self._question_to_post.get(str(reply.message_id))
            if target is not None and not self._is_resolved(target):
                return target
        open_posts = [pid for pid, fut in self._pending_answers.items() if not fut.done()]
        if len(open_posts) == 1:
            return open_posts[0]
        return None

    def _is_resolved(self, post_id: str) -> bool:
        future = self._pending_answers.get(post_id)
        return future is None or future.done()

    @staticmethod
    def _extract_subject(text: str) -> str:
        """Extrai o assunto de frases como "poste sobre X" / "posta sobre X".

        Mensagens que claramente não pedem um post (muito curtas) são ignoradas.
        """
        lowered = text.lower()
        for prefix in ("poste sobre ", "posta sobre ", "post sobre ", "poste ", "posta "):
            if lowered.startswith(prefix):
                return text[len(prefix):].strip()
        # Sem prefixo reconhecido: trata a mensagem inteira como assunto, desde
        # que tenha conteúdo mínimo (evita reagir a "oi", "ok", etc.).
        return text if len(text) >= 4 else ""
