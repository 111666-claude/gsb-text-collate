"""文本排序（collation）。"""

from .key import CollateError, collate, fold_text, number_chunks, sort_key

__all__ = ["CollateError", "collate", "fold_text", "number_chunks", "sort_key"]
