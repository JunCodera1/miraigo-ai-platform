"""Japanese morphological analysis on top of Sudachi.

Deterministic and dictionary-based: tokens, lemmas, parts of speech, conjugation, readings,
furigana and romaji need no language model, cost nothing per call and always give the same
answer. An LLM is only worth calling for what this cannot do (explaining *why*, judging
naturalness, correcting).
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import Literal

from sudachipy import Dictionary, SplitMode

from japanese_ai.services.language import kana

SplitModeName = Literal["A", "B", "C"]
_MODES = {"A": SplitMode.A, "B": SplitMode.B, "C": SplitMode.C}

_POS_EN = {
    "名詞": "noun",
    "代名詞": "pronoun",
    "動詞": "verb",
    "形容詞": "i-adjective",
    "形状詞": "na-adjective",
    "副詞": "adverb",
    "助詞": "particle",
    "助動詞": "auxiliary",
    "接続詞": "conjunction",
    "連体詞": "adnominal",
    "感動詞": "interjection",
    "接頭辞": "prefix",
    "接尾辞": "suffix",
    "補助記号": "punctuation",
    "記号": "symbol",
    "空白": "whitespace",
}
_NON_WORDS = {"punctuation", "symbol", "whitespace"}

_FORM_EN = {
    "未然形": "irrealis (negative/passive stem)",
    "連用形": "continuative (masu-stem / te-form base)",
    "終止形": "terminal (sentence-final)",
    "連体形": "attributive (before a noun)",
    "仮定形": "conditional (ba-form)",
    "命令形": "imperative",
    "意志推量形": "volitional",
    "語幹": "stem",
}

# Particles are spelled は/へ/を but pronounced wa/e/o.
_PARTICLE_SOUND = {"ハ": "ワ", "ヘ": "エ", "ヲ": "オ"}

# Readings where the dictionary's first choice is not what a learner is taught.
_READING_OVERRIDES = {("私", "代名詞"): "ワタシ"}

_DIGITS = re.compile(r"[0-9０-９]+")
_KANJI_DIGITS = "〇一二三四五六七八九"
_SMALL_UNITS = ("", "十", "百", "千")
_BIG_UNITS = ("", "万", "億", "兆")


@dataclass(frozen=True)
class FuriganaPart:
    text: str
    reading: str | None  # hiragana, only for the parts that need it (kanji)


@dataclass(frozen=True)
class Token:
    surface: str
    lemma: str
    normalized: str
    reading: str | None  # katakana as written (は stays ハ); None for punctuation and unreadable tokens
    pos: str
    pos_detail: tuple[str, ...]
    conjugation_type: str | None
    conjugation_form: str | None
    start: int
    end: int
    is_oov: bool

    @property
    def is_word(self) -> bool:
        return self.pos not in _NON_WORDS

    @property
    def conjugation_form_en(self) -> str | None:
        if self.conjugation_form is None:
            return None
        return _FORM_EN.get(self.conjugation_form.split("-")[0])

    @property
    def reading_hiragana(self) -> str | None:
        return kana.to_hiragana(self.reading) if self.reading else None

    @property
    def pronunciation(self) -> str | None:
        """Katakana as spoken: the particles は/へ/を are said わ/え/お."""
        if self.reading and self.pos == "particle" and self.surface in ("は", "へ", "を"):
            return _PARTICLE_SOUND.get(self.reading, self.reading)
        return self.reading

    @property
    def romaji(self) -> str | None:
        # Hepburn spells particles as they sound (wa, e, o).
        return kana.to_romaji(self.pronunciation) if self.pronunciation else None

    @property
    def furigana(self) -> tuple[FuriganaPart, ...] | None:
        if not self.reading or not kana.has_kanji(self.surface):
            return None
        return furigana_parts(self.surface, self.reading)


class JapaneseAnalyzer:
    def __init__(self) -> None:
        self._tokenizer = Dictionary().tokenizer()
        self._lock = threading.Lock()  # the tokenizer object is not safe to share across threads

    def tokenize(self, text: str, mode: SplitModeName = "C") -> list[Token]:
        with self._lock:
            morphemes = list(self._tokenizer.tokenize(text, _MODES[mode]))
        return [_to_token(morpheme) for morpheme in morphemes]

    def reading_units(self, text: str) -> list[tuple[Token, list[str]]]:
        """Each pronounceable token with its morae, for comparing speech against text.

        Digits are spelled out first (2011 -> 二千十一) so they are read as numbers, and long
        vowels are written canonically inside each word.
        """
        # Sudachi can split unknown kana mid-mora (とうき + ょ); such pieces are glued back
        # onto the previous word before morae are counted.
        pieces: list[tuple[Token, str]] = []
        for token in self.tokenize(spell_out_numbers(text)):
            if not token.is_word or not token.pronunciation:
                continue
            reading = kana.same_sound(token.pronunciation)
            if pieces and (reading[0] in kana.SMALL_KANA or reading[0] == kana.LONG):
                previous, previous_reading = pieces[-1]
                pieces[-1] = (previous, previous_reading + reading)
            else:
                pieces.append((token, reading))
        units = []
        for token, reading in pieces:
            morae = kana.canonical_long_vowels(kana.split_morae(reading))
            if morae:
                units.append((token, morae))
        return units


def _to_token(morpheme: object) -> Token:
    tags = tuple(morpheme.part_of_speech())  # type: ignore[attr-defined]
    pos_ja = tags[0]
    surface = morpheme.surface()  # type: ignore[attr-defined]
    pos = _POS_EN.get(pos_ja, "other")

    reading: str | None = None
    if pos not in _NON_WORDS:
        candidate = _READING_OVERRIDES.get((surface, pos_ja)) or morpheme.reading_form()  # type: ignore[attr-defined]
        if candidate and kana.is_katakana_word(candidate):
            reading = candidate

    return Token(
        surface=surface,
        lemma=morpheme.dictionary_form(),  # type: ignore[attr-defined]
        normalized=morpheme.normalized_form(),  # type: ignore[attr-defined]
        reading=reading,
        pos=pos,
        pos_detail=tuple(tag for tag in tags[:4] if tag != "*"),
        conjugation_type=tags[4] if tags[4] != "*" else None,
        conjugation_form=tags[5] if tags[5] != "*" else None,
        start=morpheme.begin(),  # type: ignore[attr-defined]
        end=morpheme.end(),  # type: ignore[attr-defined]
        is_oov=morpheme.is_oov(),  # type: ignore[attr-defined]
    )


def furigana_parts(surface: str, reading_katakana: str) -> tuple[FuriganaPart, ...]:
    """Attach the reading to the kanji only: 食べる + タベル -> 食(た) べる.

    The kana already written in the word anchor the split. If they do not line up with the
    reading (irregular spellings), the whole word gets the whole reading.
    """
    runs: list[tuple[str, bool]] = []
    for char in surface:
        is_kana_char = kana.is_kana(char)
        if runs and runs[-1][1] == is_kana_char:
            runs[-1] = (runs[-1][0] + char, is_kana_char)
        else:
            runs.append((char, is_kana_char))

    pattern = "".join(
        re.escape(kana.to_katakana(text)) if is_kana_run else "(.+?)" for text, is_kana_run in runs
    )
    match = re.fullmatch(pattern, reading_katakana)
    if match is None:
        return (FuriganaPart(text=surface, reading=kana.to_hiragana(reading_katakana)),)

    groups = iter(match.groups())
    return tuple(
        FuriganaPart(text=text, reading=None if is_kana_run else kana.to_hiragana(next(groups)))
        for text, is_kana_run in runs
    )


def _four_digits(value: int) -> str:
    out = ""
    for position in range(3, -1, -1):
        digit = value // 10**position % 10
        if digit == 0:
            continue
        out += ("" if digit == 1 and position > 0 else _KANJI_DIGITS[digit]) + _SMALL_UNITS[position]
    return out


def number_to_kanji(value: int) -> str:
    if value == 0:
        return "〇"
    groups = []
    index = 0
    while value > 0 and index < len(_BIG_UNITS):
        value, chunk = divmod(value, 10_000)
        if chunk:
            groups.append(_four_digits(chunk) + _BIG_UNITS[index])
        index += 1
    return "".join(reversed(groups))


def spell_out_numbers(text: str) -> str:
    """Replace digit runs with kanji numerals. Runs with a leading zero or too many digits
    (phone numbers, ids) are left alone: those are read digit by digit anyway."""

    def replace(match: re.Match[str]) -> str:
        digits = match.group().translate(str.maketrans("０１２３４５６７８９", "0123456789"))
        if len(digits) > 16 or (len(digits) > 1 and digits[0] == "0"):
            return match.group()
        return number_to_kanji(int(digits))

    return _DIGITS.sub(replace, text)
