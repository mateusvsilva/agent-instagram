"""Porta `Publisher` — contrato de publicação de carrossel.

Implementado hoje por `BufferPublisherService` (API oficial via Buffer). O
contrato reflete os métodos públicos que o pipeline usa: `publish_carousel` e
`set_last_post_at` (chamado em `main.py`), além de `check_session` e
`get_rate_limit_status`.
"""
from datetime import datetime
from typing import Protocol, runtime_checkable

from ..models.post import ComposedPost, PublishResult, RateLimitInfo, SessionStatus


@runtime_checkable
class Publisher(Protocol):
    async def publish_carousel(self, post: ComposedPost) -> PublishResult: ...

    async def check_session(self) -> SessionStatus: ...

    def get_rate_limit_status(self) -> RateLimitInfo: ...

    def set_last_post_at(self, dt: datetime) -> None: ...
