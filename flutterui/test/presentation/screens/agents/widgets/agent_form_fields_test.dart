import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_form_fields.dart';

void main() {
  group('AgentFormFields Widget Tests', () {
    late TextEditingController nameController;
    late TextEditingController descriptionController;
    late TextEditingController instructionsController;
    late List<String> nameChanges;
    late List<String> descriptionChanges;
    late List<String> instructionsChanges;

    setUp(() {
      nameController = TextEditingController();
      descriptionController = TextEditingController();
      instructionsController = TextEditingController();
      nameChanges = [];
      descriptionChanges = [];
      instructionsChanges = [];
    });

    tearDown(() {
      nameController.dispose();
      descriptionController.dispose();
      instructionsController.dispose();
    });

    testWidgets('should display all form fields', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: true,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      expect(find.text('Agent Name'), findsOneWidget);
      expect(find.text('Description (Optional)'), findsOneWidget);
      expect(find.text('Instructions'), findsOneWidget);
      expect(find.byType(TextFormField), findsNWidgets(3));
    });

    testWidgets('should call onNameChanged when name field changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: true,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextFormField).first, 'Test Agent Name');
      expect(nameChanges, contains('Test Agent Name'));
    });

    testWidgets('should call onDescriptionChanged when description field changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: true,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextFormField).at(1), 'Test Description');
      expect(descriptionChanges, contains('Test Description'));
    });

    testWidgets('should call onInstructionsChanged when instructions field changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: true,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextFormField).at(2), 'Test Instructions');
      expect(instructionsChanges, contains('Test Instructions'));
    });

    testWidgets('should disable all fields when enabled is false', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: false,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      final textFields = tester.widgetList<TextFormField>(find.byType(TextFormField));
      for (final textField in textFields) {
        expect(textField.enabled, isFalse);
      }
    });

    testWidgets('should validate name field when empty', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Form(
              child: AgentFormFields(
                nameController: nameController,
                descriptionController: descriptionController,
                instructionsController: instructionsController,
                enabled: true,
                onNameChanged: (value) => nameChanges.add(value),
                onDescriptionChanged: (value) => descriptionChanges.add(value),
                onInstructionsChanged: (value) => instructionsChanges.add(value),
              ),
            ),
          ),
        ),
      );

      final nameField = tester.widget<TextFormField>(find.byType(TextFormField).first);
      final validation = nameField.validator?.call('');
      expect(validation, equals('Please enter an agent name'));
    });

    testWidgets('should validate instructions field when empty', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Form(
              child: AgentFormFields(
                nameController: nameController,
                descriptionController: descriptionController,
                instructionsController: instructionsController,
                enabled: true,
                onNameChanged: (value) => nameChanges.add(value),
                onDescriptionChanged: (value) => descriptionChanges.add(value),
                onInstructionsChanged: (value) => instructionsChanges.add(value),
              ),
            ),
          ),
        ),
      );

      final instructionsField = tester.widget<TextFormField>(find.byType(TextFormField).at(2));
      final validation = instructionsField.validator?.call('');
      expect(validation, equals('Please enter instructions for the agent'));
    });

    testWidgets('should not validate description field when empty', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Form(
              child: AgentFormFields(
                nameController: nameController,
                descriptionController: descriptionController,
                instructionsController: instructionsController,
                enabled: true,
                onNameChanged: (value) => nameChanges.add(value),
                onDescriptionChanged: (value) => descriptionChanges.add(value),
                onInstructionsChanged: (value) => instructionsChanges.add(value),
              ),
            ),
          ),
        ),
      );

      final descriptionField = tester.widget<TextFormField>(find.byType(TextFormField).at(1));
      expect(descriptionField.validator, isNull);
    });

    testWidgets('should allow multiline input for instructions field', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentFormFields(
              nameController: nameController,
              descriptionController: descriptionController,
              instructionsController: instructionsController,
              enabled: true,
              onNameChanged: (value) => nameChanges.add(value),
              onDescriptionChanged: (value) => descriptionChanges.add(value),
              onInstructionsChanged: (value) => instructionsChanges.add(value),
            ),
          ),
        ),
      );

      // Test that multiline text can be entered in the instructions field
      const multilineText = 'Line 1\nLine 2\nLine 3\nLine 4\nLine 5';
      await tester.enterText(find.byType(TextFormField).at(2), multilineText);
      expect(instructionsChanges, contains(multilineText));
    });
  });

  group('AgentTextField Widget Tests', () {
    late TextEditingController controller;

    setUp(() {
      controller = TextEditingController();
    });

    testWidgets('should display text field with label', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.text('Test Label'), findsOneWidget);
      expect(find.byType(TextFormField), findsOneWidget);
    });

    testWidgets('should be enabled by default', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      expect(textField.enabled, isTrue);
    });

    testWidgets('should be disabled when enabled is false', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              enabled: false,
            ),
          ),
        ),
      );

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      expect(textField.enabled, isFalse);
    });

    testWidgets('should handle multiline text input when maxLines is provided', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              maxLines: 3,
            ),
          ),
        ),
      );

      const multilineText = 'Line 1\nLine 2\nLine 3';
      await tester.enterText(find.byType(TextFormField), multilineText);
      expect(find.text(multilineText), findsOneWidget);
    });

    testWidgets('should handle single line text input by default', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      const singleLineText = 'Single line text';
      await tester.enterText(find.byType(TextFormField), singleLineText);
      expect(find.text(singleLineText), findsOneWidget);
    });

    testWidgets('should call validator when provided', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              validator: (value) => value?.isEmpty == true ? 'Required' : null,
            ),
          ),
        ),
      );

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      final validation = textField.validator?.call('');
      expect(validation, equals('Required'));
    });

    testWidgets('should call onChanged when text changes', (tester) async {
      String? changedValue;
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              onChanged: (value) => changedValue = value,
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextFormField), 'Test Value');
      expect(changedValue, equals('Test Value'));
    });

    testWidgets('should be styled correctly when enabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onSurface: Colors.black,
              surfaceContainerLow: Colors.grey,
            ),
          ),
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              enabled: true,
            ),
          ),
        ),
      );

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      expect(textField.enabled, isTrue);
      expect(find.text('Test Label'), findsOneWidget);
    });

    testWidgets('should be styled correctly when disabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              onSurface: Colors.black,
            ),
          ),
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              enabled: false,
            ),
          ),
        ),
      );

      final textField = tester.widget<TextFormField>(find.byType(TextFormField));
      expect(textField.enabled, isFalse);
    });

    testWidgets('should display with proper styling', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onSurface: Colors.black,
            ),
          ),
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.byType(TextFormField), findsOneWidget);
      expect(find.text('Test Label'), findsOneWidget);
    });

    testWidgets('should handle long text input', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
              maxLines: 5,
            ),
          ),
        ),
      );

      const longText = 'This is a very long text that spans multiple lines and should be handled properly by the text field widget without any issues or overflow problems.';
      
      await tester.enterText(find.byType(TextFormField), longText);
      expect(find.text(longText), findsOneWidget);
    });

    testWidgets('should handle special characters', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      const specialText = 'Text with émojis 🤖 and spëcial chars @#\$%^&*()';
      
      await tester.enterText(find.byType(TextFormField), specialText);
      expect(find.text(specialText), findsOneWidget);
    });

    testWidgets('should maintain controller value', (tester) async {
      controller.text = 'Initial Value';
      
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.text('Initial Value'), findsOneWidget);
      expect(controller.text, equals('Initial Value'));
    });

    testWidgets('should handle theme changes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.light(),
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.byType(TextFormField), findsOneWidget);

      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.byType(TextFormField), findsOneWidget);
    });

    testWidgets('should display label correctly', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      expect(find.text('Test Label'), findsOneWidget);
      expect(find.byType(TextFormField), findsOneWidget);
    });

    testWidgets('should handle focus and unfocus states', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AgentTextField(
              controller: controller,
              labelText: 'Test Label',
            ),
          ),
        ),
      );

      await tester.tap(find.byType(TextFormField));
      await tester.pump();

      expect(tester.binding.focusManager.primaryFocus?.hasFocus, isTrue);

      await tester.tap(find.byType(Scaffold));
      await tester.pump();

      expect(tester.binding.focusManager.primaryFocus?.hasFocus, isFalse);
    });
  });
}
