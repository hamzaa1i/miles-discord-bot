"""
utils/ai_sanitize.py — PHASE N shared output-sanitization pipeline.

Extracted verbatim from utils/ai_handler.py (the FIX 1 / FIX 2 lineage) so
the multi-provider router can run EVERY provider's output through the exact
same protections before anything reaches Discord. One pipeline, one owner
of "what clean text looks like" — providers and router import from here.

Guarantees (Phase N Part 5 — no provider may bypass these):
  * <think>/<thinking> reasoning-tag stripping (incl. unterminated blocks)
  * untagged CoT / meta-reasoning preamble stripping
  * empty visible content detection (returns "" so the caller can fail over)
  * never returns None
  * Discord length protection (1900 chars + "...")

The CoT starter lists below are the live-tested ones from the Groq era —
they also catch Gemini/GLM/Mistral style leaks ("Here is the response...",
"The user says..."), which is why they live in the shared pipeline.
"""
import logging
import re

logger = logging.getLogger('cyn.ai')

# Canned reply used by the facade when every provider produced no visible
# text. Returned via the is_empty_content() protocol, not embedded here.
EMPTY_CONTENT_MARK = ""

DISCORD_CHAR_CAP = 1900

# ─── FIX 1 (live P0) — untagged CoT / meta-reasoning leak stripping ────

_COT_STARTERS = (
    "we need to",
    "we have a conversation",
    "the user says",
    "the developer says",
    "let's choose",
    "let me choose",
    "let's pick",
    "let me think",
    "thinking process",
    "here is the response",
    "here's the response",
    "here's a thinking process",
    "here's my thinking process",
)

_COT_PREAMBLE_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _COT_STARTERS) + r")"
    r".*?\n\n+",
    flags=re.DOTALL | re.IGNORECASE,
)

_COT_STARTER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _COT_STARTERS) + r")\b",
    flags=re.IGNORECASE,
)

# Edge-case guard: starters that COULD legitimately open a casual reply
# ("let me think about that ♡") vs. hard analysis starters. Used ONLY for
# the single-LINE no-answer case below.
_SOFT_COT_STARTERS = (
    "let's choose",
    "let me choose",
    "let's pick",
    "let me think",
)

_SOFT_STARTER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _SOFT_COT_STARTERS) + r")\b",
    flags=re.IGNORECASE,
)


def _looks_like_pure_reasoning(text: str) -> bool:
    """Is this single line analysis, not a reply?

    Pure-reasoning one-liners carry at least two of three signals:
      * an option-list / contract colon  (": ")
      * multi-sentence structure          (". ")
      * unusual length for a casual reply (> 100 chars)
    Plus the conclusive meta-analysis references ("the developer says",
    "we have a conversation") count as one signal each.
    """
    signals = 0
    if ": " in text:
        signals += 1
    if ". " in text:
        signals += 1
    if len(text) > 100:
        signals += 1
    lowered = text.lower()
    if "the developer says" in lowered or "we have a conversation" in lowered:
        signals += 1
    return signals >= 2


def strip_cot_preambles(content: str) -> str:
    """Remove untagged reasoning preambles from output.

    Legitimate replies that merely MENTION these phrases mid-text are
    untouched — only LEADING paragraphs are stripped.
    """
    if not content:
        return content

    content = content.strip()

    # 1. Drop leading reasoning paragraphs (blank-line separated).
    stripped_any = False
    for _ in range(5):
        new = _COT_PREAMBLE_RE.sub("", content, count=1)
        if new == content:
            break
        content = new
        stripped_any = True

    if not _COT_STARTER_RE.match(content):
        return content.strip()

    # 2. Reasoning + answer in ONE block (no blank line): keep only the
    #    final concise answer — last non-empty paragraph, else last line.
    paragraphs = [p for p in (s.strip() for s in content.split("\n\n")) if p]
    if len(paragraphs) > 1:
        if all(_COT_STARTER_RE.match(p) for p in paragraphs):
            return ""
        content = paragraphs[-1]
    else:
        # A single starter-led paragraph that survived the loop.
        if stripped_any:
            return ""
        lines = [l for l in (s.strip() for s in content.splitlines()) if l]
        if len(lines) > 1:
            content = lines[-1]
        elif (
            not _SOFT_STARTER_RE.match(content)
            and _looks_like_pure_reasoning(content)
        ):
            # Single LINE, hard analysis starter, reasoning-shaped:
            # pure reasoning with NO answer at all. Discard so the
            # caller-side empty-content failover kicks in.
            return ""

    return content.strip()


def strip_reasoning_tags(content: str) -> str:
    """Strip <think>/<thinking> blocks (incl. unterminated ones).

    Gemini thinking summaries, GLM thought blocks and Groq gpt-oss
    reasoning all arrive in (or leak into) these tag shapes.
    """
    if not content:
        return content
    content = re.sub(
        r'<think>.*?</think>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(
        r'<thinking>.*?</thinking>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Gemini thought summaries: <thought>...</thought>
    content = re.sub(
        r'<thought>.*?</thought>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Unterminated blocks — strip from the opener to the end of the string.
    if '<think>' in content.lower():
        content = re.sub(r'<think>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    if '<thinking>' in content.lower():
        content = re.sub(r'<thinking>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    if '<thought>' in content.lower():
        content = re.sub(r'<thought>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    return content


def is_empty_content(text: str) -> bool:
    """True when a provider result carries no visible content after
    sanitization — the router treats this as an EMPTY_RESPONSE failure
    and fails over to the next provider."""
    return not (text or "").strip()


def sanitize_output(content: str) -> str:
    """FULL final pipeline — identical to the legacy _extract_content
    guarantees, minus provider-specific field juggling.

    Returns "" (empty string) when no visible content survived, so the
    router can fail over; the facade turns a final "" into the legacy
    canned fallback. NEVER returns None.
    """
    try:
        if not content:
            return EMPTY_CONTENT_MARK
        content = str(content)

        content = strip_reasoning_tags(content)
        content = strip_cot_preambles(content)
        content = (content or "").strip()

        if not content:
            return EMPTY_CONTENT_MARK

        # Cap for Discord's 2000-char message limit.
        if len(content) > DISCORD_CHAR_CAP:
            content = content[:DISCORD_CHAR_CAP] + "..."

        return content
    except Exception as e:
        logger.error(f"[sanitize_output] {type(e).__name__}: {e}")
        return EMPTY_CONTENT_MARK
