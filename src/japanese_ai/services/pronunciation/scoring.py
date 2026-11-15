"""Mora-level comparison of what a learner said against what they were asked to say.

Method (``asr_alignment_v0``): the reference sentence and the recognised speech are both turned
into mora sequences and aligned. What this measures is *intelligibility to a speech recogniser*,
which is a useful, honest proxy for a first version:

- it catches the errors that change which morae are heard: dropped long vowels, missing っ,
  missing ん, voicing, wrong vowels, skipped or extra words;
- it cannot hear pitch accent, intonation or subtle articulation;
- a recogniser sometimes "repairs" a slightly wrong word into the right one (too lenient) and
  sometimes mishears a correct one (too strict). Scores are guidance, not grades.

Acoustic scoring (phoneme posteriors, pitch) is the planned next stage; see the lab notes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from japanese_ai.services.language import kana

Op = Literal["match", "substitute", "omit", "insert"]
IssueType = Literal[
    "long_vowel_shortened",
    "vowel_lengthened",
    "sokuon_missing",
    "sokuon_added",
    "n_missing",
    "n_added",
    "voicing",
    "youon",
    "vowel",
    "consonant",
    "mismatch",
    "omitted",
    "extra_sound",
]

_MESSAGES: dict[str, str] = {
    "long_vowel_shortened": "A long vowel was cut short. Hold it for one more beat.",
    "vowel_lengthened": "A vowel was held too long. Keep it to one beat.",
    "sokuon_missing": "The small っ pause was missing. Stop briefly before the next consonant.",
    "sokuon_added": "An extra っ pause was heard.",
    "n_missing": "The ん sound was missing.",
    "n_added": "An extra ん sound was heard.",
    "voicing": "Voicing differed: expected {expected}, heard {heard}.",
    "youon": "Contracted sound differed: expected {expected}, heard {heard}.",
    "vowel": "Vowel differed: expected {expected}, heard {heard}.",
    "consonant": "Consonant differed: expected {expected}, heard {heard}.",
    "mismatch": "Expected {expected}, heard {heard}.",
    "omitted": "{expected} was not heard.",
    "extra_sound": "An extra {heard} was heard.",
}
_SPECIAL = (kana.LONG, kana.SOKUON, kana.MORAIC_N)
_YOON_MARKS = set("ャュョ")


@dataclass(frozen=True)
class AlignedMora:
    op: Op
    expected: str | None
    heard: str | None


@dataclass(frozen=True)
class Issue:
    type: IssueType
    expected: str | None  # hiragana
    heard: str | None  # hiragana
    message: str


@dataclass
class WordResult:
    text: str
    expected: str  # hiragana reading
    heard: str  # hiragana, what was recognised in this word's place
    status: Literal["ok", "partial", "missed"]
    issues: list[Issue] = field(default_factory=list)


@dataclass
class PronunciationScore:
    overall: int
    accuracy: int
    completeness: int
    mora_count: int
    matched: int
    substituted: int
    omitted: int
    inserted: int
    words: list[WordResult]


def _substitution_cost(expected: str, heard: str) -> float:
    if expected == heard:
        return 0.0
    if expected in _SPECIAL or heard in _SPECIAL:
        return 1.0
    consonant_a, vowel_a = kana.mora_sounds(expected)
    consonant_b, vowel_b = kana.mora_sounds(heard)
    # Morae that share a vowel or a consonant are likelier to be the same slip than strangers.
    return 0.6 if (vowel_a == vowel_b or consonant_a == consonant_b) else 1.0


def align(expected: list[str], heard: list[str]) -> list[AlignedMora]:
    """Minimum-cost alignment (edit distance with a phonetic substitution cost)."""
    rows, cols = len(expected) + 1, len(heard) + 1
    cost = [[0.0] * cols for _ in range(rows)]
    for i in range(1, rows):
        cost[i][0] = float(i)
    for j in range(1, cols):
        cost[0][j] = float(j)
    for i in range(1, rows):
        for j in range(1, cols):
            cost[i][j] = min(
                cost[i - 1][j - 1] + _substitution_cost(expected[i - 1], heard[j - 1]),
                cost[i - 1][j] + 1.0,
                cost[i][j - 1] + 1.0,
            )

    aligned: list[AlignedMora] = []
    i, j = len(expected), len(heard)
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            step = _substitution_cost(expected[i - 1], heard[j - 1])
            if abs(cost[i][j] - (cost[i - 1][j - 1] + step)) < 1e-9:
                op: Op = "match" if step == 0.0 else "substitute"
                aligned.append(AlignedMora(op, expected[i - 1], heard[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and abs(cost[i][j] - (cost[i - 1][j] + 1.0)) < 1e-9:
            aligned.append(AlignedMora("omit", expected[i - 1], None))
            i -= 1
            continue
        aligned.append(AlignedMora("insert", None, heard[j - 1]))
        j -= 1
    aligned.reverse()
    return aligned


def classify(step: AlignedMora) -> IssueType | None:
    if step.op == "match":
        return None
    if step.op == "omit":
        return {
            kana.LONG: "long_vowel_shortened",
            kana.SOKUON: "sokuon_missing",
            kana.MORAIC_N: "n_missing",
        }.get(step.expected or "", "omitted")  # type: ignore[return-value]
    if step.op == "insert":
        return {kana.LONG: "vowel_lengthened", kana.SOKUON: "sokuon_added", kana.MORAIC_N: "n_added"}.get(
            step.heard or "", "extra_sound"
        )  # type: ignore[return-value]

    expected, heard = step.expected or "", step.heard or ""
    if expected in _SPECIAL or heard in _SPECIAL:
        return "mismatch"
    if kana.differ_only_in_voicing(expected, heard):
        return "voicing"
    if bool(_YOON_MARKS & set(expected)) != bool(_YOON_MARKS & set(heard)):
        return "youon"
    consonant_a, vowel_a = kana.mora_sounds(expected)
    consonant_b, vowel_b = kana.mora_sounds(heard)
    if consonant_a == consonant_b:
        return "vowel"
    if vowel_a == vowel_b:
        return "consonant"
    return "mismatch"


def _issue(step: AlignedMora) -> Issue | None:
    issue_type = classify(step)
    if issue_type is None:
        return None
    expected = kana.to_hiragana(step.expected) if step.expected else None
    heard = kana.to_hiragana(step.heard) if step.heard else None
    message = _MESSAGES[issue_type].format(expected=expected or "", heard=heard or "")
    return Issue(type=issue_type, expected=expected, heard=heard, message=message)


def score(reference: list[tuple[str, list[str]]], heard: list[str]) -> PronunciationScore:
    """Score recognised morae against a reference given as ``(word, morae)`` pairs."""
    expected = [mora for _, morae in reference for mora in morae]
    owner = [index for index, (_, morae) in enumerate(reference) for _ in morae]
    aligned = align(expected, heard)

    # Group alignment steps under the reference word they belong to. An inserted sound has no
    # reference mora of its own, so it goes to the word of the last reference mora seen.
    per_word: list[list[AlignedMora]] = [[] for _ in reference]
    position = 0
    for step in aligned:
        if step.op == "insert":
            target = owner[min(position, len(owner) - 1)] if position == 0 else owner[position - 1]
        else:
            target = owner[position]
            position += 1
        per_word[target].append(step)

    words: list[WordResult] = []
    for (text, morae), steps in zip(reference, per_word, strict=True):
        matched = sum(1 for step in steps if step.op == "match")
        omitted = sum(1 for step in steps if step.op == "omit")
        if matched == len(morae) and all(step.op == "match" for step in steps):
            status: Literal["ok", "partial", "missed"] = "ok"
        elif omitted == len(morae):
            status = "missed"
        else:
            status = "partial"
        issues = [issue for step in steps if (issue := _issue(step)) is not None]
        words.append(
            WordResult(
                text=text,
                expected=kana.to_hiragana("".join(morae)),
                heard=kana.to_hiragana("".join(step.heard for step in steps if step.heard)),
                status=status,
                issues=issues,
            )
        )

    total = len(expected)
    matched = sum(1 for step in aligned if step.op == "match")
    substituted = sum(1 for step in aligned if step.op == "substitute")
    omitted = sum(1 for step in aligned if step.op == "omit")
    inserted = sum(1 for step in aligned if step.op == "insert")
    return PronunciationScore(
        overall=round(100 * max(0.0, 1 - (substituted + omitted + inserted) / total)),
        accuracy=round(100 * matched / total),
        completeness=round(100 * (total - omitted) / total),
        mora_count=total,
        matched=matched,
        substituted=substituted,
        omitted=omitted,
        inserted=inserted,
        words=words,
    )
