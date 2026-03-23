import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/presentation/screens/agents/widgets/folder_card.dart';
import 'package:flutterui/providers/core_providers.dart';
import 'package:flutterui/core/theme/app_theme.dart';

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

void main() {
  Widget buildTestWidget({
    required FolderModel folder,
    VoidCallback? onTap,
    VoidCallback? onRename,
    VoidCallback? onDelete,
    bool isHighlighted = false,
  }) {
    return ProviderScope(
      overrides: [
        appThemeProvider.overrideWithValue(_TestAppTheme()),
      ],
      child: MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 240,
            height: 200,
            child: FolderCard(
              folder: folder,
              onTap: onTap ?? () {},
              onRename: onRename,
              onDelete: onDelete,
              isHighlighted: isHighlighted,
            ),
          ),
        ),
      ),
    );
  }

  group('FolderCard', () {
    testWidgets('renders folder name and agent count', (tester) async {
      const folder = FolderModel(
        id: 'fld_1',
        name: 'Work Agents',
        agentCount: 5,
        sortOrder: 0,
      );

      await tester.pumpWidget(buildTestWidget(folder: folder));
      await tester.pumpAndSettle();

      expect(find.text('Work Agents'), findsOneWidget);
      expect(find.text('5 agents'), findsOneWidget);
      expect(find.byIcon(Icons.folder_rounded), findsOneWidget);
    });

    testWidgets('shows singular "agent" for count of 1', (tester) async {
      const folder = FolderModel(
        id: 'fld_1',
        name: 'Solo',
        agentCount: 1,
        sortOrder: 0,
      );

      await tester.pumpWidget(buildTestWidget(folder: folder));
      await tester.pumpAndSettle();

      expect(find.text('1 agent'), findsOneWidget);
    });

    testWidgets('tap triggers onTap callback', (tester) async {
      bool tapped = false;
      const folder = FolderModel(id: 'fld_1', name: 'Test', agentCount: 0, sortOrder: 0);

      await tester.pumpWidget(buildTestWidget(
        folder: folder,
        onTap: () => tapped = true,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Test'));
      expect(tapped, true);
    });

    testWidgets('long press shows context menu with rename and delete', (tester) async {
      bool renamed = false;
      const folder = FolderModel(id: 'fld_1', name: 'Context', agentCount: 0, sortOrder: 0);

      await tester.pumpWidget(buildTestWidget(
        folder: folder,
        onRename: () => renamed = true,
        onDelete: () {},
      ));
      await tester.pumpAndSettle();

      // Long press on the card (use the Card widget as target)
      await tester.longPress(find.byType(Card));
      await tester.pumpAndSettle();

      expect(find.text('Rename folder'), findsOneWidget);
      expect(find.text('Delete folder'), findsOneWidget);

      // Tap rename
      await tester.tap(find.text('Rename folder'));
      await tester.pumpAndSettle();
      expect(renamed, true);
    });
  });
}
