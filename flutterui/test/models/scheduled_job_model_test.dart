import 'package:flutter_test/flutter_test.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';

void main() {
  group('ScheduledJob.fromJson', () {
    test('parses all fields correctly', () {
      final json = {
        'id': 'job-1',
        'user_id': 'user-1',
        'agent_id': 'agent-1',
        'agent_name': 'My Agent',
        'name': 'Daily Report',
        'prompt': 'Generate a summary',
        'schedule': '0 9 * * *',
        'timezone': 'America/New_York',
        'is_enabled': true,
        'status': 'pending',
        'timeout_seconds': 300,
        'last_run_at': '2026-03-10T09:00:00.000Z',
        'last_run_status': 'completed',
        'last_run_error': null,
        'last_thread_id': 'thread-1',
        'next_run_at': '2026-03-11T09:00:00.000Z',
        'created_at': '2026-03-01T00:00:00.000Z',
        'updated_at': '2026-03-10T09:00:00.000Z',
      };

      final job = ScheduledJob.fromJson(json);

      expect(job.id, 'job-1');
      expect(job.userId, 'user-1');
      expect(job.agentId, 'agent-1');
      expect(job.agentName, 'My Agent');
      expect(job.name, 'Daily Report');
      expect(job.prompt, 'Generate a summary');
      expect(job.schedule, '0 9 * * *');
      expect(job.timezone, 'America/New_York');
      expect(job.isEnabled, true);
      expect(job.status, 'pending');
      expect(job.timeoutSeconds, 300);
      expect(job.lastRunAt, isNotNull);
      expect(job.lastRunStatus, 'completed');
      expect(job.lastRunError, isNull);
      expect(job.lastThreadId, 'thread-1');
      expect(job.nextRunAt, isNotNull);
      expect(job.createdAt, isNotNull);
      expect(job.updatedAt, isNotNull);
    });

    test('handles null optional fields', () {
      final json = {
        'id': 'job-2',
        'user_id': 'user-2',
        'agent_id': 'agent-2',
        'name': 'Simple Job',
        'prompt': 'Do something',
        'schedule': '0 * * * *',
        'agent_name': null,
        'timezone': null,
        'is_enabled': null,
        'status': null,
        'timeout_seconds': null,
        'last_run_at': null,
        'last_run_status': null,
        'last_run_error': null,
        'last_thread_id': null,
        'next_run_at': null,
        'created_at': null,
        'updated_at': null,
      };

      final job = ScheduledJob.fromJson(json);

      expect(job.agentName, isNull);
      expect(job.timezone, 'UTC'); // Default
      expect(job.isEnabled, true); // Default
      expect(job.status, 'pending'); // Default
      expect(job.timeoutSeconds, 300); // Default
      expect(job.lastRunAt, isNull);
      expect(job.lastRunStatus, isNull);
      expect(job.lastRunError, isNull);
      expect(job.lastThreadId, isNull);
      expect(job.nextRunAt, isNull);
    });

    test('handles missing optional keys', () {
      final json = {
        'id': 'job-3',
        'user_id': 'user-3',
        'agent_id': 'agent-3',
        'name': 'Minimal Job',
        'prompt': 'Run',
        'schedule': '0 9 * * *',
      };

      final job = ScheduledJob.fromJson(json);

      expect(job.id, 'job-3');
      expect(job.timezone, 'UTC');
      expect(job.isEnabled, true);
      expect(job.status, 'pending');
      expect(job.timeoutSeconds, 300);
    });

    test('converts date strings to local time', () {
      final json = {
        'id': 'job-4',
        'user_id': 'user-4',
        'agent_id': 'agent-4',
        'name': 'Date Test',
        'prompt': 'Test',
        'schedule': '0 9 * * *',
        'last_run_at': '2026-03-10T14:30:00.000Z',
        'next_run_at': '2026-03-11T14:00:00.000Z',
        'created_at': '2026-03-01T00:00:00.000Z',
      };

      final job = ScheduledJob.fromJson(json);

      // Dates should be converted to local time
      expect(job.lastRunAt!.isUtc, false);
      expect(job.nextRunAt!.isUtc, false);
      expect(job.createdAt!.isUtc, false);
    });
  });

  group('ScheduledJob.copyWith', () {
    final base = ScheduledJob(
      id: 'job-1',
      userId: 'user-1',
      agentId: 'agent-1',
      agentName: 'My Agent',
      name: 'Original',
      prompt: 'Original prompt',
      schedule: '0 9 * * *',
      lastRunStatus: 'completed',
      lastThreadId: 'thread-1',
    );

    test('preserves fields when not specified', () {
      final copy = base.copyWith(name: 'Updated');

      expect(copy.name, 'Updated');
      expect(copy.agentId, 'agent-1');
      expect(copy.prompt, 'Original prompt');
      expect(copy.schedule, '0 9 * * *');
      expect(copy.lastRunStatus, 'completed');
    });

    test('replaces specified fields', () {
      final copy = base.copyWith(
        name: 'New Name',
        prompt: 'New prompt',
        schedule: '0 */4 * * *',
        isEnabled: false,
      );

      expect(copy.name, 'New Name');
      expect(copy.prompt, 'New prompt');
      expect(copy.schedule, '0 */4 * * *');
      expect(copy.isEnabled, false);
    });

    test('clears agentName with flag', () {
      final copy = base.copyWith(clearAgentName: true);
      expect(copy.agentName, isNull);
    });

    test('clears lastRunStatus with flag', () {
      final copy = base.copyWith(clearLastRunStatus: true);
      expect(copy.lastRunStatus, isNull);
    });

    test('clears lastThreadId with flag', () {
      final copy = base.copyWith(clearLastThreadId: true);
      expect(copy.lastThreadId, isNull);
    });

    test('clears lastRunError with flag', () {
      final job = base.copyWith(lastRunError: 'Some error');
      final cleared = job.copyWith(clearLastRunError: true);
      expect(cleared.lastRunError, isNull);
    });
  });

  group('ScheduledJob.toJson', () {
    test('serializes all fields', () {
      final job = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        agentName: 'Agent',
        name: 'Test Job',
        prompt: 'Do it',
        schedule: '0 9 * * *',
        timezone: 'UTC',
        isEnabled: true,
        status: 'pending',
        timeoutSeconds: 300,
        lastRunStatus: 'completed',
        lastThreadId: 'thread-1',
      );

      final json = job.toJson();

      expect(json['id'], 'job-1');
      expect(json['user_id'], 'user-1');
      expect(json['agent_id'], 'agent-1');
      expect(json['agent_name'], 'Agent');
      expect(json['name'], 'Test Job');
      expect(json['prompt'], 'Do it');
      expect(json['schedule'], '0 9 * * *');
      expect(json['timezone'], 'UTC');
      expect(json['is_enabled'], true);
      expect(json['status'], 'pending');
      expect(json['timeout_seconds'], 300);
      expect(json['last_run_status'], 'completed');
      expect(json['last_thread_id'], 'thread-1');
    });

    test('includes null values for absent optional fields', () {
      final job = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Test',
        prompt: 'Test',
        schedule: '0 9 * * *',
      );

      final json = job.toJson();

      expect(json.containsKey('last_run_at'), true);
      expect(json['last_run_at'], isNull);
      expect(json.containsKey('last_run_status'), true);
      expect(json['last_run_status'], isNull);
      expect(json.containsKey('last_thread_id'), true);
      expect(json['last_thread_id'], isNull);
    });
  });

  group('ScheduledJob.fromJson roundtrip', () {
    test('toJson then fromJson preserves all fields', () {
      final original = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        agentName: 'My Agent',
        name: 'Test Job',
        prompt: 'Run this',
        schedule: '0 9 * * *',
        timezone: 'UTC',
        isEnabled: true,
        status: 'pending',
        timeoutSeconds: 600,
        lastRunStatus: 'failed',
        lastRunError: 'Timeout',
        lastThreadId: 'thread-1',
      );

      final json = original.toJson();
      final restored = ScheduledJob.fromJson(json);

      expect(restored.id, original.id);
      expect(restored.userId, original.userId);
      expect(restored.agentId, original.agentId);
      expect(restored.agentName, original.agentName);
      expect(restored.name, original.name);
      expect(restored.prompt, original.prompt);
      expect(restored.schedule, original.schedule);
      expect(restored.timezone, original.timezone);
      expect(restored.isEnabled, original.isEnabled);
      expect(restored.status, original.status);
      expect(restored.timeoutSeconds, original.timeoutSeconds);
      expect(restored.lastRunStatus, original.lastRunStatus);
      expect(restored.lastRunError, original.lastRunError);
      expect(restored.lastThreadId, original.lastThreadId);
    });
  });

  group('ScheduledJob equality', () {
    test('identical objects are equal', () {
      final a = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Same',
        prompt: 'Same',
        schedule: '0 9 * * *',
      );
      expect(a, equals(a));
    });

    test('objects with all same fields are equal', () {
      final a = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Same',
        prompt: 'Same',
        schedule: '0 9 * * *',
      );
      final b = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Same',
        prompt: 'Same',
        schedule: '0 9 * * *',
      );
      expect(a, equals(b));
      expect(a.hashCode, equals(b.hashCode));
    });

    test('same ID but different fields are NOT equal', () {
      final a = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Name A',
        prompt: 'A',
        schedule: '0 9 * * *',
      );
      final b = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Name B',
        prompt: 'B',
        schedule: '0 12 * * *',
      );
      expect(a, isNot(equals(b)));
    });

    test('different IDs are not equal', () {
      final a = ScheduledJob(
        id: 'job-1',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Same',
        prompt: 'Same',
        schedule: '0 9 * * *',
      );
      final b = ScheduledJob(
        id: 'job-2',
        userId: 'user-1',
        agentId: 'agent-1',
        name: 'Same',
        prompt: 'Same',
        schedule: '0 9 * * *',
      );
      expect(a, isNot(equals(b)));
    });
  });

  group('parseUtcToLocal', () {
    test('handles naive datetime string (no Z suffix) as UTC', () {
      // Backend returns naive UTC datetimes like "2026-03-10T14:30:00"
      final result = ScheduledJob.parseUtcToLocal('2026-03-10T14:30:00');

      // Should NOT be UTC (converted to local)
      expect(result.isUtc, false);
      // The UTC source hour is 14, so local should differ by the local offset
      final expectedUtc = DateTime.utc(2026, 3, 10, 14, 30, 0);
      expect(result, expectedUtc.toLocal());
    });

    test('handles datetime with Z suffix correctly', () {
      final result = ScheduledJob.parseUtcToLocal('2026-03-10T14:30:00.000Z');

      expect(result.isUtc, false);
      final expectedUtc = DateTime.utc(2026, 3, 10, 14, 30, 0);
      expect(result, expectedUtc.toLocal());
    });

    test('naive and Z-suffixed produce the same local time', () {
      final naive = ScheduledJob.parseUtcToLocal('2026-03-10T09:00:00');
      final withZ = ScheduledJob.parseUtcToLocal('2026-03-10T09:00:00.000Z');

      expect(naive, withZ);
    });

    test('handles datetime with milliseconds', () {
      final result = ScheduledJob.parseUtcToLocal('2026-03-10T14:30:00.123');
      expect(result.isUtc, false);
      expect(result.millisecond, 123);
    });
  });

  group('ScheduledJobRun.fromJson', () {
    test('parses all fields', () {
      final json = {
        'thread_id': 'thread-1',
        'thread_name': '[Scheduled] Daily Report - 2026-03-10 09:00',
        'created_at': '2026-03-10T09:00:00.000Z',
        'status': 'completed',
      };

      final run = ScheduledJobRun.fromJson(json);

      expect(run.threadId, 'thread-1');
      expect(run.threadName, '[Scheduled] Daily Report - 2026-03-10 09:00');
      expect(run.createdAt, isNotNull);
      expect(run.status, 'completed');
    });

    test('handles null optional fields', () {
      final json = {
        'thread_id': 'thread-2',
        'thread_name': 'Some thread',
        'created_at': null,
        'status': null,
      };

      final run = ScheduledJobRun.fromJson(json);

      expect(run.threadId, 'thread-2');
      expect(run.createdAt, isNull);
      expect(run.status, isNull);
    });
  });
}
