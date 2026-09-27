"""文本排序（collation）。只用标准库。缺陷：数字块按字符串比，重音不折叠，空行被丢。"""

import re


class CollateError(ValueError):
    """输入不合法。缺陷：不带行号。"""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def fold_text(text):
    """折叠大小写与重音。缺陷：只 casefold，没有去掉组合记号。"""
    return text.strip().casefold()


def number_chunks(text):
    """按出现顺序取数字块。缺陷：给的是字符串，不是 (数值, 位数)。"""
    return re.findall(r"[0-9]+", text)


def sort_key(line):
    """缺陷：数字块按字符串比，重音留在折叠串里。"""
    folded = re.sub(r"[0-9]+", "0", fold_text(line))
    return (folded, number_chunks(line), line)


def collate(lines):
    """缺陷：空行与纯空白行被丢掉，行的多重集合会变。"""
    kept = [line for line in lines if line.strip()]
    return sorted(kept, key=sort_key)
