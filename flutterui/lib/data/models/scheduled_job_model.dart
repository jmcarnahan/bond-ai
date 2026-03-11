import 'package:flutter/foundation.dart' show immutable;

@immutable
class ScheduledJob {
  final String id;
  final String userId;
  final String agentId;
  final String? agentName;
  final String name;
  final String prompt;
  final String schedule;
  final String timezone;
  final bool isEnabled;
  final String status;
  final int timeoutSeconds;
  final DateTime? lastRunAt;
  final String? lastRunStatus;
  final String? lastRunError;
  final String? lastThreadId;
  final DateTime? nextRunAt;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  const ScheduledJob({
    required this.id,
    required this.userId,
    required this.agentId,
    this.agentName,
    required this.name,
    required this.prompt,
    required this.schedule,
    this.timezone = 'UTC',
    this.isEnabled = true,
    this.status = 'pending',
    this.timeoutSeconds = 300,
    this.lastRunAt,
    this.lastRunStatus,
    this.lastRunError,
    this.lastThreadId,
    this.nextRunAt,
    this.createdAt,
    this.updatedAt,
  });

  /// Parse a datetime string from the backend as UTC, then convert to local.
  /// The backend stores naive UTC datetimes (no 'Z' suffix), so DateTime.parse
  /// would incorrectly treat them as local time.  Also used by ScheduledJobRun.
  static DateTime parseUtcToLocal(String value) {
    final parsed = DateTime.parse(value);
    if (parsed.isUtc) return parsed.toLocal();
    return DateTime.utc(
      parsed.year, parsed.month, parsed.day,
      parsed.hour, parsed.minute, parsed.second, parsed.millisecond,
    ).toLocal();
  }

  factory ScheduledJob.fromJson(Map<String, dynamic> json) {
    return ScheduledJob(
      id: json['id'] as String,
      userId: json['user_id'] as String,
      agentId: json['agent_id'] as String,
      agentName: json['agent_name'] as String?,
      name: json['name'] as String,
      prompt: json['prompt'] as String,
      schedule: json['schedule'] as String,
      timezone: (json['timezone'] as String?) ?? 'UTC',
      isEnabled: (json['is_enabled'] as bool?) ?? true,
      status: (json['status'] as String?) ?? 'pending',
      timeoutSeconds: (json['timeout_seconds'] as int?) ?? 300,
      lastRunAt: json['last_run_at'] != null
          ? parseUtcToLocal(json['last_run_at'] as String)
          : null,
      lastRunStatus: json['last_run_status'] as String?,
      lastRunError: json['last_run_error'] as String?,
      lastThreadId: json['last_thread_id'] as String?,
      nextRunAt: json['next_run_at'] != null
          ? parseUtcToLocal(json['next_run_at'] as String)
          : null,
      createdAt: json['created_at'] != null
          ? parseUtcToLocal(json['created_at'] as String)
          : null,
      updatedAt: json['updated_at'] != null
          ? parseUtcToLocal(json['updated_at'] as String)
          : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'agent_id': agentId,
      'agent_name': agentName,
      'name': name,
      'prompt': prompt,
      'schedule': schedule,
      'timezone': timezone,
      'is_enabled': isEnabled,
      'status': status,
      'timeout_seconds': timeoutSeconds,
      'last_run_at': lastRunAt?.toIso8601String(),
      'last_run_status': lastRunStatus,
      'last_run_error': lastRunError,
      'last_thread_id': lastThreadId,
      'next_run_at': nextRunAt?.toIso8601String(),
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  ScheduledJob copyWith({
    String? id,
    String? userId,
    String? agentId,
    String? agentName,
    bool clearAgentName = false,
    String? name,
    String? prompt,
    String? schedule,
    String? timezone,
    bool? isEnabled,
    String? status,
    int? timeoutSeconds,
    DateTime? lastRunAt,
    bool clearLastRunAt = false,
    String? lastRunStatus,
    bool clearLastRunStatus = false,
    String? lastRunError,
    bool clearLastRunError = false,
    String? lastThreadId,
    bool clearLastThreadId = false,
    DateTime? nextRunAt,
    bool clearNextRunAt = false,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ScheduledJob(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      agentId: agentId ?? this.agentId,
      agentName: clearAgentName ? null : (agentName ?? this.agentName),
      name: name ?? this.name,
      prompt: prompt ?? this.prompt,
      schedule: schedule ?? this.schedule,
      timezone: timezone ?? this.timezone,
      isEnabled: isEnabled ?? this.isEnabled,
      status: status ?? this.status,
      timeoutSeconds: timeoutSeconds ?? this.timeoutSeconds,
      lastRunAt: clearLastRunAt ? null : (lastRunAt ?? this.lastRunAt),
      lastRunStatus: clearLastRunStatus ? null : (lastRunStatus ?? this.lastRunStatus),
      lastRunError: clearLastRunError ? null : (lastRunError ?? this.lastRunError),
      lastThreadId: clearLastThreadId ? null : (lastThreadId ?? this.lastThreadId),
      nextRunAt: clearNextRunAt ? null : (nextRunAt ?? this.nextRunAt),
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is ScheduledJob &&
        other.id == id &&
        other.userId == userId &&
        other.agentId == agentId &&
        other.agentName == agentName &&
        other.name == name &&
        other.prompt == prompt &&
        other.schedule == schedule &&
        other.timezone == timezone &&
        other.isEnabled == isEnabled &&
        other.status == status &&
        other.timeoutSeconds == timeoutSeconds &&
        other.lastRunAt == lastRunAt &&
        other.lastRunStatus == lastRunStatus &&
        other.lastRunError == lastRunError &&
        other.lastThreadId == lastThreadId &&
        other.nextRunAt == nextRunAt &&
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt;
  }

  @override
  int get hashCode =>
      id.hashCode ^
      userId.hashCode ^
      agentId.hashCode ^
      agentName.hashCode ^
      name.hashCode ^
      prompt.hashCode ^
      schedule.hashCode ^
      timezone.hashCode ^
      isEnabled.hashCode ^
      status.hashCode ^
      timeoutSeconds.hashCode ^
      lastRunAt.hashCode ^
      lastRunStatus.hashCode ^
      lastRunError.hashCode ^
      lastThreadId.hashCode ^
      nextRunAt.hashCode ^
      createdAt.hashCode ^
      updatedAt.hashCode;
}

@immutable
class ScheduledJobRun {
  final String threadId;
  final String threadName;
  final DateTime? createdAt;
  final String? status;

  const ScheduledJobRun({
    required this.threadId,
    required this.threadName,
    this.createdAt,
    this.status,
  });

  factory ScheduledJobRun.fromJson(Map<String, dynamic> json) {
    return ScheduledJobRun(
      threadId: json['thread_id'] as String,
      threadName: json['thread_name'] as String,
      createdAt: json['created_at'] != null
          ? ScheduledJob.parseUtcToLocal(json['created_at'] as String)
          : null,
      status: json['status'] as String?,
    );
  }
}
