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


class DalleSize(str, Enum):
    SQUARE = "1024x1024"
    VERTICAL = "1024x1792"
    LANDSCAPE = "1792x1024"


class DalleQuality(str, Enum):
    STANDARD = "standard"
    HD = "hd"


class DalleStyle(str, Enum):
    VIVID = "vivid"
    NATURAL = "natural"
