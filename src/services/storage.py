import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

from ..domain.models.enums import ApprovalStatus, PostStatus
from ..domain.models.post import GeneratedImage, Metrics, Post
from ..utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    template_id TEXT NOT NULL,
    schedule_id TEXT,
    caption TEXT DEFAULT '',
    hashtags TEXT DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'generating',
    approval_status TEXT NOT NULL DEFAULT 'pending',
    attempt INTEGER DEFAULT 1,
    max_attempts INTEGER DEFAULT 3,
    total_cost_usd REAL DEFAULT 0.0,
    telegram_message_id TEXT,
    instagram_media_id TEXT,
    created_at TEXT NOT NULL,
    approved_at TEXT,
    published_at TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS generated_images (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    prompt_used TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    created_at TEXT NOT NULL,
    dalle_params TEXT DEFAULT '{}',
    FOREIGN KEY (post_id) REFERENCES posts(id)
);

CREATE TABLE IF NOT EXISTS costs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    amount_usd REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_costs_created_at ON costs(created_at);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

_UPDATABLE_COLUMNS = {"telegram_message_id", "instagram_media_id", "approved_at", "published_at", "error"}
_MAX_ERROR_CHARS = 1000


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


class StorageService:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    def _connect(self) -> aiosqlite.Connection:
        return aiosqlite.connect(self._db_path)

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._connect() as db:
            await db.executescript(SCHEMA)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def save_post(self, post: Post) -> str:
        async with self._connect() as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO posts
                (id, template_id, schedule_id, caption, hashtags, status, approval_status,
                 attempt, max_attempts, total_cost_usd, telegram_message_id, instagram_media_id,
                 created_at, approved_at, published_at, error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    post.id, post.template_id, post.schedule_id, post.caption, json.dumps(post.hashtags),
                    post.status.value, post.approval_status.value, post.attempt, post.max_attempts,
                    post.total_cost_usd, post.telegram_message_id, post.instagram_media_id,
                    post.created_at.isoformat(), _iso(post.approved_at), _iso(post.published_at), post.error,
                ),
            )
            await db.executemany(
                """
                INSERT OR REPLACE INTO generated_images
                (id, post_id, file_path, prompt_used, cost_usd, created_at, dalle_params)
                VALUES (?,?,?,?,?,?,?)
                """,
                [
                    (img.id, img.post_id, img.file_path, img.prompt_used, img.cost_usd,
                     img.created_at.isoformat(), json.dumps(img.dalle_params))
                    for img in post.images
                ],
            )
            await db.commit()
        return post.id

    async def get_post(self, post_id: str) -> Optional[Post]:
        posts = await self._fetch_posts("SELECT * FROM posts WHERE id = ?", (post_id,))
        return posts[0] if posts else None

    async def update_status(
        self,
        post_id: str,
        status: Optional[PostStatus] = None,
        approval_status: Optional[ApprovalStatus] = None,
        **columns,
    ) -> None:
        unknown = columns.keys() - _UPDATABLE_COLUMNS
        if unknown:
            raise ValueError(f"Colunas não atualizáveis: {sorted(unknown)}")
        if status is not None:
            columns["status"] = status.value
        if approval_status is not None:
            columns["approval_status"] = approval_status.value
        if not columns:
            return
        assignments = ", ".join(f"{name} = ?" for name in columns)
        values = [_iso(v) if isinstance(v, datetime) else v for v in columns.values()]
        async with self._connect() as db:
            await db.execute(f"UPDATE posts SET {assignments} WHERE id = ?", (*values, post_id))
            await db.commit()

    async def expire_pending(self) -> int:
        async with self._connect() as db:
            cursor = await db.execute(
                "UPDATE posts SET approval_status = ?, status = ? WHERE approval_status = ?",
                (ApprovalStatus.EXPIRED.value, PostStatus.DISCARDED.value, ApprovalStatus.PENDING.value),
            )
            await db.commit()
            return cursor.rowcount

    async def get_history(self, limit: int = 50) -> list[Post]:
        return await self._fetch_posts("SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,))

    async def get_pending_posts(self) -> list[Post]:
        return await self._fetch_posts(
            "SELECT * FROM posts WHERE approval_status = ? ORDER BY created_at ASC",
            (ApprovalStatus.PENDING.value,),
        )

    async def record_cost(self, post_id: str, amount: float) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO costs (post_id, amount_usd, created_at) VALUES (?,?,?)",
                (post_id, amount, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()

    async def get_cost_since(self, since: datetime) -> float:
        async with self._connect() as db:
            async with db.execute(
                "SELECT COALESCE(SUM(amount_usd), 0) FROM costs WHERE created_at >= ?", (since.isoformat(),)
            ) as cur:
                return (await cur.fetchone())[0]

    async def get_metrics(self, period: str = "30d") -> Metrics:
        days = int(period.rstrip("d")) if period.endswith("d") else 30
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        async with self._connect() as db:
            async with db.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(status = 'published'), 0),
                       COALESCE(SUM(approval_status = 'rejected'), 0),
                       COALESCE(SUM(total_cost_usd), 0)
                FROM posts WHERE created_at >= ?
                """,
                (since,),
            ) as cur:
                total, published, rejected, total_cost = await cur.fetchone()
        return Metrics(
            total_posts=total,
            published=published,
            rejected=rejected,
            approval_rate=round(published / total, 4) if total else 0.0,
            total_cost_usd=round(total_cost, 4),
            avg_cost_per_post=round(total_cost / total, 4) if total else 0.0,
            period=period,
        )

    async def save_error(self, post_id: str, error: str) -> None:
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO errors (post_id, error, created_at) VALUES (?,?,?)",
                (post_id, error, datetime.now(timezone.utc).isoformat()),
            )
            if post_id:
                await db.execute("UPDATE posts SET error = ? WHERE id = ?", (error[:_MAX_ERROR_CHARS], post_id))
            await db.commit()

    async def get_last_published_at(self) -> Optional[datetime]:
        async with self._connect() as db:
            async with db.execute(
                "SELECT published_at FROM posts WHERE status = 'published' ORDER BY published_at DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
        return _parse_dt(row[0]) if row else None

    async def _fetch_posts(self, sql: str, params: tuple) -> list[Post]:
        async with self._connect() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql, params) as cur:
                rows = await cur.fetchall()
            return [self._row_to_post(row, await self._load_images(db, row["id"])) for row in rows]

    @staticmethod
    async def _load_images(db: aiosqlite.Connection, post_id: str) -> list[GeneratedImage]:
        async with db.execute("SELECT * FROM generated_images WHERE post_id = ?", (post_id,)) as cur:
            rows = await cur.fetchall()
        return [
            GeneratedImage(
                id=row["id"],
                post_id=row["post_id"],
                file_path=row["file_path"],
                prompt_used=row["prompt_used"],
                cost_usd=row["cost_usd"],
                created_at=datetime.fromisoformat(row["created_at"]),
                dalle_params=json.loads(row["dalle_params"]),
            )
            for row in rows
        ]

    @staticmethod
    def _row_to_post(row: aiosqlite.Row, images: list[GeneratedImage]) -> Post:
        return Post(
            id=row["id"],
            template_id=row["template_id"],
            schedule_id=row["schedule_id"],
            images=images,
            caption=row["caption"] or "",
            hashtags=json.loads(row["hashtags"] or "[]"),
            status=PostStatus(row["status"]),
            approval_status=ApprovalStatus(row["approval_status"]),
            attempt=row["attempt"],
            max_attempts=row["max_attempts"],
            total_cost_usd=row["total_cost_usd"],
            telegram_message_id=row["telegram_message_id"],
            instagram_media_id=row["instagram_media_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            approved_at=_parse_dt(row["approved_at"]),
            published_at=_parse_dt(row["published_at"]),
            error=row["error"],
        )
