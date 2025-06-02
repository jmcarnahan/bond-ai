import 'package:flutter_test/flutter_test.dart';
import 'package:logger/logger.dart';
import 'package:flutterui/core/utils/logger.dart';

void main() {
  group('Logger Configuration Tests', () {
    test('logger should be properly initialized', () {
      expect(logger, isA<Logger>());
    });


    test('logger should be able to log different levels', () {
      expect(() => logger.d('Debug message'), returnsNormally);
      expect(() => logger.i('Info message'), returnsNormally);
      expect(() => logger.w('Warning message'), returnsNormally);
      expect(() => logger.e('Error message'), returnsNormally);
    });
  });
}
