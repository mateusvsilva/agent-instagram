from unittest.mock import MagicMock

from src.handlers.access import AccessPolicy


def allow(*ids: int) -> AccessPolicy:
    return AccessPolicy(list(ids), list(ids))


def callback_update(query, user_id=None):
    chat_id = query.message.chat_id if query.message else None
    update = MagicMock()
    update.callback_query = query
    update.effective_chat = MagicMock(id=chat_id) if query.message else None
    update.effective_user = MagicMock(id=chat_id if user_id is None else user_id)
    return update
