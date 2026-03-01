@TestOn('browser')
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/main.dart'
    show navigationIndexProvider, isUserNavigatingProvider;
import 'package:flutterui/providers/config_provider.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/providers/connections_provider.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/presentation/widgets/app_drawer.dart';

// ---------------------------------------------------------------------------
// Minimal stubs for providers the drawer watches
// ---------------------------------------------------------------------------

class _TestAppTheme implements AppTheme {
  @override
  ThemeData get themeData => ThemeData.light();
  @override
  String get name => 'Test';
  @override
  String get brandingMessage => '';
  @override
  String get logo => '';
  @override
  String get logoIcon => '';
}

class _FakeAuthNotifier extends StateNotifier<AuthState>
    implements AuthNotifier {
  _FakeAuthNotifier()
      : super(Authenticated(User(
          email: 'test@test.com',
          name: 'Test User',
          userId: 'test-user-id',
          provider: 'test',
        )));

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _FakeConnectionsNotifier extends StateNotifier<ConnectionsState>
    implements ConnectionsNotifier {
  _FakeConnectionsNotifier() : super(const ConnectionsState());

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

/// Builds a ProviderScope with the AppDrawer open, returning the container
/// so tests can inspect provider state.
Future<ProviderContainer> _pumpDrawer(
  WidgetTester tester, {
  bool agentsEnabled = true,
  int initialNavIndex = 1,
}) async {
  final container = ProviderContainer(
    overrides: [
      isAgentsEnabledProvider.overrideWithValue(agentsEnabled),
      authNotifierProvider.overrideWith((ref) => _FakeAuthNotifier()),
      appThemeProvider.overrideWithValue(_TestAppTheme()),
      connectionsNotifierProvider
          .overrideWith((ref) => _FakeConnectionsNotifier()),
      navigationIndexProvider.overrideWith((ref) => initialNavIndex),
      isUserNavigatingProvider.overrideWith((ref) => false),
    ],
  );

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        home: Scaffold(
          drawer: const AppDrawer(),
          body: const SizedBox.expand(),
        ),
      ),
    ),
  );

  // Open the drawer
  final scaffoldState =
      tester.firstState<ScaffoldState>(find.byType(Scaffold));
  scaffoldState.openDrawer();
  await tester.pumpAndSettle();

  return container;
}

/// Taps a drawer item, processes the synchronous state changes, then drains
/// the 500ms Future.delayed timer so the test framework doesn't complain
/// about pending timers on teardown.
Future<void> _tapDrawerItem(WidgetTester tester, String label) async {
  await tester.tap(find.text(label));
  // Process the tap (synchronous: Navigator.pop, provider state updates)
  await tester.pump();
  // Drain the 500ms isUserNavigating reset timer
  await tester.pump(const Duration(milliseconds: 600));
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

void main() {
  group('AppDrawer navigation items', () {
    testWidgets('shows Agents, Conversation, History when agents enabled',
        (tester) async {
      await _pumpDrawer(tester, agentsEnabled: true);

      expect(find.text('Agents'), findsOneWidget);
      expect(find.text('Conversation'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
    });

    testWidgets('hides Agents when agents disabled', (tester) async {
      await _pumpDrawer(tester, agentsEnabled: false, initialNavIndex: 0);

      expect(find.text('Agents'), findsNothing);
      expect(find.text('Conversation'), findsOneWidget);
      expect(find.text('History'), findsOneWidget);
    });

    testWidgets('always shows Connections, Profile, Logout', (tester) async {
      await _pumpDrawer(tester);

      expect(find.text('Connections'), findsOneWidget);
      expect(find.text('Profile'), findsOneWidget);
      expect(find.text('Logout'), findsOneWidget);
    });
  });

  group('AppDrawer sets navigationIndex correctly', () {
    testWidgets('tapping Agents sets index to 0', (tester) async {
      final container = await _pumpDrawer(tester, agentsEnabled: true);

      await _tapDrawerItem(tester, 'Agents');

      expect(container.read(navigationIndexProvider), 0);
    });

    testWidgets('tapping Conversation sets index to 1 (agents enabled)',
        (tester) async {
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: true,
        initialNavIndex: 0,
      );

      await _tapDrawerItem(tester, 'Conversation');

      expect(container.read(navigationIndexProvider), 1);
    });

    testWidgets('tapping History sets index to 2 (agents enabled)',
        (tester) async {
      final container = await _pumpDrawer(tester, agentsEnabled: true);

      await _tapDrawerItem(tester, 'History');

      expect(container.read(navigationIndexProvider), 2);
    });

    testWidgets('tapping Conversation sets index to 0 (agents disabled)',
        (tester) async {
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: false,
        initialNavIndex: 1,
      );

      await _tapDrawerItem(tester, 'Conversation');

      expect(container.read(navigationIndexProvider), 0);
    });

    testWidgets('tapping History sets index to 1 (agents disabled)',
        (tester) async {
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: false,
        initialNavIndex: 0,
      );

      await _tapDrawerItem(tester, 'History');

      expect(container.read(navigationIndexProvider), 1);
    });
  });

  group('AppDrawer sets isUserNavigating flag', () {
    testWidgets('tapping Agents sets isUserNavigating to true',
        (tester) async {
      final container = await _pumpDrawer(tester, agentsEnabled: true);
      expect(container.read(isUserNavigatingProvider), false);

      await tester.tap(find.text('Agents'));
      await tester.pump(); // Process tap only

      // Flag should be true immediately after tap
      expect(container.read(isUserNavigatingProvider), true);

      // Drain the timer
      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('tapping Conversation sets isUserNavigating to true',
        (tester) async {
      final container = await _pumpDrawer(tester);

      await tester.tap(find.text('Conversation'));
      await tester.pump();

      expect(container.read(isUserNavigatingProvider), true);

      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('tapping History sets isUserNavigating to true',
        (tester) async {
      final container = await _pumpDrawer(tester);

      await tester.tap(find.text('History'));
      await tester.pump();

      expect(container.read(isUserNavigatingProvider), true);

      await tester.pump(const Duration(milliseconds: 600));
    });

    testWidgets('isUserNavigating resets to false after 500ms delay',
        (tester) async {
      final container = await _pumpDrawer(tester);

      await tester.tap(find.text('History'));
      await tester.pump();
      expect(container.read(isUserNavigatingProvider), true);

      // Advance past the 500ms delay
      await tester.pump(const Duration(milliseconds: 600));
      expect(container.read(isUserNavigatingProvider), false);
    });
  });

  group('Regression: History navigation not hijacked', () {
    testWidgets(
        'tapping History results in History index, not Conversation index',
        (tester) async {
      // Core regression test for the bug where clicking History in the drawer
      // would navigate to Conversation instead.
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: true,
        initialNavIndex: 1, // Start on Conversation (typical state)
      );

      await _tapDrawerItem(tester, 'History');

      // History should be index 2 when agents are enabled
      final navIndex = container.read(navigationIndexProvider);
      expect(navIndex, 2, reason: 'History should be at index 2');

      // Verify it's NOT the Conversation index
      final navItems = container.read(bottomNavItemsProvider);
      final chatIndex =
          navItems.indexWhere((item) => item.label == 'Conversation');
      expect(navIndex, isNot(chatIndex),
          reason: 'History navigation must not resolve to Conversation index');
    });

    testWidgets('tapping History when already on History stays on History',
        (tester) async {
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: true,
        initialNavIndex: 2,
      );

      await _tapDrawerItem(tester, 'History');

      expect(container.read(navigationIndexProvider), 2);
    });

    testWidgets(
        'tapping Agents from History navigates to Agents, not Conversation',
        (tester) async {
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: true,
        initialNavIndex: 2,
      );

      await _tapDrawerItem(tester, 'Agents');

      expect(container.read(navigationIndexProvider), 0);
    });

    testWidgets(
        'each drawer nav item sets both navigationIndex and isUserNavigating',
        (tester) async {
      // Verify the fix is applied consistently: every navigation item must
      // set isUserNavigating to prevent the selectedThread listener from
      // hijacking navigation.
      final container = await _pumpDrawer(
        tester,
        agentsEnabled: true,
        initialNavIndex: 1,
      );

      // Test History
      await tester.tap(find.text('History'));
      await tester.pump();
      expect(container.read(navigationIndexProvider), 2);
      expect(container.read(isUserNavigatingProvider), true);

      // Drain timer and re-open drawer
      await tester.pump(const Duration(milliseconds: 600));
      final scaffoldState =
          tester.firstState<ScaffoldState>(find.byType(Scaffold));
      scaffoldState.openDrawer();
      await tester.pumpAndSettle();

      // Test Agents
      await tester.tap(find.text('Agents'));
      await tester.pump();
      expect(container.read(navigationIndexProvider), 0);
      expect(container.read(isUserNavigatingProvider), true);

      // Drain timer
      await tester.pump(const Duration(milliseconds: 600));
    });
  });
}
