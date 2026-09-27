"""文本排序（collation）。只用标准库（unicodedata）。

口径（README 为准）：
- 折叠：每行先去首尾空白，再 NFKD 分解、丢掉组合记号（Mn 类）、casefold；
  全角字母与数字落回半角，重音与大小写不影响相对顺序。
- 分段键：一行切成「文本段 / 数字段」交替的序列，排序键是 (段序列, 原串)。
  文本段存折叠后的文本，数字段存 (数值, 位数)；相邻数字段之间的空文本段保留。
- 数字段：先比数值，数值相同再按位数少的在前（1 排在 01 前面）。
- 空行与纯空白行保留，段序列为空，排在最前。
"""

import unicodedata


class CollateError(ValueError):
    """输入不合法。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def _fold(text):
    """NFKD 分解、丢掉组合记号（Mn 类）、casefold。不去首尾空白。"""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    ).casefold()


def fold_text(text):
    """折叠一行：去首尾空白、NFKD、丢组合记号（Mn 类）、casefold。

    全角字母与数字经 NFKD 落回半角；重音与大小写被抹平。
    """
    return _fold(text.strip())


_MISSING = object()
_digit_cache = {}


def _digit_form(char):
    """单个字符折叠后若全是 ASCII 数字则返回该串，否则返回 None。

    全角数字（１２３…）等经 NFKD 落回半角后也算数字。
    """
    if "0" <= char <= "9":
        return char
    if ord(char) < 128:
        return None
    cached = _digit_cache.get(char, _MISSING)
    if cached is _MISSING:
        folded = _fold(char)
        cached = folded if folded and all("0" <= c <= "9" for c in folded) else None
        _digit_cache[char] = cached
    return cached


def segments(line):
    """把一行切成「文本段 / 数字段」交替的序列（逐字符单遍扫描，不用正则）。

    文本段是 ("t", 折叠后的文本)，数字段是 ("n", 数值, 位数)。
    相邻两个数字段之间的空文本段（例如数字间只有组合记号）保留。
    空行与纯空白行的段序列为空。
    """
    result = []
    kind = None
    buffer = []

    def flush():
        if kind == "t":
            result.append(("t", _fold("".join(buffer))))
        elif kind == "n":
            digits = "".join(buffer)
            result.append(("n", int(digits), len(digits)))

    for char in line.strip():
        digit_form = _digit_form(char)
        char_kind = "n" if digit_form is not None else "t"
        if char_kind != kind:
            flush()
            kind = char_kind
            buffer = []
        buffer.append(digit_form if char_kind == "n" else char)
    flush()
    return tuple(result)


def number_chunks(text):
    """按出现顺序取数字段，每段是 (数值, 位数)。"""
    return [segment[1:] for segment in segments(text) if segment[0] == "n"]


def sort_key(line):
    """排序键：(段序列, 原串)。--key 打印与排序复用同一个键。"""
    return (segments(line), line)


def _sort_pairs(pairs):
    """稳定排序：键相同保持输入顺序，等价类相邻。"""
    pairs.sort(key=lambda pair: pair[0])
    return [line for _, line in pairs]


def collate(lines):
    """排序。保留空行与纯空白行，行的多重集合与输入一致。"""
    pairs = [(sort_key(line), line) for line in lines]
    return _sort_pairs(pairs)


def collate_unique(lines):
    """按段序列判定等价类去重，每类只留输入顺序里的第一条。

    返回 (排序后的行, 丢掉的行数)。
    """
    pairs = [(sort_key(line), line) for line in lines]
    seen = set()
    kept = []
    dropped = 0
    for pair in pairs:
        if pair[0][0] in seen:
            dropped += 1
        else:
            seen.add(pair[0][0])
            kept.append(pair)
    return _sort_pairs(kept), dropped
