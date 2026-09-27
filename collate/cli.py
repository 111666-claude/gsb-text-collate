"""命令行入口：排序文本行，或打印每行的排序键。"""

import argparse
import json
import sys

from .key import CollateError, collate, sort_key


def build_parser():
    parser = argparse.ArgumentParser(prog="text-collate", description="文本排序（collation）")
    parser.add_argument("--text", help="直接给文本（用 \\n 表示换行）")
    parser.add_argument("--file", help="从文件读")
    parser.add_argument("--key", action="store_true", help="按输入顺序打印每行的排序键")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        if args.text is not None:
            text = args.text.replace("\\n", "\n")
        elif args.file:
            with open(args.file, encoding="utf-8") as handle:
                text = handle.read()
        else:
            print("错误：需要 --text 或 --file", file=sys.stderr)
            return 2
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines.pop()
        if args.key:
            for line in lines:
                print(json.dumps(list(sort_key(line)), ensure_ascii=False))
        else:
            for line in collate(lines):
                print(line)
    except (CollateError, ValueError, OSError) as error:
        print("错误：%s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
