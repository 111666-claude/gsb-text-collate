"""文本排序（collation）。"""

from .key import (
    CollateError,
    collate,
    collate_unique,
    fold_text,
    number_chunks,
    segments,
    sort_key,
)

__all__ = [
    "CollateError",
    "collate",
    "collate_unique",
    "fold_text",
    "number_chunks",
    "segments",
    "sort_key",
]
