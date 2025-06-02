import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_save_button.dart';

void main() {
  group('AgentSaveButton Widget Tests', () {
    late bool onPressedCalled;

    setUp(() {
      onPressedCalled = false;
    });

    testWidgets('should display create button when not editing', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.text('Save Changes'), findsNothing);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('should display save button when editing', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: true,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Save Changes'), findsOneWidget);
      expect(find.text('Create Agent'), findsNothing);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('should call onPressed when button is enabled and tapped', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byType(ElevatedButton));
      expect(onPressedCalled, isTrue);
    });

    testWidgets('should be disabled when isLoading is true', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: true,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);

      await tester.tap(find.byType(ElevatedButton));
      expect(onPressedCalled, isFalse);
    });

    testWidgets('should be disabled when isFormValid is false', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: false,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);

      await tester.tap(find.byType(ElevatedButton));
      expect(onPressedCalled, isFalse);
    });

    testWidgets('should be disabled when both isLoading and isFormValid are problematic', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: true,
              isFormValid: false,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);

      await tester.tap(find.byType(ElevatedButton));
      expect(onPressedCalled, isFalse);
    });

    testWidgets('should work with null onPressed callback', (tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: null,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
    });

    testWidgets('should apply correct alignment and layout', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.byType(Align), findsOneWidget);
      expect(find.byType(Padding), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);

      final align = tester.widget<Align>(find.byType(Align));
      expect(align.alignment, equals(Alignment.bottomCenter));

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, equals(double.infinity));
    });

    testWidgets('should apply correct theme colors when enabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onPrimary: Colors.white,
            ),
          ),
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final style = button.style!;
      expect(style.backgroundColor?.resolve({}), equals(Colors.blue));
      expect(style.foregroundColor?.resolve({}), equals(Colors.white));
    });

    testWidgets('should apply correct styling when disabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: true,
              isFormValid: false,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final style = button.style!;
      expect(style.backgroundColor?.resolve({WidgetState.disabled}), equals(Colors.grey.shade400));
      expect(style.foregroundColor?.resolve({WidgetState.disabled}), equals(Colors.grey.shade700));
    });

    testWidgets('should have correct mouse cursor when enabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final mouseCursor = button.style!.mouseCursor?.resolve({});
      expect(mouseCursor, equals(SystemMouseCursors.click));
    });

    testWidgets('should have correct mouse cursor when disabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: true,
              isFormValid: false,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final mouseCursor = button.style!.mouseCursor?.resolve({WidgetState.disabled});
      expect(mouseCursor, equals(SystemMouseCursors.forbidden));
    });

    testWidgets('should handle button style properties correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final style = button.style!;
      
      expect(style.shape?.resolve({}), isA<RoundedRectangleBorder>());
      expect(style.elevation?.resolve({}), greaterThan(0));
      expect(style.padding, isNotNull);
      expect(style.textStyle, isNotNull);
    });

    testWidgets('should handle state changes correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: false,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final disabledButton = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(disabledButton.onPressed, isNull);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final enabledButton = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(enabledButton.onPressed, isNotNull);
    });

    testWidgets('should handle different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Create Agent'), findsOneWidget);

      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should maintain full width across screen sizes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.width, equals(double.infinity));
    });

    testWidgets('should handle rapid button presses when enabled', (tester) async {
      int pressCount = 0;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => pressCount++,
            ),
          ),
        ),
      );

      for (int i = 0; i < 5; i++) {
        await tester.tap(find.byType(ElevatedButton));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(pressCount, equals(5));
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.byType(ElevatedButton), findsOneWidget);
    });

    testWidgets('should handle both button text variations', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: true,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      expect(find.text('Save Changes'), findsOneWidget);
    });

    testWidgets('should handle loading state correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: true,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
      expect(find.text('Create Agent'), findsOneWidget);
    });

    testWidgets('should handle form validation state correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: false,
              isEditing: true,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.onPressed, isNull);
      expect(find.text('Save Changes'), findsOneWidget);
    });

    testWidgets('should maintain consistent bottom positioning', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final align = tester.widget<Align>(find.byType(Align));
      expect(align.alignment, equals(Alignment.bottomCenter));

      final padding = tester.widget<Padding>(find.byType(Padding));
      expect(padding.padding, isA<EdgeInsets>());
    });

    testWidgets('should handle custom theme colors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.purple,
              primary: Colors.purple,
              onPrimary: Colors.yellow,
            ),
          ),
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      final style = button.style!;
      expect(style.backgroundColor?.resolve({}), equals(Colors.purple));
      expect(style.foregroundColor?.resolve({}), equals(Colors.yellow));
    });

    testWidgets('should work in different container sizes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              height: 100,
              child: AgentSaveButton(
                isLoading: false,
                isFormValid: true,
                isEditing: false,
                onPressed: () => onPressedCalled = true,
              ),
            ),
          ),
        ),
      );

      expect(find.text('Create Agent'), findsOneWidget);
      
      await tester.tap(find.byType(ElevatedButton));
      expect(onPressedCalled, isTrue);
    });

    testWidgets('should handle text styling correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              titleMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.normal),
            ),
          ),
          home: Scaffold(
            body: AgentSaveButton(
              isLoading: false,
              isFormValid: true,
              isEditing: false,
              onPressed: () => onPressedCalled = true,
            ),
          ),
        ),
      );

      final button = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(button.style?.textStyle, isNotNull);
    });
  });
}