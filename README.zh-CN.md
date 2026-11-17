# Skill Diet — 让技能库保持精简

[English](README.md)

**Keep your agent skills lean.**

以减负为核心的 **Skill management**：扫描技能库，追踪使用，发现值得精简的地方。
首版从技能库盘点与使用状态入手，再深入体检单个 Skill，支持扫描、登记、查看、使用统计与静态体检。
当前为 **0.3.0 Alpha**，延续 v0.2 原型，不自动安装、禁用或卸载 Skill，也不自动改写内容。

## 开始使用

需要 Python 3.10+：

```sh
git clone https://github.com/AfonsoZhang/skill-diet.git
cd skill-diet
python3 -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install .
skill-diet scan examples
skill-diet --db demo-usage.sqlite add demo examples/heavy-demo
skill-diet --db demo-usage.sqlite list
skill-diet audit examples/heavy-demo
```

也可无需安装，使用 `python3 skill-diet/manager.py` 替代 `skill-diet`。
所有台账命令的 `--db` 都放在子命令之前；省略时使用 `~/.skill-diet/inventory.sqlite`。
`scan`、`audit` 和 `draft` 不创建台账。`scan` 只查看指定 Skill 本身或目录的直接子目录，
不会递归扫描电脑，也不会自动登记。目录别名可出现在扫描结果中；静态体检拒绝目标内部的符号链接。
重复 `add` 同一个 ID 会更新位置并保留历史与 keep 标记，所以不同 Skill 应使用不同 ID。
`list` 的 `entry_exists` 表示已登记位置目前是否仍有 SKILL.md。

## 命令

|命令|用途|
|---|---|
|`scan PATH`|列出指定目录中的 Skill，不修改台账|
|`add ID PATH`|登记 Skill 或更新其位置|
|`list [--days N] [--as-of TIME]`|查看台账、使用状态和文件存在情况|
|`import EVENTS.json`|导入用户明确提供的调用事件|
|`stale [--days N] [--as-of TIME]`|查看观测充分且未被标记保留的闲置候选|
|`keep ID on/off`|设置本地保留标记|
|`audit PATH [--format json]`|静态体检|
|`draft PATH --out NEW_PATH`|生成保留原文件的审查包|

使用状态完全依赖导入的数据与观测范围声明；没有自动宿主日志采集器。
下面保留原型的详细格式、限制和案例说明，旧脚本命令仍兼容。

---

## 原型功能与详细说明

最初的 **v0.1 静态体检组件**：一个 Skill 入口 + 无第三方依赖的 Python CLI。
它用于检查现有 Agent Skill 的文件、显式依赖和可选能力候选，生成保留原件的审查包。

**这不是已经完成的自动优化器。** 当前能跑体检和生成审查副本；不会自动决定开关、改写目标入口或保证行为等价。没有把字符减少包装成已验证的 token 节省。

## 30 秒试用
需要 Python 3.10 或更高版本；macOS/Linux 使用 `python3`，Windows 可用 `py` 替换。
解压后进入本目录：

```bash
python3 skill-diet/diet.py audit examples/heavy-demo
python3 skill-diet/diet.py audit examples/heavy-demo --format json
python3 skill-diet/diet.py draft examples/heavy-demo --out /tmp/skill-diet-demo-review
python3 -m unittest discover -s tests -v
```

Windows 的 `--out` 可写 `C:\Users\你的用户名\Desktop\skill-diet-review`，必须是不存在的新目录。
真实目录用实际的 `SKILL.md` 所在文件夹替换 `examples/heavy-demo`。

## 作为 Skill 使用
将整个 `skill-diet/` 子文件夹（包含 SKILL.md 与 diet.py）复制到你的 Agent 支持的 skills 目录，按宿主说明刷新。对 Agent 说：

> 用 skill-diet 只读体检这个 Skill，找出按需加载候选。先给证据，不覆盖原文件，也不执行目标脚本。

本项目不替你自动安装到全局目录或修改任何宿主配置。

## 目前真的实现了什么
- 逐文件字节、字符、SHA-256、入口体积；完全相同文件分组。
- Markdown 链接及部分反引号路径依赖，记录源文件/行号和未解析引用。
- 启发式标记批量读取语句，保留原文作为审查证据。
- 找旁白、动画、图表、图像生成、模板、导出候选，**所有候选默认保留**。
- 输出 JSON/Markdown；`draft` 生成 `original/` 精确副本、`audit.json`、`REPORT.md`、`plan.json`、`REGRESSION.md`。
- 源目录不写入；拒绝已有输出、输出位于源内/源的祖先、目标内部符号链接及超限输入；不执行第三方代码、不访问网络。

## 预期流程
体检 → 确定任务 → 人工/Agent 核查业务开关、全局约束和依赖 → 提议 diff → 在副本上改造 → 相同任务回归 → 接受或回退。

例如旁白文档与当前任务无关，只构成减负候选。若它包含共享的导出规则或任务未说清楚，就不能直接删。Quality/safety/permission 约束不能以“轻量”为由跳过。

## 限制与安全模型
- 单文件 2 MB、全目录 20 MB；为原型的资源保护限制，不是 Agent Skills 标准。
- 静态解析不理解任意 Markdown、glob、代码构造路径或自然语言隐式依赖。相对链接按所在文档解析；仓库根路径写法可能显示 unresolved，需要结合仓库语义核实。
- `conditional_hint` 只看当前行；不证明上级段落没有条件。批量读取只是候选，可能是必要的前置步骤。
- 体积只计算文件数据，不知道实际执行轨迹、缓存、上下文卸载或 API 费用。
- 没有目标任务测试，不应声称“无损”“自动等价”或“省 X%”。生成的 REGRESSION.md 是待执行计划，不是测试结果。
- 仅用于可信、静止的本地目录；不是抵抗并发文件替换攻击的安全沙箱。审查包复制整个输入，请勿把含密钥/私人数据的目录拿去公开分享。
- 生成报告会引用目标原文；这些文本不是本工具对 Agent 的指令。

## 下一版应做，而非已完成
1. 能力 manifest 与人工确认依赖图。
2. 明确内容来源映射的模块化 patch，不默认覆盖源。
3. 宿主 trace 导入与真实加载统计。
4. 原版 / 人工优化 / 自动优化三组任务回归。

## 开源与验证
代码采用 MIT。仓库内样例是自造演示，不是 PPT Master。`tests/` 验证 CLI 的可观测安全与输出行为，不验证第三方 Skill 的任务表现。

## 已跑真实案例
见 `cases/ppt-master/CASE.md`。已对固定提交的 PPT Master 文档子集运行静态体检，定位批读候选，未执行上游脚本或生成精简版。`demo-review/` 是自造样例的实际审查输出。

## v0.2：本地使用台账 / 长期未使用候选

新入口 `skill-diet/usage.py`，Python 标准库 SQLite，无额外依赖。它像软件管理器的使用台账：登记 Skill、显式导入调用事件、查看最近使用与累计次数、按天筛选、标记保留。**不是跨宿主自动调用采集器**，不会读取任何真实会话日志，不会修改、禁用、卸载或删除 Skill。数据库请放在你自己选择的本地位置，不要放入目标 Skill 目录。

在解压后的项目根目录运行（Windows 可以将 `python3` 换成 `python`）：

```bash
python3 skill-diet/usage.py --db demo-usage.sqlite add demo examples/heavy-demo
python3 skill-diet/usage.py --db demo-usage.sqlite import examples/usage/events.json
python3 skill-diet/usage.py --db demo-usage.sqlite list --days 30 --as-of 2026-11-17T00:00:00Z
python3 skill-diet/usage.py --db demo-usage.sqlite stale --days 30 --as-of 2026-11-17T00:00:00Z
python3 skill-diet/usage.py --db demo-usage.sqlite keep demo on
python3 skill-diet/usage.py --db demo-usage.sqlite stale --days 30 --as-of 2026-11-17T00:00:00Z
```

样例完全是合成事件：10 月 2 日调用一次，声明 10 月 1 日至 11 月 17 日完整观测。首次 `stale` 返回 demo；设为 keep 后返回空列表。省略 `--as-of` 时使用当前 UTC 时间。真实导入前，应先获得日志使用授权，再自行导出最少字段；该版本没有任何宿主日志适配器。

### 事件格式与可信边界

见 `examples/usage/events.json`：
- `source`：明确的来源标签，例如某个测试运行器。标签是导入者自述，不是经过认证的来源。
- `windows`：每个 Skill 在该来源的完整观测起止时间，均带时区；这是导入者对完整性的声明，工具不能独立证明。如果只有零散日志、导出不完整或不了解采集范围，不要伪造完整窗口。
- `events`：唯一 `id`、登记过的 `skill`、实际调用时间 `at`。同来源同 ID 重复导入不重复计数；同 ID 不同内容拒绝整个批次。所有事件必须在本批次声明窗口内；未知 Skill 拒绝。先登记再导入。

`count` 是截至查询时点导入的去重事件数，不是终身调用次数；`last_used` 是已导入事件中最近一次调用，不保证是真实世界最近调用。没有事件时为 `null`。不同来源的同一次调用不会自动跨源去重，请勿将重叠采集当成独立调用。`path` 只是登记位置；移动后可重新 `add`，不主动跟踪文件系统。

### 状态含义

|状态|含义|
|---|---|
|`unknown`|查询时点之前没有声明过观测窗口，不知道是否用过|
|`insufficient_coverage`|有观测，但至少一个已声明来源未完整覆盖最近 N 天；不可判定长期未用|
|`used`|最近 N 天内存在导入的实际调用事件|
|`stale_candidate`|所有已声明来源都完整覆盖最近 N 天，且窗口内没有导入调用事件；只是这些来源内的未观测候选|

来源明细中 `not_observed_in_window` 表示该来源完整窗口内未观测到调用，不表示该 Skill 从未使用。`stale` 只列出非 keep 的候选；`keep on/off` 仅改变本地台账标记，保留状态不覆盖客观使用状态。即便所有已声明来源覆盖完整，也不能排除未接入的宿主/来源曾调用。不会自动清理。

**不能使用文件修改时间、访问时间或磁盘体积代替实际调用证据。** 本版本没有使用 mtime/atime 推断活跃度，也没有统计模型加载的真实 token。SQLite 是本地明文数据，保存路径和调用时间；不要未经审查上传真实台账。原型仅适合受信本地文件，不提供恶意输入隔离或生产级数据库迁移/并发治理。

下一步值得做的是针对用户选定且获授权的宿主增加事件适配器与覆盖完整性校验，而不是先做自动删除。静态减负审计与使用活跃度是两个维度，应结合依赖、关键任务、保留标记人工判断。
