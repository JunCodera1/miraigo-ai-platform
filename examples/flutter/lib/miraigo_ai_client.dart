/// Client for the MiraiGo Japanese AI Platform. Pure Dart (package:http), so it runs in
/// Flutter on Android, iOS, web and desktop.
///
/// Responses use the MiraiGo envelope `{status, message, errorCode?, data?, requestId?}`;
/// this client unwraps `data` and throws [AiException] for errors.
library;

import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class AiException implements Exception {
  AiException(this.message, this.status, {this.errorCode, this.requestId});
  final String message;
  final int status;
  final String? errorCode;
  final String? requestId;

  @override
  String toString() => 'AiException($status ${errorCode ?? ''}): $message';
}

/// Returns the current MiraiGo access token (the same one the backend accepts).
typedef TokenProvider = Future<String?> Function();

class MiraigoAiClient {
  MiraigoAiClient({
    required this.baseUrl,
    required this.getAccessToken,
    this.refreshAccessToken,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 60),
  }) : _http = httpClient ?? http.Client();

  final String baseUrl;
  final TokenProvider getAccessToken;

  /// Called once after a 401; return a new token or null if the session is over.
  final TokenProvider? refreshAccessToken;
  final Duration timeout;
  final http.Client _http;

  Uri _uri(String path) => Uri.parse('${baseUrl.replaceAll(RegExp(r'/$'), '')}$path');

  Future<Map<String, dynamic>> _send(Future<http.BaseRequest> Function(String? token) build) async {
    var response = await _execute(await build(await getAccessToken()));
    if (response.statusCode == 401 && refreshAccessToken != null) {
      final fresh = await refreshAccessToken!();
      if (fresh != null) response = await _execute(await build(fresh));
    }
    Map<String, dynamic> body;
    try {
      body = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    } catch (_) {
      throw AiException('Unexpected response', response.statusCode);
    }
    if (response.statusCode >= 400) {
      throw AiException(body['message'] as String? ?? 'Request failed', response.statusCode,
          errorCode: body['errorCode'] as String?, requestId: body['requestId'] as String?);
    }
    return body['data'] as Map<String, dynamic>;
  }

  Future<http.Response> _execute(http.BaseRequest request) async {
    final streamed = await _http.send(request).timeout(timeout);
    return http.Response.fromStream(streamed);
  }

  Map<String, String> _headers(String? token) => {
        'Accept': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  /// Tokens, readings (hiragana), furigana, romaji and conjugation for [text].
  Future<Map<String, dynamic>> analyze(String text, {String splitMode = 'C'}) => _send((token) async {
        return http.Request('POST', _uri('/api/v1/language/analyze'))
          ..headers.addAll({..._headers(token), 'Content-Type': 'application/json'})
          ..body = jsonEncode({'text': text, 'splitMode': splitMode});
      });

  /// Speech to text. [audio] is any common audio/video file (m4a, wav, webm, mp4...).
  Future<TranscriptionResult> transcribe(Uint8List audio, String filename,
      {bool wordTimestamps = false, String? model}) async {
    final data = await _send((token) async {
      return http.MultipartRequest('POST', _uri('/api/v1/speech/transcribe'))
        ..headers.addAll(_headers(token))
        ..files.add(http.MultipartFile.fromBytes('file', audio, filename: filename))
        ..fields.addAll({if (wordTimestamps) 'wordTimestamps': 'true', if (model != null) 'model': model});
    });
    return TranscriptionResult.fromJson(data);
  }

  /// Scores a recording of the learner reading [referenceText] aloud.
  Future<PronunciationResult> evaluatePronunciation(Uint8List audio, String filename, String referenceText) async {
    final data = await _send((token) async {
      return http.MultipartRequest('POST', _uri('/api/v1/pronunciation/evaluate'))
        ..headers.addAll(_headers(token))
        ..files.add(http.MultipartFile.fromBytes('file', audio, filename: filename))
        ..fields['referenceText'] = referenceText;
    });
    return PronunciationResult.fromJson(data);
  }

  void close() => _http.close();
}

class Segment {
  Segment(this.start, this.end, this.text);
  final double start;
  final double end;
  final String text;
}

class TranscriptionResult {
  TranscriptionResult(this.text, this.durationSeconds, this.segments, this.model);
  final String text;
  final double durationSeconds;
  final List<Segment> segments;
  final String model;

  factory TranscriptionResult.fromJson(Map<String, dynamic> json) => TranscriptionResult(
        json['text'] as String,
        (json['durationSeconds'] as num).toDouble(),
        [
          for (final s in json['segments'] as List)
            Segment((s['start'] as num).toDouble(), (s['end'] as num).toDouble(), s['text'] as String)
        ],
        (json['meta'] as Map)['model'] as String,
      );
}

class PronunciationIssue {
  PronunciationIssue(this.type, this.expected, this.heard, this.message);
  final String type;
  final String? expected;
  final String? heard;
  final String message;
}

class WordScore {
  WordScore(this.text, this.expected, this.heard, this.status, this.issues);
  final String text;
  final String expected;
  final String heard;

  /// "ok", "partial" or "missed".
  final String status;
  final List<PronunciationIssue> issues;
}

class PronunciationResult {
  PronunciationResult(this.overall, this.accuracy, this.completeness, this.recognizedText, this.words, this.limitations);
  final int overall;
  final int accuracy;
  final int completeness;
  final String recognizedText;
  final List<WordScore> words;
  final List<String> limitations;

  factory PronunciationResult.fromJson(Map<String, dynamic> json) {
    final scores = json['scores'] as Map<String, dynamic>;
    return PronunciationResult(
      scores['overall'] as int,
      scores['accuracy'] as int,
      scores['completeness'] as int,
      json['recognizedText'] as String,
      [
        for (final w in json['words'] as List)
          WordScore(w['text'] as String, w['expected'] as String, w['heard'] as String, w['status'] as String, [
            for (final i in w['issues'] as List)
              PronunciationIssue(i['type'] as String, i['expected'] as String?, i['heard'] as String?, i['message'] as String)
          ])
      ],
      [for (final l in json['limitations'] as List) l as String],
    );
  }
}
