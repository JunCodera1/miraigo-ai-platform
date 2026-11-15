# Models: registry, swapping, evaluation

All models are declared in [`src/japanese_ai/model_registry/models.yaml`](../src/japanese_ai/model_registry/models.yaml)
(or a copy pointed to by `JAI_MODELS_FILE`). The file is validated at startup: unknown fields,
duplicate ids, and routing references to missing models fail fast.

```yaml
- id: reazonspeech-zipformer-ja        # stable id used by clients (`model` field) and logs
  capability: asr
  provider: sherpa_onnx                # adapter: sherpa_onnx | faster_whisper | openai_compatible | legacy_voiceai
  deployment: local                    # local models share the inference concurrency limit
  languages: [ja]
  license: Apache-2.0
  source: https://…
  enabled: true
  cost: {unit: audio_minute, usd: 0}   # used for per-request cost estimates
  config: {family: transducer, dir: sherpa/…, files: {…}, num_threads: 4}

routing:
  asr: {primary: sensevoice-small-int8, fallbacks: [reazonspeech-zipformer-ja, …], timeout_seconds: 120, max_retries: 1}
```

- Routes: `asr` (transcription, stream) and `pronunciation` each have their own primary/fallbacks.
- Switch a primary without editing: `JAI_ASR_MODEL=…`, `JAI_PRONUNCIATION_MODEL=…`.
- A model whose files, package or API key are missing is reported unavailable and skipped.
- A caller-chosen `model` is never silently replaced; fallbacks apply only to default routing.
- Retries happen only for transient errors (network, 429, 5xx, timeout); then the next model.
- New engine = one adapter class implementing `ASRProvider` (`availability`, `transcribe`, optional
  `warm_up`/`aclose`) + one line in `providers/factory.py`.

## Evaluating a model

```bash
scripts/run-capped.sh 3500 python scripts/eval_asr.py --model <id> \
  --dataset ~/.local/share/japanese-ai-platform/eval/fleurs/ja_jp-test.parquet --limit 100 \
  --out ~/.local/share/japanese-ai-platform/eval/reports/<id>.json
```

Reports CER (strict), kana CER (readings, script-agnostic), RTF, p50/p90 latency, load time and
memory, plus every hypothesis. `run-capped.sh` puts the process in a cgroup with a hard memory limit
and no swap. Record results in `lab/EXPERIMENT_RESULTS.md`.

Pitfall found: the sherpa-onnx archive `sense-voice-…-int8-2025-09-09` is a **Cantonese** fine-tune
(WSYue); on Japanese it scored 79 % CER. Use the `2024-07-17` build.
