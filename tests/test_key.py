import io
import json
import random
import unittest
import unicodedata
from collections import Counter
from contextlib import redirect_stdout

from collate.cli import main
from collate.key import collate, fold_text, key_to_jsonable, segments, sort_key, unique


# ---------------------------------------------------------------------------
# 参考实现：与生产实现完全独立的「逐字符状态机分段」，用于随机对照
# ---------------------------------------------------------------------------

def reference_fold(text):
    """参考折叠：与生产代码写法不同，语义相同。"""
    stripped = text.strip()
    chars = []
    for char in unicodedata.normalize("NFKD", stripped):
        if unicodedata.combining(char) == 0:
            chars.append(char)
    return "".join(chars).casefold()


def reference_segments(line):
    """逐字符状态机：TEXT / NUMBER 两个状态，显式迁移。"""
    folded = reference_fold(line)
    result = []
    buffer = []
    state = "TEXT"
    for char in folded:
        digit = "0" <= char <= "9"
        if state == "TEXT":
            if digit:
                result.append(("t", "".join(buffer)))
                buffer = [char]
                state = "NUMBER"
            else:
                buffer.append(char)
        else:
            if digit:
                buffer.append(char)
            else:
                digits = "".join(buffer)
                result.append(("n", int(digits), len(digits)))
                buffer = [char]
                state = "TEXT"
    if state == "NUMBER":
        digits = "".join(buffer)
        result.append(("n", int(digits), len(digits)))
        buffer = []
    result.append(("t", "".join(buffer)))
    return tuple(result)


def reference_sort_key(line):
    return (reference_segments(line), line)


# ---------------------------------------------------------------------------
# 折叠
# ---------------------------------------------------------------------------

class FoldTest(unittest.TestCase):
    def test_casefold(self):
        self.assertEqual(fold_text("AbC"), "abc")

    def test_strips_around(self):
        self.assertEqual(fold_text("  a  "), "a")

    def test_accents_stripped_after_nfkd(self):
        self.assertEqual(fold_text("café"), "cafe")
        self.assertEqual(fold_text("naïve"), "naive")

    def test_accent_and_case_insensitive(self):
        self.assertEqual(fold_text("Café"), fold_text("cafe"))

    def test_fullwidth_letters_to_halfwidth(self):
        self.assertEqual(fold_text("Ａｂｃ"), "abc")
        self.assertEqual(fold_text("Ｖ"), "v")

    def test_fullwidth_digits_to_halfwidth(self):
        self.assertEqual(fold_text("１２３"), "123")
        self.assertEqual(fold_text("v１０"), "v10")

    def test_whitespace_only_folds_empty(self):
        self.assertEqual(fold_text("   \t "), "")
        self.assertEqual(fold_text(""), "")


# ---------------------------------------------------------------------------
# 分段
# ---------------------------------------------------------------------------

class SegmentTest(unittest.TestCase):
    def test_text_number_text(self):
        self.assertEqual(
            segments("file9"),
            (("t", "file"), ("n", 9, 1), ("t", "")),
        )

    def test_starts_and_ends_with_number(self):
        self.assertEqual(
            segments("9file10"),
            (("t", ""), ("n", 9, 1), ("t", "file"), ("n", 10, 2), ("t", "")),
        )

    def test_fullwidth_digits_are_numbers(self):
        self.assertEqual(segments("v１0"), (("t", "v"), ("n", 10, 2), ("t", "")))

    def test_empty_line_is_single_empty_text_segment(self):
        self.assertEqual(segments(""), (("t", ""),))
        self.assertEqual(segments("   "), (("t", ""),))

    def test_pure_text(self):
        self.assertEqual(segments("abc"), (("t", "abc"),))

    def test_no_adjacent_number_segments_without_text_gap_recorded(self):
        # "a1.2b" -> a / 1 / . / 2 / b，空文本段不丢
        self.assertEqual(
            segments("a1.2b"),
            (("t", "a"), ("n", 1, 1), ("t", "."), ("n", 2, 1), ("t", "b")),
        )


# ---------------------------------------------------------------------------
# 排序键
# ---------------------------------------------------------------------------

class KeyTest(unittest.TestCase):
    def test_key_shape(self):
        key = sort_key("file7")
        self.assertEqual(key, ((( "t", "file"), ("n", 7, 1), ("t", "")), "file7"))

    def test_same_line_same_key(self):
        self.assertEqual(sort_key("x"), sort_key("x"))

    def test_key_jsonable_structure(self):
        data = key_to_jsonable("file9")
        self.assertEqual(
            data,
            [[["t", "file"], ["n", 9, 1], ["t", ""]], "file9"],
        )
        json.dumps(data, ensure_ascii=False)


# ---------------------------------------------------------------------------
# 排序口径
# ---------------------------------------------------------------------------

class CollateTest(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(collate(["a", "B", "c"]), ["a", "B", "c"])

    def test_numeric_value_natural_order(self):
        self.assertEqual(collate(["file10", "file9"]), ["file9", "file10"])

    def test_accent_folding_order(self):
        self.assertEqual(collate(["cafz", "café"]), ["café", "cafz"])

    def test_leading_zeros_fewer_digits_first(self):
        self.assertEqual(collate(["01", "1"]), ["1", "01"])
        self.assertEqual(collate(["001", "1", "01"]), ["1", "01", "001"])

    def test_value_before_digit_count(self):
        self.assertEqual(collate(["02", "1"]), ["1", "02"])

    def test_fullwidth_digits_compare_as_numbers(self):
        self.assertEqual(collate(["v20", "v１0"]), ["v１0", "v20"])

    def test_fullwidth_letters_fold(self):
        self.assertEqual(collate(["Ａｂ", "aa"]), ["aa", "Ａｂ"])

    def test_empty_lines_kept_and_first(self):
        self.assertEqual(collate(["b", "", "a"]), ["", "a", "b"])

    def test_blank_only_lines_kept_and_first(self):
        result = collate(["b", "   ", "a"])
        self.assertEqual(result, ["   ", "a", "b"])

    def test_multiple_empty_lines(self):
        result = collate(["b", "", "a", ""])
        self.assertEqual(result, ["", "", "a", "b"])

    def test_equal_keys_keep_input_order(self):
        self.assertEqual(collate(["Ab", "ab"]), ["Ab", "ab"])

    def test_multiset_preserved(self):
        lines = ["a", "a", "file10", "", "  ", "file9", "Ab", "ab"]
        result = collate(lines)
        self.assertEqual(Counter(result), Counter(lines))
        self.assertEqual(len(result), len(lines))

    def test_empty_input(self):
        self.assertEqual(collate([]), [])

    def test_deterministic(self):
        lines = ["x10", "x9", "café", "cafz", "", "a", "Ａ"]
        self.assertEqual(collate(lines), collate(lines))


# ---------------------------------------------------------------------------
# --unique
# ---------------------------------------------------------------------------

class UniqueTest(unittest.TestCase):
    def test_drops_by_segment_equivalence_keep_first(self):
        dropped, kept = unique(["Ab", "ab", "AB"])
        self.assertEqual(dropped, 2)
        self.assertEqual(kept, ["Ab"])

    def test_leading_zeros_are_distinct_classes(self):
        dropped, kept = unique(["1", "01"])
        self.assertEqual(dropped, 0)
        self.assertEqual(kept, ["1", "01"])

    def test_fullwidth_and_halfwidth_equivalent(self):
        dropped, kept = unique(["v１0", "v10"])
        self.assertEqual(dropped, 1)
        self.assertEqual(kept, ["v１0"])

    def test_blank_lines_equivalent(self):
        dropped, kept = unique(["a", "", "   ", "b"])
        self.assertEqual(dropped, 1)
        self.assertEqual(kept, ["", "a", "b"])

    def test_classes_adjacent_and_stable_within(self):
        dropped, kept = unique(["B", "b", "a", "A", "c"])
        self.assertEqual(dropped, 2)
        # 等价类 B/b 保留输入第一条 B；A/a 保留 a；结果按段序列排序
        self.assertEqual(kept, ["a", "B", "c"])


# ---------------------------------------------------------------------------
# 随机对照：2000 组随机输入，生产实现必须与状态机参考实现逐位一致
# ---------------------------------------------------------------------------

ALPHABET = list(
    "abcABCxX0129"
    + "１２０９Ａｚ"
    + "éüïñÉç"
    + " ._-/\n\t"
) + [""]


class RandomReferenceTest(unittest.TestCase):
    def test_2000_random_groups(self):
        rng = random.Random(20260928)
        for _ in range(2000):
            count = rng.randrange(0, 25)
            lines = [
                "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 8)))
                for _ in range(count)
            ]
            for line in lines:
                self.assertEqual(segments(line), reference_segments(line), line)
                self.assertEqual(sort_key(line), reference_sort_key(line), line)
            self.assertEqual(
                collate(lines),
                sorted(lines, key=reference_sort_key),
                lines,
            )
            dropped, kept = unique(lines)
            self.assertEqual(dropped, _reference_dropped(lines), lines)
            self.assertEqual(kept, _reference_unique(lines), lines)


def _reference_dropped(lines):
    seen = set()
    dropped = 0
    for line in lines:
        seg = reference_segments(line)
        if seg in seen:
            dropped += 1
        else:
            seen.add(seg)
    return dropped


def _reference_unique(lines):
    seen = set()
    kept = []
    for line in lines:
        seg = reference_segments(line)
        if seg not in seen:
            seen.add(seg)
            kept.append(line)
    return sorted(kept, key=reference_sort_key)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class CliTest(unittest.TestCase):
    def test_sorted_output(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "b\\na"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().splitlines(), ["a", "b"])

    def test_numeric_order_cli(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "file10\\nfile9"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().splitlines(), ["file9", "file10"])

    def test_empty_lines_preserved_cli(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "b\\n\\na"])
        self.assertEqual(buffer.getvalue().splitlines(), ["", "a", "b"])

    def test_key_mode_json(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "v1", "--key"])
        self.assertEqual(code, 0)
        payload = json.loads(buffer.getvalue())
        self.assertEqual(payload, [[["t", "v"], ["n", 1, 1], ["t", ""]], "v1"])

    def test_key_mode_input_order(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "b\\na", "--key"])
        self.assertEqual(code, 0)
        payloads = [json.loads(line) for line in buffer.getvalue().splitlines()]
        self.assertEqual([item[1] for item in payloads], ["b", "a"])

    def test_unique_mode(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "Ab\\nab\\nAB", "--unique"])
        self.assertEqual(code, 0)
        lines = buffer.getvalue().splitlines()
        self.assertEqual(lines[0], "dropped=2")
        self.assertEqual(lines[1:], ["Ab"])

    def test_unique_fullwidth_drop(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "v１0\\nv10\\nv2", "--unique"])
        self.assertEqual(code, 0)
        lines = buffer.getvalue().splitlines()
        self.assertEqual(lines[0], "dropped=1")
        self.assertEqual(lines[1:], ["v2", "v１0"])

    def test_missing_input(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
