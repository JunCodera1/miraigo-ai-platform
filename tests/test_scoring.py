import pytest

from japanese_ai.services.language.analyzer import JapaneseAnalyzer
from japanese_ai.services.pronunciation.scoring import align, score


@pytest.fixture(scope="module")
def analyzer():
    return JapaneseAnalyzer()


def run(analyzer, reference: str, heard: str):
    ref = [(t.surface, m) for t, m in analyzer.reading_units(reference)]
    morae = [m for _, ms in analyzer.reading_units(heard) for m in ms]
    return score(ref, morae)


def issue_types(result):
    return [issue.type for word in result.words for issue in word.issues]


def test_perfect_reading_scores_100(analyzer):
    result = run(analyzer, "東京に行きました", "東京に行きました")
    assert (result.overall, result.accuracy, result.completeness) == (100, 100, 100)
    assert all(word.status == "ok" for word in result.words)


def test_kana_spelling_of_the_same_sounds_is_not_penalised(analyzer):
    assert run(analyzer, "東京に行きました", "とうきょうにいきました").overall == 100


@pytest.mark.parametrize(
    ("reference", "heard", "expected_issue"),
    [
        ("東京", "ときょ", "long_vowel_shortened"),
        ("切手", "きて", "sokuon_missing"),
        ("来て", "きって", "sokuon_added"),
        ("学校", "かっこう", "voicing"),
        ("病院", "びよういん", "youon"),
        ("本", "ほ", "n_missing"),
    ],
)
def test_typical_learner_errors_are_named(analyzer, reference, heard, expected_issue):
    result = run(analyzer, reference, heard)
    assert expected_issue in issue_types(result)
    assert result.overall < 100


def test_missing_words_lower_completeness(analyzer):
    result = run(analyzer, "毎日日本語を勉強します", "毎日日本語を")
    assert result.completeness < 70
    assert result.words[-1].status == "missed"


def test_alignment_is_minimal():
    steps = align(["ア", "イ", "ウ"], ["ア", "ウ"])
    assert [s.op for s in steps] == ["match", "omit", "match"]


def test_scores_stay_in_range_with_many_insertions(analyzer):
    result = run(analyzer, "は", "あいうえおかきくけこ")
    assert 0 <= result.overall <= 100
