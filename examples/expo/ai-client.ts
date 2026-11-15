/**
 * MiraiGo AI Platform client for the Expo app (iOS, Android, web).
 *
 * Copy into the app (e.g. `src/integrations/ai/ai-client.ts`). It only needs `zod`, which the
 * app already uses. Responses use the same envelope as the MiraiGo backend, so `data` is
 * unwrapped and validated exactly like `api-client.ts` does.
 *
 * Auth: the platform accepts the same access token as the backend. On 401 the client calls
 * `refreshAccessToken` once and retries. In the app, the simplest refresh is to call any backend
 * endpoint through the existing `api` client (its single-flight 401 -> refresh logic rotates the
 * token) and then read the new token from `authStorage`. See README "Expo integration".
 *
 * Uploads: on native, pass `{ uri, name, type }` from expo-audio / expo-document-picker; on
 * web, pass a `Blob` or `File`.
 */
import { z } from 'zod';

export type AiFile = Blob | { uri: string; name: string; type: string };

export type AiClientOptions = {
  baseUrl: string;
  getAccessToken: () => Promise<string | null>;
  /** Return a fresh access token, or null if the session is gone. Called at most once per request. */
  refreshAccessToken?: () => Promise<string | null>;
  timeoutMs?: number;
};

export class AiError extends Error {
  readonly status: number;
  readonly errorCode?: string;
  readonly requestId?: string;

  constructor(message: string, status: number, errorCode?: string, requestId?: string) {
    super(message);
    this.name = 'AiError';
    this.status = status;
    this.errorCode = errorCode;
    this.requestId = requestId;
  }
}

const metaSchema = z.object({
  model: z.string(),
  provider: z.string(),
  processingMs: z.number(),
  estimatedCostUsd: z.number(),
  fallbackUsed: z.boolean(),
});

export const transcriptionSchema = z.object({
  text: z.string(),
  language: z.string().nullish(),
  durationSeconds: z.number(),
  segments: z.array(
    z.object({
      start: z.number(),
      end: z.number(),
      text: z.string(),
      words: z.array(z.object({ text: z.string(), start: z.number(), end: z.number() })).nullish(),
    }),
  ),
  meta: metaSchema,
});

const issueSchema = z.object({
  type: z.string(),
  expected: z.string().nullable(),
  heard: z.string().nullable(),
  message: z.string(),
});

export const pronunciationSchema = z.object({
  method: z.string(),
  referenceText: z.string(),
  recognizedText: z.string(),
  scores: z.object({ overall: z.number(), accuracy: z.number(), completeness: z.number() }),
  counts: z.object({
    morae: z.number(),
    matched: z.number(),
    substituted: z.number(),
    omitted: z.number(),
    inserted: z.number(),
  }),
  speechRateMoraePerSecond: z.number().nullable(),
  durationSeconds: z.number(),
  words: z.array(
    z.object({
      text: z.string(),
      expected: z.string(),
      heard: z.string(),
      status: z.enum(['ok', 'partial', 'missed']),
      issues: z.array(issueSchema),
    }),
  ),
  limitations: z.array(z.string()),
  meta: metaSchema,
});

export const analysisSchema = z.object({
  text: z.string(),
  reading: z.string(),
  romaji: z.string(),
  tokens: z.array(
    z.object({
      surface: z.string(),
      lemma: z.string(),
      reading: z.string().nullable(),
      romaji: z.string().nullable(),
      pos: z.string(),
      posDetail: z.array(z.string()),
      conjugationType: z.string().nullable(),
      conjugationForm: z.string().nullable(),
      conjugationFormEn: z.string().nullable(),
      furigana: z.array(z.object({ text: z.string(), reading: z.string().nullable() })).nullable(),
      start: z.number(),
      end: z.number(),
      isWord: z.boolean(),
      isOov: z.boolean(),
    }),
  ),
});

export type Transcription = z.infer<typeof transcriptionSchema>;
export type PronunciationResult = z.infer<typeof pronunciationSchema>;
export type Analysis = z.infer<typeof analysisSchema>;

type Envelope = { message?: string; errorCode?: string; requestId?: string; data?: unknown };

export const createAiClient = ({ baseUrl, getAccessToken, refreshAccessToken, timeoutMs = 60_000 }: AiClientOptions) => {
  const root = baseUrl.replace(/\/$/, '');

  const send = async (path: string, init: RequestInit, token: string | null) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (token) headers.set('Authorization', `Bearer ${token}`);
    try {
      return await fetch(`${root}${path}`, { ...init, headers, signal: controller.signal });
    } catch (error) {
      if (controller.signal.aborted) throw new AiError('Request timed out', 0, 'TIMEOUT');
      throw new AiError(error instanceof Error ? error.message : 'Network error', 0, 'NETWORK');
    } finally {
      clearTimeout(timer);
    }
  };

  const request = async <T>(path: string, makeInit: () => RequestInit, schema: z.ZodType<T>): Promise<T> => {
    let response = await send(path, makeInit(), await getAccessToken());
    if (response.status === 401 && refreshAccessToken) {
      const fresh = await refreshAccessToken();
      // A FormData body can only be sent once, so the init is rebuilt for the retry.
      if (fresh) response = await send(path, makeInit(), fresh);
    }

    let envelope: Envelope = {};
    try {
      envelope = (await response.json()) as Envelope;
    } catch {
      // non-JSON body (e.g. a proxy error page)
    }
    if (!response.ok) {
      throw new AiError(envelope.message ?? response.statusText, response.status, envelope.errorCode, envelope.requestId);
    }
    const parsed = schema.safeParse(envelope.data);
    if (!parsed.success) throw new AiError(`Unexpected response from ${path}`, 0, 'INVALID_RESPONSE');
    return parsed.data;
  };

  const form = (fields: Record<string, string | undefined>, file: AiFile) => () => {
    const body = new FormData();
    // React Native's FormData accepts {uri, name, type}; the DOM typings only know Blob.
    body.append('file', file as Blob);
    for (const [key, value] of Object.entries(fields)) if (value !== undefined) body.append(key, value);
    return { method: 'POST', body };
  };

  return {
    analyze: (text: string, splitMode: 'A' | 'B' | 'C' = 'C') =>
      request(
        '/api/v1/language/analyze',
        () => ({ method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text, splitMode }) }),
        analysisSchema,
      ),
    transcribe: (file: AiFile, options: { model?: string; wordTimestamps?: boolean } = {}) =>
      request(
        '/api/v1/speech/transcribe',
        form({ model: options.model, wordTimestamps: options.wordTimestamps ? 'true' : undefined }, file),
        transcriptionSchema,
      ),
    evaluatePronunciation: (file: AiFile, referenceText: string, options: { model?: string } = {}) =>
      request('/api/v1/pronunciation/evaluate', form({ referenceText, model: options.model }, file), pronunciationSchema),
  };
};

export type AiClient = ReturnType<typeof createAiClient>;
