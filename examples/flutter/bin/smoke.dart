// Smoke test against a running platform:
//   dart run bin/smoke.dart http://127.0.0.1:8090 path/to/audio.wav "参照テキスト" [accessToken]
import 'dart:io';

import 'package:miraigo_ai_client/miraigo_ai_client.dart';

Future<void> main(List<String> args) async {
  final client = MiraigoAiClient(
    baseUrl: args[0],
    getAccessToken: () async => args.length > 3 ? args[3] : null,
  );
  final audio = await File(args[1]).readAsBytes();
  try {
    final analysis = await client.analyze('昨日、友達と映画を見ました。');
    print('analyze: ${analysis['reading']} | ${analysis['romaji']}');
    final t = await client.transcribe(audio, args[1].split('/').last);
    print('transcribe [${t.model}] ${t.durationSeconds}s: ${t.text}');
    final p = await client.evaluatePronunciation(audio, args[1].split('/').last, args[2]);
    print('pronunciation: overall ${p.overall}, accuracy ${p.accuracy}, completeness ${p.completeness}');
    for (final w in p.words.where((w) => w.issues.isNotEmpty)) {
      print('  ${w.text}: ${w.issues.first.message}');
    }
    try {
      await client.evaluatePronunciation(audio, 'x.wav', '!!!');
    } on AiException catch (e) {
      print('expected error: $e');
    }
  } finally {
    client.close();
  }
}
