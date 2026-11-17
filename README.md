# absolutely

**decisive mode** — a Claude Code skill that turns padded, defensive replies into determinate, specific ones. English is the original; Chinese is a translation.
**decisive mode**：把冗余、防御性的回答改写成确定、具体的回答。英文为原始版本，中文为译本。

| Layer / 层 | Mechanism / 机制 | light | strict |
|---|---|---|---|
| L1 | Prompt rules / 提示词规则 (`rules.<lang>.md`) | ✓ | ✓ |
| L2 | `UserPromptSubmit` hook injects rules every turn / 每轮注入 | ✓ | ✓ |
| L3 | `Stop` hook self-check with fix + examples, one rewrite / 自检并附改法与正反例，改写一次 | | ✓ |
| Stats | Log of check ids only / 日志仅记检查项 id | | ✓ |

Nine checks / 九个检测项: `deferral_ending`, `hedge_density`, `disclaimer_stack`, `options_without_pick`, `apology_preamble`, `capability_hedge`, `preemptive_negation`, `vague_degree`, `stacked_negation`.

```sh
S=.claude/skills/decisive/scripts/decisive.py
python3 $S mode strict|light|off|status   # or /decisive on in Claude Code
python3 $S lang en|zh
python3 $S check reply.txt
python3 $S stats
python3 -m unittest discover -s .claude/skills/decisive/tests
```

Docs / 文档: [`SKILL.md`](.claude/skills/decisive/SKILL.md) (English, original) · [`SKILL.zh.md`](.claude/skills/decisive/SKILL.zh.md) (中文译本)

## Costs and risks / 代价和风险

- **Per-turn tokens / 每轮 token**: L2 injects about 450 tokens per turn in English and about 700 in Chinese. `off` costs nothing.
  L2 每轮注入：英文约 450 token，中文约 700 token。`off` 模式无开销。
- **Extra generation / 额外生成**: in `strict`, a matched reply triggers one rewrite, so the user sees both the original and the revised reply. Use `light` to avoid this.
  `strict` 模式下，命中的回复会触发一次改写，用户会同时看到原回复和改写后的回复。不想要这一点就用 `light`。
- **Untested on real conversations / 未经真实对话验证**: thresholds are tuned to miss rather than misfire, but have only been checked against unit tests. Run `strict` for a while, use `stats` to find checks that fire often without improving replies, then raise their thresholds or disable them in `config.json`.
  阈值按"宁可漏报"调过，但目前只经过单元测试验证。建议先用 `strict` 跑一段时间，用 `stats` 找出命中频繁、改写后质量却没有提升的检测项，再在 `config.json` 中调高阈值或关闭。
- **Pattern matching limits / 正则的局限**: checks are regular expressions, not semantic judgment. They can miss rephrased padding and can flag a warranted sentence; the one-rewrite limit and the "keep it if warranted" instruction bound the damage.
  检测基于正则，而不是语义判断：换个说法的冗余措辞可能漏掉，必要的句子也可能被误报。每轮最多改写一次，加上"确属必要就保留"的提示，可以把误报的影响控制在一次改写以内。
- **Chinese skill file / 中文 skill 文件**: Claude Code loads only `SKILL.md`; `SKILL.zh.md` is a reference translation. With `lang zh`, the injected rules and feedback are in Chinese.
  Claude Code 只加载 `SKILL.md`，`SKILL.zh.md` 是对照译本。设为 `lang zh` 时，注入的规则和回传的修改意见是中文。

**Scope / 边界**: refusals are never checked or sent back for rewriting; confirming high-risk actions is not treated as defensive. 拒绝不检测、不改写；高风险操作的确认不算防御性。

To use elsewhere / 迁移: copy `.claude/skills/decisive/` and merge the two hooks from `.claude/settings.json`.
