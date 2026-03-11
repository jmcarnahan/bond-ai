@TestOn('browser')
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/data/services/scheduled_job_service.dart';
import 'package:flutterui/providers/scheduled_job_provider.dart';
import 'package:flutterui/providers/services/service_providers.dart'
    show scheduledJobServiceProvider;

// ---------------------------------------------------------------------------
// Manual mock for ScheduledJobService
// ---------------------------------------------------------------------------
class MockScheduledJobService implements ScheduledJobService {
  Future<List<ScheduledJob>> Function()? getScheduledJobsStub;

  Future<ScheduledJob> Function({
    required String agentId,
    required String name,
    required String prompt,
    required String schedule,
    String timezone,
    bool isEnabled,
    int timeoutSeconds,
  })? createScheduledJobStub;

  Future<ScheduledJob> Function(
    String jobId, {
    String? name,
    String? prompt,
    String? schedule,
    String? timezone,
    bool? isEnabled,
    int? timeoutSeconds,
  })? updateScheduledJobStub;

  Future<void> Function(String jobId)? deleteScheduledJobStub;

  Future<List<ScheduledJobRun>> Function(String jobId)? getJobRunsStub;

  @override
  Future<List<ScheduledJob>> getScheduledJobs() {
    if (getScheduledJobsStub != null) return getScheduledJobsStub!();
    return Future.value([]);
  }

  @override
  Future<ScheduledJob> createScheduledJob({
    required String agentId,
    required String name,
    required String prompt,
    required String schedule,
    String timezone = 'UTC',
    bool isEnabled = true,
    int timeoutSeconds = 300,
  }) {
    if (createScheduledJobStub != null) {
      return createScheduledJobStub!(
        agentId: agentId,
        name: name,
        prompt: prompt,
        schedule: schedule,
        timezone: timezone,
        isEnabled: isEnabled,
        timeoutSeconds: timeoutSeconds,
      );
    }
    throw UnimplementedError('createScheduledJob not stubbed');
  }

  @override
  Future<ScheduledJob> updateScheduledJob(
    String jobId, {
    String? name,
    String? prompt,
    String? schedule,
    String? timezone,
    bool? isEnabled,
    int? timeoutSeconds,
  }) {
    if (updateScheduledJobStub != null) {
      return updateScheduledJobStub!(
        jobId,
        name: name,
        prompt: prompt,
        schedule: schedule,
        timezone: timezone,
        isEnabled: isEnabled,
        timeoutSeconds: timeoutSeconds,
      );
    }
    throw UnimplementedError('updateScheduledJob not stubbed');
  }

  @override
  Future<void> deleteScheduledJob(String jobId) {
    if (deleteScheduledJobStub != null) return deleteScheduledJobStub!(jobId);
    throw UnimplementedError('deleteScheduledJob not stubbed');
  }

  @override
  Future<List<ScheduledJobRun>> getJobRuns(String jobId) {
    if (getJobRunsStub != null) return getJobRunsStub!(jobId);
    return Future.value([]);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
ScheduledJob _job(String id, {String name = 'Job', bool isEnabled = true}) {
  return ScheduledJob(
    id: id,
    userId: 'user-1',
    agentId: 'agent-1',
    name: name,
    prompt: 'Test prompt',
    schedule: '0 9 * * *',
    isEnabled: isEnabled,
  );
}

({ProviderContainer container, ScheduledJobsNotifier notifier, MockScheduledJobService mock})
    _createNotifier({MockScheduledJobService? mock}) {
  final mockService = mock ?? MockScheduledJobService();

  final container = ProviderContainer(
    overrides: [
      scheduledJobServiceProvider.overrideWithValue(mockService),
    ],
  );

  final notifier = container.read(scheduledJobsNotifierProvider.notifier);

  return (container: container, notifier: notifier, mock: mockService);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------
void main() {
  group('ScheduledJobsNotifier', () {
    // -----------------------------------------------------------------------
    // loadJobs
    // -----------------------------------------------------------------------
    group('loadJobs', () {
      test('populates state from service response', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [
          _job('j1', name: 'First'),
          _job('j2', name: 'Second'),
        ];

        await setup.notifier.loadJobs();

        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.jobs, hasLength(2));
        expect(state.jobs[0].name, 'First');
        expect(state.jobs[1].name, 'Second');
        expect(state.isLoading, false);
        expect(state.error, isNull);
        setup.container.dispose();
      });

      test('sets loading state during fetch', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async {
          // Check that loading is true during the fetch
          final state = setup.container.read(scheduledJobsNotifierProvider);
          expect(state.isLoading, true);
          return [_job('j1')];
        };

        await setup.notifier.loadJobs();
        setup.container.dispose();
      });

      test('sets error on failure', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async =>
            throw Exception('Network error');

        await setup.notifier.loadJobs();

        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.isLoading, false);
        expect(state.error, isNotNull);
        expect(state.error, contains('Network error'));
        setup.container.dispose();
      });

      test('clears previous error on successful load', () async {
        final setup = _createNotifier();

        // First: fail
        setup.mock.getScheduledJobsStub = () async =>
            throw Exception('fail');
        await setup.notifier.loadJobs();
        expect(setup.container.read(scheduledJobsNotifierProvider).error, isNotNull);

        // Second: succeed
        setup.mock.getScheduledJobsStub = () async => [_job('j1')];
        await setup.notifier.loadJobs();

        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.error, isNull);
        expect(state.jobs, hasLength(1));
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // createJob
    // -----------------------------------------------------------------------
    group('createJob', () {
      test('adds job to state on success', () async {
        final setup = _createNotifier();
        final newJob = _job('j-new', name: 'New Job');
        setup.mock.createScheduledJobStub = ({
          required String agentId,
          required String name,
          required String prompt,
          required String schedule,
          String timezone = 'UTC',
          bool isEnabled = true,
          int timeoutSeconds = 300,
        }) async => newJob;

        final result = await setup.notifier.createJob(
          agentId: 'agent-1',
          name: 'New Job',
          prompt: 'Do something',
          schedule: '0 9 * * *',
        );

        expect(result, isNotNull);
        expect(result!.id, 'j-new');

        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.jobs, hasLength(1));
        expect(state.jobs.first.name, 'New Job');
        setup.container.dispose();
      });

      test('prepends new job to existing list', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [_job('j1', name: 'Existing')];
        await setup.notifier.loadJobs();

        setup.mock.createScheduledJobStub = ({
          required String agentId,
          required String name,
          required String prompt,
          required String schedule,
          String timezone = 'UTC',
          bool isEnabled = true,
          int timeoutSeconds = 300,
        }) async => _job('j2', name: 'New');

        await setup.notifier.createJob(
          agentId: 'agent-1',
          name: 'New',
          prompt: 'Test',
          schedule: '0 * * * *',
        );

        final jobs = setup.container.read(scheduledJobsNotifierProvider).jobs;
        expect(jobs, hasLength(2));
        expect(jobs[0].name, 'New'); // prepended
        expect(jobs[1].name, 'Existing');
        setup.container.dispose();
      });

      test('returns null and sets error on failure', () async {
        final setup = _createNotifier();
        setup.mock.createScheduledJobStub = ({
          required String agentId,
          required String name,
          required String prompt,
          required String schedule,
          String timezone = 'UTC',
          bool isEnabled = true,
          int timeoutSeconds = 300,
        }) async => throw Exception('Create failed');

        final result = await setup.notifier.createJob(
          agentId: 'agent-1',
          name: 'Fail',
          prompt: 'Test',
          schedule: '0 9 * * *',
        );

        expect(result, isNull);
        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.error, isNotNull);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // updateJob
    // -----------------------------------------------------------------------
    group('updateJob', () {
      test('updates job in state on success', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [_job('j1', name: 'Old')];
        await setup.notifier.loadJobs();

        setup.mock.updateScheduledJobStub = (jobId, {
          String? name,
          String? prompt,
          String? schedule,
          String? timezone,
          bool? isEnabled,
          int? timeoutSeconds,
        }) async => _job('j1', name: 'Updated');

        final success = await setup.notifier.updateJob('j1', name: 'Updated');

        expect(success, true);
        final jobs = setup.container.read(scheduledJobsNotifierProvider).jobs;
        expect(jobs.first.name, 'Updated');
        setup.container.dispose();
      });

      test('returns false and sets error on failure', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [_job('j1')];
        await setup.notifier.loadJobs();

        setup.mock.updateScheduledJobStub = (jobId, {
          String? name,
          String? prompt,
          String? schedule,
          String? timezone,
          bool? isEnabled,
          int? timeoutSeconds,
        }) async => throw Exception('Update failed');

        final success = await setup.notifier.updateJob('j1', name: 'New');

        expect(success, false);
        final state = setup.container.read(scheduledJobsNotifierProvider);
        expect(state.error, isNotNull);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // toggleJob
    // -----------------------------------------------------------------------
    group('toggleJob', () {
      test('toggles isEnabled via updateJob', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [_job('j1', isEnabled: true)];
        await setup.notifier.loadJobs();

        setup.mock.updateScheduledJobStub = (jobId, {
          String? name,
          String? prompt,
          String? schedule,
          String? timezone,
          bool? isEnabled,
          int? timeoutSeconds,
        }) async => _job('j1', isEnabled: false);

        final success = await setup.notifier.toggleJob('j1', false);

        expect(success, true);
        final jobs = setup.container.read(scheduledJobsNotifierProvider).jobs;
        expect(jobs.first.isEnabled, false);
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // deleteJob
    // -----------------------------------------------------------------------
    group('deleteJob', () {
      test('removes job from state on success', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [
          _job('j1', name: 'Keep'),
          _job('j2', name: 'Delete'),
        ];
        await setup.notifier.loadJobs();

        setup.mock.deleteScheduledJobStub = (_) async {};

        final success = await setup.notifier.deleteJob('j2');

        expect(success, true);
        final jobs = setup.container.read(scheduledJobsNotifierProvider).jobs;
        expect(jobs, hasLength(1));
        expect(jobs.first.id, 'j1');
        setup.container.dispose();
      });

      test('returns false and sets error on failure', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async => [_job('j1')];
        await setup.notifier.loadJobs();

        setup.mock.deleteScheduledJobStub = (_) async =>
            throw Exception('Delete failed');

        final success = await setup.notifier.deleteJob('j1');

        expect(success, false);
        // Job should still be in state
        final jobs = setup.container.read(scheduledJobsNotifierProvider).jobs;
        expect(jobs, hasLength(1));
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // loadJobRuns
    // -----------------------------------------------------------------------
    group('loadJobRuns', () {
      test('returns runs from service', () async {
        final setup = _createNotifier();
        setup.mock.getJobRunsStub = (jobId) async => [
          ScheduledJobRun(
            threadId: 'thread-1',
            threadName: '[Scheduled] Job - 2026-03-10',
            createdAt: DateTime(2026, 3, 10, 9, 0),
            status: 'completed',
          ),
          ScheduledJobRun(
            threadId: 'thread-2',
            threadName: '[Scheduled] Job - 2026-03-09',
            createdAt: DateTime(2026, 3, 9, 9, 0),
            status: 'completed',
          ),
        ];

        final runs = await setup.notifier.loadJobRuns('j1');

        expect(runs, hasLength(2));
        expect(runs[0].threadId, 'thread-1');
        expect(runs[1].threadId, 'thread-2');
        setup.container.dispose();
      });

      test('rethrows exception on failure', () async {
        final setup = _createNotifier();
        setup.mock.getJobRunsStub = (_) async =>
            throw Exception('Runs failed');

        expect(
          () => setup.notifier.loadJobRuns('j1'),
          throwsA(isA<Exception>()),
        );
        setup.container.dispose();
      });
    });

    // -----------------------------------------------------------------------
    // clearError
    // -----------------------------------------------------------------------
    group('clearError', () {
      test('clears error from state', () async {
        final setup = _createNotifier();
        setup.mock.getScheduledJobsStub = () async =>
            throw Exception('fail');
        await setup.notifier.loadJobs();

        expect(setup.container.read(scheduledJobsNotifierProvider).error, isNotNull);

        setup.notifier.clearError();

        expect(setup.container.read(scheduledJobsNotifierProvider).error, isNull);
        setup.container.dispose();
      });
    });
  });

  group('ScheduledJobsState', () {
    test('default state has empty jobs and no loading', () {
      const state = ScheduledJobsState();
      expect(state.jobs, isEmpty);
      expect(state.isLoading, false);
      expect(state.error, isNull);
    });

    test('copyWith preserves error when not explicitly cleared', () {
      final state = ScheduledJobsState(
        jobs: [_job('j1')],
        isLoading: false,
        error: 'some error',
      );

      final updated = state.copyWith(isLoading: true);

      expect(updated.jobs, hasLength(1));
      expect(updated.isLoading, true);
      expect(updated.error, 'some error');
    });

    test('copyWith clears error with clearError flag', () {
      final state = ScheduledJobsState(
        jobs: [_job('j1')],
        isLoading: false,
        error: 'some error',
      );

      final updated = state.copyWith(clearError: true);

      expect(updated.error, isNull);
    });

    test('copyWith replaces error with new value', () {
      final state = ScheduledJobsState(
        error: 'old error',
      );

      final updated = state.copyWith(error: 'new error');

      expect(updated.error, 'new error');
    });
  });
}
