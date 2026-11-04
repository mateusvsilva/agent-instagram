import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from ..config import Settings
from ..domain.models.post import ComposedPost, PublishResult, RateLimitInfo, SessionStatus
from ..domain.ports import ImageUploader
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

_ORGANIZATIONS_QUERY = "query GetOrganizations { account { organizations { id name } } }"

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
        self._cooldown = timedelta(minutes=settings.post_cooldown_minutes)
        self._uploader = image_uploader
        self._last_post_at: Optional[datetime] = None

    async def _graphql(self, query: str, variables: Optional[dict] = None) -> dict:
        payload = {"query": query, **({"variables": variables} if variables else {})}
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(self._api_url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise RuntimeError(f"Buffer HTTP {resp.status_code}: {resp.text[:300]}")
        body = resp.json()
        if body.get("errors"):
            raise RuntimeError(f"Buffer GraphQL error: {body['errors']}")
        return body["data"]

    async def list_channels(self) -> list[dict]:
        data = await self._graphql(_ORGANIZATIONS_QUERY)
        channels: list[dict] = []
        for org in data["account"]["organizations"]:
            d = await self._graphql(_CHANNELS_BY_ORG, {"orgId": org["id"]})
            channels += [{**ch, "organization": org["name"]} for ch in d["channels"]]
        return channels

    async def _resolve_url(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        if self._uploader is None:
            raise RuntimeError(
                "Imagem local sem uploader configurado — o Buffer exige URL pública. "
                "Configure um image uploader (ex.: Cloudinary) ou passe URLs."
            )
        return await self._uploader.upload(path)

    def _build_mutation(self, caption: str, urls: list[str]) -> str:
        mode = self._settings.buffer_scheduling_mode
        extra = ""
        if mode == "customScheduled":
            due = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
            extra = f"\n    dueAt: {json.dumps(due)},"
        return _CREATE_POST_TEMPLATE.format(
            text=json.dumps(caption),
            channel_id=json.dumps(self._channel_id),
            mode=mode,
            extra=extra,
            ig_type=self._settings.buffer_instagram_post_type,
            assets=", ".join("{ image: { url: %s } }" % json.dumps(u) for u in urls),
        )

    async def publish_carousel(self, post: ComposedPost) -> PublishResult:
        if not self._api_key or not self._channel_id:
            return PublishResult(success=False, error="BUFFER_API_KEY ou BUFFER_CHANNEL_ID não configurados no .env")

        rate_info = self.get_rate_limit_status()
        if not rate_info.can_post:
            msg = f"Rate limit: {rate_info.minutes_remaining:.1f} minutos restantes"
            logger.warning(msg)
            return PublishResult(success=False, error=msg)

        if not post.composed_image_paths:
            return PublishResult(success=False, error="Nenhuma imagem para publicar")

        try:
            urls = [await self._resolve_url(p) for p in post.composed_image_paths]
            data = await self._graphql(self._build_mutation(post.caption, urls))
        except Exception as exc:
            logger.error("Falha ao publicar no Buffer: %s", exc)
            return PublishResult(success=False, error=str(exc))

        result = data.get("createPost") or {}
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
            await self._graphql(_ORGANIZATIONS_QUERY)
            return SessionStatus(logged_in=True)
        except Exception:
            return SessionStatus(logged_in=False)

    def get_rate_limit_status(self) -> RateLimitInfo:
        cooldown_minutes = int(self._cooldown.total_seconds() // 60)
        if not self._last_post_at:
            return RateLimitInfo(can_post=True, cooldown_minutes=cooldown_minutes)
        remaining = self._cooldown - (datetime.now(timezone.utc) - self._last_post_at)
        return RateLimitInfo(
            can_post=remaining <= timedelta(0),
            last_post_at=self._last_post_at,
            cooldown_minutes=cooldown_minutes,
            minutes_remaining=max(0.0, round(remaining.total_seconds() / 60, 1)),
        )

    def set_last_post_at(self, dt: datetime) -> None:
        self._last_post_at = dt
