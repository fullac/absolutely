#!/usr/bin/env python3
"""decisive mode: mechanical layer for cutting padded, defensive phrasing.

Subcommands:
  mode [on|light|strict|off|status]   switch/show mode (stored in .claude/decisive-mode.on)
  lang [en|zh]                        switch/show output language (stored in config.json)
  hook-prompt                         UserPromptSubmit hook: inject rules.<lang>.md
  hook-stop                           Stop hook: check the last reply; on a match, ask for one rewrite
  check [FILE|-] [--transcript PATH]  check a text or the last reply of a transcript offline
  stats                               summarize the hook log (check ids only, no conversation content)

Detection covers English and Chinese regardless of `lang`; `lang` only picks the
language of injected rules and feedback. Standard library only. Every check is a
heuristic tuned to miss rather than to flag specific, warranted statements.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = SKILL_DIR / "config.json"
MESSAGES_PATH = SKILL_DIR / "messages.json"
MODES = ("off", "light", "strict")
LANGS = ("en", "zh")
CODE = "‹code›"  # placeholder left where code was stripped; counts as a concrete reference


# ---------------------------------------------------------------- config / state

def project_dir() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def state_path() -> Path:
    return project_dir() / ".claude" / "decisive-mode.on"


def log_path() -> Path:
    return project_dir() / ".claude" / "decisive-mode.log"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"checks": {}, "log": False, "lang": "en"}


def current_mode() -> str:
    env = os.environ.get("DECISIVE_MODE", "").strip().lower()
    if env in ("0", "off"):
        return "off"
    if env in ("light", "strict"):
        return env
    p = state_path()
    if p.exists():
        v = p.read_text(encoding="utf-8").strip().lower()
        return v if v in ("light", "strict") else "strict"
    return "off"


def current_lang(config: dict | None = None) -> str:
    env = os.environ.get("DECISIVE_LANG", "").strip().lower()
    if env in LANGS:
        return env
    lang = (config if config is not None else load_config()).get("lang", "en")
    return lang if lang in LANGS else "en"


def load_messages(lang: str) -> dict:
    try:
        data = json.loads(MESSAGES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data.get(lang) or data.get("en") or {}


def rules_path(lang: str) -> Path:
    return SKILL_DIR / f"rules.{lang}.md"


# ---------------------------------------------------------------- patterns

# Refusals and declines: if matched, the whole reply is skipped.
# This skill trims padding only; it never sends a refusal back for rewriting.
# Hard boundary - do not remove.
REFUSAL_GUARD = re.compile(
    r"\bI (?:can(?:no|')?t|won'?t|will not|am not able to|'m not able to|am unable to|'m unable to)"
    r" (?:help|assist|provide|support|do that|do this|write|create|comply)"
    r"|\bI(?:'m| am) not going to (?:help|assist|do|write|provide)"
    r"|\b(?:I have to|I must|I'll|I will) decline\b"
    r"|against (?:my|the|our) (?:guidelines|policies|policy|usage polic)"
    r"|(?:无法|不能|不会|没法)(?:协助|帮助|帮你|帮忙|提供|完成|参与)"
    r"|我(?:必须|只能|需要)?(?:拒绝|婉拒)"
    r"|(?:违反|不符合)[^。\n]{0,12}(?:政策|规定|准则|边界)",
    re.IGNORECASE,
)

# A sentence counts as concrete if it carries a number, code, file, or explicit condition.
CONCRETE = re.compile(
    CODE + r"|\d|%|[<>≤≥]|[\w-]+\.(?:py|js|ts|tsx|json|md|ya?ml|toml|sh|go|rs|java|log|txt|cfg|ini)\b"
    r"|\b(?:when|if|unless)\b|当|如果|若|只要|除非|超过|低于|高于|少于|大于|小于",
    re.IGNORECASE,
)

ASK = re.compile(
    r"\b(?:should I|shall I|do you want me to|would you like me to|want me to)\b"
    r"|要我|需要我|是否需要|要不要我|我是否应该|是否要我|如果你(?:需要|愿意|希望)[，,]?我(?:可以|再)",
    re.IGNORECASE,
)
FILLER = re.compile(
    r"\b(?:let me know if|feel free to|hope this helps|happy to help)\b"
    r"|如有(?:任何)?(?:问题|需要)|随时(?:告诉|联系|找)我|希望(?:这|以上|这些)[^。\n]{0,6}(?:有|对你有)(?:所)?帮助",
    re.IGNORECASE,
)
CONSEQUENCE = re.compile(
    r"\b(?:will|would|overwrites?|deletes?|irreversible|because|publish|push|deploy)\b"
    r"|会|将|导致|覆盖|删除|不可逆|无法恢复|发布|推送|部署|因为",
    re.IGNORECASE,
)

HEDGES_EN = re.compile(
    r"\b(?:might|perhaps|possibly|maybe|it seems|it appears|I think|I believe|"
    r"could potentially|may or may not|generally speaking|arguably|I'm not (?:entirely )?sure)\b",
    re.IGNORECASE,
)
HEDGES_ZH = re.compile(r"可能|也许|或许|似乎|大概|好像|一般来说|不一定|未必|我觉得|我认为")

DISCLAIMERS = re.compile(
    r"\b(?:please note|it'?s (?:important|worth) (?:to note|noting)|keep in mind|"
    r"I'?m not an? (?:lawyer|doctor|financial advisor|professional|expert)|"
    r"consult (?:with )?(?:a|an|your) (?:professional|expert|lawyer|doctor|specialist)|"
    r"use (?:it )?at your own risk|for (?:educational|informational) purposes only|disclaimer)\b"
    r"|请注意|需要注意的是|值得注意的是|免责声明|仅供参考|(?:建议|请)咨询专业|风险自负|务必谨慎|请谨慎",
    re.IGNORECASE,
)

OPTION_MARKER = re.compile(
    r"^[ \t>*\-#]*(?:\*\*)?(?:Option|Approach|Alternative|方案|选项|做法|思路)\s*"
    r"(?:[A-Za-z0-9]|[一二三四五六七八九十])",
    re.IGNORECASE | re.MULTILINE,
)
RECOMMENDATION = re.compile(
    r"\b(?:recommend|I'?d (?:go with|pick|choose|use)|I suggest|best (?:choice|option|fit)|go with|"
    r"by default|default to|if unsure)\b"
    r"|推荐|建议(?:选|用|采用|走)|我(?:会|倾向于?)(?:选|用)|首选|优先(?:选|用|考虑)|默认(?:选|用)|不确定(?:就|的话)(?:选|用)",
    re.IGNORECASE,
)

APOLOGY = re.compile(r"\b(?:sorry|apologi[sz]e)\b|抱歉|对不起|不好意思", re.IGNORECASE)
ERROR_CAUSE = re.compile(
    r"\b(?:because|caused|treated|mistook|was wrong|bug)\b|因为|由于|导致|错在|当成|写成|误把",
    re.IGNORECASE,
)

CAPABILITY_HEDGE = re.compile(
    r"\bI (?:don'?t|do not) have (?:access|the ability)\b"
    r"|\bI(?:'m| am)? ?(?:unable to|can(?:no|')?t) (?:run|execute|browse|access|verify|check|test|open)\b"
    r"|我(?:无法|不能|没法)(?:运行|执行|访问|验证|查看|测试|打开)|我没有(?:权限|能力|办法)(?:访问|运行|执行|查看)",
    re.IGNORECASE,
)
LACK = re.compile(r"\b(?:needs?|requires?|missing|lacks?|without)\b|缺|需要|未配置|没有配置", re.IGNORECASE)

PREEMPT_STRONG = re.compile(
    r"\b(?:should not|shouldn't|must not) be (?:understood|interpreted|read|taken|seen|construed) as\b"
    r"|\b(?:is not|isn't) (?:meant|intended|trying|an attempt) to\b"
    r"|\bI(?:'m| am) not (?:saying|suggesting|implying)\b"
    r"|\b(?:this|that|it) is not to say\b|\bnot to say that\b"
    r"|不应(?:该)?被?(?:理解|解读|视|看作|认为)为?|并非(?:试图|要|旨在|意在)|并不是(?:说|要|试图)"
    r"|我(?:并)?不是(?:说|要说|在说)|不是要说|无意(?:暗示|表示|贬低)",
    re.IGNORECASE,
)
PREEMPT_WEAK = re.compile(
    r"\b(?:this|that|it) (?:does not|doesn't) (?:mean|imply|suggest)\b|\b(?:does not|doesn't) necessarily\b"
    r"|并不意味着|并不代表|这不代表|不一定意味着|并不等于",
    re.IGNORECASE,
)

VAGUE_DEGREE = re.compile(
    r"\bto (?:some|a certain|a large|a great|a lesser) (?:extent|degree)\b"
    r"|\bin (?:some|certain) (?:cases|situations|circumstances|scenarios)\b"
    r"|\bunder certain conditions\b|\brelatively\b|\bsomewhat\b|\bfairly\b|\bmore or less\b"
    r"|一定程度上|某种程度上|在很大程度上|(?:某些|一些|特定|部分)(?:情况|场景|条件|场合)下?|相对(?:而言|来说)|较为|或多或少|多少有些",
    re.IGNORECASE,
)

STACKED_NEGATION = [
    re.compile(
        r"\b(?:not yet|haven'?t|hasn'?t|have not|has not)\b[^.\n]{0,80}\b(?:so|therefore|thus|hence)\b"
        r"[^.\n]{0,40}\b(?:not|won'?t|wouldn'?t|can'?t|cannot)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcan(?:no|')?t rule out\b[^.\n]{0,40}\bnot\b", re.IGNORECASE),
    re.compile(
        r"\bnot (?:unlike|unlikely|uncommon|unreasonable|unimportant|insignificant|impossible|irrelevant|without)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bI (?:wouldn'?t|would not) (?:say|think|consider|assume|conclude)\b", re.IGNORECASE),
    re.compile(r"(?:尚未|还没有?|没有|未)[^。！？\n]{0,40}(?:因此|所以|故而?|因而)[^。！？\n]{0,15}(?:不|无法|没法|未必)"),
    re.compile(r"不(?:能|可)排除[^。！？\n]{0,15}(?:不|没|非|未)"),
    re.compile(r"并非不|不无|不是没有|未必不|不可能不|不能不说|并不是不"),
    re.compile(r"我(?:不会|不太|并不会)(?:认为|觉得|说|断定)"),
]


# ---------------------------------------------------------------- analysis

@dataclass
class Finding:
    check: str
    evidence: str
    params: dict = field(default_factory=dict)


def strip_code(text: str) -> str:
    text = re.sub(r"```.*?```", f" {CODE} ", text, flags=re.DOTALL)
    return re.sub(r"`[^`\n]*`", f" {CODE} ", text)


def sentences(body: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])|\n+|(?<=\.)\s+", body)
    return [p.strip() for p in parts if p and p.strip()]


def text_units(text: str) -> float:
    """Rough word count: English words, plus Chinese characters at two per word."""
    return len(re.findall(r"[A-Za-z]+", text)) + len(re.findall(r"[一-鿿]", text)) / 2


def _uniq(items) -> str:
    return ", ".join(dict.fromkeys(items))


def analyze(text: str, config: dict | None = None) -> list[Finding]:
    config = config if config is not None else load_config()
    checks = config.get("checks", {})

    def on(name: str) -> dict | None:
        c = checks.get(name, {"enabled": True})
        return c if c.get("enabled", True) else None

    if not text or not text.strip():
        return []
    body = strip_code(text)
    if REFUSAL_GUARD.search(body):
        return []

    sents = sentences(body)
    vague_sents = [s for s in sents if not CONCRETE.search(s)]
    out: list[Finding] = []

    if (c := on("deferral_ending")) is not None:
        lines = [ln for ln in body.splitlines() if ln.strip()]
        tail = " ".join(lines[-c.get("tail_lines", 2):])[-300:]
        if m := FILLER.search(tail):
            out.append(Finding("deferral_ending", m.group(0)))
        elif (m := ASK.search(tail)) and not (CONCRETE.search(tail) and CONSEQUENCE.search(tail)):
            out.append(Finding("deferral_ending", m.group(0)))

    if (c := on("hedge_density")) is not None:
        hits = [h for s in vague_sents for h in HEDGES_EN.findall(s) + HEDGES_ZH.findall(s)]
        density = len(hits) * 100 / max(text_units(body), 1.0)
        if len(hits) >= c.get("min_count", 4) and density >= c.get("per_100_units", 2.5):
            out.append(Finding("hedge_density", _uniq(hits[:6]), {"n": len(hits), "density": density}))

    if (c := on("disclaimer_stack")) is not None:
        hits = [h for s in vague_sents for h in DISCLAIMERS.findall(s)]
        if len(hits) >= c.get("min_count", 2):
            out.append(Finding("disclaimer_stack", _uniq(hits[:4]), {"n": len(hits)}))

    if (c := on("options_without_pick")) is not None:
        n = len(OPTION_MARKER.findall(body))
        if n >= c.get("min_options", 2) and not RECOMMENDATION.search(body):
            out.append(Finding("options_without_pick", f"{n} options", {"n": n}))

    if on("apology_preamble") is not None:
        head = body[:200]
        if (m := APOLOGY.search(body[:120])) and not (CONCRETE.search(head) and ERROR_CAUSE.search(head)):
            out.append(Finding("apology_preamble", m.group(0)))

    if on("capability_hedge") is not None:
        if m := CAPABILITY_HEDGE.search(body):
            window = body[max(0, m.start() - 150): m.end() + 150]
            if not (CONCRETE.search(window) and LACK.search(window)):
                out.append(Finding("capability_hedge", m.group(0)))

    if (c := on("preemptive_negation")) is not None:
        strong, weak = PREEMPT_STRONG.findall(body), PREEMPT_WEAK.findall(body)
        if len(strong) >= c.get("strong_min", 1) or len(strong) + len(weak) >= c.get("total_min", 2):
            out.append(Finding("preemptive_negation", _uniq((strong + weak)[:4])))

    if (c := on("vague_degree")) is not None:
        hits = [h for s in vague_sents for h in VAGUE_DEGREE.findall(s)]
        if len(hits) >= c.get("min_count", 1):
            out.append(Finding("vague_degree", _uniq(hits[:4]), {"n": len(hits)}))

    if on("stacked_negation") is not None:
        hits = [m.group(0) for p in STACKED_NEGATION for m in p.finditer(body)]
        if hits:
            out.append(Finding("stacked_negation", _uniq(h[:40] for h in hits[:3])))

    return out


def render(findings: list[Finding], lang: str) -> list[dict]:
    msgs = load_messages(lang).get("checks", {})
    rendered = []
    for f in findings:
        m = msgs.get(f.check, {})
        rendered.append({
            "check": f.check,
            "problem": m.get("problem", f.check).format(**f.params),
            "fix": m.get("fix", ""),
            "bad": m.get("bad", ""),
            "good": m.get("good", ""),
            "evidence": f.evidence,
        })
    return rendered


def feedback(findings: list[Finding], lang: str) -> str:
    msgs = load_messages(lang)
    lab = msgs.get("labels", {})
    blocks = []
    for r in render(findings, lang):
        blocks.append(
            f"- [{r['check']}] {r['problem']} ({lab.get('matched', 'matched')}: {r['evidence']})\n"
            f"  {lab.get('fix', 'Fix')}: {r['fix']}\n"
            f"  ✗ {r['bad']}\n"
            f"  ✓ {r['good']}"
        )
    return f"{msgs.get('header', '')}\n" + "\n".join(blocks) + f"\n{msgs.get('footer', '')}"


# ---------------------------------------------------------------- transcript

def last_assistant_text(transcript: str | os.PathLike) -> str:
    """Last assistant message with text in a JSONL transcript; chunks sharing a message.id are merged."""
    last_id, parts = None, []
    try:
        fh = open(transcript, encoding="utf-8", errors="replace")
    except OSError:
        return ""
    with fh:
        for line in fh:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("type") != "assistant":
                continue
            msg = e.get("message") or {}
            content = msg.get("content")
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                texts = [b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text"]
            else:
                texts = []
            t = "\n".join(x for x in texts if x.strip())
            if not t:
                continue
            mid = msg.get("id")
            if mid is not None and mid == last_id:
                parts.append(t)
            else:
                last_id, parts = mid, [t]
    return "\n".join(parts)


# ---------------------------------------------------------------- log

def write_log(session: str | None, findings: list[Finding], action: str) -> None:
    if not load_config().get("log", False):
        return
    rec = {"ts": int(time.time()), "session": session, "action": action,
           "checks": [f.check for f in findings]}  # check ids only; no conversation content
    try:
        with open(log_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- subcommands

def cmd_mode(args: list[str]) -> int:
    if not args or args[0] == "status":
        src = "env DECISIVE_MODE" if os.environ.get("DECISIVE_MODE") else str(state_path())
        print(f"decisive mode: {current_mode()}  lang: {current_lang()}  (source: {src})")
        return 0
    want = {"on": "strict"}.get(args[0], args[0])
    if want not in MODES:
        print(f"unknown mode {args[0]!r}; use on|light|strict|off|status", file=sys.stderr)
        return 2
    p = state_path()
    if want == "off":
        p.unlink(missing_ok=True)
    else:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(want + "\n", encoding="utf-8")
    print(f"decisive mode -> {want}")
    return 0


def cmd_lang(args: list[str]) -> int:
    if not args:
        print(f"decisive lang: {current_lang()}")
        return 0
    if args[0] not in LANGS:
        print(f"unknown lang {args[0]!r}; use {'|'.join(LANGS)}", file=sys.stderr)
        return 2
    cfg = load_config()
    cfg["lang"] = args[0]
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"decisive lang -> {args[0]}")
    return 0


def read_hook_input() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return {}


def cmd_hook_prompt() -> int:
    read_hook_input()
    if current_mode() == "off":
        return 0
    try:
        print(rules_path(current_lang()).read_text(encoding="utf-8").strip())
    except OSError:
        pass
    return 0


def cmd_hook_stop() -> int:
    data = read_hook_input()
    if current_mode() != "strict":
        return 0
    # At most one rewrite per turn: prevents loops and leaves the final call on
    # "this item is warranted" to the agent.
    if data.get("stop_hook_active"):
        return 0
    text = data.get("last_assistant_message") or ""
    if not text and data.get("transcript_path"):
        text = last_assistant_text(data["transcript_path"])
    config = load_config()
    findings = analyze(text, config)
    sid = data.get("session_id")
    if not findings:
        write_log(sid, findings, "pass")
        return 0
    write_log(sid, findings, "block")
    reason = feedback(findings, current_lang(config))
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


def cmd_check(args: list[str]) -> int:
    if "--transcript" in args:
        text = last_assistant_text(args[args.index("--transcript") + 1])
    elif args and args[0] != "-":
        text = Path(args[0]).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()
    config = load_config()
    findings = analyze(text, config)
    print(json.dumps(render(findings, current_lang(config)), ensure_ascii=False, indent=2))
    return 1 if findings else 0


def cmd_stats() -> int:
    p = log_path()
    if not p.exists():
        print("no log yet")
        return 0
    total = blocked = 0
    per: dict[str, int] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        total += 1
        if r.get("action") == "block":
            blocked += 1
        for c in r.get("checks", []):
            per[c] = per.get(c, 0) + 1
    rate = blocked / total * 100 if total else 0
    print(f"evaluated: {total}  flagged: {blocked} ({rate:.1f}%)")
    for c, n in sorted(per.items(), key=lambda kv: -kv[1]):
        print(f"  {c:22s} {n}")
    return 0


COMMANDS = {
    "mode": lambda a: cmd_mode(a),
    "lang": lambda a: cmd_lang(a),
    "hook-prompt": lambda a: cmd_hook_prompt(),
    "hook-stop": lambda a: cmd_hook_stop(),
    "check": lambda a: cmd_check(a),
    "stats": lambda a: cmd_stats(),
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in COMMANDS:
        print(__doc__)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
