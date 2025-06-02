import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/presentation/screens/auth/login_screen.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/core/theme/generated_theme.dart';
import 'package:flutterui/main.dart';
import 'package:mockito/mockito.dart';

class MockAuthNotifier extends AuthNotifier {
  AuthState _currentState = const Unauthenticated();
  bool initiateLoginCalled = false;

  MockAuthNotifier() : super(MockAuthService()) {
    state = _currentState;
  }

  void setState(AuthState state) {
    _currentState = state;
  }

  @override
  AuthState get state => _currentState;

  @override
  Future<void> initiateLogin() async {
    initiateLoginCalled = true;
  }
}

// ignore: must_be_immutable
class MockAuthService extends Mock implements AuthService {}

void main() {
  group('LoginScreen Widget Tests', () {
    late ProviderContainer container;
    late MockAuthNotifier mockAuthNotifier;

    setUp(() {
      mockAuthNotifier = MockAuthNotifier();
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should display login form with unauthenticated state', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text('Welcome to Bond AI'), findsOneWidget);
      expect(find.text('Sign in with Google'), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);
      expect(find.byType(Image), findsAtLeastNWidgets(1));
    });

    testWidgets('should display loading indicator when auth is loading', (tester) async {
      mockAuthNotifier.setState(const AuthLoading());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Sign in with Google'), findsNothing);
      expect(find.byType(ElevatedButton), findsNothing);
    });

    testWidgets('should display error message when auth has error', (tester) async {
      const errorMessage = 'Login failed';
      mockAuthNotifier.setState(const Unauthenticated(message: errorMessage));
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text(errorMessage), findsOneWidget);
      expect(find.text('Sign in with Google'), findsOneWidget);
    });

    testWidgets('should call initiateLogin when sign in button pressed', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      await tester.tap(find.byType(ElevatedButton));
      await tester.pump();

      expect(mockAuthNotifier.initiateLoginCalled, isTrue);
    });

    testWidgets('should show snackbar on auth error state change', (tester) async {
      final mockErrorNotifier = MockAuthNotifierWithError();
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      container.updateOverrides([
        authNotifierProvider.overrideWith((ref) => mockErrorNotifier),
        appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
      ]);

      await tester.pump();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Login Error: Authentication failed'), findsOneWidget);
    });

    testWidgets('should display mobile layout for small screens', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.byType(SingleChildScrollView), findsOneWidget);
      expect(find.byType(Row), findsNothing);
      expect(find.text('Welcome to Bond AI'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should display desktop layout for large screens', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(1200, 800));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.byType(Row), findsAtLeastNWidgets(1));
      expect(find.text('Welcome to Bond AI'), findsAtLeastNWidgets(1));
      expect(find.text('Efficient. Powerful. Everywhere.'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should display Google logo in sign in button', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      final images = find.byType(Image);
      expect(images, findsAtLeastNWidgets(2));
      
      final googleLogoImages = tester.widgetList<Image>(images).where((image) {
        if (image.image is AssetImage) {
          final assetImage = image.image as AssetImage;
          return assetImage.assetName.contains('google_logo.png');
        }
        return false;
      });
      
      expect(googleLogoImages, isNotEmpty);
    });

    testWidgets('should apply correct button styling', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      final elevatedButton = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final buttonStyle = elevatedButton.style;
      
      expect(buttonStyle?.backgroundColor?.resolve({}), equals(Colors.white));
      expect(buttonStyle?.foregroundColor?.resolve({}), equals(Colors.black87));
    });

    testWidgets('should display app theme name in welcome text', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.textContaining('Welcome to'), findsOneWidget);
      expect(find.text('Welcome to Bond AI'), findsOneWidget);
    });

    testWidgets('should handle different auth state transitions', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text('Sign in with Google'), findsOneWidget);

      final loadingNotifier = MockAuthNotifierLoading();
      container.updateOverrides([
        authNotifierProvider.overrideWith((ref) => loadingNotifier),
        appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
      ]);

      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(find.text('Sign in with Google'), findsNothing);

      final authenticatedNotifier = MockAuthNotifierAuthenticated();
      container.updateOverrides([
        authNotifierProvider.overrideWith((ref) => authenticatedNotifier),
        appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
      ]);

      await tester.pump();

      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('should maintain layout constraints', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      final constrainedBox = tester.widget<ConstrainedBox>(find.byType(ConstrainedBox).first);
      expect(constrainedBox.constraints.maxWidth, equals(400));
    });

    testWidgets('should handle card elevation and styling', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      final cards = tester.widgetList<Card>(find.byType(Card));
      expect(cards, isNotEmpty);
      
      for (final card in cards) {
        expect(card.elevation, greaterThan(0));
        expect(card.shape, isA<RoundedRectangleBorder>());
      }
    });

    testWidgets('should handle theme colors correctly', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                surface: Colors.blue,
                onSurface: Colors.white,
                error: Colors.red,
              ),
            ),
            home: const LoginScreen(),
          ),
        ),
      );

      final scaffold = tester.widget<Scaffold>(find.byType(Scaffold));
      expect(scaffold.backgroundColor, equals(Colors.blue));
    });

    testWidgets('should handle responsive breakpoint correctly', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(767, 800));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.byType(Row), findsNothing);

      await tester.binding.setSurfaceSize(const Size(769, 800));
      await tester.pump();

      expect(find.byType(Row), findsAtLeastNWidgets(1));

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle very small screen sizes', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(200, 400));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text('Welcome to Bond AI'), findsOneWidget);
      expect(find.text('Sign in with Google'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle very large screen sizes', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.binding.setSurfaceSize(const Size(1920, 1080));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text('Welcome to Bond AI'), findsAtLeastNWidgets(1));
      expect(find.text('Efficient. Powerful. Everywhere.'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle null error message gracefully', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated(message: null));
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.text('Sign in with Google'), findsOneWidget);
      expect(find.byType(Text), findsAtLeastNWidgets(1));
    });

    testWidgets('should render all required UI elements', (tester) async {
      mockAuthNotifier.setState(const Unauthenticated());
      container = ProviderContainer(
        overrides: [
          authNotifierProvider.overrideWith((ref) => mockAuthNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: LoginScreen(),
          ),
        ),
      );

      expect(find.byType(Scaffold), findsOneWidget);
      expect(find.byType(LayoutBuilder), findsOneWidget);
      expect(find.byType(Center), findsAtLeastNWidgets(1));
      expect(find.byType(Column), findsAtLeastNWidgets(1));
      expect(find.byType(SizedBox), findsAtLeastNWidgets(2));
    });
  });
}

class MockAuthNotifierWithError extends AuthNotifier {
  MockAuthNotifierWithError() : super(MockAuthService());

  @override
  AuthState get state => const AuthError('Authentication failed');
}

class MockAuthNotifierLoading extends AuthNotifier {
  MockAuthNotifierLoading() : super(MockAuthService());

  @override
  AuthState get state => const AuthLoading();
}

class MockAuthNotifierAuthenticated extends AuthNotifier {
  MockAuthNotifierAuthenticated() : super(MockAuthService());

  @override
  AuthState get state => Authenticated(
    User(email: 'test@example.com', name: 'Test User'),
  );
}