import pytest

from japanese_ai.services.language import kana


@pytest.mark.parametrize(
    ("katakana", "romaji"),
    [
        ("トウキョウ", "toukyou"),
        ("キッテ", "kitte"),
        ("マッチャ", "matcha"),
        ("ゲンイン", "gen'in"),
        ("シンブン", "shinbun"),
        ("コーヒー", "koohii"),
        ("ジュウ", "juu"),
        ("ファイル", "fairu"),
        ("チョット", "chotto"),
    ],
)
def test_romaji(katakana, romaji):
    assert kana.to_romaji(katakana) == romaji


def test_split_morae_counts_special_morae():
    assert kana.split_morae("キョウ") == ["キョ", "ウ"]
    assert kana.split_morae("ガッコウ") == ["ガ", "ッ", "コ", "ウ"]
    assert kana.split_morae("コンピューター") == ["コ", "ン", "ピュ", "ー", "タ", "ー"]


def test_script_conversion_roundtrip():
    assert kana.to_katakana("ひらがな") == "ヒラガナ"
    assert kana.to_hiragana("カタカナー") == "かたかなー"


def test_long_vowels_are_canonical_within_a_word():
    assert kana.canonical_long_vowels(kana.split_morae("トウキョウ")) == ["ト", "ー", "キョ", "ー"]
    assert kana.canonical_long_vowels(kana.split_morae("トーキョー")) == ["ト", "ー", "キョ", "ー"]
    assert kana.canonical_long_vowels(kana.split_morae("センセイ")) == ["セ", "ン", "セ", "ー"]
    assert kana.canonical_long_vowels(kana.split_morae("オカアサン")) == ["オ", "カ", "ー", "サ", "ン"]


def test_voicing_pairs():
    assert kana.differ_only_in_voicing("カ", "ガ")
    assert kana.differ_only_in_voicing("シ", "ジ")
    assert not kana.differ_only_in_voicing("カ", "サ")
    assert not kana.differ_only_in_voicing("カ", "ギ")
