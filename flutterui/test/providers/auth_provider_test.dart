import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';

// ignore: must_be_immutable
class MockAuthService implements AuthService {
  String? storedToken;
  User? mockUser;
  bool shouldThrowError = false;
  String? errorMessage;
  bool launchLoginUrlCalled = false;
  bool storeTokenCalled = false;
  bool clearTokenCalled = false;
  bool getCurrentUserCalled = false;
  bool retrieveTokenCalled = false;

  @override
  Future<String?> retrieveToken() async {
    retrieveTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock retrieve error');
    }
    return storedToken;
  }

  @override
  Future<User> getCurrentUser() async {
    getCurrentUserCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock user error');
    }
    if (mockUser == null) {
      throw Exception('No user found');
    }
    return mockUser!;
  }

  @override
  Future<void> storeToken(String token) async {
    storeTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock store error');
    }
    storedToken = token;
  }

  @override
  Future<void> clearToken() async {
    clearTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock clear error');
    }
    storedToken = null;
  }

  @override
  Future<void> launchLoginUrl() async {
    launchLoginUrlCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock launch error');
    }
  }

  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock headers error');
    }
    if (storedToken == null) {
      throw Exception('Not authenticated for this request.');
    }
    return {
      'Authorization': 'Bearer $storedToken',
      'Content-Type': 'application/json',
    };
  }
}

void main() {
  group('Auth Provider Tests', () {
    late MockAuthService mockAuthService;
    late ProviderContainer container;

    setUp(() {
      mockAuthService = MockAuthService();
      container = ProviderContainer(
        overrides: [
          authServiceProvider.overrideWithValue(mockAuthService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    group('AuthState Classes', () {
      test('AuthInitial should be const', () {
        const state1 = AuthInitial();
        const state2 = AuthInitial();
        expect(state1, equals(state2));
        expect(identical(state1, state2), isTrue);
      });

      test('AuthLoading should be const', () {
        const state1 = AuthLoading();
        const state2 = AuthLoading();
        expect(state1, equals(state2));
        expect(identical(state1, state2), isTrue);
      });

      test('Authenticated should implement equality correctly', () {
        final user1 = User(email: 'test@example.com', name: 'Test User');
        final user2 = User(email: 'test@example.com', name: 'Test User');
        final user3 = User(email: 'other@example.com', name: 'Other User');

        final auth1 = Authenticated(user1);
        final auth2 = Authenticated(user2);
        final auth3 = Authenticated(user3);

        expect(auth1, equals(auth2));
        expect(auth1, isNot(equals(auth3)));
        expect(auth1.hashCode, equals(auth2.hashCode));
      });

      test('Unauthenticated should handle optional message', () {
        const unauth1 = Unauthenticated();
        const unauth2 = Unauthenticated(message: 'Test message');

        expect(unauth1.message, isNull);
        expect(unauth2.message, equals('Test message'));
      });

      test('AuthError should store error message', () {
        const error = AuthError('Test error');
        expect(error.error, equals('Test error'));
      });
    });

    group('AuthNotifier Initial State', () {
      test('should start with AuthInitial state', () {
        final notifier = AuthNotifier(mockAuthService);
        expect(notifier.state, isA<AuthInitial>());
      });

      test('should check initial auth status on creation', () async {
        mockAuthService.storedToken = 'valid-token';
        mockAuthService.mockUser = User(
          email: 'test@example.com',
          name: 'Test User',
        );

        final notifier = AuthNotifier(mockAuthService);
        
        await Future.delayed(const Duration(milliseconds: 100));

        expect(mockAuthService.retrieveTokenCalled, isTrue);
        expect(mockAuthService.getCurrentUserCalled, isTrue);
        expect(notifier.state, isA<Authenticated>());
        
        final authenticatedState = notifier.state as Authenticated;
        expect(authenticatedState.user.email, equals('test@example.com'));
      });

      test('should set Unauthenticated when no token found', () async {
        mockAuthService.storedToken = null;

        final notifier = AuthNotifier(mockAuthService);
        
        await Future.delayed(const Duration(milliseconds: 100));

        expect(notifier.state, isA<Unauthenticated>());
      });

      test('should set Unauthenticated when token is empty', () async {
        mockAuthService.storedToken = '';

        final notifier = AuthNotifier(mockAuthService);
        
        await Future.delayed(const Duration(milliseconds: 100));

        expect(notifier.state, isA<Unauthenticated>());
      });

      test('should handle error during initial auth check', () async {
        mockAuthService.storedToken = 'invalid-token';
        mockAuthService.shouldThrowError = true;
        mockAuthService.errorMessage = 'Invalid token';

        final notifier = AuthNotifier(mockAuthService);
        
        await Future.delayed(const Duration(milliseconds: 100));

        expect(notifier.state, isA<Unauthenticated>());
        final unauthState = notifier.state as Unauthenticated;
        expect(unauthState.message, equals('Session error. Please log in again.'));
        expect(mockAuthService.clearTokenCalled, isTrue);
      });
    });

    group('initiateLogin', () {
      test('should call launchLoginUrl on auth service', () async {
        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.initiateLogin();

        expect(mockAuthService.launchLoginUrlCalled, isTrue);
      });

      test('should set AuthError state when launch fails', () async {
        mockAuthService.shouldThrowError = true;
        mockAuthService.errorMessage = 'Launch failed';

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.initiateLogin();

        expect(notifier.state, isA<AuthError>());
        final errorState = notifier.state as AuthError;
        expect(errorState.error, contains('Launch failed'));
      });
    });

    group('loginWithToken', () {
      test('should successfully login with valid token', () async {
        mockAuthService.mockUser = User(
          email: 'test@example.com',
          name: 'Test User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        final result = await notifier.loginWithToken('valid-token');

        expect(result, isTrue);
        expect(mockAuthService.storeTokenCalled, isTrue);
        expect(mockAuthService.getCurrentUserCalled, isTrue);
        expect(notifier.state, isA<Authenticated>());
        
        final authenticatedState = notifier.state as Authenticated;
        expect(authenticatedState.user.email, equals('test@example.com'));
      });

      test('should set AuthLoading state during login', () async {
        mockAuthService.mockUser = User(
          email: 'test@example.com',
          name: 'Test User',
        );

        final notifier = container.read(authNotifierProvider.notifier);
        
        final loginFuture = notifier.loginWithToken('valid-token');
        
        expect(notifier.state, isA<AuthLoading>());
        
        await loginFuture;
      });

      test('should handle store token error', () async {
        mockAuthService.shouldThrowError = true;
        mockAuthService.errorMessage = 'Storage failed';

        final notifier = container.read(authNotifierProvider.notifier);

        final result = await notifier.loginWithToken('invalid-token');

        expect(result, isFalse);
        expect(notifier.state, isA<AuthError>());
        expect(mockAuthService.clearTokenCalled, isTrue);
        
        final errorState = notifier.state as AuthError;
        expect(errorState.error, contains('Login failed'));
      });

      test('should handle getCurrentUser error', () async {
        mockAuthService.mockUser = null;

        final notifier = container.read(authNotifierProvider.notifier);

        final result = await notifier.loginWithToken('valid-token');

        expect(result, isFalse);
        expect(notifier.state, isA<AuthError>());
        expect(mockAuthService.clearTokenCalled, isTrue);
      });

      test('should handle empty token', () async {
        mockAuthService.mockUser = User(
          email: 'test@example.com',
          name: 'Test User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        final result = await notifier.loginWithToken('');

        expect(result, isTrue);
        expect(mockAuthService.storeTokenCalled, isTrue);
      });

      test('should handle special characters in token', () async {
        mockAuthService.mockUser = User(
          email: 'test@example.com',
          name: 'Test User',
        );

        const specialToken = 'token-with-special-chars-@#%^&*()';
        final notifier = container.read(authNotifierProvider.notifier);

        final result = await notifier.loginWithToken(specialToken);

        expect(result, isTrue);
        expect(mockAuthService.storedToken, equals(specialToken));
      });
    });

    group('logout', () {
      test('should successfully logout', () async {
        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.logout();

        expect(mockAuthService.clearTokenCalled, isTrue);
        expect(notifier.state, isA<Unauthenticated>());
        
        final unauthState = notifier.state as Unauthenticated;
        expect(unauthState.message, equals('Successfully logged out.'));
      });

      test('should set AuthLoading state during logout', () async {
        final notifier = container.read(authNotifierProvider.notifier);
        
        final logoutFuture = notifier.logout();
        
        expect(notifier.state, isA<AuthLoading>());
        
        await logoutFuture;
      });

      test('should handle logout error gracefully', () async {
        mockAuthService.shouldThrowError = true;
        mockAuthService.errorMessage = 'Clear token failed';

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.logout();

        expect(mockAuthService.clearTokenCalled, isTrue);
        expect(notifier.state, isA<Unauthenticated>());
        
        final unauthState = notifier.state as Unauthenticated;
        expect(unauthState.message, equals('Logged out, but encountered an issue clearing session.'));
      });
    });

    group('authNotifierProvider', () {
      test('should create AuthNotifier with injected auth service', () {
        final notifier = container.read(authNotifierProvider.notifier);
        expect(notifier, isA<AuthNotifier>());
      });

      test('should provide auth state correctly', () {
        final state = container.read(authNotifierProvider);
        expect(state, isA<AuthState>());
      });

      test('should handle provider refresh', () {
        final initialNotifier = container.read(authNotifierProvider.notifier);
        
        container.invalidate(authNotifierProvider);
        
        final newNotifier = container.read(authNotifierProvider.notifier);
        expect(newNotifier, isNot(same(initialNotifier)));
      });
    });

    group('Complex Workflows', () {
      test('should handle complete login workflow', () async {
        mockAuthService.mockUser = User(
          email: 'workflow@example.com',
          name: 'Workflow User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.initiateLogin();
        expect(mockAuthService.launchLoginUrlCalled, isTrue);

        final loginResult = await notifier.loginWithToken('workflow-token');
        expect(loginResult, isTrue);
        expect(notifier.state, isA<Authenticated>());

        await notifier.logout();
        expect(notifier.state, isA<Unauthenticated>());
      });

      test('should handle login failure then retry success', () async {
        final notifier = container.read(authNotifierProvider.notifier);

        mockAuthService.shouldThrowError = true;
        final firstResult = await notifier.loginWithToken('bad-token');
        expect(firstResult, isFalse);
        expect(notifier.state, isA<AuthError>());

        mockAuthService.shouldThrowError = false;
        mockAuthService.mockUser = User(
          email: 'retry@example.com',
          name: 'Retry User',
        );
        
        final secondResult = await notifier.loginWithToken('good-token');
        expect(secondResult, isTrue);
        expect(notifier.state, isA<Authenticated>());
      });

      test('should handle rapid state changes', () async {
        mockAuthService.mockUser = User(
          email: 'rapid@example.com',
          name: 'Rapid User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        final futures = <Future>[];
        for (int i = 0; i < 5; i++) {
          futures.add(notifier.loginWithToken('token-$i'));
        }

        await Future.wait(futures);
        expect(notifier.state, isA<Authenticated>());
      });
    });

    group('Edge Cases', () {
      test('should handle user with special characters', () async {
        mockAuthService.mockUser = User(
          email: 'spëcial@émojis.com',
          name: 'User with émojis 🚀',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.loginWithToken('special-token');

        expect(notifier.state, isA<Authenticated>());
        final authenticatedState = notifier.state as Authenticated;
        expect(authenticatedState.user.email, equals('spëcial@émojis.com'));
        expect(authenticatedState.user.name, equals('User with émojis 🚀'));
      });

      test('should handle user with empty properties', () async {
        mockAuthService.mockUser = User(
          email: '',
          name: '',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.loginWithToken('empty-user-token');

        expect(notifier.state, isA<Authenticated>());
        final authenticatedState = notifier.state as Authenticated;
        expect(authenticatedState.user.email, equals(''));
        expect(authenticatedState.user.name, equals(''));
      });

      test('should handle very long error messages', () async {
        const longError = 'This is a very long error message that should be handled properly without causing any issues in the authentication system even though it contains many characters and might be displayed to the user in various contexts throughout the application interface and logging systems.';
        
        mockAuthService.shouldThrowError = true;
        mockAuthService.errorMessage = longError;

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.initiateLogin();

        expect(notifier.state, isA<AuthError>());
        final errorState = notifier.state as AuthError;
        expect(errorState.error, equals('Exception: $longError'));
      });

      test('should handle null values gracefully', () async {
        mockAuthService.mockUser = User(
          email: 'null@test.com',
          name: 'Null Test',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.loginWithToken('null-token');
        expect(notifier.state, isA<Authenticated>());

        await notifier.logout();
        expect(notifier.state, isA<Unauthenticated>());
      });
    });

    group('State Persistence', () {
      test('should maintain state across multiple operations', () async {
        mockAuthService.mockUser = User(
          email: 'persistent@example.com',
          name: 'Persistent User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        await notifier.loginWithToken('persistent-token');
        final authenticatedState = notifier.state as Authenticated;
        
        expect(authenticatedState.user.email, equals('persistent@example.com'));

        await notifier.initiateLogin();
        
        expect(notifier.state, isA<Authenticated>());
        final stillAuthenticatedState = notifier.state as Authenticated;
        expect(stillAuthenticatedState.user.email, equals('persistent@example.com'));
      });

      test('should handle concurrent operations correctly', () async {
        mockAuthService.mockUser = User(
          email: 'concurrent@example.com',
          name: 'Concurrent User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        final loginFuture = notifier.loginWithToken('concurrent-token');
        final initiateFuture = notifier.initiateLogin();

        await Future.wait([loginFuture, initiateFuture]);

        expect(notifier.state, isA<Authenticated>());
      });
    });

    group('Service Integration', () {
      test('should properly integrate with auth service lifecycle', () {
        mockAuthService.mockUser = User(
          email: 'lifecycle@example.com',
          name: 'Lifecycle User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        expect(notifier, isA<AuthNotifier>());
        expect(mockAuthService, isA<AuthService>());
      });

      test('should handle service method call order correctly', () async {
        mockAuthService.mockUser = User(
          email: 'order@example.com',
          name: 'Order User',
        );

        final notifier = container.read(authNotifierProvider.notifier);

        mockAuthService.storeTokenCalled = false;
        mockAuthService.getCurrentUserCalled = false;

        await notifier.loginWithToken('order-token');

        expect(mockAuthService.storeTokenCalled, isTrue);
        expect(mockAuthService.getCurrentUserCalled, isTrue);
      });
    });
  });
}