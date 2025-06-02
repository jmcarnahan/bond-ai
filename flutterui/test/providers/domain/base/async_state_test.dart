import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/providers/domain/base/async_state.dart';

void main() {
  group('AsyncState Tests', () {
    test('constructor should create state with default values', () {
      const state = AsyncState<String>();
      
      expect(state.data, isNull);
      expect(state.isLoading, isFalse);
      expect(state.error, isNull);
      expect(state.lastUpdated, isNull);
    });

    test('constructor should create state with provided values', () {
      const state = AsyncState<String>(
        data: 'test data',
        isLoading: true,
        error: 'test error',
        lastUpdated: null,
      );
      
      expect(state.data, equals('test data'));
      expect(state.isLoading, isTrue);
      expect(state.error, equals('test error'));
    });

    test('copyWith should update specific fields', () {
      const originalState = AsyncState<String>(
        data: 'original data',
        isLoading: false,
        error: 'original error',
      );
      
      final newState = originalState.copyWith(
        isLoading: true,
        data: 'new data',
      );
      
      expect(newState.data, equals('new data'));
      expect(newState.isLoading, isTrue);
      expect(newState.error, equals('original error'));
    });

    test('copyWith should clear error when clearError is true', () {
      const originalState = AsyncState<String>(
        data: 'test data',
        error: 'test error',
      );
      
      final newState = originalState.copyWith(clearError: true);
      
      expect(newState.data, equals('test data'));
      expect(newState.error, isNull);
    });

    test('copyWith should preserve fields when not specified', () {
      final lastUpdated = DateTime.now();
      final originalState = AsyncState<String>(
        data: 'test data',
        isLoading: true,
        error: 'test error',
        lastUpdated: lastUpdated,
      );
      
      final newState = originalState.copyWith();
      
      expect(newState.data, equals('test data'));
      expect(newState.isLoading, isTrue);
      expect(newState.error, equals('test error'));
      expect(newState.lastUpdated, equals(lastUpdated));
    });

    group('Getters', () {
      test('hasData should return true when data is not null', () {
        const state = AsyncState<String>(data: 'test');
        expect(state.hasData, isTrue);
      });

      test('hasData should return false when data is null', () {
        const state = AsyncState<String>();
        expect(state.hasData, isFalse);
      });

      test('hasError should return true when error is not null', () {
        const state = AsyncState<String>(error: 'test error');
        expect(state.hasError, isTrue);
      });

      test('hasError should return false when error is null', () {
        const state = AsyncState<String>();
        expect(state.hasError, isFalse);
      });

      test('isIdle should return true when not loading and no error', () {
        const state = AsyncState<String>(data: 'test');
        expect(state.isIdle, isTrue);
      });

      test('isIdle should return false when loading', () {
        const state = AsyncState<String>(isLoading: true);
        expect(state.isIdle, isFalse);
      });

      test('isIdle should return false when has error', () {
        const state = AsyncState<String>(error: 'test error');
        expect(state.isIdle, isFalse);
      });

      test('isSuccess should return true when has data, not loading, and no error', () {
        const state = AsyncState<String>(data: 'test');
        expect(state.isSuccess, isTrue);
      });

      test('isSuccess should return false when loading', () {
        const state = AsyncState<String>(data: 'test', isLoading: true);
        expect(state.isSuccess, isFalse);
      });

      test('isSuccess should return false when has error', () {
        const state = AsyncState<String>(data: 'test', error: 'error');
        expect(state.isSuccess, isFalse);
      });

      test('isSuccess should return false when no data', () {
        const state = AsyncState<String>();
        expect(state.isSuccess, isFalse);
      });
    });

    group('Equality', () {
      test('should be equal when all fields match', () {
        final lastUpdated = DateTime.now();
        final state1 = AsyncState<String>(
          data: 'test',
          isLoading: true,
          error: 'error',
          lastUpdated: lastUpdated,
        );
        final state2 = AsyncState<String>(
          data: 'test',
          isLoading: true,
          error: 'error',
          lastUpdated: lastUpdated,
        );
        
        expect(state1, equals(state2));
        expect(state1.hashCode, equals(state2.hashCode));
      });

      test('should not be equal when data differs', () {
        const state1 = AsyncState<String>(data: 'test1');
        const state2 = AsyncState<String>(data: 'test2');
        
        expect(state1, isNot(equals(state2)));
      });

      test('should not be equal when loading state differs', () {
        const state1 = AsyncState<String>(isLoading: true);
        const state2 = AsyncState<String>(isLoading: false);
        
        expect(state1, isNot(equals(state2)));
      });
    });

    test('toString should return formatted string', () {
      const state = AsyncState<String>(
        data: 'test',
        isLoading: true,
        error: 'error',
      );
      
      final result = state.toString();
      expect(result, contains('AsyncState<String>'));
      expect(result, contains('data: test'));
      expect(result, contains('isLoading: true'));
      expect(result, contains('error: error'));
    });

    group('Extensions', () {
      test('toLoading should set loading true and clear error', () {
        const originalState = AsyncState<String>(
          data: 'test',
          error: 'error',
        );
        
        final loadingState = originalState.toLoading();
        
        expect(loadingState.data, equals('test'));
        expect(loadingState.isLoading, isTrue);
        expect(loadingState.error, isNull);
      });

      test('toSuccess should set data, loading false, and clear error', () {
        const originalState = AsyncState<String>(
          isLoading: true,
          error: 'error',
        );
        
        final successState = originalState.toSuccess('new data');
        
        expect(successState.data, equals('new data'));
        expect(successState.isLoading, isFalse);
        expect(successState.error, isNull);
        expect(successState.lastUpdated, isNotNull);
      });

      test('toError should set error and loading false', () {
        const originalState = AsyncState<String>(
          data: 'test',
          isLoading: true,
        );
        
        final errorState = originalState.toError('new error');
        
        expect(errorState.data, equals('test'));
        expect(errorState.isLoading, isFalse);
        expect(errorState.error, equals('new error'));
      });

      test('clearError should remove error', () {
        const originalState = AsyncState<String>(
          data: 'test',
          error: 'error',
        );
        
        final clearedState = originalState.clearError();
        
        expect(clearedState.data, equals('test'));
        expect(clearedState.error, isNull);
      });
    });

    group('Generic Types', () {
      test('should work with int type', () {
        const state = AsyncState<int>(data: 42);
        expect(state.data, equals(42));
        expect(state.hasData, isTrue);
      });

      test('should work with List type', () {
        const state = AsyncState<List<String>>(data: ['a', 'b', 'c']);
        expect(state.data, equals(['a', 'b', 'c']));
        expect(state.hasData, isTrue);
      });

      test('should work with Map type', () {
        const state = AsyncState<Map<String, int>>(data: {'key': 123});
        expect(state.data, equals({'key': 123}));
        expect(state.hasData, isTrue);
      });

      test('should work with custom objects', () {
        final customObject = {'name': 'test', 'value': 42};
        final state = AsyncState<Map<String, dynamic>>(data: customObject);
        expect(state.data, equals(customObject));
        expect(state.hasData, isTrue);
      });
    });

    group('Edge Cases', () {
      test('should handle null data explicitly', () {
        const state = AsyncState<String?>(data: null);
        expect(state.data, isNull);
        expect(state.hasData, isFalse);
      });

      test('should handle empty string data', () {
        const state = AsyncState<String>(data: '');
        expect(state.data, equals(''));
        expect(state.hasData, isTrue);
      });

      test('should handle empty list data', () {
        const state = AsyncState<List<String>>(data: []);
        expect(state.data, equals([]));
        expect(state.hasData, isTrue);
      });

      test('should handle DateTime for lastUpdated', () {
        final now = DateTime.now();
        final state = AsyncState<String>(
          data: 'test',
          lastUpdated: now,
        );
        expect(state.lastUpdated, equals(now));
      });
    });
  });
}