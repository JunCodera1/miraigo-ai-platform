"""Reusable Japanese ASR evaluation: CER, real-time factor and memory for registry models.

Runs one model per process (so peak memory is that model's alone). Wrap every run in the memory
cap, e.g.:

    scripts/run-capped.sh 2500 python scripts/eval_asr.py --model sensevoice-small-int8 \
        --dataset ~/.local/share/japanese-ai-platform/eval/fleurs/ja_jp-test.parquet --limit 100

Outputs a JSON report (per-utterance hypotheses + summary) to --out. CER is computed after
NFKC, removing punctuation/symbols/whitespace, and mapping katakana->hiragana is NOT applied
(kanji/kana choice counts as an error, like "strict" CER). A second "kana CER" compares
Sudachi readings, which ignores script choice and is closer to what pronunciation scoring sees.

Datasets: a parquet in the Hugging Face FLEURS layout (``audio.bytes`` + ``transcription`` /
``raw_transcription``), or a directory of ``*.wav`` with a ``transcripts.tsv`` (file<TAB>text).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import statistics
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np

from japanese_ai.core.config import Settings
from japanese_ai.model_registry.registry import ModelRegistry
from japanese_ai.providers.base import SAMPLE_RATE, AudioClip, TranscribeOptions
from japanese_ai.providers.factory import ProviderPool
from japanese_ai.services.language.analyzer import JapaneseAnalyzer


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in text if unicodedata.category(ch)[0] not in "ZPS")


def edit_distance(ref: str, hyp: str) -> int:
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (r != h)))
        previous = current
    return previous[-1]


def decode_audio(data: bytes) -> np.ndarray:
    import subprocess

    out = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-i",
            "pipe:0",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        input=data,
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(out, dtype="<f4")


def load_dataset(path: Path, limit: int) -> list[tuple[str, np.ndarray, str]]:
    items: list[tuple[str, np.ndarray, str]] = []
    if path.suffix == ".parquet":
        import pyarrow.parquet as pq

        # Stream small batches: the file is ~0.5 GB of audio and must not be loaded whole.
        parquet = pq.ParquetFile(path)
        for batch in parquet.iter_batches(batch_size=16, columns=["id", "audio", "raw_transcription"]):
            for row in batch.to_pylist():
                items.append((str(row["id"]), decode_audio(row["audio"]["bytes"]), row["raw_transcription"]))
                if len(items) >= limit:
                    return items
    else:
        for line in (path / "transcripts.tsv").read_text("utf-8").splitlines()[:limit]:
            name, text = line.split("\t", 1)
            items.append((name, decode_audio((path / name).read_bytes()), text))
    return items


def kana_reading(analyzer: JapaneseAnalyzer, text: str) -> str:
    return "".join(m for _, morae in analyzer.reading_units(text) for m in morae)


async def evaluate(model_id: str, dataset: Path, limit: int, models_dir: Path | None) -> dict:
    settings = Settings(_env_file=None, **({"models_dir": models_dir} if models_dir else {}))
    registry = ModelRegistry.load(settings.models_file)
    spec = registry.get(model_id)
    if spec is None:
        sys.exit(f"unknown model {model_id}")
    provider = ProviderPool(settings).get(spec)
    usable, reason = provider.availability()
    if not usable:
        sys.exit(f"{model_id} unavailable: {reason}")

    items = load_dataset(dataset, limit)
    analyzer = JapaneseAnalyzer()
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    started = time.perf_counter()
    await provider.warm_up()
    load_seconds = time.perf_counter() - started
    rss_loaded = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    # Warm the inference path once (first decode allocates buffers).
    await provider.transcribe(AudioClip(samples=items[0][1][: SAMPLE_RATE * 2]), TranscribeOptions())

    rows = []
    total_errors = total_chars = kana_errors = kana_chars = 0
    audio_seconds = decode_seconds = 0.0
    for item_id, samples, reference in items:
        clip = AudioClip(samples=samples)
        t0 = time.perf_counter()
        hypothesis = (await provider.transcribe(clip, TranscribeOptions(language="ja"))).text
        elapsed = time.perf_counter() - t0
        ref_n, hyp_n = normalize(reference), normalize(hypothesis)
        errors = edit_distance(ref_n, hyp_n)
        ref_k, hyp_k = kana_reading(analyzer, reference), kana_reading(analyzer, hypothesis)
        k_errors = edit_distance(ref_k, hyp_k)
        total_errors += errors
        total_chars += len(ref_n)
        kana_errors += k_errors
        kana_chars += len(ref_k)
        audio_seconds += clip.duration
        decode_seconds += elapsed
        rows.append(
            {
                "id": item_id,
                "seconds": round(clip.duration, 2),
                "decode_s": round(elapsed, 3),
                "cer": round(errors / max(1, len(ref_n)), 4),
                "kana_cer": round(k_errors / max(1, len(ref_k)), 4),
                "reference": reference,
                "hypothesis": hypothesis,
            }
        )
    per_item_latency = [row["decode_s"] for row in rows]
    return {
        "model": model_id,
        "dataset": str(dataset),
        "utterances": len(rows),
        "audio_minutes": round(audio_seconds / 60, 2),
        "cer": round(total_errors / max(1, total_chars), 4),
        "kana_cer": round(kana_errors / max(1, kana_chars), 4),
        "rtf": round(decode_seconds / audio_seconds, 4),
        "latency_p50_s": round(statistics.median(per_item_latency), 3),
        "latency_p90_s": round(sorted(per_item_latency)[int(0.9 * (len(per_item_latency) - 1))], 3),
        "load_seconds": round(load_seconds, 2),
        "peak_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        "model_rss_mb": round((rss_loaded - rss_before) / 1024),
        "threads": spec.config.get("num_threads") or spec.config.get("cpu_threads"),
        "rows": rows,
        "normalization": "NFKC; drop Unicode Z/P/S categories; corpus-level CER",
        "kana_note": "kana_cer compares Sudachi katakana readings (script choice ignored)",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = asyncio.run(evaluate(args.model, args.dataset.expanduser(), args.limit, args.models_dir))
    summary = {k: v for k, v in report.items() if k != "rows"}
    print(json.dumps(summary, ensure_ascii=False))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1), "utf-8")


if __name__ == "__main__":
    main()
