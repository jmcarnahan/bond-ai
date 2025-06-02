import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/create_agent_screen.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';
import 'package:flutterui/core/theme/generated_theme.dart';
import 'package:flutterui/main.dart';
import 'package:mockito/mockito.dart';

class MockRef extends Mock implements Ref<Object?> {}

class MockCreateAgentFormNotifier extends CreateAgentFormNotifier {
  String lastName = '';
  String lastDescription = '';
  String lastInstructions = '';
  bool lastEnableCodeInterpreter = false;
  bool lastEnableFileSearch = false;
  bool resetStateCalled = false;

  MockCreateAgentFormNotifier() : super(MockRef());

  @override
  void setName(String name) {
    lastName = name;
    state = state.copyWith(name: name);
  }

  @override
  void setDescription(String description) {
    lastDescription = description;
    state = state.copyWith(description: description);
  }

  @override
  void setInstructions(String instructions) {
    lastInstructions = instructions;
    state = state.copyWith(instructions: instructions);
  }

  @override
  void setEnableCodeInterpreter(bool enable) {
    lastEnableCodeInterpreter = enable;
    state = state.copyWith(enableCodeInterpreter: enable);
  }

  @override
  void setEnableFileSearch(bool enable) {
    lastEnableFileSearch = enable;
    state = state.copyWith(enableFileSearch: enable);
  }

  @override
  void resetState() {
    resetStateCalled = true;
    state = CreateAgentFormState();
  }
}

class MockAppThemeNotifier extends Mock implements AppGeneratedTheme {}

void main() {
  group('CreateAgentScreen Widget Tests', () {
    late MockCreateAgentFormNotifier mockFormNotifier;

    setUp(() {
      mockFormNotifier = MockCreateAgentFormNotifier();
    });

    Widget createTestWidget({
      CreateAgentFormState? initialFormState,
    }) {
      return ProviderScope(
        overrides: [
          createAgentFormProvider.overrideWith((ref) => mockFormNotifier),
          appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
        ],
        child: MaterialApp(
          home: CreateAgentScreen(),
        ),
      );
    }

    testWidgets('should display all required UI elements', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Create Agent'), findsOneWidget);
      expect(find.byIcon(Icons.arrow_back), findsOneWidget);
      expect(find.byIcon(Icons.save_outlined), findsOneWidget);
      expect(find.text('Agent Name'), findsOneWidget);
      expect(find.text('Description (Optional)'), findsOneWidget);
      expect(find.text('Instructions'), findsOneWidget);
      expect(find.text('Code Interpreter'), findsOneWidget);
      expect(find.text('File Search'), findsOneWidget);
      expect(find.text('Create Agent'), findsNWidgets(2));
    });

    testWidgets('should reset state on initialization', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(mockFormNotifier.resetStateCalled, isTrue);
    });

    testWidgets('should update form state when text fields change', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Test Agent Name');
      expect(mockFormNotifier.lastName, equals('Test Agent Name'));

      await tester.enterText(find.byType(TextFormField).at(1), 'Test Description');
      expect(mockFormNotifier.lastDescription, equals('Test Description'));

      await tester.enterText(find.byType(TextFormField).at(2), 'Test Instructions');
      expect(mockFormNotifier.lastInstructions, equals('Test Instructions'));
    });

    testWidgets('should update form state when switches are toggled', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.byType(SwitchListTile).at(0));
      await tester.pump();
      expect(mockFormNotifier.lastEnableCodeInterpreter, isTrue);

      await tester.tap(find.byType(SwitchListTile).at(1));
      await tester.pump();
      expect(mockFormNotifier.lastEnableFileSearch, isTrue);
    });

    testWidgets('should validate required fields', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Create Agent').last);
      await tester.pumpAndSettle();

      expect(find.text('Please enter an agent name'), findsOneWidget);
      expect(find.text('Please enter instructions for the agent'), findsOneWidget);
    });

    testWidgets('should not show validation errors for optional fields', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Test Agent');
      await tester.enterText(find.byType(TextFormField).at(2), 'Test Instructions');
      
      await tester.tap(find.text('Create Agent').last);
      await tester.pumpAndSettle();

      expect(find.text('Please enter an agent name'), findsNothing);
      expect(find.text('Please enter instructions for the agent'), findsNothing);
      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Agent creation initiated...'), findsOneWidget);
    });

    testWidgets('should show success message when form is valid', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Valid Agent');
      await tester.enterText(find.byType(TextFormField).at(1), 'Valid Description');
      await tester.enterText(find.byType(TextFormField).at(2), 'Valid Instructions');

      await tester.tap(find.text('Create Agent').last);
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Agent creation initiated...'), findsOneWidget);
    });

    testWidgets('should navigate back when back button is pressed', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () {
                Navigator.push(
                  tester.element(find.byType(ElevatedButton)),
                  MaterialPageRoute(builder: (_) => ProviderScope(
                    overrides: [
                      createAgentFormProvider.overrideWith((ref) => mockFormNotifier),
                      appThemeProvider.overrideWith((ref) => AppGeneratedTheme()),
                    ],
                    child: CreateAgentScreen(),
                  )),
                );
              },
              child: Text('Go to Create Agent'),
            ),
          ),
        ),
      ));

      await tester.tap(find.text('Go to Create Agent'));
      await tester.pumpAndSettle();

      expect(find.text('Create Agent'), findsNWidgets(2));

      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();

      expect(find.text('Go to Create Agent'), findsOneWidget);
    });

    testWidgets('should trigger save when save icon is pressed', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Agent Name');
      await tester.enterText(find.byType(TextFormField).at(2), 'Agent Instructions');

      await tester.tap(find.byIcon(Icons.save_outlined));
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.text('Agent creation initiated...'), findsOneWidget);
    });

    testWidgets('should update text controllers when form state changes', (tester) async {
      mockFormNotifier.state = mockFormNotifier.state.copyWith(
        name: 'Preset Name',
        description: 'Preset Description',
        instructions: 'Preset Instructions',
      );

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Preset Name'), findsOneWidget);
      expect(find.text('Preset Description'), findsOneWidget);
      expect(find.text('Preset Instructions'), findsOneWidget);
    });

    testWidgets('should display switch states correctly', (tester) async {
      mockFormNotifier.state = mockFormNotifier.state.copyWith(
        enableCodeInterpreter: true,
        enableFileSearch: false,
      );

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final codeInterpreterSwitch = tester.widget<SwitchListTile>(find.byType(SwitchListTile).at(0));
      final fileSearchSwitch = tester.widget<SwitchListTile>(find.byType(SwitchListTile).at(1));

      expect(codeInterpreterSwitch.value, isTrue);
      expect(fileSearchSwitch.value, isFalse);
    });

    testWidgets('should handle empty text field validation correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), '');
      await tester.enterText(find.byType(TextFormField).at(2), '');
      
      await tester.tap(find.text('Create Agent').last);
      await tester.pumpAndSettle();

      expect(find.text('Please enter an agent name'), findsOneWidget);
      expect(find.text('Please enter instructions for the agent'), findsOneWidget);
    });

    testWidgets('should handle long text input', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final longText = 'Very long text ' * 100;
      
      await tester.enterText(find.byType(TextFormField).at(0), longText);
      await tester.enterText(find.byType(TextFormField).at(1), longText);
      await tester.enterText(find.byType(TextFormField).at(2), longText);

      expect(mockFormNotifier.lastName, equals(longText));
      expect(mockFormNotifier.lastDescription, equals(longText));
      expect(mockFormNotifier.lastInstructions, equals(longText));
    });

    testWidgets('should handle special characters in text input', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      const specialText = 'Agent with émojis 🤖 and spëcial chars @#\$%';
      
      await tester.enterText(find.byType(TextFormField).at(0), specialText);
      await tester.enterText(find.byType(TextFormField).at(1), specialText);
      await tester.enterText(find.byType(TextFormField).at(2), specialText);

      expect(mockFormNotifier.lastName, equals(specialText));
      expect(mockFormNotifier.lastDescription, equals(specialText));
      expect(mockFormNotifier.lastInstructions, equals(specialText));
    });

    testWidgets('should have correct text field properties', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final nameField = tester.widget<TextFormField>(find.byType(TextFormField).at(0));
      final descriptionField = tester.widget<TextFormField>(find.byType(TextFormField).at(1));
      final instructionsField = tester.widget<TextFormField>(find.byType(TextFormField).at(2));

      expect(nameField.validator, isNotNull);
      expect(descriptionField.validator, isNull);
      expect(instructionsField.validator, isNotNull);
    });

    testWidgets('should apply correct theme styling', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      final appBar = tester.widget<AppBar>(find.byType(AppBar));
      expect(appBar.leading, isNotNull);
      expect(appBar.title, isNotNull);
      expect(appBar.actions, isNotNull);
      expect(appBar.actions!, hasLength(1));

      final elevatedButton = tester.widget<ElevatedButton>(find.byType(ElevatedButton));
      expect(elevatedButton.style, isNotNull);
    });

    testWidgets('should handle rapid switch toggling', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      for (int i = 0; i < 5; i++) {
        await tester.tap(find.byType(SwitchListTile).at(0));
        await tester.pump();
      }

      expect(mockFormNotifier.lastEnableCodeInterpreter, isTrue);

      for (int i = 0; i < 3; i++) {
        await tester.tap(find.byType(SwitchListTile).at(1));
        await tester.pump();
      }

      expect(mockFormNotifier.lastEnableFileSearch, isTrue);
    });

    testWidgets('should handle form submission with all fields filled', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Complete Agent');
      await tester.enterText(find.byType(TextFormField).at(1), 'Complete Description');
      await tester.enterText(find.byType(TextFormField).at(2), 'Complete Instructions');
      
      await tester.tap(find.byType(SwitchListTile).at(0));
      await tester.tap(find.byType(SwitchListTile).at(1));
      await tester.pump();

      await tester.tap(find.text('Create Agent').last);
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(mockFormNotifier.lastName, equals('Complete Agent'));
      expect(mockFormNotifier.lastDescription, equals('Complete Description'));
      expect(mockFormNotifier.lastInstructions, equals('Complete Instructions'));
      expect(mockFormNotifier.lastEnableCodeInterpreter, isTrue);
      expect(mockFormNotifier.lastEnableFileSearch, isTrue);
    });

    testWidgets('should handle scroll behavior with long content', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.byType(SingleChildScrollView), findsOneWidget);
      
      await tester.drag(find.byType(SingleChildScrollView), const Offset(0, -300));
      await tester.pumpAndSettle();

      expect(find.text('Create Agent'), findsNWidgets(2));
    });

    testWidgets('should maintain form state across rebuilds', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).at(0), 'Persistent Name');
      await tester.tap(find.byType(SwitchListTile).at(0));
      await tester.pump();

      mockFormNotifier.state = mockFormNotifier.state.copyWith(
        name: 'Persistent Name',
        enableCodeInterpreter: true,
      );

      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Persistent Name'), findsOneWidget);
      final switch1 = tester.widget<SwitchListTile>(find.byType(SwitchListTile).at(0));
      expect(switch1.value, isTrue);
    });

    testWidgets('should dispose controllers properly', (tester) async {
      await tester.pumpWidget(createTestWidget());
      await tester.pumpAndSettle();

      await tester.pumpWidget(Container());
      await tester.pumpAndSettle();

      expect(find.byType(CreateAgentScreen), findsNothing);
    });
  });
}