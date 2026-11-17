# absolutely

English | [中文](README.zh.md)

**decisive mode** is a Claude Code skill that turns padded, defensive replies into determinate, specific ones. English is the original version; Chinese is a translation.

## Layers

| Layer | Mechanism | light | strict |
|---|---|---|---|
| L1 | Prompt rules (`rules.<lang>.md`) | ✓ | ✓ |
| L2 | `UserPromptSubmit` hook injects the rules every turn | ✓ | ✓ |
| L3 | `Stop` hook self-check that returns the problem, the fix, and bad/good examples for one rewrite | | ✓ |
| Stats | Log of check ids only, summarized by `stats` | | ✓ |

Nine checks: `deferral_ending`, `hedge_density`, `disclaimer_stack`, `options_without_pick`, `apology_preamble`, `capability_hedge`, `preemptive_negation`, `vague_degree`, `stacked_negation`.

## Usage

```sh
S=.claude/skills/decisive/scripts/decisive.py
python3 $S mode strict|light|off|status   # or /decisive on in Claude Code
python3 $S lang en|zh
python3 $S check reply.txt
python3 $S stats
python3 -m unittest discover -s .claude/skills/decisive/tests
```

Full documentation: [`SKILL.md`](.claude/skills/decisive/SKILL.md).

## Costs and risks

- **Per-turn tokens**: L2 injects about 450 tokens per turn in English and about 700 in Chinese. `off` costs nothing.
- **Extra generation**: in `strict`, a matched reply triggers one rewrite, so the user sees both the original and the revised reply. Use `light` to avoid this.
- **Untested on real conversations**: thresholds are tuned to miss rather than misfire, but have only been checked against unit tests. Run `strict` for a while, use `stats` to find checks that fire often without improving replies, then raise their thresholds or disable them in `config.json`.
- **Pattern matching limits**: checks are regular expressions, not semantic judgment. They can miss rephrased padding and can flag a warranted sentence; the one-rewrite limit and the "keep it if warranted" instruction bound the damage to a single rewrite.
- **Chinese skill file**: Claude Code loads only `SKILL.md`; `SKILL.zh.md` is a reference translation. With `lang zh`, the injected rules and feedback are in Chinese.

## Scope

Refusals are never checked or sent back for rewriting. Confirming high-risk actions is not treated as defensive.

## Using it elsewhere

Copy `.claude/skills/decisive/` and merge the two hooks from `.claude/settings.json` into the target project's settings.
