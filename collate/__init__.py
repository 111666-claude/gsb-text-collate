"""文本排序（collation）。"""

from .key import (
    CollateError,
    collate,
    fold_text,
    key_to_jsonable,
    segments,
    sort_key,
    unique,
)

__all__ = [
    "CollateError",
    "collate",
    "fold_text",
    "key_to_jsonable",
    "segments",
    "sort_key",
    "unique",
]
