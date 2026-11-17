# absolutely

[English](README.md) | 中文

**decisive mode** 是一个 Claude Code skill，把冗余、防御性的回答改写成确定、具体的回答。英文为原始版本，中文为译本。

## 干预层

| 层 | 机制 | light | strict |
|---|---|---|---|
| L1 | 提示词规则（`rules.<lang>.md`） | ✓ | ✓ |
| L2 | `UserPromptSubmit` hook 每轮注入规则 | ✓ | ✓ |
| L3 | `Stop` hook 自检，回传问题、改法和正反例，要求改写一次 | | ✓ |
| 统计 | 日志仅记录检查项 id，由 `stats` 汇总 | | ✓ |

九个检测项：`deferral_ending`、`hedge_density`、`disclaimer_stack`、`options_without_pick`、`apology_preamble`、`capability_hedge`、`preemptive_negation`、`vague_degree`、`stacked_negation`。

## 用法

```sh
S=.claude/skills/decisive/scripts/decisive.py
python3 $S mode strict|light|off|status   # 或在 Claude Code 中输入 /decisive on
python3 $S lang en|zh
python3 $S check reply.txt
python3 $S stats
python3 -m unittest discover -s .claude/skills/decisive/tests
```

完整文档：[`SKILL.zh.md`](.claude/skills/decisive/SKILL.zh.md)。

## 代价和风险

- **每轮 token**：L2 每轮注入，英文约 450 token，中文约 700 token。`off` 模式无开销。
- **额外生成**：`strict` 模式下，命中的回复会触发一次改写，用户会同时看到原回复和改写后的回复。不想要这一点就用 `light`。
- **未经真实对话验证**：阈值按"宁可漏报"调过，但目前只经过单元测试验证。建议先用 `strict` 跑一段时间，用 `stats` 找出命中频繁、改写后质量却没有提升的检测项，再在 `config.json` 中调高阈值或关闭。
- **正则的局限**：检测基于正则，而不是语义判断。换个说法的冗余措辞可能漏掉，必要的句子也可能被误报；每轮最多改写一次，加上"确属必要就保留"的提示，误报的影响最多是一次改写。
- **中文 skill 文件**：Claude Code 只加载 `SKILL.md`，`SKILL.zh.md` 是对照译本。设为 `lang zh` 时，注入的规则和回传的修改意见是中文。

## 边界

拒绝不检测、不改写。高风险操作的确认不算防御性。

## 迁移到其他项目

复制 `.claude/skills/decisive/`，并把 `.claude/settings.json` 中的两个 hook 合并进目标项目的 settings。
