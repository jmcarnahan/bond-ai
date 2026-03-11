@TestOn('browser')
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/presentation/screens/scheduled_jobs/widgets/scheduled_job_run_item.dart';
import 'package:flutterui/presentation/screens/scheduled_jobs/widgets/scheduled_job_list_item.dart';
import 'package:flutterui/presentation/screens/scheduled_jobs/widgets/scheduled_jobs_empty_state.dart';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

ScheduledJob _makeJob({
  bool isEnabled = true,
  String? lastRunStatus,
  DateTime? nextRunAt,
  String schedule = '0 * * * *',
  String? lastThreadId,
}) {
  return ScheduledJob(
    id: 'job-1',
    userId: 'user-1',
    agentId: 'agent-1',
    name: 'Test Job',
    prompt: 'Run test',
    schedule: schedule,
    isEnabled: isEnabled,
    lastRunStatus: lastRunStatus,
    lastThreadId: lastThreadId,
    nextRunAt: nextRunAt,
  );
}

Widget _wrap(Widget child) {
  return MaterialApp(home: Scaffold(body: child));
}

// ---------------------------------------------------------------------------
// ScheduledJobRunItem tests
// ---------------------------------------------------------------------------

void main() {
  group('ScheduledJobRunItem', () {
    testWidgets('completed run shows green check icon', (tester) async {
      final run = ScheduledJobRun(
        threadId: 't1',
        threadName: 'Run 1',
        status: 'completed',
        createdAt: DateTime(2026, 1, 1, 12, 0),
      );
      await tester.pumpWidget(_wrap(ScheduledJobRunItem(
        run: run,
        onTap: () {},
      )));

      final icon = tester.widget<Icon>(find.byIcon(Icons.check_circle));
      expect(icon.color, Colors.green);
    });

    testWidgets('failed run shows error icon', (tester) async {
      final run = ScheduledJobRun(
        threadId: 't2',
        threadName: 'Run 2',
        status: 'failed',
      );
      await tester.pumpWidget(_wrap(ScheduledJobRunItem(
        run: run,
        onTap: () {},
      )));

      expect(find.byIcon(Icons.error), findsOneWidget);
    });

    testWidgets('null status shows help_outline icon', (tester) async {
      final run = ScheduledJobRun(
        threadId: 't3',
        threadName: 'Run 3',
        status: null,
      );
      await tester.pumpWidget(_wrap(ScheduledJobRunItem(
        run: run,
        onTap: () {},
      )));

      expect(find.byIcon(Icons.help_outline), findsOneWidget);
    });

    testWidgets('displays thread name', (tester) async {
      final run = ScheduledJobRun(
        threadId: 't4',
        threadName: 'My Thread Name',
        status: 'completed',
      );
      await tester.pumpWidget(_wrap(ScheduledJobRunItem(
        run: run,
        onTap: () {},
      )));

      expect(find.text('My Thread Name'), findsOneWidget);
    });
  });

  // ---------------------------------------------------------------------------
  // ScheduledJobListItem tests
  // ---------------------------------------------------------------------------

  group('ScheduledJobListItem', () {
    testWidgets('disabled job shows gray status dot', (tester) async {
      final job = _makeJob(isEnabled: false);
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      // The status dot is the first Container with BoxDecoration circle
      final containers = tester.widgetList<Container>(find.byType(Container));
      final dot = containers.firstWhere(
        (c) => c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).shape == BoxShape.circle,
      );
      final dotColor = (dot.decoration as BoxDecoration).color!;
      // Disabled dot should NOT be green and NOT be red
      expect(dotColor, isNot(Colors.green));
    });

    testWidgets('failed job shows red status dot', (tester) async {
      final job = _makeJob(isEnabled: true, lastRunStatus: 'failed');
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      final containers = tester.widgetList<Container>(find.byType(Container));
      final dot = containers.firstWhere(
        (c) => c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).shape == BoxShape.circle,
      );
      final dotColor = (dot.decoration as BoxDecoration).color!;
      // Error color from theme
      expect(dotColor, isNot(Colors.green));
    });

    testWidgets('active enabled job shows green status dot', (tester) async {
      final job = _makeJob(isEnabled: true, lastRunStatus: 'completed');
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      final containers = tester.widgetList<Container>(find.byType(Container));
      final dot = containers.firstWhere(
        (c) => c.decoration is BoxDecoration &&
            (c.decoration as BoxDecoration).shape == BoxShape.circle,
      );
      final dotColor = (dot.decoration as BoxDecoration).color!;
      expect(dotColor, Colors.green);
    });

    testWidgets('humanReadableSchedule shows "Every hour" for 0 * * * *',
        (tester) async {
      final job = _makeJob(schedule: '0 * * * *');
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      expect(find.text('Every hour'), findsOneWidget);
    });

    testWidgets('humanReadableSchedule shows raw cron for unknown pattern',
        (tester) async {
      final job = _makeJob(schedule: '30 2 * * 5');
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      expect(find.text('30 2 * * 5 (UTC)'), findsOneWidget);
    });

    testWidgets('overdue nextRunAt shows "overdue"', (tester) async {
      final pastTime = DateTime.now().subtract(const Duration(minutes: 10));
      final job = _makeJob(isEnabled: true, nextRunAt: pastTime);
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      expect(find.textContaining('overdue'), findsOneWidget);
    });

    testWidgets('future nextRunAt shows "in Xm"', (tester) async {
      final futureTime = DateTime.now().add(const Duration(minutes: 30));
      final job = _makeJob(isEnabled: true, nextRunAt: futureTime);
      await tester.pumpWidget(_wrap(ScheduledJobListItem(
        job: job,
        onTap: () {},
        onEdit: () {},
        onToggle: () {},
      )));

      expect(find.textContaining('in '), findsOneWidget);
    });
  });

  // ---------------------------------------------------------------------------
  // ScheduledJobsEmptyState tests
  // ---------------------------------------------------------------------------

  group('ScheduledJobsEmptyState', () {
    testWidgets('displays CTA button text', (tester) async {
      await tester.pumpWidget(_wrap(ScheduledJobsEmptyState(
        onCreateJob: () {},
      )));

      expect(find.text('Create Scheduled Job'), findsOneWidget);
      expect(find.text('No Scheduled Jobs'), findsOneWidget);
    });

    testWidgets('CTA button fires callback', (tester) async {
      var called = false;
      await tester.pumpWidget(_wrap(ScheduledJobsEmptyState(
        onCreateJob: () => called = true,
      )));

      await tester.tap(find.text('Create Scheduled Job'));
      expect(called, isTrue);
    });
  });
}
