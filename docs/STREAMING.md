# Live transcription — `WS /api/v1/speech/stream`

Utterance-level streaming: voice activity detection (Silero) closes an utterance at a pause
(≥ 0.35 s) or after 15 s, then that utterance is transcribed. Latency is "end of utterance + decode"
— measured 0.32–0.60 s after the speaker stops, feeding audio at real time on CPU (lab E-003) — not word by word.

```
client → {"type":"start","token":"<access token>","sampleRate":16000,"model":"<optional id>"}   first text message, within 10 s
server → {"type":"ready"}
client → binary frames: PCM16 little-endian, mono, 16 kHz, ≤ 64 KiB each (100–200 ms recommended)
server → {"type":"speech_start"}
server → {"type":"segment","start":3.19,"end":8.58,"text":"…","model":"sensevoice-small-int8"}
client → {"type":"stop"}                      flushes the open utterance
server → {"type":"done"}  then closes
server → {"type":"error","errorCode":"AI_AUTH_INVALID","message":"…"}  then closes (1008/1009/1011)
```

- `start`/`end` are seconds from the first audio frame.
- Token in the first message, not the query string, so it never reaches access logs. Service callers
  may send `"apiKey"` instead.
- Browser connections must come from an origin in `JAI_CORS_ALLOWED_ORIGINS`; native apps send no
  Origin header and are allowed.
- Limits: total stream ≤ 5 × `JAI_MAX_AUDIO_SECONDS`; counts against the inference rate limit once per connection.
- Short pauses split sentences (e.g. "インターネットで。" + rest); join segments client-side for display.
- Requires `sherpa/silero_vad.onnx` in the models dir; otherwise the server answers
  `AI_PROVIDER_UNAVAILABLE` and closes.

Capture on the client: Expo native → record PCM with a streaming audio module; web → `AudioWorklet`
downsampling to 16 kHz Int16. For simple push-to-talk, recording a file and calling
`/speech/transcribe` is simpler and as accurate.
