import 'dart:convert';
import 'package:http/http.dart' as http;

import 'package:flutterui/core/constants/api_constants.dart';
import 'package:flutterui/data/models/scheduled_job_model.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/web_http_client.dart' as web_client;
import '../../core/utils/logger.dart';

class ScheduledJobService {
  final http.Client _httpClient;
  final AuthService _authService;

  ScheduledJobService({http.Client? httpClient, required AuthService authService})
    : _httpClient = httpClient ?? web_client.createHttpClient(),
      _authService = authService;

  Future<List<ScheduledJob>> getScheduledJobs() async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse('${ApiConstants.baseUrl}${ApiConstants.scheduledJobsEndpoint}'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final jobs = data
            .map((item) => ScheduledJob.fromJson(item as Map<String, dynamic>))
            .toList();
        logger.i("[ScheduledJobService] Loaded ${jobs.length} scheduled jobs");
        return jobs;
      } else {
        logger.e(
          "[ScheduledJobService] Failed to load jobs. Status: ${response.statusCode}",
        );
        throw Exception('Failed to load scheduled jobs: ${response.statusCode}');
      }
    } on Exception {
      rethrow;
    } catch (e) {
      logger.e("[ScheduledJobService] Error in getScheduledJobs: $e");
      throw Exception('Failed to fetch scheduled jobs: $e');
    }
  }

  Future<ScheduledJob> createScheduledJob({
    required String agentId,
    required String name,
    required String prompt,
    required String schedule,
    String timezone = 'UTC',
    bool isEnabled = true,
    int timeoutSeconds = 300,
  }) async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final body = json.encode({
        'agent_id': agentId,
        'name': name,
        'prompt': prompt,
        'schedule': schedule,
        'timezone': timezone,
        'is_enabled': isEnabled,
        'timeout_seconds': timeoutSeconds,
      });

      final response = await _httpClient.post(
        Uri.parse('${ApiConstants.baseUrl}${ApiConstants.scheduledJobsEndpoint}'),
        headers: headers,
        body: body,
      );

      if (response.statusCode == 201) {
        final data = json.decode(response.body);
        final job = ScheduledJob.fromJson(data as Map<String, dynamic>);
        logger.i("[ScheduledJobService] Created job: ${job.id}");
        return job;
      } else {
        logger.e(
          "[ScheduledJobService] Failed to create job. Status: ${response.statusCode}, Body: ${response.body}",
        );
        throw Exception('Failed to create scheduled job: ${response.statusCode}');
      }
    } on Exception {
      rethrow;
    } catch (e) {
      logger.e("[ScheduledJobService] Error in createScheduledJob: $e");
      throw Exception('Failed to create scheduled job: $e');
    }
  }

  Future<ScheduledJob> updateScheduledJob(
    String jobId, {
    String? name,
    String? prompt,
    String? schedule,
    String? timezone,
    bool? isEnabled,
    int? timeoutSeconds,
  }) async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final Map<String, dynamic> payload = {};
      if (name != null) payload['name'] = name;
      if (prompt != null) payload['prompt'] = prompt;
      if (schedule != null) payload['schedule'] = schedule;
      if (timezone != null) payload['timezone'] = timezone;
      if (isEnabled != null) payload['is_enabled'] = isEnabled;
      if (timeoutSeconds != null) payload['timeout_seconds'] = timeoutSeconds;

      final response = await _httpClient.put(
        Uri.parse('${ApiConstants.baseUrl}${ApiConstants.scheduledJobsEndpoint}/$jobId'),
        headers: headers,
        body: json.encode(payload),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        final job = ScheduledJob.fromJson(data as Map<String, dynamic>);
        logger.i("[ScheduledJobService] Updated job: ${job.id}");
        return job;
      } else {
        logger.e(
          "[ScheduledJobService] Failed to update job. Status: ${response.statusCode}",
        );
        throw Exception('Failed to update scheduled job: ${response.statusCode}');
      }
    } on Exception {
      rethrow;
    } catch (e) {
      logger.e("[ScheduledJobService] Error in updateScheduledJob: $e");
      throw Exception('Failed to update scheduled job: $e');
    }
  }

  Future<void> deleteScheduledJob(String jobId) async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.delete(
        Uri.parse('${ApiConstants.baseUrl}${ApiConstants.scheduledJobsEndpoint}/$jobId'),
        headers: headers,
      );

      if (response.statusCode == 204) {
        logger.i("[ScheduledJobService] Deleted job: $jobId");
        return;
      } else {
        logger.e(
          "[ScheduledJobService] Failed to delete job. Status: ${response.statusCode}",
        );
        throw Exception('Failed to delete scheduled job: ${response.statusCode}');
      }
    } on Exception {
      rethrow;
    } catch (e) {
      logger.e("[ScheduledJobService] Error in deleteScheduledJob: $e");
      throw Exception('Failed to delete scheduled job: $e');
    }
  }

  Future<List<ScheduledJobRun>> getJobRuns(String jobId) async {
    try {
      final headers = await _authService.authenticatedHeaders;
      final response = await _httpClient.get(
        Uri.parse('${ApiConstants.baseUrl}${ApiConstants.scheduledJobsEndpoint}/$jobId/runs'),
        headers: headers,
      );

      if (response.statusCode == 200) {
        final List<dynamic> data = json.decode(response.body);
        final runs = data
            .map((item) => ScheduledJobRun.fromJson(item as Map<String, dynamic>))
            .toList();
        logger.i("[ScheduledJobService] Loaded ${runs.length} runs for job $jobId");
        return runs;
      } else {
        logger.e(
          "[ScheduledJobService] Failed to load runs. Status: ${response.statusCode}",
        );
        throw Exception('Failed to load job runs: ${response.statusCode}');
      }
    } on Exception {
      rethrow;
    } catch (e) {
      logger.e("[ScheduledJobService] Error in getJobRuns: $e");
      throw Exception('Failed to fetch job runs: $e');
    }
  }
}
