import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import aiosqlite

from ..domain.models.enums import ApprovalStatus, PostStatus
from ..domain.models.post import GeneratedImage, Post, Metrics
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

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id TEXT,
    error TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


class StorageService:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    async def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self._db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        logger.info("Database initialized at %s", self._db_path)

    async def save_post(self, post: Post) -> str:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO posts
                (id, template_id, schedule_id, caption, hashtags, status, approval_status,
                 attempt, max_attempts, total_cost_usd, telegram_message_id, instagram_media_id,
                 created_at, approved_at, published_at, error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    post.id,
                    post.template_id,
                    post.schedule_id,
                    post.caption,
                    json.dumps(post.hashtags),
                    post.status.value,
                    post.approval_status.value,
                    post.attempt,
                    post.max_attempts,
                    post.total_cost_usd,
                    post.telegram_message_id,
                    post.instagram_media_id,
                    post.created_at.isoformat(),
                    post.approved_at.isoformat() if post.approved_at else None,
                    post.published_at.isoformat() if post.published_at else None,
                    post.error,
                ),
            )
            for img in post.images:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO generated_images
                    (id, post_id, file_path, prompt_used, cost_usd, created_at, dalle_params)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        img.id,
                        img.post_id,
                        img.file_path,
                        img.prompt_used,
                        img.cost_usd,
                        img.created_at.isoformat(),
                        json.dumps(img.dalle_params),
                    ),
                )
            await db.commit()
        return post.id

    async def get_post(self, post_id: str) -> Optional[Post]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM posts WHERE id = ?", (post_id,)) as cursor:
                row = await cursor.fetchone()
            if not row:
                return None
            images = await self._load_images(db, post_id)
            return self._row_to_post(row, images)

    async def update_status(
        self,
        post_id: str,
        status: PostStatus | None = None,
        approval_status: ApprovalStatus | None = None,
        **kwargs,
    ) -> None:
        fields: list[str] = []
        values: list = []
        if status is not None:
            fields.append("status = ?")
            values.append(status.value)
        if approval_status is not None:
            fields.append("approval_status = ?")
            values.append(approval_status.value)
        for key, val in kwargs.items():
            fields.append(f"{key} = ?")
            values.append(val.isoformat() if isinstance(val, datetime) else val)
        if not fields:
            return
        values.append(post_id)
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(f"UPDATE posts SET {', '.join(fields)} WHERE id = ?", values)
            await db.commit()

    async def get_history(self, limit: int = 50) -> list[Post]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
            result = []
            for row in rows:
                images = await self._load_images(db, row["id"])
                result.append(self._row_to_post(row, images))
            return result

    async def get_pending_posts(self) -> list[Post]:
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM posts WHERE approval_status = 'pending' ORDER BY created_at ASC"
            ) as cursor:
                rows = await cursor.fetchall()
            result = []
            for row in rows:
                images = await self._load_images(db, row["id"])
                result.append(self._row_to_post(row, images))
            return result

    async def get_metrics(self, period: str = "30d") -> Metrics:
        days = int(period.rstrip("d")) if period.endswith("d") else 30
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM posts WHERE created_at >= ?", (since,)
            ) as cur:
                total = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COUNT(*) FROM posts WHERE status = 'published' AND created_at >= ?",
                (since,),
            ) as cur:
                published = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COUNT(*) FROM posts WHERE approval_status = 'rejected' AND created_at >= ?",
                (since,),
            ) as cur:
                rejected = (await cur.fetchone())[0]
            async with db.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM posts WHERE created_at >= ?",
                (since,),
            ) as cur:
                total_cost = (await cur.fetchone())[0]

        approval_rate = published / total if total else 0.0
        avg_cost = total_cost / total if total else 0.0

        return Metrics(
            total_posts=total,
            published=published,
            rejected=rejected,
            approval_rate=round(approval_rate, 4),
            total_cost_usd=round(total_cost, 4),
            avg_cost_per_post=round(avg_cost, 4),
            period=period,
        )

    async def save_error(self, post_id: str, error: str) -> None:
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                "INSERT INTO errors (post_id, error, created_at) VALUES (?,?,?)",
                (post_id, error, _now_iso()),
            )
            if post_id:
                await db.execute(
                    "UPDATE posts SET error = ? WHERE id = ?", (error[:1000], post_id)
                )
            await db.commit()

    async def get_last_published_at(self) -> Optional[datetime]:
        async with aiosqlite.connect(self._db_path) as db:
            async with db.execute(
                "SELECT published_at FROM posts WHERE status = 'published' ORDER BY published_at DESC LIMIT 1"
            ) as cur:
                row = await cur.fetchone()
        return _parse_dt(row[0]) if row else None

    async def _load_images(self, db: aiosqlite.Connection, post_id: str) -> list[GeneratedImage]:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM generated_images WHERE post_id = ?", (post_id,)
        ) as cursor:
            rows = await cursor.fetchall()
        images = []
        for row in rows:
            images.append(
                GeneratedImage(
                    id=row["id"],
                    post_id=row["post_id"],
                    file_path=row["file_path"],
                    prompt_used=row["prompt_used"],
                    cost_usd=row["cost_usd"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    dalle_params=json.loads(row["dalle_params"]),
                )
            )
        return images

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
