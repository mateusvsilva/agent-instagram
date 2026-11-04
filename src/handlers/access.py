from telegram import Update


class AccessPolicy:
    def __init__(self, chat_ids: list[int], user_ids: list[int]):
        self._chat_ids = set(chat_ids)
        self._user_ids = set(user_ids)

    def allows(self, update: Update) -> bool:
        chat, user = update.effective_chat, update.effective_user
        return chat is not None and user is not None and chat.id in self._chat_ids and user.id in self._user_ids
