import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/data/services/scheduled_job_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

class ScheduledJobsState {
  final List<ScheduledJob> jobs;
  final bool isLoading;
  final String? error;

  const ScheduledJobsState({
    this.jobs = const [],
    this.isLoading = false,
    this.error,
  });

  ScheduledJobsState copyWith({
    List<ScheduledJob>? jobs,
    bool? isLoading,
    String? error,
    bool clearError = false,
  }) {
    return ScheduledJobsState(
      jobs: jobs ?? this.jobs,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
    );
  }
}

class ScheduledJobsNotifier extends StateNotifier<ScheduledJobsState> {
  final ScheduledJobService _service;

  ScheduledJobsNotifier(this._service) : super(const ScheduledJobsState());

  Future<void> loadJobs() async {
    // Only show full-screen loading spinner on initial load (when no jobs cached).
    // Background refreshes keep the existing list visible to avoid spinner flash.
    final showLoading = state.jobs.isEmpty;
    if (showLoading) {
      state = state.copyWith(isLoading: true, clearError: true);
    }
    try {
      final jobs = await _service.getScheduledJobs();
      state = state.copyWith(jobs: jobs, isLoading: false, clearError: true);
      logger.i("[ScheduledJobsNotifier] Loaded ${jobs.length} jobs");
    } catch (e) {
      logger.e("[ScheduledJobsNotifier] Error loading jobs: $e");
      state = state.copyWith(isLoading: false, error: e.toString());
    }
  }

  Future<ScheduledJob?> createJob({
    required String agentId,
    required String name,
    required String prompt,
    required String schedule,
    String timezone = 'UTC',
    bool isEnabled = true,
    int timeoutSeconds = 300,
  }) async {
    try {
      final job = await _service.createScheduledJob(
        agentId: agentId,
        name: name,
        prompt: prompt,
        schedule: schedule,
        timezone: timezone,
        isEnabled: isEnabled,
        timeoutSeconds: timeoutSeconds,
      );
      state = state.copyWith(jobs: [job, ...state.jobs], clearError: true);
      logger.i("[ScheduledJobsNotifier] Created job: ${job.id}");
      return job;
    } catch (e) {
      logger.e("[ScheduledJobsNotifier] Error creating job: $e");
      state = state.copyWith(error: e.toString());
      return null;
    }
  }

  Future<bool> updateJob(
    String jobId, {
    String? name,
    String? prompt,
    String? schedule,
    String? timezone,
    bool? isEnabled,
    int? timeoutSeconds,
  }) async {
    try {
      final updated = await _service.updateScheduledJob(
        jobId,
        name: name,
        prompt: prompt,
        schedule: schedule,
        timezone: timezone,
        isEnabled: isEnabled,
        timeoutSeconds: timeoutSeconds,
      );
      state = state.copyWith(
        jobs: state.jobs.map((j) => j.id == jobId ? updated : j).toList(),
        clearError: true,
      );
      logger.i("[ScheduledJobsNotifier] Updated job: $jobId");
      return true;
    } catch (e) {
      logger.e("[ScheduledJobsNotifier] Error updating job: $e");
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<bool> toggleJob(String jobId, bool isEnabled) async {
    return updateJob(jobId, isEnabled: isEnabled);
  }

  Future<bool> deleteJob(String jobId) async {
    try {
      await _service.deleteScheduledJob(jobId);
      state = state.copyWith(
        jobs: state.jobs.where((j) => j.id != jobId).toList(),
        clearError: true,
      );
      logger.i("[ScheduledJobsNotifier] Deleted job: $jobId");
      return true;
    } catch (e) {
      logger.e("[ScheduledJobsNotifier] Error deleting job: $e");
      state = state.copyWith(error: e.toString());
      return false;
    }
  }

  Future<List<ScheduledJobRun>> loadJobRuns(String jobId) async {
    try {
      final runs = await _service.getJobRuns(jobId);
      logger.i("[ScheduledJobsNotifier] Loaded ${runs.length} runs for job $jobId");
      return runs;
    } catch (e) {
      logger.e("[ScheduledJobsNotifier] Error loading runs for job $jobId: $e");
      rethrow;
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

final scheduledJobsNotifierProvider =
    StateNotifierProvider<ScheduledJobsNotifier, ScheduledJobsState>((ref) {
  final service = ref.watch(scheduledJobServiceProvider);
  return ScheduledJobsNotifier(service);
});
