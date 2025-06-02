import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:flutterui/presentation/screens/agents/widgets/agent_tools_section.dart';
import 'package:flutterui/presentation/screens/agents/widgets/tool_file_upload_section.dart';
import 'package:flutterui/providers/create_agent_form_provider.dart';

void main() {
  group('AgentToolsSection Widget Tests', () {
    late bool codeInterpreterCalled;
    late bool fileSearchCalled;
    late bool codeInterpreterValue;
    late bool fileSearchValue;

    setUp(() {
      codeInterpreterCalled = false;
      fileSearchCalled = false;
      codeInterpreterValue = false;
      fileSearchValue = false;
    });

    Widget createTestWidget({
      bool enableCodeInterpreter = false,
      bool enableFileSearch = false,
      List<UploadedFileInfo> codeInterpreterFiles = const [],
      List<UploadedFileInfo> fileSearchFiles = const [],
      bool enabled = true,
    }) {
      return MaterialApp(
        home: Scaffold(
          body: AgentToolsSection(
            enableCodeInterpreter: enableCodeInterpreter,
            enableFileSearch: enableFileSearch,
            codeInterpreterFiles: codeInterpreterFiles,
            fileSearchFiles: fileSearchFiles,
            enabled: enabled,
            onCodeInterpreterChanged: (value) {
              codeInterpreterCalled = true;
              codeInterpreterValue = value;
            },
            onFileSearchChanged: (value) {
              fileSearchCalled = true;
              fileSearchValue = value;
            },
          ),
        ),
      );
    }

    testWidgets('should display all tool switches and file upload sections', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.text('Code Interpreter'), findsOneWidget);
      expect(find.text('File Search'), findsOneWidget);
      expect(find.byType(AgentToolSwitch), findsNWidgets(2));
      expect(find.byType(ToolFileUploadSection), findsNWidgets(2));
    });

    testWidgets('should call onCodeInterpreterChanged when code interpreter switch is toggled', (tester) async {
      await tester.pumpWidget(createTestWidget(enableCodeInterpreter: false));

      await tester.tap(find.byType(Switch).first);
      expect(codeInterpreterCalled, isTrue);
      expect(codeInterpreterValue, isTrue);
    });

    testWidgets('should call onFileSearchChanged when file search switch is toggled', (tester) async {
      await tester.pumpWidget(createTestWidget(enableFileSearch: false));

      await tester.tap(find.byType(Switch).last);
      expect(fileSearchCalled, isTrue);
      expect(fileSearchValue, isTrue);
    });

    testWidgets('should disable switches when enabled is false', (tester) async {
      await tester.pumpWidget(createTestWidget(enabled: false));

      final switches = tester.widgetList<SwitchListTile>(find.byType(SwitchListTile));
      for (final switch_ in switches) {
        expect(switch_.onChanged, isNull);
      }
    });

    testWidgets('should enable switches when enabled is true', (tester) async {
      await tester.pumpWidget(createTestWidget(enabled: true));

      final switches = tester.widgetList<SwitchListTile>(find.byType(SwitchListTile));
      for (final switch_ in switches) {
        expect(switch_.onChanged, isNotNull);
      }
    });

    testWidgets('should display correct switch states', (tester) async {
      await tester.pumpWidget(createTestWidget(
        enableCodeInterpreter: true,
        enableFileSearch: false,
      ));

      final switches = tester.widgetList<SwitchListTile>(find.byType(SwitchListTile)).toList();
      expect(switches[0].value, isTrue);
      expect(switches[1].value, isFalse);
    });

    testWidgets('should maintain proper layout structure', (tester) async {
      await tester.pumpWidget(createTestWidget());

      expect(find.byType(Column), findsOneWidget);
      expect(find.byType(SizedBox), findsOneWidget);

      final column = tester.widget<Column>(find.byType(Column));
      expect(column.crossAxisAlignment, equals(CrossAxisAlignment.start));
      expect(column.children, hasLength(5));
    });

    testWidgets('should apply correct spacing', (tester) async {
      await tester.pumpWidget(createTestWidget());

      final sizedBox = tester.widget<SizedBox>(find.byType(SizedBox));
      expect(sizedBox.height, greaterThan(0));
    });

    testWidgets('should work with different screen sizes', (tester) async {
      await tester.binding.setSurfaceSize(const Size(400, 800));

      await tester.pumpWidget(createTestWidget());

      expect(find.text('Code Interpreter'), findsOneWidget);
      expect(find.text('File Search'), findsOneWidget);

      await tester.binding.setSurfaceSize(const Size(800, 400));
      await tester.pump();

      expect(find.text('Code Interpreter'), findsOneWidget);
      expect(find.text('File Search'), findsOneWidget);

      addTearDown(tester.binding.setSurfaceSize as Function());
    });

    testWidgets('should pass correct data to ToolFileUploadSection widgets', (tester) async {
      final codeFiles = [
        UploadedFileInfo(fileId: '1', fileName: 'code.py', fileSize: 1024, uploadedAt: DateTime.now()),
        UploadedFileInfo(fileId: '2', fileName: 'data.csv', fileSize: 2048, uploadedAt: DateTime.now()),
      ];
      final searchFiles = [
        UploadedFileInfo(fileId: '3', fileName: 'doc.pdf', fileSize: 4096, uploadedAt: DateTime.now()),
      ];

      await tester.pumpWidget(createTestWidget(
        enableCodeInterpreter: true,
        enableFileSearch: false,
        codeInterpreterFiles: codeFiles,
        fileSearchFiles: searchFiles,
      ));

      final uploadSections = tester.widgetList<ToolFileUploadSection>(find.byType(ToolFileUploadSection)).toList();
      
      expect(uploadSections[0].toolType, equals('code_interpreter'));
      expect(uploadSections[0].toolName, equals('Code Interpreter'));
      expect(uploadSections[0].isEnabled, isTrue);
      expect(uploadSections[0].files, equals(codeFiles));
      
      expect(uploadSections[1].toolType, equals('file_search'));
      expect(uploadSections[1].toolName, equals('File Search'));
      expect(uploadSections[1].isEnabled, isFalse);
      expect(uploadSections[1].files, equals(searchFiles));
    });
  });

  group('AgentToolSwitch Widget Tests', () {
    late bool onChangedCalled;
    late bool changedValue;

    setUp(() {
      onChangedCalled = false;
      changedValue = false;
    });

    Widget createSwitchTestWidget({
      required String title,
      required bool value,
      ValueChanged<bool>? onChanged,
    }) {
      return MaterialApp(
        home: Scaffold(
          body: AgentToolSwitch(
            title: title,
            value: value,
            onChanged: onChanged,
          ),
        ),
      );
    }

    testWidgets('should display title correctly', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      expect(find.text('Test Tool'), findsOneWidget);
    });

    testWidgets('should display switch with correct value', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: true,
        onChanged: (value) {},
      ));

      final switchListTile = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(switchListTile.value, isTrue);
    });

    testWidgets('should call onChanged when switch is toggled', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {
          onChangedCalled = true;
          changedValue = value;
        },
      ));

      await tester.tap(find.byType(Switch));
      expect(onChangedCalled, isTrue);
      expect(changedValue, isTrue);
    });

    testWidgets('should be disabled when onChanged is null', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: null,
      ));

      final switchListTile = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(switchListTile.onChanged, isNull);
    });

    testWidgets('should apply correct theme colors when enabled', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              primary: Colors.blue,
              onSurface: Colors.black,
              surfaceContainer: Colors.grey,
              outlineVariant: Colors.grey,
            ),
          ),
          home: Scaffold(
            body: AgentToolSwitch(
              title: 'Test Tool',
              value: true,
              onChanged: (value) {},
            ),
          ),
        ),
      );

      final switchListTile = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(switchListTile.activeColor, equals(Colors.blue));
    });

    testWidgets('should apply disabled color when onChanged is null', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            colorScheme: const ColorScheme.light(
              onSurface: Colors.black,
              surfaceContainer: Colors.grey,
              outlineVariant: Colors.grey,
            ),
            disabledColor: Colors.grey,
          ),
          home: Scaffold(
            body: AgentToolSwitch(
              title: 'Test Tool',
              value: false,
              onChanged: null,
            ),
          ),
        ),
      );

      final text = tester.widget<Text>(find.text('Test Tool'));
      expect(text.style?.color, equals(Colors.grey));
    });

    testWidgets('should have correct card styling', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      final card = tester.widget<Card>(find.byType(Card));
      expect(card.elevation, equals(0.0));
      expect(card.shape, isA<RoundedRectangleBorder>());
    });

    testWidgets('should apply correct content padding', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      final switchListTile = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(switchListTile.contentPadding, isA<EdgeInsets>());
    });

    testWidgets('should work with dark theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData.dark(),
          home: Scaffold(
            body: AgentToolSwitch(
              title: 'Test Tool',
              value: true,
              onChanged: (value) {},
            ),
          ),
        ),
      );

      expect(find.text('Test Tool'), findsOneWidget);
      expect(find.byType(SwitchListTile), findsOneWidget);
    });

    testWidgets('should handle custom text theme', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          theme: ThemeData(
            textTheme: const TextTheme(
              titleMedium: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
          ),
          home: Scaffold(
            body: AgentToolSwitch(
              title: 'Test Tool',
              value: false,
              onChanged: (value) {},
            ),
          ),
        ),
      );

      expect(find.text('Test Tool'), findsOneWidget);
    });

    testWidgets('should handle different switch states correctly', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {
          onChangedCalled = true;
          changedValue = value;
        },
      ));

      final switchWidget = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(switchWidget.value, isFalse);

      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: true,
        onChanged: (value) {
          onChangedCalled = true;
          changedValue = value;
        },
      ));

      final updatedSwitch = tester.widget<SwitchListTile>(find.byType(SwitchListTile));
      expect(updatedSwitch.value, isTrue);
    });

    testWidgets('should maintain layout consistency', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      expect(find.byType(Card), findsOneWidget);
      expect(find.byType(SwitchListTile), findsOneWidget);
    });

    testWidgets('should handle rapid toggle events', (tester) async {
      int toggleCount = 0;

      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) => toggleCount++,
      ));

      for (int i = 0; i < 5; i++) {
        await tester.tap(find.byType(Switch));
        await tester.pump(const Duration(milliseconds: 10));
      }

      expect(toggleCount, equals(5));
    });

    testWidgets('should work in different container sizes', (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SizedBox(
              width: 200,
              child: AgentToolSwitch(
                title: 'Test Tool',
                value: false,
                onChanged: (value) {},
              ),
            ),
          ),
        ),
      );

      expect(find.text('Test Tool'), findsOneWidget);
      expect(find.byType(SwitchListTile), findsOneWidget);
    });

    testWidgets('should handle long titles gracefully', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'This is a very long tool name that should wrap properly',
        value: false,
        onChanged: (value) {},
      ));

      expect(find.textContaining('This is a very long tool'), findsOneWidget);
    });

    testWidgets('should apply correct margin', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      final card = tester.widget<Card>(find.byType(Card));
      expect(card.margin, isA<EdgeInsets>());
    });

    testWidgets('should handle accessibility requirements', (tester) async {
      await tester.pumpWidget(createSwitchTestWidget(
        title: 'Test Tool',
        value: false,
        onChanged: (value) {},
      ));

      expect(find.text('Test Tool'), findsOneWidget);
      expect(find.byType(Switch), findsOneWidget);
    });
  });
}
