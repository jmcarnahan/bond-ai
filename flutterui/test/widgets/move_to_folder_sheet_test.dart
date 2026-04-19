import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/folder_model.dart';
import 'package:flutterui/providers/folder_provider.dart';
import 'package:flutterui/presentation/screens/agents/widgets/move_to_folder_sheet.dart';

void main() {
  final testFolders = [
    const FolderModel(id: 'fld_1', name: 'Work', agentCount: 3, sortOrder: 1),
    const FolderModel(id: 'fld_2', name: 'Personal', agentCount: 1, sortOrder: 2),
  ];

  Widget buildTestApp({
    required List<FolderModel> folders,
    required Function(String?) onResult,
    String? currentFolderId,
  }) {
    return ProviderScope(
      overrides: [
        foldersProvider.overrideWith((ref) => Future.value(folders)),
      ],
      child: MaterialApp(
        home: _SheetTestPage(
          onResult: onResult,
          currentFolderId: currentFolderId,
        ),
      ),
    );
  }

  group('MoveToFolderSheet', () {
    testWidgets('shows Main Screen option and all folders', (tester) async {
      await tester.pumpWidget(buildTestApp(
        folders: testFolders,
        onResult: (_) {},
      ));
      await tester.pumpAndSettle();

      // Open the sheet
      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      expect(find.text('Move to folder'), findsOneWidget);
      expect(find.text('Main Screen'), findsOneWidget);
      expect(find.text('Work'), findsOneWidget);
      expect(find.text('Personal'), findsOneWidget);
    });

    testWidgets('selecting Main Screen returns empty string', (tester) async {
      String? result;
      await tester.pumpWidget(buildTestApp(
        folders: testFolders,
        onResult: (r) => result = r,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Main Screen'));
      await tester.pumpAndSettle();

      expect(result, '');
    });

    testWidgets('selecting a folder returns its id', (tester) async {
      String? result;
      await tester.pumpWidget(buildTestApp(
        folders: testFolders,
        onResult: (r) => result = r,
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Work'));
      await tester.pumpAndSettle();

      expect(result, 'fld_1');
    });

    testWidgets('shows message when no folders exist', (tester) async {
      await tester.pumpWidget(buildTestApp(
        folders: [],
        onResult: (_) {},
      ));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Open Sheet'));
      await tester.pumpAndSettle();

      expect(find.text('No folders yet. Create one from the agents screen.'), findsOneWidget);
    });
  });
}

/// Helper widget that opens the sheet on button press and captures the result.
class _SheetTestPage extends ConsumerWidget {
  final Function(String?) onResult;
  final String? currentFolderId;

  const _SheetTestPage({required this.onResult, this.currentFolderId});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Scaffold(
      body: Center(
        child: ElevatedButton(
          onPressed: () async {
            final result = await showMoveToFolderSheet(
              context,
              ref: ref,
              currentFolderId: currentFolderId,
            );
            onResult(result);
          },
          child: const Text('Open Sheet'),
        ),
      ),
    );
  }
}
