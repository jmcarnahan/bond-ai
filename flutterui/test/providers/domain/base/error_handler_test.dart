import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/providers/domain/base/error_handler.dart';

class TestState {
  final String message;
  final AppError? error;

  TestState({required this.message, this.error});
}

class TestNotifier extends StateNotifier<TestState> with ErrorHandlerMixin<TestState> {
  TestNotifier() : super(TestState(message: 'initial'));

  @override
  void handleAppError(AppError error) {
    state = TestState(message: 'error handled', error: error);
  }

  void triggerError(dynamic error, [StackTrace? stackTrace]) {
    handleError(error, stackTrace);
  }
}

void main() {
  group('AppError Tests', () {
    test('constructor should create error with required message', () {
      const error = AppError(message: 'Test error');
      
      expect(error.message, equals('Test error'));
      expect(error.code, isNull);
      expect(error.originalError, isNull);
      expect(error.stackTrace, isNull);
    });

    test('constructor should create error with all fields', () {
      final originalError = Exception('Original');
      final stackTrace = StackTrace.current;
      
      final error = AppError(
        message: 'Test error',
        code: 'TEST_001',
        originalError: originalError,
        stackTrace: stackTrace,
      );
      
      expect(error.message, equals('Test error'));
      expect(error.code, equals('TEST_001'));
      expect(error.originalError, equals(originalError));
      expect(error.stackTrace, equals(stackTrace));
    });

    test('equality should work correctly', () {
      const error1 = AppError(message: 'Test error', code: 'TEST_001');
      const error2 = AppError(message: 'Test error', code: 'TEST_001');
      const error3 = AppError(message: 'Different error', code: 'TEST_001');
      
      expect(error1, equals(error2));
      expect(error1.hashCode, equals(error2.hashCode));
      expect(error1, isNot(equals(error3)));
    });

    test('toString should return formatted string', () {
      const error = AppError(message: 'Test error', code: 'TEST_001');
      
      final result = error.toString();
      expect(result, equals('AppError(message: Test error, code: TEST_001)'));
    });

    test('toString should handle null code', () {
      const error = AppError(message: 'Test error');
      
      final result = error.toString();
      expect(result, equals('AppError(message: Test error, code: null)'));
    });
  });

  group('ErrorHandlerMixin Tests', () {
    late TestNotifier notifier;

    setUp(() {
      notifier = TestNotifier();
    });

    test('should handle AppError directly', () {
      const appError = AppError(message: 'Custom app error', code: 'APP_001');
      
      notifier.triggerError(appError);
      
      expect(notifier.state.message, equals('error handled'));
      expect(notifier.state.error, equals(appError));
      expect(notifier.state.error!.message, equals('Custom app error'));
      expect(notifier.state.error!.code, equals('APP_001'));
    });

    test('should convert Exception to AppError', () {
      final exception = Exception('Test exception message');
      
      notifier.triggerError(exception);
      
      expect(notifier.state.message, equals('error handled'));
      expect(notifier.state.error, isNotNull);
      expect(notifier.state.error!.message, equals('Test exception message'));
      expect(notifier.state.error!.originalError, equals(exception));
    });

    test('should handle Exception with "Exception: " prefix', () {
      final exception = Exception('Exception: Test error');
      
      notifier.triggerError(exception);
      
      expect(notifier.state.error!.message, equals('Exception: Test error'));
    });

    test('should convert generic error to AppError', () {
      const genericError = 'Generic error string';
      
      notifier.triggerError(genericError);
      
      expect(notifier.state.message, equals('error handled'));
      expect(notifier.state.error, isNotNull);
      expect(notifier.state.error!.message, equals('Generic error string'));
      expect(notifier.state.error!.originalError, equals(genericError));
    });

    test('should handle null error', () {
      notifier.triggerError(null);
      
      expect(notifier.state.message, equals('error handled'));
      expect(notifier.state.error, isNotNull);
      expect(notifier.state.error!.message, equals('Unknown error occurred'));
      expect(notifier.state.error!.originalError, isNull);
    });

    test('should preserve stack trace', () {
      final stackTrace = StackTrace.current;
      final exception = Exception('Test with stack trace');
      
      notifier.triggerError(exception, stackTrace);
      
      expect(notifier.state.error!.stackTrace, equals(stackTrace));
    });

    test('should handle complex object errors', () {
      final complexError = {'type': 'NetworkError', 'statusCode': 500};
      
      notifier.triggerError(complexError);
      
      expect(notifier.state.error, isNotNull);
      expect(notifier.state.error!.message, contains('NetworkError'));
      expect(notifier.state.error!.originalError, equals(complexError));
    });
  });

  group('ErrorUtils Extension Tests', () {
    test('should convert AppError to itself', () {
      const originalError = AppError(message: 'Original error', code: 'TEST');
      
      final convertedError = originalError.toAppError();
      
      expect(convertedError, equals(originalError));
      expect(identical(convertedError, originalError), isTrue);
    });

    test('should convert Exception to AppError', () {
      final exception = Exception('Test exception');
      
      final appError = exception.toAppError();
      
      expect(appError.message, equals('Test exception'));
      expect(appError.originalError, equals(exception));
      expect(appError.code, isNull);
    });

    test('should convert Exception with stack trace', () {
      final exception = Exception('Test exception');
      final stackTrace = StackTrace.current;
      
      final appError = exception.toAppError(stackTrace);
      
      expect(appError.message, equals('Test exception'));
      expect(appError.originalError, equals(exception));
      expect(appError.stackTrace, equals(stackTrace));
    });

    test('should handle Exception with "Exception: " prefix', () {
      final exception = Exception('Exception: Detailed error');
      
      final appError = exception.toAppError();
      
      expect(appError.message, equals('Exception: Detailed error'));
    });

    test('should convert generic object to AppError', () {
      const error = 'String error message';
      
      final appError = error.toAppError();
      
      expect(appError.message, equals('String error message'));
      expect(appError.originalError, equals(error));
    });

    test('should convert int to AppError', () {
      const error = 404;
      
      final appError = error.toAppError();
      
      expect(appError.message, equals('404'));
      expect(appError.originalError, equals(error));
    });

    test('should convert Map to AppError', () {
      final error = {'message': 'Network error', 'code': 500};
      
      final appError = error.toAppError();
      
      expect(appError.message, contains('Network error'));
      expect(appError.originalError, equals(error));
    });

    test('should handle null values in conversion', () {
      const dynamic nullError = null;
      
      final appError = nullError.toAppError();
      
      expect(appError.message, equals('null'));
      expect(appError.originalError, isNull);
    });
  });

  group('Integration Tests', () {
    test('should work with StateNotifier lifecycle', () {
      final notifier = TestNotifier();
      expect(notifier.state.message, equals('initial'));
      expect(notifier.state.error, isNull);
      
      notifier.triggerError(Exception('Test error'));
      expect(notifier.state.message, equals('error handled'));
      expect(notifier.state.error, isNotNull);
    });

    test('should handle multiple error types in sequence', () {
      final notifier = TestNotifier();
      
      notifier.triggerError(Exception('First error'));
      expect(notifier.state.error!.message, equals('First error'));
      
      notifier.triggerError('Second error');
      expect(notifier.state.error!.message, equals('Second error'));
      
      const appError = AppError(message: 'Third error', code: 'CUSTOM');
      notifier.triggerError(appError);
      expect(notifier.state.error, equals(appError));
    });

    test('should preserve error details through conversion chain', () {
      final originalException = Exception('Original exception');
      final stackTrace = StackTrace.current;
      
      final appError = originalException.toAppError(stackTrace);
      
      expect(appError.message, equals('Original exception'));
      expect(appError.originalError, equals(originalException));
      expect(appError.stackTrace, equals(stackTrace));
      
      final convertedAgain = appError.toAppError();
      expect(identical(convertedAgain, appError), isTrue);
    });
  });
}