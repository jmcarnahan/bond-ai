import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';

import 'package:flutterui/presentation/screens/threads/widgets/create_thread_dialog.dart';
import 'package:flutterui/providers/thread_provider.dart';

class MockThreadsNotifier extends Mock implements ThreadsNotifier {}

void main() {
  group('CreateThreadDialog Widget Tests', () {
    late ProviderContainer container;
    late MockThreadsNotifier mockThreadsNotifier;

    setUp(() {
      mockThreadsNotifier = MockThreadsNotifier();
    });

    tearDown(() {
      container.dispose();
    });

    testWidgets('should display dialog with all elements', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      expect(find.text('Create New Thread'), findsOneWidget);
      expect(find.text('Optional thread name'), findsOneWidget);
      expect(find.text('Cancel'), findsOneWidget);
      expect(find.text('Create'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
      expect(find.byType(AlertDialog), findsOneWidget);
    });

    testWidgets('should create thread with name when name provided', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), 'Test Thread Name');
      await tester.tap(find.text('Create'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: 'Test Thread Name')).called(1);
    });

    testWidgets('should create thread with null name when no name provided', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: null)).called(1);
    });

    testWidgets('should create thread with null name when only whitespace provided', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), '   \n\t   ');
      await tester.tap(find.text('Create'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: null)).called(1);
    });

    testWidgets('should show loading state when creating thread', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {
        await Future.delayed(const Duration(seconds: 1));
      });

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create'));
      await tester.pump();

      expect(find.text('Creating...'), findsOneWidget);
      expect(find.text('Creating thread...'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.enabled, isFalse);

      final cancelButton = tester.widget<TextButton>(find.text('Cancel').hitTestable());
      expect(cancelButton.onPressed, isNull);

      final createButton = tester.widget<FilledButton>(find.text('Creating...').hitTestable());
      expect(createButton.onPressed, isNull);
    });

    testWidgets('should close dialog after successful creation', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showCreateThreadDialog(context),
                  child: const Text('Open Dialog'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsOneWidget);

      await tester.tap(find.text('Create'));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsNothing);
    });

    testWidgets('should show error snackbar when creation fails', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenThrow(Exception('Creation failed'));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create'));
      await tester.pumpAndSettle();

      expect(find.byType(SnackBar), findsOneWidget);
      expect(find.textContaining('Failed to create thread:'), findsOneWidget);
      expect(find.textContaining('Creation failed'), findsOneWidget);
    });

    testWidgets('should close dialog when cancel button pressed', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showCreateThreadDialog(context),
                  child: const Text('Open Dialog'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsOneWidget);

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsNothing);
      verifyNever(mockThreadsNotifier.addThread(name: anyNamed('name')));
    });

    testWidgets('should apply correct text field properties', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.textCapitalization, equals(TextCapitalization.sentences));
      expect(textField.maxLength, equals(100));
      expect(textField.decoration?.hintText, equals('Optional thread name'));
      expect(textField.decoration?.border, isA<OutlineInputBorder>());
    });

    testWidgets('should show character counter', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), 'Test');
      await tester.pump();

      expect(find.text('4/100'), findsOneWidget);
    });

    testWidgets('should handle long thread names', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      final longName = 'A' * 50;
      await tester.enterText(find.byType(TextField), longName);
      await tester.tap(find.text('Create'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: longName)).called(1);
    });

    testWidgets('should handle special characters in thread name', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {});

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      const specialName = 'Thread with émojis 🧵 and spëcial chars @#\$%';
      await tester.enterText(find.byType(TextField), specialName);
      await tester.tap(find.text('Create'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: specialName)).called(1);
    });

    testWidgets('should apply correct theme colors', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            theme: ThemeData(
              colorScheme: const ColorScheme.light(
                primary: Colors.blue,
                error: Colors.red,
              ),
            ),
            home: const Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      expect(find.byType(TextField), findsOneWidget);
      expect(find.text('Create New Thread'), findsOneWidget);
    });

    testWidgets('should prevent multiple creation attempts', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {
        await Future.delayed(const Duration(milliseconds: 100));
      });

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create'));
      await tester.pump();

      await tester.tap(find.text('Creating...'));
      await tester.pump();

      verify(mockThreadsNotifier.addThread(name: anyNamed('name'))).called(1);
    });

    testWidgets('should reset loading state on error', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenThrow(Exception('Error'));

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Create'));
      await tester.pumpAndSettle();

      expect(find.text('Create'), findsOneWidget);
      expect(find.text('Creating...'), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);

      final textField = tester.widget<TextField>(find.byType(TextField));
      expect(textField.enabled, isTrue);
    });

    testWidgets('should show correct dialog properties', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      final alertDialog = tester.widget<AlertDialog>(find.byType(AlertDialog));
      expect(alertDialog.title, isA<Text>());
      expect(alertDialog.content, isA<Column>());
      expect(alertDialog.actions, hasLength(2));
    });

    testWidgets('showCreateThreadDialog should show dialog with correct properties', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MaterialApp(
            home: Scaffold(
              body: Builder(
                builder: (context) => ElevatedButton(
                  onPressed: () => showCreateThreadDialog(context),
                  child: const Text('Open Dialog'),
                ),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Open Dialog'));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsOneWidget);
      expect(find.byType(CreateThreadDialog), findsOneWidget);

      await tester.tapAt(const Offset(50, 50));
      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsOneWidget);
    });

    testWidgets('should maintain dialog state during creation', (tester) async {
      container = ProviderContainer(
        overrides: [
          threadsProvider.overrideWith((ref) => mockThreadsNotifier),
        ],
      );

      when(mockThreadsNotifier.addThread(name: anyNamed('name'))).thenAnswer((_) async {
        await Future.delayed(const Duration(milliseconds: 200));
      });

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: const MaterialApp(
            home: Scaffold(
              body: CreateThreadDialog(),
            ),
          ),
        ),
      );

      await tester.enterText(find.byType(TextField), 'Test Thread');
      await tester.tap(find.text('Create'));
      await tester.pump();

      expect(find.text('Test Thread'), findsOneWidget);
      expect(find.text('Creating...'), findsOneWidget);
      expect(find.text('Creating thread...'), findsOneWidget);

      await tester.pumpAndSettle();

      expect(find.text('Create New Thread'), findsNothing);
    });
  });
}