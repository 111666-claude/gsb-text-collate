# text-collate

文本排序键（大小写、重音、数字块、空行），只用 Python 标准库。

```
python3 -m collate.cli --text 'file10\nfile9'
python3 -m collate.cli --text 'cafz\ncafé'
python3 -m collate.cli --text 'v10' --key
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **数字块按数值比**：`--text 'file10\nfile9'` 按口径是 `file9` 在前，现在按字符串比，给 `file10` 在前。
- **重音要折叠**：先 NFKD 分解、丢掉组合记号，再 casefold。`--text 'cafz\ncafé'` 按口径是 `café` 在前
  （折叠成 `cafe` < `cafz`），现在 `é` 的码点比 `z` 大，给 `cafz` 在前。
- **空行要保留并排最前**：`--text 'b\n\na'` 按口径输出三行，第一行是空行；现在空行被丢掉，只输出两行。
- 排序键：`(折叠串, 数字块序列, 原串)`，折叠串里每个数字块都换成 `"0"`，数字块是 `(数值, 位数)`；
  键相同时保持输入顺序（稳定排序）。
- 折叠规则：去掉行首尾空白，NFKD 分解后丢掉组合记号（Mn 类），再 `casefold`。
- `--key`：按输入顺序打印每行的键（JSON 数组），必须与排序用的是同一个键。
- 不变量：行的多重集合与输入一致；排序结果与「逐条算键再 sorted」的参考实现逐位一致；重复运行结果相同。
- 规模：100 万行、每行 ≤ 200 个字符，单遍生成键，内存 O(行数)。
- 对照自证：随机 2000 组输入与参考实现比对，差异必须为 0。

## 现在的行为

- `number_chunks` 返回字符串，排序键里数字块按字典序比：`file10` 排在 `file9` 前面。
- `fold_text` 只 `casefold`，不去组合记号：`café` 的折叠串还是 `café`，排在 `cafz` 后面。
- `collate` 先用 `line.strip()` 过滤掉空行与纯空白行，行的多重集合会变。

## 计划新增的能力

```
--text 文本    用 \n 表示换行
--file 文件    从文件读
--key          打印每行的排序键
```

## 输出

```
file9
file10
```

## 目录

```
collate/key.py   折叠、数字块与排序键
collate/cli.py   命令行入口
tests/           unittest 用例
```
