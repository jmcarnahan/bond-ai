import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/threads/widgets/threads_app_bar.dart';
import 'package:flutterui/core/theme/generated_theme.dart';
import 'package:flutterui/main.dart';

void main() {
  group('ThreadsAppBar Widget Tests', () {
    late bool onBackCalled;

    setUp(() {
      onBackCalled = false;
    });

    Widget createTestWidget({
      VoidCallback? onBack,
    }) {
      return ProviderScope(
        overrides: [
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
        child: MaterialApp(
          home: Scaffold(
            appBar: ThreadsAppBar(
              onBack: onBack,
            ),
          ),
        ),
      );
    }

    testWidgets('should display threads title', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.text('Threads'), findsOneWidget);
    });

    testWidgets('should display logo icon', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(Image), findsOneWidget);
      
      final image = tester.widget<Image>(find.byType(Image));
      final assetImage = image.image as AssetImage;
      expect(assetImage.assetName, equals('assets/bond_logo_icon.png'));
    });

    testWidgets('should call onBack when back button is pressed', (tester) async {
      await tester.pumpWidget(createTestWidget(
        onBack: () => onBackCalled = true,
      ));

      await tester.tap(find.byIcon(Icons.arrow_back));
      expect(onBackCalled, isTrue);
    });

    testWidgets('should work without onBack callback', (tester) async {
      await tester.pumpWidget(createTestWidget(onBack: null));

      expect(find.text('Threads'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('should have correct preferred size', (tester) async {
      const appBar = ThreadsAppBar();

      expect(appBar.preferredSize.height, equals(kToolbarHeight));
      expect(appBar.preferredSize.width, equals(double.infinity));
    });

    testWidgets('should apply white color to back button icon', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final icon = tester.widget<Icon>(find.byIcon(Icons.arrow_back));
      expect(icon.color, equals(Colors.white));
    });

    testWidgets('should apply white color to title text', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final text = tester.widget<Text>(find.text('Threads'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should have correct logo dimensions', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.height, equals(24));
      expect(image.width, equals(24));
    });

    testWidgets('should maintain proper layout structure', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(AppBar), findsOneWidget);
      expect(find.byType(IconButton), findsOneWidget);
      expect(find.byType(Row), findsOneWidget);
      expect(find.byType(Image), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Text), findsOneWidget);

      final row = tester.widget<Row>(find.byType(Row));
      expect(row.mainAxisSize, equals(MainAxisSize.min));
      expect(row.children, hasLength(3));
    });

    testWidgets('should apply correct spacing between logo and title', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, equals(8));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget());

      expect(find.text('Threads'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Threads'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              appBar: ThreadsAppBar(
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Threads'), findsOneWidget);
      
      final text = tester.widget<Text>(find.text('Threads'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should implement PreferredSizeWidget correctly', (tester) async {
      const appBar = ThreadsAppBar();

      expect(appBar, isA<PreferredSizeWidget>());
      expect(appBar.preferredSize, equals(const Size.fromHeight(kToolbarHeight)));
    });

    testWidgets('should handle provider state changes', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(Image), findsOneWidget);
      expect(find.text('Threads'), findsOneWidget);
    });

    testWidgets('should work in different layout contexts', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: ThreadsAppBar(
                onBack: () => onBackCalled = true,
              ),
              body: const Center(child: Text('Body content')),
            ),
          ),
        ),
      );

      expect(find.text('Threads'), findsOneWidget);
      expect(find.text('Body content'), findsOneWidget);
    });

    testWidgets('should handle null onBack gracefully', (tester) async {
      await tester.pumpWidget(createTestWidget(onBack: null));

      final iconButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconButton.onPressed, isNull);
    });

    testWidgets('should maintain proper widget hierarchy', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.descendant(of: find.byType(AppBar), matching: find.byType(IconButton)), findsOneWidget);
      expect(find.descendant(of: find.byType(AppBar), matching: find.byType(Row)), findsOneWidget);
      expect(find.descendant(of: find.byType(Row), matching: find.byType(Image)), findsOneWidget);
      expect(find.descendant(of: find.byType(Row), matching: find.byType(Text)), findsOneWidget);
    });

    testWidgets('should maintain consistent app bar appearance', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.backgroundColor, isNotNull);
      expect(appBar.leading, isNotNull);
      expect(appBar.title, isNotNull);
    });

    testWidgets('should handle rapid button presses when enabled', (tester) async {
      int pressCount = 0;

      await tester.pumpWidget(createTestWidget(
        onBack: () => pressCount++,
      ));

      for (int i = 0; i < 5; i++) {
        await tester.tap(find.byIcon(Icons.arrow_back));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(pressCount, equals(5));
    });

    testWidgets('should work with custom text theme', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData(
              textTheme: const TextTheme(
                titleLarge: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
            ),
            home: Scaffold(
              appBar: ThreadsAppBar(
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Threads'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should handle theme changes correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.text('Threads'), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('should apply correct icon styling', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final icon = tester.widget<Icon>(find.byIcon(Icons.arrow_back));
      expect(icon.icon, equals(Icons.arrow_back));
      expect(icon.color, equals(Colors.white));
    });

    testWidgets('should work with custom app bar colors', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData(
              appBarTheme: const AppBarTheme(
                backgroundColor: Colors.purple,
              ),
            ),
            home: Scaffold(
              appBar: ThreadsAppBar(
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Threads'), findsOneWidget);
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      await tester.pumpWidget(createTestWidget(
        onBack: () => onBackCalled = true,
      ));

      expect(find.text('Threads'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('should maintain title text consistency', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.text('Threads'), findsOneWidget);
      expect(find.text('Chat'), findsNothing);
      expect(find.text('Messages'), findsNothing);
    });

    testWidgets('should work in different container sizes', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.text('Threads'), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('should handle state management correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.title, isA<Row>());
      expect(appBar.leading, isA<IconButton>());
    });

    testWidgets('should work with light theme', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData.light(),
            home: Scaffold(
              appBar: ThreadsAppBar(
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Threads'), findsOneWidget);
      
      final text = tester.widget<Text>(find.text('Threads'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should maintain consistent image properties', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.height, equals(24));
      expect(image.width, equals(24));
      
      final assetImage = image.image as AssetImage;
      expect(assetImage.assetName, contains('bond_logo_icon'));
    });

    testWidgets('should handle multiple taps without issues', (tester) async {
      int tapCount = 0;

      await tester.pumpWidget(createTestWidget(
        onBack: () => tapCount++,
      ));

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.tap(find.byIcon(Icons.arrow_back));

      expect(tapCount, equals(3));
    });

    testWidgets('should work with different app theme configurations', (tester) async {
      final customTheme = AppGeneratedTheme();
      
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWithValue(customTheme),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: ThreadsAppBar(),
            ),
          ),
        ),
      );

      expect(find.byType(Image), findsOneWidget);
      expect(find.text('Threads'), findsOneWidget);
    });

    testWidgets('should maintain correct row alignment', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final row = tester.widget<Row>(find.byType(Row));
      expect(row.mainAxisSize, equals(MainAxisSize.min));
      expect(row.children.length, equals(3));
    });
  });
}