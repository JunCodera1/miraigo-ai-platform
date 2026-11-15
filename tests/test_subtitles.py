from japanese_ai.providers.base import Segment
from japanese_ai.services.speech.subtitles import render

SEGMENTS = (Segment(0.0, 1.5, "こんにちは"), Segment(61.25, 3725.0, "さよう-->なら"), Segment(4.0, 4.0, "  "))


def test_srt():
    out = render(SEGMENTS, "srt")
    assert out.startswith("1\n00:00:00,000 --> 00:00:01,500\nこんにちは\n")
    assert "2\n00:01:01,250 --> 01:02:05,000\nさよう->なら\n" in out
    assert out.count("-->") == 2  # empty cue dropped, arrow in text neutralised


def test_vtt():
    out = render(SEGMENTS, "vtt")
    assert out.startswith("WEBVTT\n\n00:00:00.000 --> 00:00:01.500\n")
