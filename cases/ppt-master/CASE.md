# PPT Master 真实文档静态试跑

日期：2026-11-17。上游：https://github.com/hugohe3/ppt-master
固定提交：`3af3e8ef774c4d67ee57e1306d9256d08c9ee1bf`

## 做了什么

通过 GitHub tree API 列出固定提交，下载 `skills/ppt-master/` 下全部 230 个 Markdown 与 MIT LICENSE，作为文档子集。没有安装项目、调用其脚本、生成 PPT、访问其服务或改变用户本地配置。

执行本原型：

```sh
python skill-diet/diet.py audit /path/to/markdown-snapshot --format json
python skill-diet/diet.py audit /path/to/markdown-snapshot --format markdown
```

CLI 两次均成功退出。`provenance.json` 保存每份文档的固定版本 URL、字节数与 SHA-256。包中未复制上游整套源文件；自行获取案例时应保留其 MIT LICENSE。

## 可复核结果

- 输入为 231 文件、2,161,489 bytes；这只是抽取的文档子集大小。
- `SKILL.md` 为 143 行、10,323 bytes，入口并非一个没有路由的巨型文件。
- `workflows/profiles/quick-generate.md` 为 250 行、37,194 bytes。
- 修复英文词边界后，扫描得到 29 个批读语句候选；这是人工复核队列，不是缺陷数。
- Quick 文档第 170 行明确要求一起读取四份 execution core 文档，再按路由表读取触发模块。原型定位了这个可供进一步测量的批读点。

固定来源：[入口](https://github.com/hugohe3/ppt-master/blob/3af3e8ef774c4d67ee57e1306d9256d08c9ee1bf/skills/ppt-master/SKILL.md)、[Quick profile](https://github.com/hugohe3/ppt-master/blob/3af3e8ef774c4d67ee57e1306d9256d08c9ee1bf/skills/ppt-master/workflows/profiles/quick-generate.md#L170)。

## 这不证明什么

- 已有路由、条件模块、质量门槛；不能因检测到批读就断定可安全删除。
- 不包含脚本、二进制资源与非 Markdown 配置。报告里的 `unresolved` 可能是子集省略、动态占位符、项目工作目录或路径基准不同，**不是上游坏链接统计**。
- 能力词和条件词只是启发式候选；首次试跑还暴露英文子串匹配误报，已修正并新增回归测试。因此这里不把候选总数当作缺陷数。
- 没有端到端 token、时延、费用或质量数据；不能声称节省百分比，也没有生成或验证 PPT Master 精简版。

下一步：选定普通静态演示、模板复用、旁白三个任务，先捕获原版实际读取轨迹，再提出能力级开关并做同模型、同输入回归。
