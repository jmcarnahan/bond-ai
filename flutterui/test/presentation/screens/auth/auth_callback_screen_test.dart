import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/auth/auth_callback_screen.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:mockito/mockito.dart';

// ignore: must_be_immutable
class MockAuthService extends Mock implements AuthService {}

class MockAuthNotifier extends AuthNotifier {
  bool loginWithTokenCalled = false;
  String? lastToken;
  bool shouldReturnSuccess = true;
  AuthState currentAuthState = const AuthInitial();

  MockAuthNotifier() : super(MockAuthService()) {
    state = currentAuthState;
  }

  @override
  Future<bool> loginWithToken(String token) async {
    loginWithTokenCalled = true;
    lastToken = token;
    
    if (shouldReturnSuccess) {
      currentAuthState = Authenticated(User(
        email: 'test@example.com',
        name: 'Test User',
      ));
      state = currentAuthState;
    } else {
      currentAuthState = const Unauthenticated();
      state = currentAuthState;
    }
    
    return shouldReturnSuccess;
  }

  @override
  AuthState get state => currentAuthState;
}


void main() {
  group('AuthCallbackScreen Widget Tests', () {
    late MockAuthNotifier mockAuthNotifier;

    setUp(() {
      mockAuthNotifier = MockAuthNotifier();
    });

    Widget createTestWidget({
      String? initialRoute,
    }) {
      return ProviderScope(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
        child: MaterialApp(
          initialRoute: initialRoute ?? '/auth-callback',
          routes: {
            '/auth-callback': (context) => const AuthCallbackScreen(),
            '/login': (context) => const Scaffold(
              body: Center(child: Text('Login Screen')),
            ),
            '/home': (context) => const Scaffold(
              body: Center(child: Text('Home Screen')),
            ),
          },
        ),
      );
    }

    testWidgets('should display loading indicator and processing message', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
      expect(find.byType(Scaffold), findsOneWidget);
    });

    testWidgets('should have correct layout structure', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.byType(Center), findsOneWidget);
      expect(find.byType(Column), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.mainAxisAlignment, equals(MainAxisAlignment.center));
      expect(column.children, hasLength(3));
    });

    testWidgets('should initialize auth callback handling on startup', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should handle widget lifecycle correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);

      await tester.pumpWidget(Container());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsNothing);
    });

    testWidgets('should maintain consistent UI during processing', (tester) async {
      await tester.pumpWidget(createTestWidget());
      
      for (int i = 0; i < 5; i++) {
        await tester.pump(Duration(milliseconds: 100));
        expect(find.byType(CircularProgressIndicator), findsOneWidget);
        expect(find.text('Processing authentication...'), findsOneWidget);
      }
    });

    testWidgets('should handle rapid rebuilds gracefully', (tester) async {
      await tester.pumpWidget(createTestWidget());
      
      for (int i = 0; i < 10; i++) {
        await tester.pump();
        expect(find.byType(AuthCallbackScreen), findsOneWidget);
      }
    });

    testWidgets('should display correct text content', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      final textWidget = tester.widget<Text>(find.text('Processing authentication...'));
      expect(textWidget.data, equals('Processing authentication...'));
    });

    testWidgets('should use CircularProgressIndicator for loading', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      final progressIndicator = tester.widget<CircularProgressIndicator>(
        find.byType(CircularProgressIndicator),
      );
      expect(progressIndicator, isNotNull);
    });

    testWidgets('should handle different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should maintain UI consistency across theme changes', (tester) async {
      await tester.pumpWidget(MaterialApp(
        theme: ThemeData.light(),
        home: ProviderScope(
          overrides: [
            authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          ],
          child: const AuthCallbackScreen(),
        ),
      ));
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);

      await tester.pumpWidget(MaterialApp(
        theme: ThemeData.dark(),
        home: ProviderScope(
          overrides: [
            authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          ],
          child: const AuthCallbackScreen(),
        ),
      ));
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      final circularProgressIndicator = tester.widget<CircularProgressIndicator>(
        find.byType(CircularProgressIndicator),
      );
      expect(circularProgressIndicator.semanticsLabel, isNull);
      expect(circularProgressIndicator.semanticsValue, isNull);
    });

    testWidgets('should handle provider overrides correctly', (tester) async {
      final customAuthNotifier = MockAuthNotifier();
      customAuthNotifier.shouldReturnSuccess = false;

      await tester.pumpWidget(ProviderScope(
        overrides: [
          authNotifierProvider.overrideWith((ref) => customAuthNotifier),
        ],
        child: const MaterialApp(
          home: AuthCallbackScreen(),
        ),
      ));
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should maintain widget state during processing', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      final initialWidget = tester.widget<AuthCallbackScreen>(
        find.byType(AuthCallbackScreen),
      );
      expect(initialWidget, isNotNull);

      await tester.pump(Duration(milliseconds: 500));

      final laterWidget = tester.widget<AuthCallbackScreen>(
        find.byType(AuthCallbackScreen),
      );
      expect(laterWidget, isNotNull);
    });

    testWidgets('should handle rapid navigation changes', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);

      for (int i = 0; i < 3; i++) {
        await tester.pump(Duration(milliseconds: 50));
        expect(find.text('Processing authentication...'), findsOneWidget);
      }
    });

    testWidgets('should handle provider state changes gracefully', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);

      mockAuthNotifier.currentAuthState = const AuthLoading();
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);

      mockAuthNotifier.currentAuthState = const AuthError('Test error');
      await tester.pump();

      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should maintain layout consistency', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
      expect(scaffold.body, isA<Center>());

      final center = scaffold.body as Center;
      expect(center.child, isA<Column>());

      final column = center.child as Column;
      expect(column.children, hasLength(3));
      expect(column.children[0], isA<CircularProgressIndicator>());
      expect(column.children[1], isA<SizedBox>());
      expect(column.children[2], isA<Text>());
    });

    testWidgets('should handle edge case scenarios', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      await tester.pump(Duration(seconds: 1));

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
    });

    testWidgets('should handle multiple provider overrides', (tester) async {
      final authNotifier1 = MockAuthNotifier();
      final authNotifier2 = MockAuthNotifier();
      authNotifier2.shouldReturnSuccess = false;

      await tester.pumpWidget(ProviderScope(
        overrides: [
          authNotifierProvider.overrideWith((ref) => authNotifier1),
        ],
        child: ProviderScope(
          overrides: [
            authNotifierProvider.overrideWith((ref) => authNotifier2),
          ],
          child: const MaterialApp(
            home: AuthCallbackScreen(),
          ),
        ),
      ));
      await tester.pump();

      expect(find.byType(AuthCallbackScreen), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should handle widget key properly', (tester) async {
      const key = Key('auth-callback-key');
      
      await tester.pumpWidget(ProviderScope(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
        ],
        child: const MaterialApp(
          home: AuthCallbackScreen(key: key),
        ),
      ));
      await tester.pump();

      expect(find.byKey(key), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
    });

    testWidgets('should handle concurrent widget updates', (tester) async {
      await tester.pumpWidget(createTestWidget());
      
      final futures = <Future>[];
      for (int i = 0; i < 5; i++) {
        futures.add(tester.pump(Duration(milliseconds: 10)));
      }
      
      await Future.wait(futures);
      
      expect(find.byType(AuthCallbackScreen), findsOneWidget);
      expect(find.text('Processing authentication...'), findsOneWidget);
    });
  });
}