import io
import json
import random
import string
import unicodedata
import unittest
from collections import Counter
from contextlib import redirect_stdout

from collate.cli import main
from collate.key import (
    collate,
    collate_unique,
    fold_text,
    number_chunks,
    segments,
    sort_key,
)


def reference_fold_char(char):
    """参考实现：单字符折叠（NFKD、丢 Mn、casefold）。"""
    decomposed = unicodedata.normalize("NFKD", char)
    return "".join(
        c for c in decomposed if unicodedata.category(c) != "Mn"
    ).casefold()


def reference_segments(line):
    """参考实现：逐字符状态机分段，与主实现相互独立。"""
    result = []
    state = None
    buffer = []

    def emit():
        text = "".join(buffer)
        if state == "num":
            result.append(("n", int(text), len(text)))
        else:
            result.append(("t", text))

    for char in line.strip():
        folded = reference_fold_char(char)
        is_digit = bool(folded) and all("0" <= c <= "9" for c in folded)
        new_state = "num" if is_digit else "text"
        if state is not None and new_state != state:
            emit()
            buffer = []
        state = new_state
        buffer.append(folded)
    if state is not None:
        emit()
    return tuple(result)


def reference_key(line):
    return (reference_segments(line), line)


class FoldTest(unittest.TestCase):
    def test_casefold(self):
        self.assertEqual(fold_text("AbC"), "abc")

    def test_strips_around(self):
        self.assertEqual(fold_text("  a  "), "a")

    def test_accent_folds(self):
        self.assertEqual(fold_text("café"), "cafe")

    def test_combining_marks_dropped(self):
        self.assertEqual(fold_text("é"), "e")

    def test_fullwidth_folds_to_halfwidth(self):
        self.assertEqual(fold_text("ＡＢＣ１２３"), "abc123")

    def test_sharp_s_casefolds(self):
        self.assertEqual(fold_text("Straße"), "strasse")


class SegmentTest(unittest.TestCase):
    def test_alternating_text_and_number(self):
        self.assertEqual(segments("file9"), (("t", "file"), ("n", 9, 1)))

    def test_text_number_text(self):
        self.assertEqual(
            segments("v1.20beta"),
            (("t", "v"), ("n", 1, 1), ("t", "."), ("n", 20, 2), ("t", "beta")),
        )

    def test_fullwidth_digits_are_number_segment(self):
        self.assertEqual(segments("v１0"), (("t", "v"), ("n", 10, 2)))

    def test_empty_text_between_numbers_kept(self):
        self.assertEqual(
            segments("1́2"), (("n", 1, 1), ("t", ""), ("n", 2, 1))
        )

    def test_leading_zeros_give_width(self):
        self.assertEqual(segments("01"), (("n", 1, 2),))

    def test_blank_line_has_empty_segments(self):
        self.assertEqual(segments(""), ())
        self.assertEqual(segments("   "), ())

    def test_no_regex_used(self):
        import collate.key as key_module

        with open(key_module.__file__, encoding="utf-8") as handle:
            self.assertNotIn("re.", handle.read())


class ChunkTest(unittest.TestCase):
    def test_two_digit_runs(self):
        self.assertEqual(len(number_chunks("v1.20beta")), 2)

    def test_no_digits(self):
        self.assertEqual(number_chunks("abc"), [])

    def test_value_and_width(self):
        self.assertEqual(number_chunks("a01b１0"), [(1, 2), (10, 2)])


class KeyTest(unittest.TestCase):
    def test_key_shape(self):
        self.assertEqual(
            sort_key("file7"), ((("t", "file"), ("n", 7, 1)), "file7")
        )

    def test_key_is_json_serializable(self):
        self.assertEqual(
            json.loads(json.dumps(sort_key("v1"), ensure_ascii=False)),
            [[["t", "v"], ["n", 1, 1]], "v1"],
        )

    def test_same_line_same_key(self):
        self.assertEqual(sort_key("x"), sort_key("x"))

    def test_numeric_segments_compare_by_value(self):
        self.assertLess(sort_key("file9"), sort_key("file10"))

    def test_equal_value_fewer_digits_first(self):
        self.assertLess(sort_key("1"), sort_key("01"))


class CollateTest(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(collate(["a", "B", "c"]), ["a", "B", "c"])

    def test_equal_keys_keep_input_order(self):
        self.assertEqual(collate(["Ab", "ab"]), ["Ab", "ab"])

    def test_empty_input(self):
        self.assertEqual(collate([]), [])

    def test_file9_before_file10(self):
        self.assertEqual(collate(["file10", "file9"]), ["file9", "file10"])

    def test_accent_order(self):
        self.assertEqual(collate(["cafz", "café"]), ["café", "cafz"])

    def test_fullwidth_digit_order(self):
        self.assertEqual(collate(["v20", "v１0"]), ["v１0", "v20"])

    def test_leading_zero_order(self):
        self.assertEqual(collate(["01", "1"]), ["1", "01"])

    def test_empty_lines_kept_and_first(self):
        self.assertEqual(collate(["b", "", "a"]), ["", "a", "b"])

    def test_whitespace_only_lines_kept(self):
        result = collate(["b", "  ", "a"])
        self.assertEqual(result, ["  ", "a", "b"])

    def test_multiset_preserved(self):
        lines = ["b", "", "a", "b", "  ", "café", "cafz", "01", "1", "file10", "file9"]
        self.assertEqual(Counter(collate(lines)), Counter(lines))

    def test_deterministic(self):
        lines = ["B", "a", "", "10", "9", "é", "e", "  "]
        self.assertEqual(collate(lines), collate(list(lines)))


class UniqueTest(unittest.TestCase):
    def test_dedup_by_segment_sequence(self):
        result, dropped = collate_unique(["a", "A", "b", "a"])
        self.assertEqual((result, dropped), (["a", "b"], 2))

    def test_first_of_class_kept(self):
        result, dropped = collate_unique(["A", "a"])
        self.assertEqual((result, dropped), (["A"], 1))

    def test_empty_and_blank_same_class(self):
        result, dropped = collate_unique(["", "  ", "x"])
        self.assertEqual((result, dropped), (["", "x"], 1))

    def test_leading_zeros_are_distinct_classes(self):
        result, dropped = collate_unique(["1", "01"])
        self.assertEqual((result, dropped), (["1", "01"], 0))

    def test_accents_fold_into_same_class(self):
        result, dropped = collate_unique(["café", "cafe", "CAFE"])
        self.assertEqual((result, dropped), (["café"], 2))

    def test_nothing_dropped(self):
        result, dropped = collate_unique(["b", "a"])
        self.assertEqual((result, dropped), (["a", "b"], 0))


class CliTest(unittest.TestCase):
    def run_cli(self, argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(argv)
        return code, buffer.getvalue()

    def test_sorted_output(self):
        code, out = self.run_cli(["--text", "b\\na"])
        self.assertEqual(code, 0)
        self.assertEqual(out.split(), ["a", "b"])

    def test_file9_before_file10(self):
        code, out = self.run_cli(["--text", "file10\\nfile9"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["file9", "file10"])

    def test_accent_order(self):
        code, out = self.run_cli(["--text", "cafz\\ncafé"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["café", "cafz"])

    def test_fullwidth_digit_order(self):
        code, out = self.run_cli(["--text", "v20\\nv１0"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["v１0", "v20"])

    def test_empty_line_kept_first(self):
        code, out = self.run_cli(["--text", "b\\n\\na"])
        self.assertEqual(code, 0)
        self.assertEqual(out.split("\n"), ["", "a", "b", ""])

    def test_key_mode(self):
        code, out = self.run_cli(["--text", "v1", "--key"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [[["t", "v"], ["n", 1, 1]], "v1"])

    def test_key_mode_input_order_and_reuses_sort_key(self):
        code, out = self.run_cli(["--text", "file10\\nfile9", "--key"])
        self.assertEqual(code, 0)
        printed = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(
            printed,
            [json.loads(json.dumps(sort_key("file10"))),
             json.loads(json.dumps(sort_key("file9")))],
        )

    def test_unique_mode(self):
        code, out = self.run_cli(["--text", "a\\nA\\nb\\na", "--unique"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["dropped=2", "a", "b"])

    def test_unique_mode_nothing_dropped(self):
        code, out = self.run_cli(["--text", "b\\na", "--unique"])
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["dropped=0", "a", "b"])

    def test_missing_input(self):
        self.assertEqual(main([]), 2)


class ReferenceTest(unittest.TestCase):
    """随机 2000 组与「逐字符状态机分段」参考实现比对，差异必须为 0。"""

    POOL = (
        string.ascii_letters
        + string.digits
        + " \t._-,"
        + "０１２３４５６７８９"
        + "ＡＢＣａｂｃ"
        + "éèêàçüöß"
        + "́̀̈"
        + "①②½⑳"
    )

    def test_random_2000_groups_match_reference(self):
        rng = random.Random(20260927)
        diffs = 0
        for _ in range(2000):
            lines = [
                "".join(rng.choice(self.POOL) for _ in range(rng.randrange(0, 12)))
                for _ in range(rng.randrange(0, 8))
            ]
            for line in lines:
                if segments(line) != reference_segments(line):
                    diffs += 1
            if collate(lines) != sorted(lines, key=reference_key):
                diffs += 1
            if collate(lines) != sorted(lines, key=sort_key):
                diffs += 1
        self.assertEqual(diffs, 0)


class ScaleTest(unittest.TestCase):
    def test_many_lines(self):
        rng = random.Random(7)
        lines = [
            "file%d" % rng.randrange(0, 1000) for _ in range(20000)
        ] + [""] * 100
        result = collate(lines)
        self.assertEqual(Counter(result), Counter(lines))
        self.assertEqual(result[:100], [""] * 100)
        self.assertEqual(result, collate(list(lines)))


if __name__ == "__main__":
    unittest.main()
