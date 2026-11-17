import io
import json
import os
import re
import string
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import decisive as d  # noqa: E402

CFG = json.loads(Path(d.CONFIG_PATH).read_text(encoding="utf-8"))
CFG["log"] = False
MSGS = json.loads(Path(d.MESSAGES_PATH).read_text(encoding="utf-8"))


def ids(text):
    return {f.check for f in d.analyze(text, CFG)}


class ExampleConsistency(unittest.TestCase):
    """Every bad example must trigger its own check; every good example must trigger nothing."""

    def test_examples(self):
        for lang in d.LANGS:
            for check, m in MSGS[lang]["checks"].items():
                with self.subTest(lang=lang, check=check, kind="bad"):
                    self.assertIn(check, ids(m["bad"]))
                with self.subTest(lang=lang, check=check, kind="good"):
                    self.assertEqual(ids(m["good"]), set())


class TranslationParity(unittest.TestCase):
    def placeholders(self, s):
        return {f for _, f, _, _ in string.Formatter().parse(s) if f}

    def test_same_keys_and_placeholders(self):
        en, zh = MSGS["en"], MSGS["zh"]
        self.assertEqual(set(en), set(zh))
        self.assertEqual(set(en["labels"]), set(zh["labels"]))
        self.assertEqual(set(en["checks"]), set(zh["checks"]))
        self.assertEqual(set(en["checks"]), set(CFG["checks"]))
        for c in en["checks"]:
            self.assertEqual(set(en["checks"][c]), set(zh["checks"][c]), c)
            self.assertEqual(self.placeholders(en["checks"][c]["problem"]),
                             self.placeholders(zh["checks"][c]["problem"]), c)

    def test_rules_same_structure(self):
        en = d.rules_path("en").read_text(encoding="utf-8")
        zh = d.rules_path("zh").read_text(encoding="utf-8")
        num = lambda t: re.findall(r"^(\d+)\.", t, re.M)
        self.assertEqual(num(en), num(zh))

    def test_skill_docs_same_sections(self):
        en = (d.SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
        zh = (d.SKILL_DIR / "SKILL.zh.md").read_text(encoding="utf-8")
        heads = lambda t: len(re.findall(r"^#{1,3} ", t, re.M))
        self.assertEqual(heads(en), heads(zh))
        for c in CFG["checks"]:
            self.assertIn(f"`{c}`", en)
            self.assertIn(f"`{c}`", zh)


class AnalyzeTests(unittest.TestCase):
    def test_clean_reply_passes(self):
        self.assertEqual(ids("已修复 `parse()` 的越界问题，测试全部通过（12/12）。"), set())

    def test_deferral_only_in_tail(self):
        text = "你问要不要我改，我已经改好了。\n" + "\n".join(f"第{i}步完成。" for i in range(5))
        self.assertNotIn("deferral_ending", ids(text))

    def test_specific_confirmation_allowed(self):
        self.assertNotIn("deferral_ending", ids("需要我把 3 个提交 push 到 main 吗？这会覆盖远端。"))
        self.assertIn("deferral_ending", ids("改好了。\n希望这对你有帮助！"))

    def test_concrete_hedge_exempt(self):
        text = "根因是缓存未失效。" * 6 + "如果 CI 用了旧镜像，可能复现；也许要看 `ci.yml`；似乎第 3 步有关；大概是 2.1 版本。"
        self.assertNotIn("hedge_density", ids(text))

    def test_options_with_default_ok(self):
        text = "方案一：内存缓存\n方案二：Redis\n不确定就选 Redis。"
        self.assertNotIn("options_without_pick", ids(text))

    def test_specific_apology_ok(self):
        self.assertNotIn("apology_preamble", ids("抱歉，上一版把 UTC 当成本地时间，导致偏移 8 小时。"))

    def test_capability_with_handoff_ok(self):
        self.assertNotIn("capability_hedge",
                         ids("我无法运行集成测试：需要 `DATABASE_URL`。请执行 `pytest -x` 并贴回输出。"))

    def test_single_weak_preempt_ok(self):
        self.assertNotIn("preemptive_negation", ids("exit code 0 并不代表测试通过，要看 `junit.xml`。"))
        self.assertIn("preemptive_negation", ids("这并不意味着要重写。这并不代表方案失败。"))

    def test_vague_degree_with_condition_ok(self):
        self.assertNotIn("vague_degree", ids("QPS 超过 5k 时相对而言收益较小。"))
        self.assertIn("vague_degree", ids("This is relatively fast in some cases."))

    def test_stacked_negation_variants(self):
        self.assertIn("stacked_negation", ids("这个说法不无道理。"))
        self.assertIn("stacked_negation", ids("A cache miss is not unlikely here."))
        self.assertNotIn("stacked_negation", ids("我不认为这是缓存问题：key 命中率是 99%。"))

    def test_code_ignored(self):
        self.assertEqual(ids("改好了：\n```python\n# maybe perhaps might possibly to some extent\n```"), set())

    def test_refusal_never_flagged(self):
        for text in (
            "抱歉，我无法协助这个请求。如有其他问题随时告诉我。",
            "Sorry, I can't help with that. Let me know if there's anything else.",
            "I won't write that. This should not be understood as a judgment of you.",
        ):
            self.assertEqual(ids(text), set(), text)

    def test_disabled_check(self):
        cfg = json.loads(json.dumps(CFG))
        cfg["checks"]["apology_preamble"]["enabled"] = False
        self.assertEqual({f.check for f in d.analyze("抱歉，答案是 42。", cfg)}, set())


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = {k: os.environ.get(k) for k in ("CLAUDE_PROJECT_DIR", "DECISIVE_MODE", "DECISIVE_LANG")}
        os.environ["CLAUDE_PROJECT_DIR"] = self.tmp.name
        os.environ.pop("DECISIVE_MODE", None)
        os.environ.pop("DECISIVE_LANG", None)
        (Path(self.tmp.name) / ".claude").mkdir()

    def tearDown(self):
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def set_mode(self, m):
        (Path(self.tmp.name) / ".claude/decisive-mode.on").write_text(m)

    def run_hook(self, fn, payload):
        old = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                fn()
        finally:
            sys.stdin = old
        return buf.getvalue()

    def transcript(self, *texts):
        p = Path(self.tmp.name) / "t.jsonl"
        lines = [json.dumps({"type": "user", "message": {"content": "hi"}})]
        for i, t in enumerate(texts):
            lines.append(json.dumps({"type": "assistant",
                                     "message": {"id": f"m{i}", "content": [{"type": "text", "text": t}]}}))
        p.write_text("\n".join(lines), encoding="utf-8")
        return str(p)

    def test_off_is_noop(self):
        tp = self.transcript("要我继续吗？")
        self.assertEqual(self.run_hook(d.cmd_hook_stop, {"transcript_path": tp}), "")
        self.assertEqual(self.run_hook(d.cmd_hook_prompt, {}), "")

    def test_light_injects_but_no_stop(self):
        self.set_mode("light")
        self.assertIn("decisive mode", self.run_hook(d.cmd_hook_prompt, {}))
        tp = self.transcript("要我继续吗？")
        self.assertEqual(self.run_hook(d.cmd_hook_stop, {"transcript_path": tp}), "")

    def test_rules_follow_lang(self):
        self.set_mode("light")
        os.environ["DECISIVE_LANG"] = "zh"
        self.assertIn("已开启", self.run_hook(d.cmd_hook_prompt, {}))
        os.environ["DECISIVE_LANG"] = "en"
        self.assertIn("is on", self.run_hook(d.cmd_hook_prompt, {}))

    def test_strict_blocks_once_with_examples(self):
        self.set_mode("strict")
        os.environ["DECISIVE_LANG"] = "zh"
        tp = self.transcript("先看一下。", "找到原因了。\n要我修复吗？")
        out = json.loads(self.run_hook(d.cmd_hook_stop, {"transcript_path": tp}))
        self.assertEqual(out["decision"], "block")
        self.assertIn("deferral_ending", out["reason"])
        self.assertIn("改法", out["reason"])
        self.assertIn("✓", out["reason"])
        again = self.run_hook(d.cmd_hook_stop, {"transcript_path": tp, "stop_hook_active": True})
        self.assertEqual(again, "")

    def test_strict_feedback_english(self):
        self.set_mode("strict")
        os.environ["DECISIVE_LANG"] = "en"
        tp = self.transcript("It improves performance to some extent.")
        out = json.loads(self.run_hook(d.cmd_hook_stop, {"transcript_path": tp}))
        self.assertIn("unbounded degree words (1)", out["reason"])

    def test_strict_passes_clean_and_refusal(self):
        self.set_mode("strict")
        for t in ("修好了，测试通过。", "抱歉，我无法协助这个请求。"):
            tp = self.transcript(t)
            self.assertEqual(self.run_hook(d.cmd_hook_stop, {"transcript_path": tp}), "", t)

    def test_env_overrides_file(self):
        self.set_mode("strict")
        os.environ["DECISIVE_MODE"] = "off"
        self.assertEqual(d.current_mode(), "off")

    def test_split_message_merged(self):
        p = Path(self.tmp.name) / "s.jsonl"
        rows = [{"type": "assistant", "message": {"id": "x", "content": [{"type": "text", "text": "第一段"}]}},
                {"type": "assistant", "message": {"id": "x", "content": [{"type": "text", "text": "要我继续吗？"}]}}]
        p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
        self.assertEqual(d.last_assistant_text(p), "第一段\n要我继续吗？")


if __name__ == "__main__":
    unittest.main()
