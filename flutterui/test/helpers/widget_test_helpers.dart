import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/core/theme/base_theme.dart';

/// Widget testing utilities that provide common setup and helper functions
/// for widget tests. This eliminates repetitive boilerplate code and ensures
/// consistent testing environments across all widget tests.
class WidgetTestHelpers {
  
  // =============================================================================
  // BASIC WIDGET WRAPPERS
  // =============================================================================

  /// Creates a basic MaterialApp wrapper for widget testing
  static Widget createMaterialApp({
    required Widget child,
    ThemeData? theme,
    List<NavigatorObserver>? navigatorObservers,
    String? initialRoute,
    Map<String, WidgetBuilder>? routes,
  }) {
    return MaterialApp(
      home: child,
      theme: theme ?? const BaseTheme().themeData,
      navigatorObservers: navigatorObservers ?? [],
      initialRoute: initialRoute,
      routes: routes ?? {},
    );
  }

  /// Creates a MaterialApp wrapper with Scaffold for widget testing
  static Widget createScaffoldApp({
    required Widget child,
    AppBar? appBar,
    Widget? drawer,
    Widget? floatingActionButton,
    ThemeData? theme,
  }) {
    return createMaterialApp(
      theme: theme,
      child: Scaffold(
        appBar: appBar,
        body: child,
        drawer: drawer,
        floatingActionButton: floatingActionButton,
      ),
    );
  }

  // =============================================================================
  // RIVERPOD WIDGET WRAPPERS
  // =============================================================================

  /// Creates a ProviderScope wrapper for testing Riverpod providers
  static Widget createProviderScopeApp({
    required Widget child,
    required ProviderContainer container,
    ThemeData? theme,
    List<NavigatorObserver>? navigatorObservers,
  }) {
    return UncontrolledProviderScope(
      container: container,
      child: createMaterialApp(
        child: child,
        theme: theme,
        navigatorObservers: navigatorObservers,
      ),
    );
  }

  /// Creates a ProviderScope wrapper with Scaffold for testing
  static Widget createProviderScopeScaffoldApp({
    required Widget child,
    required ProviderContainer container,
    AppBar? appBar,
    Widget? drawer,
    Widget? floatingActionButton,
    ThemeData? theme,
  }) {
    return UncontrolledProviderScope(
      container: container,
      child: createScaffoldApp(
        child: child,
        appBar: appBar,
        drawer: drawer,
        floatingActionButton: floatingActionButton,
        theme: theme,
      ),
    );
  }

  /// Creates a ProviderScope with custom overrides
  static Widget createProviderAppWithOverrides({
    required Widget child,
    required List<Override> overrides,
    ThemeData? theme,
    List<NavigatorObserver>? navigatorObservers,
  }) {
    return ProviderScope(
      overrides: overrides,
      child: createMaterialApp(
        child: child,
        theme: theme,
        navigatorObservers: navigatorObservers,
      ),
    );
  }

  // =============================================================================
  // RESPONSIVE DESIGN TESTING
  // =============================================================================

  /// Creates a widget with specific screen size for responsive testing
  static Widget createResponsiveApp({
    required Widget child,
    required Size screenSize,
    required ProviderContainer container,
    ThemeData? theme,
  }) {
    return UncontrolledProviderScope(
      container: container,
      child: MediaQuery(
        data: MediaQueryData(size: screenSize),
        child: createMaterialApp(
          child: child,
          theme: theme,
        ),
      ),
    );
  }

  /// Creates a mobile-sized app for mobile UI testing
  static Widget createMobileApp({
    required Widget child,
    required ProviderContainer container,
    ThemeData? theme,
  }) {
    return createResponsiveApp(
      child: child,
      container: container,
      screenSize: const Size(375, 812), // iPhone X dimensions
      theme: theme,
    );
  }

  /// Creates a tablet-sized app for tablet UI testing
  static Widget createTabletApp({
    required Widget child,
    required ProviderContainer container,
    ThemeData? theme,
  }) {
    return createResponsiveApp(
      child: child,
      container: container,
      screenSize: const Size(768, 1024), // iPad dimensions
      theme: theme,
    );
  }

  /// Creates a desktop-sized app for desktop UI testing
  static Widget createDesktopApp({
    required Widget child,
    required ProviderContainer container,
    ThemeData? theme,
  }) {
    return createResponsiveApp(
      child: child,
      container: container,
      screenSize: const Size(1920, 1080), // Desktop dimensions
      theme: theme,
    );
  }

  // =============================================================================
  // THEME TESTING HELPERS
  // =============================================================================

  /// Creates an app with light theme for theme testing
  static Widget createLightThemeApp({
    required Widget child,
    required ProviderContainer container,
  }) {
    return createProviderScopeApp(
      child: child,
      container: container,
      theme: const BaseTheme().themeData,
    );
  }

  /// Creates an app with dark theme for theme testing
  static Widget createDarkThemeApp({
    required Widget child,
    required ProviderContainer container,
  }) {
    return createProviderScopeApp(
      child: child,
      container: container,
      theme: ThemeData.dark(),
    );
  }

  /// Creates an app with custom theme for theme testing
  static Widget createCustomThemeApp({
    required Widget child,
    required ProviderContainer container,
    required ThemeData theme,
  }) {
    return createProviderScopeApp(
      child: child,
      container: container,
      theme: theme,
    );
  }

  // =============================================================================
  // NAVIGATION TESTING HELPERS
  // =============================================================================

  /// Creates an app with navigation testing setup
  static Widget createNavigationTestApp({
    required Widget child,
    required ProviderContainer container,
    required List<NavigatorObserver> navigatorObservers,
    Map<String, WidgetBuilder>? routes,
    String? initialRoute,
  }) {
    return createProviderScopeApp(
      child: child,
      container: container,
      navigatorObservers: navigatorObservers,
    );
  }

  /// Creates an app with route testing capabilities
  static Widget createRoutingTestApp({
    required Map<String, WidgetBuilder> routes,
    required ProviderContainer container,
    String? initialRoute,
    List<NavigatorObserver>? navigatorObservers,
  }) {
    return UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        routes: routes,
        initialRoute: initialRoute ?? '/',
        navigatorObservers: navigatorObservers ?? [],
        theme: const BaseTheme().themeData,
      ),
    );
  }

  // =============================================================================
  // ACCESSIBILITY TESTING HELPERS
  // =============================================================================

  /// Creates an app with accessibility testing configurations
  static Widget createAccessibilityTestApp({
    required Widget child,
    required ProviderContainer container,
    double textScaleFactor = 1.0,
    bool boldText = false,
    bool highContrast = false,
  }) {
    return UncontrolledProviderScope(
      container: container,
      child: MediaQuery(
        data: MediaQueryData(
          textScaler: TextScaler.linear(textScaleFactor),
          boldText: boldText,
          highContrast: highContrast,
        ),
        child: createMaterialApp(child: child),
      ),
    );
  }

  // =============================================================================
  // WIDGET FINDER HELPERS
  // =============================================================================

  /// Finds widgets by their exact text content
  static Finder findByText(String text) => find.text(text);

  /// Finds widgets by text containing a substring
  static Finder findByTextContaining(String substring) => 
      find.textContaining(substring);

  /// Finds widgets by their key
  static Finder findByKey(Key key) => find.byKey(key);

  /// Finds widgets by their type
  static Finder findByType<T extends Widget>() => find.byType(T);

  /// Finds widgets by icon
  static Finder findByIcon(IconData icon) => find.byIcon(icon);

  /// Finds the first widget of a specific type
  static Finder findFirstByType<T extends Widget>() => 
      find.byType(T).first;

  /// Finds the last widget of a specific type
  static Finder findLastByType<T extends Widget>() => 
      find.byType(T).last;

  // =============================================================================
  // INTERACTION HELPERS
  // =============================================================================

  /// Taps a widget and waits for the animation to complete
  static Future<void> tapAndSettle(WidgetTester tester, Finder finder) async {
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  /// Enters text in a widget and waits for the animation to complete
  static Future<void> enterTextAndSettle(
    WidgetTester tester, 
    Finder finder, 
    String text,
  ) async {
    await tester.enterText(finder, text);
    await tester.pumpAndSettle();
  }

  /// Scrolls a widget and waits for the animation to complete
  static Future<void> scrollAndSettle(
    WidgetTester tester,
    Finder finder,
    Offset offset,
  ) async {
    await tester.drag(finder, offset);
    await tester.pumpAndSettle();
  }

  /// Drags a widget and waits for the animation to complete
  static Future<void> dragAndSettle(
    WidgetTester tester,
    Finder finder,
    Offset offset,
  ) async {
    await tester.drag(finder, offset);
    await tester.pumpAndSettle();
  }

  /// Long presses a widget and waits for the animation to complete
  static Future<void> longPressAndSettle(WidgetTester tester, Finder finder) async {
    await tester.longPress(finder);
    await tester.pumpAndSettle();
  }

  // =============================================================================
  // ASSERTION HELPERS
  // =============================================================================

  /// Verifies that a widget exists
  static void expectWidgetExists(Finder finder) {
    expect(finder, findsOneWidget);
  }

  /// Verifies that a widget does not exist
  static void expectWidgetNotExists(Finder finder) {
    expect(finder, findsNothing);
  }

  /// Verifies that multiple widgets exist
  static void expectWidgetsExist(Finder finder, int count) {
    expect(finder, findsNWidgets(count));
  }

  /// Verifies text content
  static void expectText(String text) {
    expect(find.text(text), findsOneWidget);
  }

  /// Verifies text contains substring
  static void expectTextContaining(String substring) {
    expect(find.textContaining(substring), findsOneWidget);
  }

  /// Verifies widget is enabled
  static void expectEnabled(WidgetTester tester, Finder finder) {
    final widget = tester.widget(finder);
    if (widget is ButtonStyleButton) {
      expect(widget.onPressed, isNotNull);
    } else if (widget is TextField) {
      expect(widget.enabled, isTrue);
    }
  }

  /// Verifies widget is disabled
  static void expectDisabled(WidgetTester tester, Finder finder) {
    final widget = tester.widget(finder);
    if (widget is ButtonStyleButton) {
      expect(widget.onPressed, isNull);
    } else if (widget is TextField) {
      expect(widget.enabled, isFalse);
    }
  }

  // =============================================================================
  // TIMING HELPERS
  // =============================================================================

  /// Waits for a specific duration
  static Future<void> wait(Duration duration) async {
    await Future.delayed(duration);
  }

  /// Pumps the widget tree for a specific duration
  static Future<void> pumpFor(WidgetTester tester, Duration duration) async {
    await tester.pump(duration);
  }

  /// Pumps and settles with a specific timeout
  static Future<void> pumpAndSettleWithTimeout(
    WidgetTester tester, {
    Duration timeout = const Duration(seconds: 10),
  }) async {
    await tester.pumpAndSettle(timeout);
  }

  // =============================================================================
  // DEBUGGING HELPERS
  // =============================================================================

  /// Prints the widget tree for debugging
  static void debugPrintWidgetTree(WidgetTester tester) {
    debugPrint(tester.allWidgets.toString());
  }

  /// Prints all text widgets in the tree
  static void debugPrintAllText(WidgetTester tester) {
    final textWidgets = find.byType(Text).evaluate();
    for (final element in textWidgets) {
      final textWidget = element.widget as Text;
      debugPrint('Text: ${textWidget.data}');
    }
  }

  /// Takes a screenshot for debugging (requires golden tests setup)
  static Future<void> takeScreenshot(
    WidgetTester tester, 
    String fileName,
  ) async {
    await expectLater(
      find.byType(MaterialApp),
      matchesGoldenFile('screenshots/$fileName.png'),
    );
  }
}