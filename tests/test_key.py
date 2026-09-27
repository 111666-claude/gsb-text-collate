import io
import unittest
from contextlib import redirect_stdout

from collate.cli import main
from collate.key import collate, fold_text, number_chunks, sort_key


class FoldTest(unittest.TestCase):
    def test_casefold(self):
        self.assertEqual(fold_text("AbC"), "abc")

    def test_strips_around(self):
        self.assertEqual(fold_text("  a  "), "a")


class ChunkTest(unittest.TestCase):
    def test_two_digit_runs(self):
        self.assertEqual(len(number_chunks("v1.20beta")), 2)

    def test_no_digits(self):
        self.assertEqual(number_chunks("abc"), [])


class KeyTest(unittest.TestCase):
    def test_key_shape(self):
        key = sort_key("file7")
        self.assertEqual(len(key), 3)
        self.assertEqual(key[0], "file0")
        self.assertEqual(key[2], "file7")

    def test_same_line_same_key(self):
        self.assertEqual(sort_key("x"), sort_key("x"))


class CollateTest(unittest.TestCase):
    def test_letters(self):
        self.assertEqual(collate(["a", "B", "c"]), ["a", "B", "c"])

    def test_equal_keys_keep_input_order(self):
        self.assertEqual(collate(["Ab", "ab"]), ["Ab", "ab"])

    def test_empty_input(self):
        self.assertEqual(collate([]), [])


class CliTest(unittest.TestCase):
    def test_sorted_output(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "b\\na"])
        self.assertEqual(code, 0)
        self.assertEqual(buffer.getvalue().split(), ["a", "b"])

    def test_key_mode(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = main(["--text", "v1", "--key"])
        self.assertEqual(code, 0)
        self.assertTrue(buffer.getvalue().startswith('["v0"'))

    def test_missing_input(self):
        self.assertEqual(main([]), 2)


if __name__ == "__main__":
    unittest.main()
