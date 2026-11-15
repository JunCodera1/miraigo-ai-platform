import pytest

from japanese_ai.services.language.analyzer import (
    JapaneseAnalyzer,
    furigana_parts,
    number_to_kanji,
    spell_out_numbers,
)


@pytest.fixture(scope="module")
def analyzer():
    return JapaneseAnalyzer()


def test_particles_keep_their_spelling_but_are_pronounced_as_spoken(analyzer):
    tokens = {t.surface: t for t in analyzer.tokenize("私は学校へ本を")}
    assert [tokens[p].reading_hiragana for p in "はへを"] == ["は", "へ", "を"]
    assert [tokens[p].romaji for p in "はへを"] == ["wa", "e", "o"]
    assert tokens["私"].reading_hiragana == "わたし"
    morae = [m for _, ms in analyzer.reading_units("私は") for m in ms]
    assert morae[-1] == "ワ"


def test_conjugation_and_lemma(analyzer):
    token = analyzer.tokenize("食べられなかった")[0]
    assert token.lemma == "食べる"
    assert token.pos == "verb"
    assert token.conjugation_form is not None
    assert token.conjugation_form_en.startswith("irrealis")


def test_punctuation_has_no_reading(analyzer):
    last = analyzer.tokenize("行きます。")[-1]
    assert last.surface == "。" and not last.is_word and last.reading is None


def test_furigana_only_on_kanji():
    parts = furigana_parts("食べる", "タベル")
    assert [(p.text, p.reading) for p in parts] == [("食", "た"), ("べる", None)]
    parts = furigana_parts("お婆さん", "オバアサン")
    assert [(p.text, p.reading) for p in parts] == [("お", None), ("婆", "ばあ"), ("さん", None)]


def test_furigana_falls_back_to_whole_word():
    parts = furigana_parts("今日", "キョウ")
    assert [(p.text, p.reading) for p in parts] == [("今日", "きょう")]


@pytest.mark.parametrize(
    ("value", "kanji"),
    [
        (0, "〇"),
        (7, "七"),
        (10, "十"),
        (15, "十五"),
        (100, "百"),
        (2011, "二千十一"),
        (10000, "一万"),
        (12345, "一万二千三百四十五"),
    ],
)
def test_number_to_kanji(value, kanji):
    assert number_to_kanji(value) == kanji


def test_phone_numbers_are_not_spelled_out():
    assert spell_out_numbers("090") == "090"
    assert spell_out_numbers("3時") == "三時"


def test_reading_units_glue_mid_mora_splits(analyzer):
    morae = [m for _, ms in analyzer.reading_units("とうきょに") for m in ms]
    assert "ョ" not in morae
    assert morae[:3] == ["ト", "ー", "キョ"]
