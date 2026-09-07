"""
utils/ai_sanitize.py — PHASE N.1 hardened output-sanitization pipeline.

One pipeline, one owner of "what clean text looks like" — providers and
the router import from here. EVERY provider's output runs through the
exact same protections before anything reaches Discord, and the facade
runs a second-pass guard on top (defense in depth, Part 5).

Layered architecture (Phase N.1 Part 4):

  1. strip_reasoning_tags — explicit <thinking>/<thought>/<reasoning>
     block removal, incl. unterminated blocks.
  2. strip_cot_preambles — LEADING meta-reasoning removal:
       a. leading META PARAGRAPHS are dropped (blank-line separated,
          repeatedly) when they are meta-headed AND corroborated
          (instruction references / meta-signal density);
       b. inside the first surviving block, meta SENTENCES are dropped
          (provider reasoning and the answer often share one paragraph
          with no blank line between them — and can interleave);
       c. paragraphs/sentences that merely MENTION these phrases while
          carrying real content are untouched (case C);
       d. soft conversational openers ("let me think about that ♡")
          survive (case E);
       e. nothing left after stripping -> "" so the router fails over
          (cases B / H — meta-only output is a FAILURE, Part 6).
  3. is_meta_reasoning_text — conservative high-confidence detector used
     as the FINAL OUTPUT GUARD (facade boundary, Part 5): text that
     still references instructions / response rules after the full
     pipeline is treated as leaked planning language.
  4. is_empty_content — "" detection so the router can fail over.
  5. Discord length protection (1900 chars + "...").

Regression corpus (scripts/test_phase_n1.py):
  A  meta preamble + clean answer            -> answer preserved
  B  meta-only GLM output                    -> EMPTY -> failover
  C  "we should probably use websockets ..." -> PRESERVED (real prose)
  D  "the user wants ..." preamble           -> answer preserved
  E  "let me think about that ♡"             -> preserved (casual)
  F  tagged reasoning                        -> stripped
  G  reasoning+answer, no blank line         -> extracted or failover
  H  exact GLM string leaked in production   -> sanitized to EMPTY
"""
import logging
import re

logger = logging.getLogger('cyn.ai')

# Canned reply used by the facade when every provider produced no visible
# text. Returned via the is_empty_content() protocol, not embedded here.
EMPTY_CONTENT_MARK = ""

DISCORD_CHAR_CAP = 1900

# ─── Phase N.1 Part 4 — meta-reasoning vocabulary ───────────────────
#
# HARD starters: phrases that, when they OPEN a paragraph or sentence,
# mark provider-side planning / instruction analysis. The leak that hit
# production ("We must not start two responses with same word ...")
# contains NONE of the old Phase N starters — this table closes that
# whole family (we must / we should / we need / i need to / the system
# says / let's formulate / provide the answer / ...).
_META_STARTERS = (
    # first-person plural planning
    "we must", "we must not", "we should", "we should not", "we need",
    "we need to", "we have to", "we want to", "we need ensure",
    "we need make sure",
    # first-person singular planning
    "i need to", "i need", "i should", "i must", "i must not",
    "i should not", "i will not mention",
    # bare need-construction
    "need to answer", "need respond", "need produce", "need to respond",
    "need to produce", "need to make sure", "need to ensure",
    # modal-negation about the response
    "must not mention", "must not say", "must not reveal", "must not start",
    "should not mention", "should not say", "should not reveal",
    "should not start", "should not use", "cannot mention", "can't mention",
    "don't mention", "do not mention",
    # instruction references
    "the system says", "the system message", "the system prompt",
    "the developer says", "the developer instructed", "the developer wants",
    "the instructions say", "the instructions", "the instruction says",
    "the prompt says", "the rules say", "as per instructions",
    "according to the instructions", "per the instructions",
    "following the instructions",
    # user-reference analysis
    "the user says", "the user wants", "the user asks",
    "the user is asking",
    # answer-construction language
    "let's formulate", "let's craft", "let's answer", "let's respond",
    "let's produce", "let's write", "let me formulate", "let me craft",
    "let's provide", "provide the answer", "response should",
    "final answer should", "the assistant should", "the reply should",
    "my response should", "the answer should",
    # legacy live-tested starters (Groq era, kept)
    "we have a conversation", "thinking process", "here is the response",
    "here's the response", "here's a thinking process",
    "here's my thinking process", "here is the answer", "here's the answer",
    "here's my answer", "here is my response", "here's my response",
)

# SOFT starters: could legitimately open a casual reply — never dropped
# on their own (case E: "let me think about that ♡").
_SOFT_COT_STARTERS = (
    "let's choose", "let me choose", "let's pick", "let me pick",
    "let me think", "let's see", "hmm, let me",
)

# STRONG instruction references — unambiguous proof of instruction
# analysis. Used for corroboration AND for the final guard. Deliberately
# compound phrases only: bare "the system"/"the user" would false-positive
# on ordinary prose ("the system in this game", "the user said hi").
_STRONG_INSTRUCTION_REFS = (
    "the system says", "the system message", "the system prompt",
    "the system instructed", "the developer says", "the developer wants",
    "the developer instructed", "the instructions say",
    "the instruction says", "the rules say", "the prompt says",
    "as per instructions", "according to the instructions",
    "per the instructions", "following the instructions",
    "the user says", "the user wants", "the user asks",
    "the user is asking", "my instructions", "the guidelines say",
    "the persona says", "the character card",
)

# Broad instruction-ish references — only trusted as corroboration on
# text that is ALREADY meta-headed (weak starters never trigger these).
_BROAD_INSTRUCTION_REFS = _STRONG_INSTRUCTION_REFS + (
    "the creator", "mention creator", "reveal the creator",
)

# Meta-signal phrases — counted for DENSITY (a leading meta-headed block
# needs >= 2 distinct signals before it is treated as analysis).
_META_SIGNALS = (
    "we must", "we should", "we need", "we have to", "i need to",
    "i should", "i must", "must not", "should not", "cannot mention",
    "don't mention", "do not mention", "let's formulate", "let's craft",
    "let's respond", "let's produce", "let's answer", "let's write",
    "let me formulate", "let me craft", "provide the answer",
    "two responses", "same word", "keep it short", "keep it brief",
    "under moderate length", "as an ai", "the creator", "real-time data",
    "final answer should", "the assistant should",
    "need to answer", "need respond", "need produce",
    "the user says", "the user wants", "the user asks",
    "the developer says", "the system says", "the system prompt",
    "the prompt says", "the instructions say", "the rules say",
    "per the instructions", "as per instructions",
)

_META_STARTER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _META_STARTERS) + r")\b",
    flags=re.IGNORECASE,
)
_SOFT_STARTER_RE = re.compile(
    r"^(?:" + "|".join(re.escape(s) for s in _SOFT_COT_STARTERS) + r")\b",
    flags=re.IGNORECASE,
)

# sentence split: terminator + whitespace, or a newline. Semicolons
# count — the production GLM leak chains clauses with them.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;])\s+|\n+")

# planning-word vocabulary for the informative-tail check
_PLANNING_WORDS = frozenset((
    "the", "a", "an", "to", "be", "is", "are", "it", "that", "this",
    "we", "i", "you", "our", "my", "me", "and", "or", "not", "should",
    "must", "need", "want", "keep", "short", "brief", "moderate",
    "length", "answer", "response", "reply", "mention", "say", "use",
    "start", "word", "responses", "two", "one", "now", "okay", "with",
    "under", "maybe", "creator", "asked", "unless", "provide", "same",
    "have", "only", "real", "time", "data", "ai", "as", "an", "about",
    # response-formatting vocabulary (Phase N.1: the production GLM
    # leak's tail — "multiple paragraphs", "keep lowercase", "no
    # restriction on length")
    "paragraphs", "paragraph", "lowercase", "restriction",
    "restrictions", "multiple", "include", "points", "technical",
))


def _count_meta_signals(text_lower: str) -> int:
    """Distinct meta-signal phrases present in the text."""
    hits = 0
    for sig in _META_SIGNALS:
        if sig in text_lower:
            hits += 1
    return hits


def _has_strong_instruction_ref(text_lower: str) -> bool:
    return any(ref in text_lower for ref in _STRONG_INSTRUCTION_REFS)


def _has_broad_instruction_ref(text_lower: str) -> bool:
    return any(ref in text_lower for ref in _BROAD_INSTRUCTION_REFS)


def _has_informative_tail(sentence: str) -> bool:
    """Does the sentence carry domain-ish content AFTER the meta opening?
    Planning fragments ("We need keep it short.", "Provide the answer.",
    "we only have one response now, okay.") do not."""
    s = sentence.lower().strip().rstrip(".!?;\"'")
    for starter in sorted(_META_STARTERS, key=len, reverse=True):
        if s.startswith(starter):
            s = s[len(starter):]
            break
    s = s.strip().lstrip(",;:-'\" ")
    if len(s) < 12:
        return False
    words = [w for w in re.split(r"\W+", s) if w]
    if len(words) < 3:
        return False
    return any(w not in _PLANNING_WORDS for w in words)


def _is_meta_sentence(sentence: str) -> bool:
    """A single sentence is hidden analysis (not user-facing content).

    Rules (case C is the guard rails — real prose that happens to start
    with "we should ..." survives):
      * soft conversational openers are NEVER meta;
      * meta-headed sentences need corroboration: a strong instruction
        reference, 2+ meta signals, OR no informative tail (short
        planning fragment);
      * non-meta-headed sentences are meta only when they carry a
        STRONG instruction reference and are short.
    """
    s = (sentence or "").strip()
    if not s:
        return False
    if _SOFT_STARTER_RE.match(s):
        return False
    lowered = s.lower()
    if _META_STARTER_RE.match(s):
        if _has_strong_instruction_ref(lowered):
            return True
        if _count_meta_signals(lowered) >= 2:
            return True
        return not _has_informative_tail(s)
    # not meta-headed
    if _has_strong_instruction_ref(lowered) and len(s) < 80:
        return True
    return False


def _is_meta_paragraph(paragraph: str) -> bool:
    """A LEADING paragraph is hidden analysis: meta-headed (or soft-headed
    with instruction refs) AND corroborated."""
    p = (paragraph or "").strip()
    if not p:
        return False
    lowered = p.lower()
    if _SOFT_STARTER_RE.match(p):
        # soft opener paragraph is analysis only when it references
        # instructions outright
        return _has_strong_instruction_ref(lowered)
    if not _META_STARTER_RE.match(p):
        return False
    if _has_broad_instruction_ref(lowered):
        return True
    return _count_meta_signals(lowered) >= 2


def _looks_like_pure_reasoning(text: str) -> bool:
    """Legacy single-line heuristic, retained for the no-blank-line
    single-sentence case: contract colons, multi-sentence structure,
    unusual length, or instruction references."""
    signals = 0
    if ": " in text:
        signals += 1
    if ". " in text:
        signals += 1
    if len(text) > 100:
        signals += 1
    if _has_strong_instruction_ref(text.lower()):
        signals += 2
    return signals >= 2


def _trim_first_block(paragraphs: list) -> list:
    """Sentence-level trim of the FIRST block: drop meta sentences; keep
    informative ones even when they follow meta sentences (the answer and
    the reasoning can interleave). Returns the (possibly shortened)
    paragraph list, or [] when nothing survives."""
    first = paragraphs[0]
    lowered = first.lower()
    needs_trim = (
        _META_STARTER_RE.match(first)
        or _has_strong_instruction_ref(lowered)
        or _count_meta_signals(lowered) >= 2
    )
    if not needs_trim or _SOFT_STARTER_RE.match(first):
        return paragraphs

    sentences = [s for s in _SENTENCE_SPLIT_RE.split(first) if s.strip()]
    if len(sentences) <= 1:
        only = sentences[0] if sentences else first
        if _is_meta_sentence(only) or (
            not _SOFT_STARTER_RE.match(only)
            and _looks_like_pure_reasoning(only)
        ):
            return paragraphs[1:]  # drop the whole block
        return paragraphs

    kept = [s for s in sentences if not _is_meta_sentence(s)]
    if kept:
        paragraphs[0] = " ".join(kept)
        return paragraphs
    # whole first block was meta
    return paragraphs[1:]


def strip_cot_preambles(content: str) -> str:
    """Remove LEADING meta-reasoning / instruction analysis from output.

    Paragraph-level first (blank-line separated), then sentence-level in
    the first surviving block. Legitimate replies that merely MENTION
    these phrases later in the text are untouched. Returns "" when only
    analysis was present, so the caller-side empty-content failover can
    treat the provider result as a failure (Part 6).
    """
    if not content:
        return content

    content = content.strip()
    if not content:
        return content

    paragraphs = [p for p in (s.strip() for s in content.split("\n\n")) if p]

    # ── 1. drop leading META PARAGRAPHS ──
    while len(paragraphs) > 1 and _is_meta_paragraph(paragraphs[0]):
        paragraphs.pop(0)
    if not paragraphs:
        return ""

    # ── 2. sentence-level trim of the first block ──
    paragraphs = _trim_first_block(paragraphs)
    if not paragraphs:
        return ""

    # ── 3. everything that remains is still analysis? -> empty ──
    if len(paragraphs) == 1:
        only = paragraphs[0]
        if _is_meta_paragraph(only) and (
            len(_SENTENCE_SPLIT_RE.split(only)) <= 1
            or all(_is_meta_sentence(s)
                   for s in _SENTENCE_SPLIT_RE.split(only) if s.strip())
        ):
            return ""
    else:
        if all(_is_meta_paragraph(p) for p in paragraphs):
            return ""

    return "\n\n".join(paragraphs).strip()


def strip_reasoning_tags(content: str) -> str:
    """Strip <thinking>/<thought>/<reasoning> blocks (incl. unterminated).

    Gemini thinking summaries, GLM thought blocks and Groq gpt-oss
    reasoning all arrive in (or leak into) these tag shapes.
    """
    if not content:
        return content
    content = re.sub(
        r'⊮.*?⊼', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(
        r'<thinking>.*?</thinking>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(
        r'<thought>.*?</thought>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    content = re.sub(
        r'<reasoning>.*?</reasoning>', '', content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Unterminated blocks — strip from the opener to the end of the string.
    if '⊮' in content.lower():
        content = re.sub(r'⊮.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    if '<thinking>' in content.lower():
        content = re.sub(r'<thinking>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    if '<thought>' in content.lower():
        content = re.sub(r'<thought>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    if '<reasoning>' in content.lower():
        content = re.sub(r'<reasoning>.*', '', content,
                         flags=re.DOTALL | re.IGNORECASE)
    return content


def is_empty_content(text: str) -> bool:
    """True when a provider result carries no visible content after
    sanitization — the router treats this as a content failure
    (EMPTY_RESPONSE / SANITIZATION_EMPTY) and fails over to the next
    provider."""
    return not (text or "").strip()


# ─── Part 5 — final output guard (facade boundary) ──────────────────

# Ultra-high-confidence markers: text containing these AFTER the full
# pipeline is almost certainly leaked instruction analysis, not prose.
_GUARD_HARD_MARKERS = (
    "the system prompt", "the system message", "the system says",
    "the developer instructed", "the developer says",
    "the instructions say", "as per instructions",
    "according to the instructions", "per the instructions",
    "the prompt says", "the rules say", "the persona says",
    "the character card", "we must not start two responses",
    "must not mention the creator", "mention creator unless asked",
    "we must keep under",
)

_GUARD_COMPOSITE_RE = re.compile(
    r"\b(?:we\s+must|we\s+need|we\s+should|i\s+must|i\s+need)\b[^.!?]{0,70}"
    r"\b(?:not\s+mention|not\s+say|not\s+reveal|not\s+start|ensure|"
    r"make\s+sure|keep\s+it|under\s+\w+\s+length)\b",
    flags=re.IGNORECASE,
)


def is_meta_reasoning_text(text: str) -> bool:
    """FINAL OUTPUT GUARD detector (Part 5). Conservative on purpose:

      * any single hard marker -> meta
      * a composite "we must <...> not mention / ensure / keep it" -> meta
      * 3+ distinct meta signals in a SHORT text (< 160 chars) -> meta

    Normal casual replies ("we should probably use websockets because
    ...") carry one weak signal at most and pass untouched.
    """
    if not text or not text.strip():
        return False
    lowered = text.strip().lower()
    for marker in _GUARD_HARD_MARKERS:
        if marker in lowered:
            return True
    if _GUARD_COMPOSITE_RE.search(lowered):
        return True
    if len(lowered) < 160 and _count_meta_signals(lowered) >= 3:
        return True
    return False


def sanitize_output(content: str) -> str:
    """FULL final pipeline — tags, leading meta paragraphs/sentences,
    empty handling, meta-leak last-chance check, Discord length cap.

    Returns "" (empty string) when no visible content survived, so the
    router can fail over; the facade turns a final "" into the legacy
    canned fallback. NEVER returns None.

    The LAST step before the length cap re-runs the high-confidence
    meta detector (is_meta_reasoning_text) on whatever survived the
    earlier layers: if the remaining text is still planning language
    (e.g. the production GLM leak's mid-stream tail — "we only have one
    response now, okay. We must keep under maybe moderate length …"),
    the whole result is treated as meta-only → "" → SANITIZATION_EMPTY
    → failover. Conservative by construction: only compound hard
    markers / composite patterns / 3+ signals in short text trip it.
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

        # last-chance meta check (defense in depth INSIDE the pipeline):
        # content that still reads as instruction analysis is a failed
        # generation, not an answer.
        if is_meta_reasoning_text(content):
            return EMPTY_CONTENT_MARK

        # Cap for Discord's 2000-char message limit.
        if len(content) > DISCORD_CHAR_CAP:
            content = content[:DISCORD_CHAR_CAP] + "..."

        return content
    except Exception as e:
        logger.error(f"[sanitize_output] {type(e).__name__}: {e}")
        return EMPTY_CONTENT_MARK
