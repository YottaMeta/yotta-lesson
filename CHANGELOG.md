# 更新日志

## v0.1.1 (2026-10-01)

- 文档修正：家族协同 / 边界 / 版权说明中元题的引用改为已发布实际口径（元题 = 按双向细目表从学校自备题库组卷 + 试卷结构校验，不生成题面，题面由题库提供）；同步更新中英 README 与 `references/copyright.md`。
- 行为零变更：内核 / CLI / 退出码 / 门禁契约不变。
- 新增文档契约回归：家族引用不得回退为「规划中 / (planned)」。

## v0.1.0 (2026-09-24)

初始发布：

- 定位：元案 —— 本地、确定性的教案骨架与覆盖校验技能（零依赖，Python 3.8+ 标准库）；不联网、不调用模型、不内置教材与题目原文。
- 输入：课标映射包 JSON（课题 / 知识点 / 重难点 / 易错点 / 课标来源）+ 可选结构配置 JSON（每课时分钟、环节与比例、必填环节、环节关键词）。
- 能力：教案骨架生成（学习目标带来源、重难点与易错点、五环节 + 分钟级时间分配、板书与评价清单）、覆盖检查（`knowledge_missing` / `stage_missing` / `source_missing` / `time_missing` / `minutes_mismatch`）、映射包 list / show / validate。
- 时间分配：最大余数法，各环节分钟合计精确等于「课时 × 每课时分钟」。
- CLI：`plan` / `check` / `map` / `template`；退出码 0 / 1 / 2 / 3 / 4；支持 `--periods`、`--format md|json`、`--out`、`--stdin`、`--gate findings=<n>`。
- 测试：55 项，Python 3.8.20 / 3.11.9 / 3.13.15 全绿；合成样例（完整教案 / 缺口教案）端到端通过。
- 文档：SKILL.md + references（map-format / plan-format / copyright）+ 中英 README + 四方式安装 + banner。
