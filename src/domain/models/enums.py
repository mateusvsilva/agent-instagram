from enum import Enum


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REDO = "redo"
    EXPIRED = "expired"
    PUBLISHED = "published"
    FAILED = "failed"


class PostStatus(str, Enum):
    GENERATING = "generating"
    COMPOSING = "composing"
    AWAITING_APPROVAL = "awaiting_approval"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"
    DISCARDED = "discarded"


class TemplateSelection(str, Enum):
    RANDOM = "random"
    SEQUENTIAL = "sequential"
    ROUND_ROBIN = "round_robin"
