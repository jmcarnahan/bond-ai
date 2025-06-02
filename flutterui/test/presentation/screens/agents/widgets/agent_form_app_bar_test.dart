import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_form_app_bar.dart';
import 'package:flutterui/core/theme/app_theme.dart';
import 'package:flutterui/main.dart';

class MockAppTheme extends AppTheme {
  String get logoFull => 'assets/bond_logo.png';
  String get themeName => 'mock';

  @override
  String get logoIcon => 'assets/bond_logo_icon.png';
  
  @override
  String get brandingMessage => throw UnimplementedError();
  
  @override
  String get logo => throw UnimplementedError();
  
  @override
  String get name => throw UnimplementedError();
  
  @override
  ThemeData get themeData => throw UnimplementedError();
}


void main() {
  group('AgentFormAppBar Widget Tests', () {
    late bool onBackCalled;

    setUp(() {
      onBackCalled = false;
    });

    Widget createTestWidget({
      required bool isEditing,
      required bool isLoading,
      VoidCallback? onBack,
    }) {
      return ProviderScope(
        overrides: [
          appThemeProvider.overrideWithValue(MockAppTheme()),
        ],
        child: MaterialApp(
          home: Scaffold(
            appBar: AgentFormAppBar(
              isEditing: isEditing,
              isLoading: isLoading,
              onBack: onBack,
            ),
          ),
        ),
      );
    }

    testWidgets('should display create agent title when not editing', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.text('Edit Agent'), findsNothing);
    });

    testWidgets('should display edit agent title when editing', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: true,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Edit Agent'), findsOneWidget);
      expect(find.text('Create Agent'), findsNothing);
    });

    testWidgets('should call onBack when back button is pressed and not loading', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      await tester.tap(find.byIcon(Icons.arrow_back));
      expect(onBackCalled, isTrue);
    });

    testWidgets('should disable back button when loading', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: true,
          onBack: () => onBackCalled = true,
        ),
      );

      final iconButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconButton.onPressed, isNull);

      await tester.tap(find.byIcon(Icons.arrow_back));
      expect(onBackCalled, isFalse);
    });

    testWidgets('should enable back button when not loading', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final iconButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconButton.onPressed, isNotNull);
    });

    testWidgets('should work without onBack callback', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: null,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });

    testWidgets('should display logo icon', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.byType(Image), findsOneWidget);
      
      final image = tester.widget<Image>(find.byType(Image));
      final assetImage = image.image as AssetImage;
      expect(assetImage.assetName, equals('assets/bond_logo_icon.png'));
    });

    testWidgets('should have correct preferred size', (tester) async {
      const appBar = AgentFormAppBar(
        isEditing: false,
        isLoading: false,
      );

      expect(appBar.preferredSize.height, equals(kToolbarHeight));
      expect(appBar.preferredSize.width, equals(double.infinity));
    });

    testWidgets('should apply white color to back button icon', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.arrow_back));
      expect(icon.color, equals(Colors.white));
    });

    testWidgets('should apply white color to title text', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final text = tester.widget<Text>(find.text('Create Agent'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should have correct logo dimensions', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final image = tester.widget<Image>(find.byType(Image));
      expect(image.height, equals(24));
      expect(image.width, equals(24));
    });

    testWidgets('should maintain proper layout structure', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

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
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, equals(8));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Create Agent'), findsOneWidget);

      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should handle theme changes correctly', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.byType(AppBar), findsOneWidget);
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWithValue(MockAppTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData.dark(),
            home: Scaffold(
              appBar: AgentFormAppBar(
                isEditing: false,
                isLoading: false,
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      
      final text = tester.widget<Text>(find.text('Create Agent'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should handle both loading states correctly', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: true,
          onBack: () => onBackCalled = true,
        ),
      );

      final loadingButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(loadingButton.onPressed, isNull);

      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final enabledButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(enabledButton.onPressed, isNotNull);
    });

    testWidgets('should handle both editing states correctly', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);

      await tester.pumpWidget(
        createTestWidget(
          isEditing: true,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Edit Agent'), findsOneWidget);
    });

    testWidgets('should maintain consistent app bar appearance', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.backgroundColor, isNotNull);
      expect(appBar.leading, isNotNull);
      expect(appBar.title, isNotNull);
    });

    testWidgets('should handle rapid button presses when enabled', (tester) async {
      int pressCount = 0;

      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => pressCount++,
        ),
      );

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
            appThemeProvider.overrideWithValue(MockAppTheme()),
          ],
          child: MaterialApp(
            theme: ThemeData(
              textTheme: const TextTheme(
                titleLarge: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
              ),
            ),
            home: Scaffold(
              appBar: AgentFormAppBar(
                isEditing: false,
                isLoading: false,
                onBack: () => onBackCalled = true,
              ),
            ),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Create Agent'));
      expect(text.style?.color, equals(Colors.white));
    });

    testWidgets('should implement PreferredSizeWidget correctly', (tester) async {
      const appBar = AgentFormAppBar(
        isEditing: false,
        isLoading: false,
      );

      expect(appBar, isA<PreferredSizeWidget>());
      expect(appBar.preferredSize, equals(const Size.fromHeight(kToolbarHeight)));
    });

    testWidgets('should handle provider state changes', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.byType(Image), findsOneWidget);
      expect(find.text('Create Agent'), findsOneWidget);
    });

    testWidgets('should work in different layout contexts', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            appThemeProvider.overrideWithValue(MockAppTheme()),
          ],
          child: MaterialApp(
            home: Scaffold(
              appBar: AgentFormAppBar(
                isEditing: false,
                isLoading: false,
                onBack: () => onBackCalled = true,
              ),
              body: const Center(child: Text('Body content')),
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.text('Body content'), findsOneWidget);
    });

    testWidgets('should handle null onBack gracefully', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: null,
        ),
      );

      final iconButton = tester.widget<IconButton>(find.byType(IconButton));
      expect(iconButton.onPressed, isNull);
    });

    testWidgets('should maintain proper widget hierarchy', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.descendant(of: find.byType(AppBar), matching: find.byType(IconButton)), findsOneWidget);
      expect(find.descendant(of: find.byType(AppBar), matching: find.byType(Row)), findsOneWidget);
      expect(find.descendant(of: find.byType(Row), matching: find.byType(Image)), findsOneWidget);
      expect(find.descendant(of: find.byType(Row), matching: find.byType(Text)), findsOneWidget);
    });

    testWidgets('should handle combined state scenarios', (tester) async {
      final scenarios = [
        (isEditing: false, isLoading: false, expectedTitle: 'Create Agent'),
        (isEditing: false, isLoading: true, expectedTitle: 'Create Agent'),
        (isEditing: true, isLoading: false, expectedTitle: 'Edit Agent'),
        (isEditing: true, isLoading: true, expectedTitle: 'Edit Agent'),
      ];

      for (final scenario in scenarios) {
        await tester.pumpWidget(
          createTestWidget(
            isEditing: scenario.isEditing,
            isLoading: scenario.isLoading,
            onBack: () => onBackCalled = true,
          ),
        );

        expect(find.text(scenario.expectedTitle), findsOneWidget);
        
        final iconButton = tester.widget<IconButton>(find.byType(IconButton));
        if (scenario.isLoading) {
          expect(iconButton.onPressed, isNull);
        } else {
          expect(iconButton.onPressed, isNotNull);
        }
      }
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      await tester.pumpWidget(
        createTestWidget(
          isEditing: false,
          isLoading: false,
          onBack: () => onBackCalled = true,
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
    });
  });
}