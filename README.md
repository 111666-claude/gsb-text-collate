# text-collate

文本排序键（大小写、重音、数字块、空行），只用 Python 标准库。

```
python3 -m collate.cli --text 'file10\nfile9'
python3 -m collate.cli --text 'cafz\ncafé'
python3 -m collate.cli --text 'v10' --key
python3 -m collate.cli --text 'Ab\nab' --unique
python3 -m unittest discover -s tests -v
```

## 口径

- **折叠**：每行先去首尾空白，再 NFKD 分解、丢掉组合记号（Mn 类）、`casefold`。
  全角字母与数字落回半角，重音与大小写不影响相对顺序。
- **空行保留**：空行与纯空白行不丢，折叠后为空文本段，排在最前；行的多重集合与输入一致。
- **分段键**：一行切成「文本段 / 数字段」交替的序列（以文本段开头与结尾，可为空），
  排序键是 `(段序列, 原串)`。文本段存折叠后的文本，数字段存 `(数值, 位数)`；
  相邻数字段之间的空文本段也保留，`file9` 与 `file10` 逐段比出顺序。
- **数字段**：先比数值，数值相同再按位数少的在前（`1` 在 `01` 前）；
  前导零只影响位数，数字段不按字符串整体比。
- `--key`：按输入顺序打印每行的键（JSON），结构为
  `[[["t", 折叠文本], ["n", 数值, 位数], ...], 原串]`，与排序复用同一个键。
- `--unique`：按段序列判定等价类，每类只留输入顺序里的第一条；
  先打印 `dropped=<丢掉的行数>`，再打印排序后的结果。
- 不变量：同一输入重复运行结果相同；等价类在结果里相邻、类内保持输入顺序（稳定排序）；
  非 `--unique` 时行的多重集合与输入一致。
- 规模：100 万行、每行 ≤ 200 个字符时单遍生成键，内存 O(行数)；
  逐字符状态机分段，不用会回溯的正则，也不把整行 JSON 化当键。
- 对照自证：随机 2000 组输入与独立的「逐字符状态机分段」参考实现比对，差异为 0
  （见 `tests/test_key.py` 的 `RandomReferenceTest`）。

## 示例

```
$ python3 -m collate.cli --text 'file10\nfile9'
file9
file10
$ python3 -m collate.cli --text 'cafz\ncafé'
café
cafz
$ python3 -m collate.cli --text 'b\n\na'

a
b
$ python3 -m collate.cli --text 'v1' --key
[[["t", "v"], ["n", 1, 1], ["t", ""]], "v1"]
```

## 参数

```
--text 文本    用 \n 表示换行
--file 文件    从文件读
--key          按输入顺序打印每行的排序键（JSON）
--unique       按段序列去重，先打印 dropped=<行数>，再打印排序结果
```

## 目录

```
collate/key.py   折叠、分段与排序键
collate/cli.py   命令行入口
tests/           unittest 用例（含随机 2000 组参考实现对照）
```
