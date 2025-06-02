import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/tool_file_upload_section.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';

class MockRef implements Ref {
  @override
  T read<T>(ProviderListenable<T> provider) {
    throw UnimplementedError();
  }

  @override
  ProviderSubscription<T> listen<T>(ProviderListenable<T> provider, void Function(T? previous, T next) listener, {bool fireImmediately = false, void Function(Object error, StackTrace stackTrace)? onError}) {
    throw UnimplementedError();
  }

  @override
  void invalidate(ProviderOrFamily provider) {
    throw UnimplementedError();
  }

  @override
  bool exists(ProviderBase<Object?> provider) {
    throw UnimplementedError();
  }

  @override
  T refresh<T>(Refreshable<T> provider) {
    throw UnimplementedError();
  }

  @override
  T watch<T>(ProviderListenable<T> provider) {
    throw UnimplementedError();
  }

  @override
  void listenSelf(void Function(Object? previous, Object? next) listener, {void Function(Object error, StackTrace stackTrace)? onError}) {
    throw UnimplementedError();
  }

  @override
  void notifyListeners() {
    throw UnimplementedError();
  }

  @override
  ProviderContainer get container => throw UnimplementedError();

  @override
  void onDispose(void Function() cb) {
    throw UnimplementedError();
  }

  @override
  void onCancel(void Function() cb) {
    throw UnimplementedError();
  }

  @override
  void onResume(void Function() cb) {
    throw UnimplementedError();
  }

  @override
  void onAddListener(void Function() cb) {
    throw UnimplementedError();
  }

  @override
  void onRemoveListener(void Function() cb) {
    throw UnimplementedError();
  }
  
  @override
  void invalidateSelf() {
    // TODO: implement invalidateSelf
  }
  
  @override
  KeepAliveLink keepAlive() {
    // TODO: implement keepAlive
    throw UnimplementedError();
  }
}

class MockCreateAgentFormNotifier extends CreateAgentFormNotifier {
  bool uploadFileForToolCalled = false;
  bool removeFileFromToolCalled = false;
  String? lastToolType;
  String? lastFileId;

  MockCreateAgentFormNotifier() : super(MockRef());

  @override
  Future<void> uploadFileForTool(String toolType) async {
    uploadFileForToolCalled = true;
    lastToolType = toolType;
  }

  @override
  void removeFileFromTool(String toolType, String fileId) {
    removeFileFromToolCalled = true;
    lastToolType = toolType;
    lastFileId = fileId;
  }
}

void main() {
  group('ToolFileUploadSection Widget Tests', () {
    late MockCreateAgentFormNotifier mockNotifier;

    setUp(() {
      mockNotifier = MockCreateAgentFormNotifier();
    });

    Widget createTestWidget({
      String toolType = 'code_interpreter',
      String toolName = 'Code Interpreter',
      bool isEnabled = true,
      List<UploadedFileInfo> files = const [],
      CreateAgentFormState? formState,
    }) {
      return ProviderScope(
        overrides: [
          createAgentFormProvider.overrideWith((ref) => mockNotifier),
        ],
        child: MaterialApp(
          home: Scaffold(
            body: ToolFileUploadSection(
              toolType: toolType,
              toolName: toolName,
              isEnabled: isEnabled,
              files: files,
            ),
          ),
        ),
      );
    }

    testWidgets('should not display when isEnabled is false', (tester) async {
      await tester.pumpWidget(createTestWidget(isEnabled: false));

      expect(find.byType(SizedBox), findsOneWidget);
      expect(find.byType(Card), findsNothing);
    });

    testWidgets('should display when isEnabled is true', (tester) async {
      await tester.pumpWidget(createTestWidget(isEnabled: true));

      expect(find.byType(Card), findsOneWidget);
      expect(find.text('Code Interpreter Files'), findsOneWidget);
      expect(find.text('Add File'), findsOneWidget);
    });

    testWidgets('should display correct icon for code interpreter', (tester) async {
      await tester.pumpWidget(createTestWidget(
        toolType: 'code_interpreter',
        toolName: 'Code Interpreter',
      ));

      expect(find.byIcon(Icons.code), findsOneWidget);
      expect(find.text('Code Interpreter Files'), findsOneWidget);
    });

    testWidgets('should display correct icon for file search', (tester) async {
      await tester.pumpWidget(createTestWidget(
        toolType: 'file_search',
        toolName: 'File Search',
      ));

      expect(find.byIcon(Icons.search), findsOneWidget);
      expect(find.text('File Search Files'), findsOneWidget);
    });

    testWidgets('should display empty state when no files', (tester) async {
      await tester.pumpWidget(createTestWidget(files: []));

      expect(find.text('No files uploaded yet'), findsOneWidget);
      expect(find.text('Upload files to use with Code Interpreter'), findsOneWidget);
      expect(find.byIcon(Icons.upload_file), findsOneWidget);
    });

    testWidgets('should display file list when files are present', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'test.py',
          fileSize: 1024,
          uploadedAt: DateTime.now().subtract(const Duration(minutes: 5)),
        ),
        UploadedFileInfo(
          fileId: '2',
          fileName: 'data.csv',
          fileSize: 2048,
          uploadedAt: DateTime.now().subtract(const Duration(hours: 1)),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.text('test.py'), findsOneWidget);
      expect(find.text('data.csv'), findsOneWidget);
      expect(find.byIcon(Icons.code), findsNWidgets(2));
      expect(find.byIcon(Icons.grid_on), findsOneWidget);
      expect(find.byIcon(Icons.delete_outline), findsNWidgets(2));
    });

    testWidgets('should call uploadFileForTool when add file button is pressed', (tester) async {
      await tester.pumpWidget(createTestWidget(toolType: 'code_interpreter'));

      await tester.tap(find.text('Add File'));
      await tester.pump();

      expect(mockNotifier.uploadFileForToolCalled, isTrue);
      expect(mockNotifier.lastToolType, equals('code_interpreter'));
    });

    testWidgets('should call removeFileFromTool when delete button is pressed', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: 'test-file-id',
          fileName: 'test.py',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(
        files: files,
        toolType: 'code_interpreter',
      ));

      await tester.tap(find.byIcon(Icons.delete_outline));
      await tester.pump();

      expect(mockNotifier.removeFileFromToolCalled, isTrue);
      expect(mockNotifier.lastToolType, equals('code_interpreter'));
      expect(mockNotifier.lastFileId, equals('test-file-id'));
    });

    testWidgets('should format file sizes correctly', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'small.txt',
          fileSize: 512,
          uploadedAt: DateTime.now(),
        ),
        UploadedFileInfo(
          fileId: '2',
          fileName: 'medium.doc',
          fileSize: 1536,
          uploadedAt: DateTime.now(),
        ),
        UploadedFileInfo(
          fileId: '3',
          fileName: 'large.pdf',
          fileSize: 1048576,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.textContaining('512 B'), findsOneWidget);
      expect(find.textContaining('1.5 KB'), findsOneWidget);
      expect(find.textContaining('1.0 MB'), findsOneWidget);
    });

    testWidgets('should format dates correctly', (tester) async {
      final now = DateTime.now();
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'recent.txt',
          fileSize: 1024,
          uploadedAt: now.subtract(const Duration(seconds: 30)),
        ),
        UploadedFileInfo(
          fileId: '2',
          fileName: 'minutes.txt',
          fileSize: 1024,
          uploadedAt: now.subtract(const Duration(minutes: 30)),
        ),
        UploadedFileInfo(
          fileId: '3',
          fileName: 'hours.txt',
          fileSize: 1024,
          uploadedAt: now.subtract(const Duration(hours: 2)),
        ),
        UploadedFileInfo(
          fileId: '4',
          fileName: 'days.txt',
          fileSize: 1024,
          uploadedAt: now.subtract(const Duration(days: 3)),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.textContaining('just now'), findsOneWidget);
      expect(find.textContaining('30m ago'), findsOneWidget);
      expect(find.textContaining('2h ago'), findsOneWidget);
      expect(find.textContaining('3d ago'), findsOneWidget);
    });

    testWidgets('should display correct file icons based on extension', (tester) async {
      final files = [
        UploadedFileInfo(fileId: '1', fileName: 'doc.pdf', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '2', fileName: 'sheet.xlsx', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '3', fileName: 'script.py', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '4', fileName: 'image.jpg', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '5', fileName: 'unknown.xyz', fileSize: 1024, uploadedAt: DateTime.now()),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.byIcon(Icons.picture_as_pdf), findsOneWidget);
      expect(find.byIcon(Icons.table_chart), findsOneWidget);
      expect(find.byIcon(Icons.code), findsNWidgets(2));
      expect(find.byIcon(Icons.image), findsOneWidget);
      expect(find.byIcon(Icons.insert_drive_file), findsOneWidget);
    });

    testWidgets('should apply correct theme colors', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onSurface: Colors.black,
              surface: Colors.white,
            ),
          ),
          home: Scaffold(
            body: ProviderScope(
              overrides: [
                createAgentFormProvider.overrideWith((ref) => mockNotifier),
              ],
              child: ToolFileUploadSection(
                toolType: 'code_interpreter',
                toolName: 'Code Interpreter',
                isEnabled: true,
                files: const [],
              ),
            ),
          ),
        ),
      );

      final icon = tester.widget<Icon>(find.byIcon(Icons.code));
      expect(icon.color, equals(Colors.blue));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget());

      expect(find.text('Code Interpreter Files'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Code Interpreter Files'), findsOneWidget);

      addTearDown(() => tester.binding.setSurfaceSize(null));
    });

    testWidgets('should handle long file names with ellipsis', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'this_is_a_very_long_filename_that_should_be_truncated_with_ellipsis.py',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      final text = tester.widget<Text>(find.textContaining('this_is_a_very_long_filename'));
      expect(text.overflow, equals(TextOverflow.ellipsis));
    });

    testWidgets('should maintain layout structure correctly', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(Card), findsOneWidget);
      expect(find.byType(Padding), findsOneWidget);
      expect(find.byType(Column), findsOneWidget);
      expect(find.byType(Row), findsOneWidget);
      expect(find.byType(Spacer), findsOneWidget);
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: ProviderScope(
              overrides: [
                createAgentFormProvider.overrideWith((ref) => mockNotifier),
              ],
              child: ToolFileUploadSection(
                toolType: 'file_search',
                toolName: 'File Search',
                isEnabled: true,
                files: const [],
              ),
            ),
          ),
        ),
      );

      expect(find.text('File Search Files'), findsOneWidget);
      expect(find.byIcon(Icons.search), findsOneWidget);
    });

    testWidgets('should handle empty file list properly', (tester) async {
      await tester.pumpWidget(createTestWidget(files: []));

      expect(find.byType(Container), findsOneWidget);
      expect(find.text('No files uploaded yet'), findsOneWidget);
      expect(find.byIcon(Icons.upload_file), findsOneWidget);
    });

    testWidgets('should display proper tooltips', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'test.py',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      final deleteButton = tester.widget<IconButton>(find.byIcon(Icons.delete_outline));
      expect(deleteButton.tooltip, equals('Remove file'));
    });

    testWidgets('should handle visual density correctly', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'test.py',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      final deleteButton = tester.widget<IconButton>(find.byIcon(Icons.delete_outline));
      expect(deleteButton.visualDensity, equals(VisualDensity.compact));
    });

    testWidgets('should work in different container layouts', (tester) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            createAgentFormProvider.overrideWith((ref) => mockNotifier),
          ],
          child: MaterialApp(
            home: Scaffold(
              body: SizedBox(
                width: 300,
                child: ToolFileUploadSection(
                  toolType: 'code_interpreter',
                  toolName: 'Code Interpreter',
                  isEnabled: true,
                  files: const [],
                ),
              ),
            ),
          ),
        ),
      );

      expect(find.text('Code Interpreter Files'), findsOneWidget);
    });

    testWidgets('should handle rapid button presses', (tester) async {
      await tester.pumpWidget(createTestWidget());

      for (int i = 0; i < 3; i++) {
        await tester.tap(find.text('Add File'));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(mockNotifier.uploadFileForToolCalled, isTrue);
    });

    testWidgets('should format large file sizes correctly', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'huge.zip',
          fileSize: 1073741824,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.textContaining('1.0 GB'), findsOneWidget);
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'test.py',
          fileSize: 1024,
          uploadedAt: DateTime.now(),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.text('Add File'), findsOneWidget);
      final deleteButton = tester.widget<IconButton>(find.byIcon(Icons.delete_outline));
      expect(deleteButton.tooltip, equals('Remove file'));
    });

    testWidgets('should handle edge cases in file extensions', (tester) async {
      final files = [
        UploadedFileInfo(fileId: '1', fileName: 'file', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '2', fileName: 'file.', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '3', fileName: '.hidden', fileSize: 1024, uploadedAt: DateTime.now()),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.byIcon(Icons.insert_drive_file), findsNWidgets(3));
    });

    testWidgets('should maintain consistent spacing', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(SizedBox), findsAtLeastNWidgets(1));
      expect(find.byType(Padding), findsOneWidget);
    });

    testWidgets('should handle very old file dates', (tester) async {
      final files = [
        UploadedFileInfo(
          fileId: '1',
          fileName: 'old.txt',
          fileSize: 1024,
          uploadedAt: DateTime(2020, 1, 1),
        ),
      ];

      await tester.pumpWidget(createTestWidget(files: files));

      expect(find.textContaining('1/1/2020'), findsOneWidget);
    });

    testWidgets('should work with custom color schemes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: ColorScheme.fromSeed(
              seedColor: Colors.purple,
              primary: Colors.purple,
              error: Colors.orange,
            ),
          ),
          home: Scaffold(
            body: ProviderScope(
              overrides: [
                createAgentFormProvider.overrideWith((ref) => mockNotifier),
              ],
              child: ToolFileUploadSection(
                toolType: 'code_interpreter',
                toolName: 'Code Interpreter',
                isEnabled: true,
                files: [
                  UploadedFileInfo(
                    fileId: '1',
                    fileName: 'test.py',
                    fileSize: 1024,
                    uploadedAt: DateTime.now(),
                  ),
                ],
              ),
            ),
          ),
        ),
      );

      final headerIcon = tester.widget<Icon>(find.byIcon(Icons.code).first);
      expect(headerIcon.color, equals(Colors.purple));

      final deleteIcon = tester.widget<Icon>(find.byIcon(Icons.delete_outline));
      expect(deleteIcon.color, equals(Colors.orange));
    });
  });
}
