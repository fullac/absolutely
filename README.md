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

## The nine patterns

Defensive phrasing is wording that protects the writer rather than informing the reader. Test: delete the sentence. If the reader loses no information, it is defensive.

Most of these patterns have a legitimate form. Each check targets the vague form and lets the specific form through. A sentence that carries a number, code, a file name, or an explicit condition counts as specific. Code blocks are not analyzed, and refusals skip every check.

| Category | Checks | What goes wrong |
|---|---|---|
| Deferring | `deferral_ending`, `options_without_pick`, `capability_hedge` | Work or decisions are pushed back to the user |
| Vagueness | `hedge_density`, `vague_degree` | The claim can't be wrong, so it carries no information |
| Posturing | `disclaimer_stack`, `apology_preamble` | Attitude takes the place of content |
| Convolution | `preemptive_negation`, `stacked_negation` | The reader has to unwind the sentence to find the claim |

The examples below are the ones the `Stop` hook sends back; the tests check that each ✗ triggers its check and each ✓ triggers nothing.

### Deferring

**`deferral_ending`: ending with a request for permission or a pleasantry**
- **Why it's defensive:** a reversible, in-scope step is handed back to the user, or the reply ends on words that carry no information.
- **Flagged when:** the last two lines contain a request ("want me to…", "should I…") or a pleasantry ("let me know if…", "hope this helps").
- **Allowed when:** the question names a concrete object and its consequence.
- ✗ Want me to continue?
- ✓ Next step is `git push --force` to main, which overwrites 3 remote commits. I'll run it once you confirm.

**`options_without_pick`: listing options without a recommendation**
- **Why it's defensive:** it avoids a judgment and shifts the cost of deciding to the user.
- **Flagged when:** two or more lines start with "Option", "Approach", or "Alternative", and the reply contains no recommendation.
- **Allowed when:** the reply recommends one, gives a default, or says what to pick if unsure.
- ✗ Option A: Redis, pros… cons… / Option B: in-memory cache, pros… cons…
- ✓ It hinges on multi-instance deployment: single instance, use the in-memory cache; multiple instances, use Redis. If unsure, pick Redis; migrating later costs more.

**`capability_hedge`: "I can't run / access / verify this"**
- **Why it's defensive:** it declares a limit without trying or saying what is missing.
- **Flagged when:** the reply says it can't run, execute, access, verify, check, test, or open something.
- **Allowed when:** the surrounding text names a concrete gap, such as a missing variable, file, or command.
- ✗ I can't run this code; you can try it yourself.
- ✓ Unit tests pass (12/12). Integration tests need `DATABASE_URL`, which this environment lacks. Run `pytest tests/integration -x` and paste the first failure.

### Vagueness

**`hedge_density`: hedges scattered through the reply**
- **Why it's defensive:** "possibly X" is true whatever happens, so it says nothing, and it stands in for verification.
- **Flagged when:** vague sentences contain at least 4 hedges ("might", "perhaps", "possibly") at 2.5 or more per 100 words.
- **Allowed when:** the hedge sits in a specific sentence; those are not counted.
- ✗ It might be a cache issue, possibly config, perhaps a version mismatch; maybe reinstall.
- ✓ Root cause: stale cache. Every request after 14:02 hits the old key (`app.log:88`). Unverified: whether CI shares the same Redis; compare `run_id` from `redis-cli info server` to check.

**`vague_degree`: degree words with no bound**
- **Why it's defensive:** a degree with no size or condition can't be wrong.
- **Flagged when:** "to some extent", "in some cases", "relatively", "somewhat", and similar appear in a sentence with no number or condition.
- **Allowed when:** the same sentence gives a number, a range, or a condition.
- ✗ It improves performance to some extent.
- ✓ Below 1k QPS, p99 latency drops by about 30%; above 5k the bottleneck moves to the database and the gain disappears.

### Posturing

**`disclaimer_stack`: stacked boilerplate caveats**
- **Why it's defensive:** a caveat that names no risk protects the writer, not the reader.
- **Flagged when:** vague sentences contain two or more boilerplate caveats ("please note", "for informational purposes only", "consult a professional").
- **Allowed when:** the caveat names a trigger, a command, or a number.
- ✗ Please note: this is for informational purposes only; use at your own risk.
- ✓ `rm -rf "$DIR/"` deletes the root directory if `DIR` is empty. Add `: "${DIR:?}"` first.

**`apology_preamble`: opening with an apology**
- **Why it's defensive:** it is a gesture with no content.
- **Flagged when:** an apology appears in the first 120 characters.
- **Allowed when:** the opening states what was wrong and why, concretely.
- ✗ Sorry for the confusion in my previous answer.
- ✓ The last version treated UTC as local time, shifting results by 8 hours. Fixed with `datetime.now(timezone.utc)`; only `export()` was affected.

### Convolution

**`preemptive_negation`: rebutting a reading nobody proposed**
- **Why it's defensive:** the reader has to build the misreading in their head and then discard it.
- **Flagged when:** one strong phrase appears ("should not be understood as", "not intended to", "I'm not saying"), or two weak ones ("this doesn't mean", "doesn't necessarily").
- **Allowed when:** a single weak phrase appears, since it often corrects a real misconception ("exit code 0 doesn't mean the tests passed").
- ✗ This should not be understood as saying unit tests are useless.
- ✓ Unit tests are still the fastest way to pin down logic errors; what they miss is cross-service timing.

**`stacked_negation`: layered negation or stance-talk**
- **Why it's defensive:** the conclusion is hidden behind negations, and "I wouldn't say" reports the writer's stance instead of the fact.
- **Flagged when:** "haven't X, so … not Y", "not unlikely", "can't rule out that it isn't", or "I wouldn't say / think / assume".
- **Allowed when:** the reply states a direct claim with evidence, such as "I don't think it's the cache: the hit rate is 99%".
- ✗ We haven't load-tested yet, so I wouldn't assume it handles high concurrency.
- ✓ Not load-tested; concurrency capacity is unknown. `wrk -c 1000 -d 30s` will measure it.

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
