"""文本排序（collation）。只用标准库（unicodedata）。

口径：
- 折叠：去首尾空白 -> NFKD 分解 -> 丢组合记号（Mn 类）-> casefold。
  全角字母与数字经 NFKD 落回半角；重音与大小写不影响相对顺序。
- 分段键：一行切成「文本段 / 数字段」交替的序列（文本段开头与结尾，可为空），
  排序键是 (段序列, 原串)。文本段存折叠后的文本，数字段存 (数值, 位数)。
- 数字段：先比数值，数值相同再按位数少的在前（1 排在 01 前面）。
- 逐字符单遍分段，不用正则，不把整行 JSON 化当键。
"""

import unicodedata


class CollateError(ValueError):
    """输入不合法。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def fold_text(text):
    """去首尾空白，NFKD 分解，丢掉组合记号（Mn 类），再 casefold。"""
    text = text.strip()
    decomposed = unicodedata.normalize("NFKD", text)
    folded = "".join(
        char for char in decomposed if unicodedata.category(char) != "Mn"
    )
    return folded.casefold()


def _is_digit(char):
    return "0" <= char <= "9"


def segments(line):
    """把一行切成「文本段 / 数字段」交替的段序列。

    文本段是 ("t", 折叠后的文本)，数字段是 ("n", 数值, 位数)。
    序列以文本段开头与结尾，相邻数字段之间的空文本段保留。
    """
    folded = fold_text(line)
    result = []
    text_chars = []
    index = 0
    length = len(folded)
    while index < length:
        char = folded[index]
        if _is_digit(char):
            end = index + 1
            while end < length and _is_digit(folded[end]):
                end += 1
            digits = folded[index:end]
            result.append(("t", "".join(text_chars)))
            text_chars = []
            result.append(("n", int(digits), end - index))
            index = end
        else:
            text_chars.append(char)
            index += 1
    result.append(("t", "".join(text_chars)))
    return tuple(result)


def sort_key(line):
    """排序键：(段序列, 原串)。段序列相同再按原串比，键相同保持稳定。"""
    return (segments(line), line)


def key_to_jsonable(line):
    """把 sort_key 的结果转成可 JSON 化的结构，供 --key 使用。"""
    segment_sequence, original = sort_key(line)
    return [[list(segment) for segment in segment_sequence], original]


def collate(lines):
    """稳定排序；保留空行、纯空白行与重复行，行的多重集合不变。"""
    return sorted(lines, key=sort_key)


def unique(lines):
    """按段序列判定等价类，每类只留输入顺序里的第一条。

    返回 (丢掉的行数, 排序后的行)。键只生成一遍。
    """
    seen = set()
    keyed = []
    dropped = 0
    for line in lines:
        key = sort_key(line)
        if key[0] in seen:
            dropped += 1
            continue
        seen.add(key[0])
        keyed.append((key, line))
    keyed.sort(key=lambda pair: pair[0])
    return dropped, [line for _, line in keyed]
