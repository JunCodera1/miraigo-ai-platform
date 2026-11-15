"""Kana utilities: script conversion, mora segmentation, romanisation, mora phonetics.

Everything here is plain rule-based code. The mora is the unit Japanese timing and pitch accent
are counted in, so it is also the unit pronunciation feedback is given in.
"""

from __future__ import annotations

import re

_HIRAGANA = re.compile(r"[ぁ-ゖ]")
_KATAKANA = re.compile(r"[ァ-ヺ]")
_KATAKANA_ONLY = re.compile(r"^[ァ-ヺー]+$")
_KANJI = re.compile(r"[㐀-䶿一-鿿豈-﫿々〆〇]")

LONG = "ー"
SOKUON = "ッ"
MORAIC_N = "ン"
SMALL_KANA = frozenset("ァィゥェォャュョヮ")
_SMALL = SMALL_KANA

# Kana that are written differently but pronounced the same in standard Japanese.
_SAME_SOUND = str.maketrans({"ヲ": "オ", "ヂ": "ジ", "ヅ": "ズ", "ヰ": "イ", "ヱ": "エ"})


def to_katakana(text: str) -> str:
    return _HIRAGANA.sub(lambda match: chr(ord(match.group()) + 0x60), text)


def to_hiragana(text: str) -> str:
    return _KATAKANA.sub(
        lambda match: chr(ord(match.group()) - 0x60) if match.group() <= "ヶ" else match.group(), text
    )


def is_katakana_word(text: str) -> bool:
    return bool(_KATAKANA_ONLY.match(text))


def is_kana(char: str) -> bool:
    return bool(_HIRAGANA.match(char) or _KATAKANA.match(char) or char == LONG)


def has_kanji(text: str) -> bool:
    return bool(_KANJI.search(text))


def same_sound(katakana: str) -> str:
    """Fold spellings that sound identical (ヲ/オ, ヂ/ジ, ヅ/ズ)."""
    return katakana.translate(_SAME_SOUND)


def split_morae(katakana: str) -> list[str]:
    """Split a katakana string into morae. キョ is one mora; ッ, ン and ー are one each."""
    morae: list[str] = []
    for char in katakana:
        if char in _SMALL and morae and morae[-1] not in (LONG, SOKUON, MORAIC_N):
            morae[-1] += char
        elif _KATAKANA.match(char) or char == LONG:
            morae.append(char)
    return morae


# --- Romanisation (Hepburn) -----------------------------------------------------------------
_BASE = {
    "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo",
    "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヰ": "i", "ヱ": "e", "ヲ": "o",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "ヴ": "vu",
}  # fmt: skip
_YOON_STEMS = {
    "キ": "ky", "ギ": "gy", "シ": "sh", "ジ": "j", "チ": "ch", "ヂ": "j", "ニ": "ny",
    "ヒ": "hy", "ビ": "by", "ピ": "py", "ミ": "my", "リ": "ry",
}  # fmt: skip
_YOON_VOWELS = {"ャ": "a", "ュ": "u", "ョ": "o", "ェ": "e"}
_FOREIGN = {
    "ファ": "fa", "フィ": "fi", "フェ": "fe", "フォ": "fo", "フュ": "fyu",
    "ティ": "ti", "ディ": "di", "トゥ": "tu", "ドゥ": "du", "テュ": "tyu", "デュ": "dyu",
    "ウィ": "wi", "ウェ": "we", "ウォ": "wo", "イェ": "ye",
    "ツァ": "tsa", "ツィ": "tsi", "ツェ": "tse", "ツォ": "tso",
    "ヴァ": "va", "ヴィ": "vi", "ヴェ": "ve", "ヴォ": "vo",
    "クァ": "kwa", "グァ": "gwa",
}  # fmt: skip
_SMALL_VOWELS = {
    "ァ": "a",
    "ィ": "i",
    "ゥ": "u",
    "ェ": "e",
    "ォ": "o",
    "ャ": "ya",
    "ュ": "yu",
    "ョ": "yo",
    "ヮ": "wa",
}


def mora_romaji(mora: str) -> str:
    """Romaji for one mora. ン -> "n"; ッ and ー have no sound of their own and return ""."""
    if mora in (SOKUON, LONG):
        return ""
    if mora == MORAIC_N:
        return "n"
    if mora in _BASE:
        return _BASE[mora]
    if mora in _FOREIGN:
        return _FOREIGN[mora]
    if len(mora) == 2 and mora[0] in _YOON_STEMS and mora[1] in _YOON_VOWELS:
        return _YOON_STEMS[mora[0]] + _YOON_VOWELS[mora[1]]
    # Unusual combination: spell the parts out.
    return "".join(_BASE.get(char, _SMALL_VOWELS.get(char, "")) for char in mora)


def to_romaji(katakana: str) -> str:
    """Hepburn romanisation. Long vowels are written out (ō -> "ou"/"oo"), not with macrons."""
    morae = split_morae(katakana)
    parts: list[str] = []
    double_next = False
    for index, mora in enumerate(morae):
        if mora == SOKUON:
            double_next = True
            continue
        if mora == LONG:
            if parts and parts[-1] and parts[-1][-1] in "aiueo":
                parts.append(parts[-1][-1])
            continue
        roman = mora_romaji(mora)
        if mora == MORAIC_N:
            following = mora_romaji(morae[index + 1]) if index + 1 < len(morae) else ""
            if following[:1] in ("a", "i", "u", "e", "o", "y"):
                roman = "n'"
        if double_next and roman:
            roman = ("t" if roman.startswith("ch") else roman[0]) + roman
        double_next = False
        parts.append(roman)
    return "".join(parts)


# --- Mora phonetics (for comparing what was said with what was expected) -----------------------
_VOICING_PAIRS = {
    frozenset(pair)
    for pair in (("k", "g"), ("s", "z"), ("sh", "j"), ("t", "d"), ("ch", "j"), ("ts", "z"), ("h", "b"), ("h", "p"), ("b", "p"), ("f", "b"), ("f", "p"))
}  # fmt: skip


def mora_sounds(mora: str) -> tuple[str, str]:
    """``(consonant, vowel)`` of a mora. Special morae get a marker instead of a vowel."""
    if mora in (SOKUON, LONG, MORAIC_N):
        return "", {"ッ": "Q", "ー": "R", "ン": "N"}[mora]
    roman = mora_romaji(mora)
    if not roman:
        return "", ""
    return roman[:-1], roman[-1]


def differ_only_in_voicing(first: str, second: str) -> bool:
    consonant_a, vowel_a = mora_sounds(first)
    consonant_b, vowel_b = mora_sounds(second)
    return vowel_a == vowel_b and frozenset((consonant_a, consonant_b)) in _VOICING_PAIRS


def canonical_long_vowels(morae: list[str]) -> list[str]:
    """Rewrite spelled-out long vowels as ー so that トウキョウ and トーキョー compare equal.

    オ-row + ウ, エ-row + イ, and a repeated vowel are treated as long. Callers apply this inside
    one word at a time; across a word boundary the two vowels are separate sounds.
    """
    result: list[str] = []
    for mora in morae:
        if result and mora in ("ア", "イ", "ウ", "エ", "オ"):
            _, previous_vowel = mora_sounds(result[-1])
            vowel = _BASE[mora]
            if previous_vowel == vowel or (previous_vowel, vowel) in (("o", "u"), ("e", "i")):
                result.append(LONG)
                continue
            if previous_vowel == "R":  # already long: カアア -> カーー is not a thing
                result.append(mora)
                continue
        result.append(mora)
    return result
