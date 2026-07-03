"""Publica posts via API GraphQL oficial do Buffer.

O Buffer publica pela API oficial do Instagram (Graph API da Meta), então não há
login com senha nem "challenge".

IMPORTANTE: o Buffer NÃO hospeda imagens — ele só aceita uma URL pública. Como
o agente gera imagens locais, é preciso um "image uploader" que sobe o arquivo
para algum lugar público e devolve a URL. Imagens cujo caminho já comece com
http(s) são usadas diretamente.
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx

from ..config import Settings
from ..domain.ports import ImageUploader
from ..domain.models.post import ComposedPost, PublishResult, RateLimitInfo, SessionStatus
from ..utils.logger import get_logger

logger = get_logger(__name__)

_CREATE_POST_TEMPLATE = """
mutation {{
  createPost(input: {{
    text: {text},
    channelId: {channel_id},
    schedulingType: automatic,
    mode: {mode}{extra}
    metadata: {{ instagram: {{ type: {ig_type}, shouldShareToFeed: true }} }}
    assets: [{assets}]
  }}) {{
    __typename
    ... on PostActionSuccess {{ post {{ id }} }}
    ... on MutationError {{ message }}
  }}
}}
"""

_CHANNELS_QUERY = """
query GetOrganizations { account { organizations { id name } } }
"""

_CHANNELS_BY_ORG = """
query GetChannels($orgId: OrganizationId!) {
  channels(input: { organizationId: $orgId }) { id name service }
}
"""


class BufferPublisherService:
    def __init__(self, settings: Settings, image_uploader: Optional[ImageUploader] = None):
        self._settings = settings
        self._api_url = settings.buffer_api_url.rstrip("/")
        self._api_key = settings.buffer_api_key
        self._channel_id = settings.buffer_channel_id
        self._mode = settings.buffer_scheduling_mode
        self._cooldown_minutes = settings.post_cooldown_minutes
        self._uploader = image_uploader
        self._last_post_at: Optional[datetime] = None

    @property
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    async def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._api_url, headers=self._headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Buffer HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        if body.get("errors"):
            raise RuntimeError(f"Buffer GraphQL error: {body['errors']}")
        return body["data"]

    async def list_channels(self) -> list[dict]:
        """Lista os canais conectados (para descobrir o BUFFER_CHANNEL_ID)."""
        data = await self._graphql(_CHANNELS_QUERY)
        orgs = data["account"]["organizations"]
        channels: list[dict] = []
        for org in orgs:
            d = await self._graphql(_CHANNELS_BY_ORG, {"orgId": org["id"]})
            for ch in d["channels"]:
                channels.append({**ch, "organization": org["name"]})
        return channels

    async def _resolve_url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if self._uploader is None:
            raise RuntimeError(
                "Imagem local sem uploader configurado — o Buffer exige URL pública. "
                "Configure um image uploader (ex.: Cloudinary) ou passe URLs."
            )
        return await self._uploader.upload(path)

    async def publish_carousel(self, post: ComposedPost) -> PublishResult:
        if not self._api_key or not self._channel_id:
            return PublishResult(
                success=False,
                error="BUFFER_API_KEY ou BUFFER_CHANNEL_ID não configurados no .env",
            )

        rate_info = self.get_rate_limit_status()
        if not rate_info.can_post:
            msg = f"Rate limit: {rate_info.minutes_remaining:.1f} minutos restantes"
            logger.warning(msg)
            return PublishResult(success=False, error=msg)

        try:
            urls = [await self._resolve_url(p) for p in post.composed_image_paths]
        except Exception as exc:
            logger.error("Falha ao hospedar imagens: %s", exc)
            return PublishResult(success=False, error=str(exc))

        if not urls:
            return PublishResult(success=False, error="Nenhuma imagem para publicar")

        assets = ", ".join("{ image: { url: %s } }" % json.dumps(u) for u in urls)
        extra = ""
        mode = self._mode
        if mode == "customScheduled":
            due = (datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            extra = f"\n    dueAt: {json.dumps(due)},"
        query = _CREATE_POST_TEMPLATE.format(
            text=json.dumps(post.caption),
            channel_id=json.dumps(self._channel_id),
            mode=mode,
            extra=extra,
            ig_type=self._settings.buffer_instagram_post_type,
            assets=assets,
        )

        try:
            data = await self._graphql(query)
        except Exception as exc:
            logger.error("Falha ao publicar no Buffer: %s", exc)
            return PublishResult(success=False, error=str(exc))

        result = data.get("createPost", {})
        if result.get("__typename") == "PostActionSuccess":
            self._last_post_at = datetime.now(timezone.utc)
            media_id = str(result["post"]["id"])
            logger.info("Post %s enviado ao Buffer → post_id=%s", post.id, media_id)
            return PublishResult(success=True, media_id=media_id)

        error_msg = result.get("message", "Erro desconhecido do Buffer")
        logger.error("Buffer recusou o post %s: %s", post.id, error_msg)
        return PublishResult(success=False, error=error_msg)

    async def check_session(self) -> SessionStatus:
        try:
            await self._graphql(_CHANNELS_QUERY)
            return SessionStatus(logged_in=True, session_file_exists=True)
        except Exception:
            return SessionStatus(logged_in=False, session_file_exists=False)

    def get_rate_limit_status(self) -> RateLimitInfo:
        if not self._last_post_at:
            return RateLimitInfo(can_post=True, cooldown_minutes=self._cooldown_minutes)
        elapsed = datetime.now(timezone.utc) - self._last_post_at
        cooldown = timedelta(minutes=self._cooldown_minutes)
        if elapsed >= cooldown:
            return RateLimitInfo(
                can_post=True,
                last_post_at=self._last_post_at,
                cooldown_minutes=self._cooldown_minutes,
            )
        remaining = (cooldown - elapsed).total_seconds() / 60
        return RateLimitInfo(
            can_post=False,
            last_post_at=self._last_post_at,
            cooldown_minutes=self._cooldown_minutes,
            minutes_remaining=round(remaining, 1),
        )

    def set_last_post_at(self, dt: datetime) -> None:
        self._last_post_at = dt
