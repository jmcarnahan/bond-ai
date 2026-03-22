@TestOn('browser')
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/presentation/screens/agents/widgets/agent_form_fields.dart';

Widget _wrap(Widget child) {
  return MaterialApp(
    home: Scaffold(
      body: SingleChildScrollView(
        child: Form(child: child),
      ),
    ),
  );
}

AgentFormFields _buildFormFields({
  TextEditingController? nameController,
  TextEditingController? descriptionController,
  TextEditingController? instructionsController,
  TextEditingController? introductionController,
  TextEditingController? reminderController,
}) {
  return AgentFormFields(
    nameController: nameController ?? TextEditingController(),
    descriptionController: descriptionController ?? TextEditingController(),
    instructionsController: instructionsController ?? TextEditingController(),
    introductionController: introductionController ?? TextEditingController(),
    reminderController: reminderController ?? TextEditingController(),
    enabled: true,
    onNameChanged: (_) {},
    onDescriptionChanged: (_) {},
    onInstructionsChanged: (_) {},
    onIntroductionChanged: (_) {},
    onReminderChanged: (_) {},
  );
}

bool _hasAsterisk(Widget widget) {
  if (widget is! Text) return false;
  final span = widget.textSpan;
  if (span == null) return false;
  return span.toPlainText().contains('*');
}

void main() {
  group('AgentFormFields required indicators', () {
    testWidgets('Agent Name field has red asterisk', (tester) async {
      await tester.pumpWidget(_wrap(_buildFormFields()));

      // Look for a RichText widget containing "Agent Name *"
      expect(
        find.byWidgetPredicate(
          (widget) =>
              _hasAsterisk(widget) &&
              (widget as Text).textSpan!.toPlainText().contains('Agent Name'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('Instructions field has red asterisk', (tester) async {
      await tester.pumpWidget(_wrap(_buildFormFields()));

      expect(
        find.byWidgetPredicate(
          (widget) =>
              _hasAsterisk(widget) &&
              (widget as Text)
                  .textSpan!
                  .toPlainText()
                  .contains('Instructions'),
        ),
        findsOneWidget,
      );
    });

    testWidgets('Description field does NOT have asterisk', (tester) async {
      await tester.pumpWidget(_wrap(_buildFormFields()));

      // Description label should not contain an asterisk
      expect(
        find.byWidgetPredicate(
          (widget) =>
              _hasAsterisk(widget) &&
              (widget as Text)
                  .textSpan!
                  .toPlainText()
                  .contains('Description'),
        ),
        findsNothing,
      );
    });

    testWidgets('Introduction field does NOT have asterisk', (tester) async {
      await tester.pumpWidget(_wrap(_buildFormFields()));

      expect(
        find.byWidgetPredicate(
          (widget) =>
              _hasAsterisk(widget) &&
              (widget as Text)
                  .textSpan!
                  .toPlainText()
                  .contains('Introduction'),
        ),
        findsNothing,
      );
    });

    testWidgets('Reminder field does NOT have asterisk', (tester) async {
      await tester.pumpWidget(_wrap(_buildFormFields()));

      expect(
        find.byWidgetPredicate(
          (widget) =>
              _hasAsterisk(widget) &&
              (widget as Text).textSpan!.toPlainText().contains('Reminder'),
        ),
        findsNothing,
      );
    });
  });

  group('AgentFormFields validation', () {
    testWidgets('shows error for empty Agent Name on form validate',
        (tester) async {
      final formKey = GlobalKey<FormState>();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: _buildFormFields(),
              ),
            ),
          ),
        ),
      );

      // Trigger validation
      formKey.currentState!.validate();
      await tester.pump();

      expect(find.text('Please enter an agent name'), findsOneWidget);
    });

    testWidgets('shows error for empty Instructions on form validate',
        (tester) async {
      final formKey = GlobalKey<FormState>();
      final nameController = TextEditingController(text: 'My Agent');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: _buildFormFields(nameController: nameController),
              ),
            ),
          ),
        ),
      );

      formKey.currentState!.validate();
      await tester.pump();

      expect(find.text('Please enter instructions for the agent'),
          findsOneWidget);
    });

    testWidgets('no validation errors when both required fields are filled',
        (tester) async {
      final formKey = GlobalKey<FormState>();
      final nameController = TextEditingController(text: 'My Agent');
      final instructionsController =
          TextEditingController(text: 'Do something');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: _buildFormFields(
                  nameController: nameController,
                  instructionsController: instructionsController,
                ),
              ),
            ),
          ),
        ),
      );

      final isValid = formKey.currentState!.validate();
      await tester.pump();

      expect(isValid, isTrue);
      expect(find.text('Please enter an agent name'), findsNothing);
      expect(
          find.text('Please enter instructions for the agent'), findsNothing);
    });
  });
}
