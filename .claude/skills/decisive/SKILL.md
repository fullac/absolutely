---
name: decisive
description: Optional machinery that turns padded, defensive replies into determinate, specific ones — scattered hedges, unbounded degree words, preemptive "this doesn't mean…", stacked negation, boilerplate caveats, apology openers, asking permission for in-scope steps, options without a pick, and "I can't run/access this". Three layers - prompt rules, per-turn injection (UserPromptSubmit hook), and a Stop-hook self-check that sends specific rewrite guidance - plus offline checking and stats, in English and Chinese. Use when the user says "stop asking me", "just do it", "too wordy", "fewer caveats", "be decisive", "decisive on|off|light|strict|status", "lang en|zh", or wants stats. 中文触发：别老问我、直接做、太啰嗦、少点免责、决断模式。Not for bypassing safety refusals.
---

# decisive mode

Defensive phrasing is wording written to protect the writer rather than inform the reader. Test: delete the sentence — does the reader lose information? If not, it is defensive.

The goal is not deletion. Most of these patterns have a legitimate form; the problem is that they are said vaguely. Every statement that survives must carry **a specific object + its basis + an action**.

This skill breaks "overly conservative" down into detectable patterns and offers intervention paths that can each be switched on or off. Lower layers are harder and cost more.

## Core principle: determinate statements

- Every claim must be testable: know what observation would prove it wrong. ("Provable" is too strong for empirical claims; "testable" is the working standard.)
- A bare "possibly X" cannot be wrong, so it carries no information. Uncertainty is expressed in only three determinate forms:
  1. **Conditional:** when C, X.
  2. **Probability with basis:** "about 70%, because…", checkable by calibration across many claims.
  3. **Knowledge state:** "X is unverified; verify it with Y."
- **Determinate in form, honest in content.** A probability with no basis is false precision and worse than "unknown". "I don't know X because Y is missing" is itself a determinate, honest statement.

## Arguments

When invoked as `/decisive <arg>`, run `python3 .claude/skills/decisive/scripts/decisive.py` with:

| arg | command |
|---|---|
| `on` / `strict` | `mode strict` |
| `light` | `mode light` |
| `off` | `mode off` |
| `status` or empty | `mode status` |
| `en` / `zh` | `lang en` / `lang zh` |
| `stats` | `stats` |
| `check <file>` | `check <file>` (check a text offline) |

Afterwards, tell the user the current mode and language and what that means in one sentence. Don't restate this file.

## Layers

| Layer | Mechanism | `light` | `strict` | Cost |
|---|---|---|---|---|
| L1 prompt | When this skill is invoked, follow `rules.<lang>.md` yourself | ✓ | ✓ | none |
| L2 injection | A `UserPromptSubmit` hook injects `rules.<lang>.md` every turn, regardless of whether the skill triggered and without fading in long conversations | ✓ | ✓ | ~450 tokens per turn (en), ~700 (zh) |
| L3 self-check | A `Stop` hook checks the last reply; on a match it blocks the stop and returns, per pattern, the problem, the fix, and a bad/good example for one rewrite | | ✓ | one extra generation on a match; the user sees both replies |
| Monitoring | The hook logs each check (check ids only) to `.claude/decisive-mode.log`; `stats` summarizes rates | | ✓ | none |

Examples are delivered just in time: L2 carries only the compact rules, and L3 attaches examples only for the patterns that actually fired.

Mode precedence: env `DECISIVE_MODE` (`off|light|strict`) > `.claude/decisive-mode.on` > default `off`.
Language precedence: env `DECISIVE_LANG` (`en|zh`) > `"lang"` in `config.json` > `en`. Language selects only the injected rules and feedback; detection covers English and Chinese at all times.
Hooks are registered in `.claude/settings.json` and do nothing while the mode is `off`.

## Checks

Each can be enabled or tuned in `config.json`. Sentences that carry a number, code, a file name, or an explicit condition count as concrete and are exempt from the vagueness checks. Code blocks are not analyzed.

| id | Pattern | Legitimate when | Specific form |
|---|---|---|---|
| `deferral_ending` | Ends with "want me to…?", "let me know if…", "hope this helps" | The next step is irreversible, out of scope, or a matter of user preference | Name the action, its consequence, and why it needs confirming; end with the single most important open risk instead of a pleasantry |
| `hedge_density` | Dense "might / perhaps / possibly / 可能 / 也许" | Uncertainty remains after verification | Verified (evidence) / inferred (basis) / unknown (how to check), in one place |
| `disclaimer_stack` | ≥2 boilerplate caveats ("please note", "for informational purposes only") | A real risk exists | Risk + trigger + consequence + mitigation; for referrals, what exceeds your judgment and what to ask |
| `options_without_pick` | ≥2 options and no recommendation | The choice depends on information only the user has | Name the deciding variable, map values to options, give a default |
| `apology_preamble` | Opens with an apology | A real error was made | What was wrong, why, what changed, what it affects |
| `capability_hedge` | "I can't run / access / verify" | A real limitation exists | Try first; state done/verified/not; name the gap; hand off a minimal command and the output to return; deliver the partial result |
| `preemptive_negation` | "this doesn't mean…", "should not be understood as…", "not intended to…" | A specific misreading is likely | Say what it is; if needed, name the misreading and the correct reading |
| `vague_degree` | "to some extent", "in some cases", "relatively" | Never as is | A number, a range, or the condition under which it holds |
| `stacked_negation` | "haven't X, so I wouldn't Y", "not unlikely", "cannot rule out that it isn't" | Never as is | Fact state, conclusion, and verification as separate statements; litotes become a probability |

`preemptive_negation` fires on one strong phrase or two phrases total, because a single "doesn't mean" often corrects a real misconception ("exit code 0 doesn't mean the tests passed"). `deferral_ending` lets a question through when it names a concrete object and a consequence. `apology_preamble` and `capability_hedge` let the reply through when it states the cause or names the gap concretely.

## Design constraints (do not change)

- **Refusals are out of scope.** When `REFUSAL_GUARD` matches, the whole reply skips every check: safety refusals, declines, and policy explanations are never sent back. This skill trims padding; it must not be extended to bypass refusals or safety mechanisms.
- **Confirming high-risk actions is not defensive.** Irreversible, outward-facing, delete or overwrite actions warrant confirmation; the L3 feedback explicitly allows keeping it.
- **At most one rewrite per turn.** When `stop_hook_active` is true the hook lets the reply through, which prevents loops and leaves the final call to the agent.
- **Heuristics should miss rather than misfire.** A false positive costs a pointless extra generation.
- **The log holds no conversation content**, only a timestamp, session id, and check ids.
- **Examples must stay consistent.** Every bad example must trigger its check and every good example must trigger nothing, in both languages; the tests enforce this.

## Tuning

1. Run `mode strict` for a while.
2. Check `stats`. A check that fires often without improving replies: raise its threshold or disable it in `config.json`.
3. Reproduce specific replies with `check <file>` and adjust the patterns in `scripts/decisive.py`.
4. After changing patterns or messages, run `python3 -m unittest discover -s .claude/skills/decisive/tests`.
5. For style rules without extra generations, use `light`.

## Files and translation

- English is the original: `SKILL.md`, `rules.en.md`, `messages.json` → `en`.
- Chinese is a translation: `SKILL.zh.md`, `rules.zh.md`, `messages.json` → `zh`. Update English first, then the translation; the tests check that keys, placeholders, numbered rules, and sections stay aligned.
