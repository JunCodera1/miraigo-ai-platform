# Japanese pronunciation assessment — approaches (2026-11-12)

Labels: [V] fetched/read this session, [B] published result (not reproduced), [H] recall, [P] proposal.

## 1. What the commercial option can and cannot do — Azure Speech [V]
Sources: learn.microsoft.com `speech-service/language-support?tabs=pronunciation-assessment`
(ms.date 2026-10-28) and `how-to-pronunciation-assessment` (ms.date 2025-11-21), fetched 2026-11-12.
- `ja-JP` is one of 33 supported locales.
- "Prosody assessment is only available in the en-US locale." → **no pitch-accent or intonation scoring for Japanese**.
- Syllable-level results are en-US only; phoneme names (IPA) en-US only. Whether ja-JP returns phoneme
  scores is not stated; community reports from 2023–2024 describe empty phoneme arrays for Japanese [B, anecdotal].
- So for Japanese it gives accuracy / fluency / completeness per word and overall. Scripted (reference text)
  and unscripted modes; streaming supported; basic assessment is billed as standard speech-to-text.
- Prices on the pricing page rendered as placeholders when fetched; not verified.

Conclusion: Azure is a fast way to get word-level scores, but mora-level and pitch-accent feedback — the
things Japanese learners actually need — must be built.

## 2. Research direction — Kubo et al., "Building Tailored Speech Recognizers for Japanese Speaking Assessment" [B]
arXiv:2509.20655 (Sakana AI, 2025-09-25).
- Recogniser emits **mora-wise katakana with accent markers** via CTC; trained on CSJ core (~45 h with
  hand-annotated accents) with multitask + UniDic lattice fusion.
- Mora-label error rate on CSJ core eval1–3: 4.1–4.9 % ignoring accent, 7.0–9.1 % including accent.
- Key argument: general-purpose ASR "tends to correct speaker errors" (a normalisation effect), which hides
  exactly the mistakes an assessor must see. CTC is chosen because it corrects least.
- No code or weights released; learner speech not evaluated.

## 3. Open building blocks [V: Hugging Face API, 2026-11-12]
| Model | Licence | Use |
|---|---|---|
| prj-beatrice/japanese-hubert-base-phoneme-ctc-v4 | Apache-2.0 | phoneme CTC (HuBERT-base); ONNX export at `air-air/…-v4-ONNX` |
| vumichien/wav2vec2-large-xlsr-japanese-hiragana | Apache-2.0 | hiragana CTC, 134k downloads/mo |
| reazon-research/japanese-wav2vec2-large-rs35kh | Apache-2.0 | strong Japanese SSL encoder |
| imprt/kushinada-hubert-{base,large} | Apache-2.0 | Japanese HuBERT encoders (feature extraction) |
| facebook/mms-1b-all | **CC-BY-NC-4.0** | not usable commercially |
| pyopenjtalk-plus (cp314 wheel available) | see repo | G2P + dictionary accent (accent phrase, nucleus) |

## 4. Plan [P]
| Stage | Method | Gives | Limits |
|---|---|---|---|
| **v0 (built this session)** | ASR transcript → kana reading → mora alignment against the reference | completeness, mora accuracy, speech rate, typed error hints (long vowel, sokuon, ん, voicing, yōon) | measures *intelligibility to a recogniser*; ASR may auto-correct errors (lenient) or mis-hear (strict); no pitch |
| v1 | phoneme-CTC posteriors + forced alignment → goodness-of-pronunciation per phoneme/mora | real acoustic scores, per-mora timing (long vowel / sokuon duration) | needs calibration data; ~380 MB model on CPU |
| v2 | F0 contour (pYIN/Harvest) per mora vs dictionary accent pattern (pyopenjtalk) | pitch-accent feedback (H/L per mora) | dictionary accent ≠ sentence-level sandhi; needs careful UX |
| optional | Azure ja-JP as a second opinion / fallback | vendor word-level scores | cost, data leaves the platform, no prosody |

Evaluation need (all stages): a small set of **learner** recordings with human judgements. No public
Japanese learner corpus was found this session; collecting ~100 consented clips from the app is the realistic path.
