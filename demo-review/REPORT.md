# Skill Diet 静态体检

文件 4 个；磁盘 544 bytes；入口 347 字符。

**没有运行任务；不宣称节省 token 或保持行为等价。**

## 体积前十（并非实际加载量）
- `SKILL.md`: 347 bytes
- `references/narration.md`: 70 bytes
- `references/charts.md`: 64 bytes
- `references/core.md`: 63 bytes

## 待核查证据
- batch_read_candidate: `SKILL.md`:6 — Always read all following files before starting.

## 能力候选（默认保留，不能直接关闭）
- narration: `SKILL.md`，行 8,12
- charts: `SKILL.md`，行 9
- charts: `references/charts.md`，行 1,2
- export: `references/core.md`，行 2
- narration: `references/narration.md`，行 1,2

## 限制
- 未运行目标 Skill，不执行其脚本。
- 磁盘字节/字符不是实际上下文 token 或费用。
- Markdown 静态引用只覆盖显式链接和部分反引号路径；代码/动态路径/隐式依赖需人工核查。
- 条件提示是行级启发式，不证明安全可省略。
