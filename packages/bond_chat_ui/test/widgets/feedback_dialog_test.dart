import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:bond_chat_ui/bond_chat_ui.dart';

void main() {
  Widget buildTestWidget({
    String feedbackType = 'up',
    String? existingMessage,
    bool isEditing = false,
    required VoidCallback onCancel,
    required Function(String, String?) onSubmit,
    VoidCallback? onDelete,
  }) {
    return MaterialApp(
      home: Scaffold(
        body: FeedbackDialog(
          feedbackType: feedbackType,
          existingMessage: existingMessage,
          isEditing: isEditing,
          onCancel: onCancel,
          onSubmit: onSubmit,
          onDelete: onDelete,
        ),
      ),
    );
  }

  group('FeedbackDialog', () {
    testWidgets('shows "Add feedback" when not editing', (tester) async {
      await tester.pumpWidget(buildTestWidget(onCancel: () {}, onSubmit: (_, __) {}));
      await tester.pumpAndSettle();
      expect(find.text('Add feedback'), findsOneWidget);
    });

    testWidgets('shows "Edit feedback" when editing', (tester) async {
      await tester.pumpWidget(buildTestWidget(isEditing: true, onCancel: () {}, onSubmit: (_, __) {}));
      await tester.pumpAndSettle();
      expect(find.text('Edit feedback'), findsOneWidget);
    });

    testWidgets('Cancel calls onCancel', (tester) async {
      bool cancelled = false;
      await tester.pumpWidget(buildTestWidget(onCancel: () => cancelled = true, onSubmit: (_, __) {}));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cancel'));
      expect(cancelled, true);
    });

    testWidgets('Submit calls onSubmit with type and message', (tester) async {
      String? type;
      String? msg;
      await tester.pumpWidget(buildTestWidget(
        feedbackType: 'down',
        onCancel: () {},
        onSubmit: (t, m) { type = t; msg = m; },
      ));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField), 'not helpful');
      await tester.tap(find.text('Submit'));
      expect(type, 'down');
      expect(msg, 'not helpful');
    });

    testWidgets('Delete button appears only when editing with onDelete', (tester) async {
      await tester.pumpWidget(buildTestWidget(onCancel: () {}, onSubmit: (_, __) {}));
      await tester.pumpAndSettle();
      expect(find.text('Delete'), findsNothing);

      bool deleted = false;
      await tester.pumpWidget(buildTestWidget(
        isEditing: true,
        onCancel: () {},
        onSubmit: (_, __) {},
        onDelete: () => deleted = true,
      ));
      await tester.pumpAndSettle();
      expect(find.text('Delete'), findsOneWidget);
      await tester.tap(find.text('Delete'));
      expect(deleted, true);
    });
  });
}
