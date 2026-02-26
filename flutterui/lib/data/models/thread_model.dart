import 'package:flutter/foundation.dart' show immutable;

@immutable
class Thread {
  final String id;
  final String name;
  final String? description;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final String? lastAgentId;
  final String? lastAgentName;

  const Thread({
    required this.id,
    required this.name,
    this.description,
    this.createdAt,
    this.updatedAt,
    this.lastAgentId,
    this.lastAgentName,
  });

  factory Thread.fromJson(Map<String, dynamic> json) {
    return Thread(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'] as String).toLocal()
          : null,
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'] as String).toLocal()
          : null,
      lastAgentId: json['last_agent_id'] as String?,
      lastAgentName: json['last_agent_name'] as String?,
    );
  }

  Thread copyWith({
    String? id,
    String? name,
    String? description,
    DateTime? createdAt,
    DateTime? updatedAt,
    String? lastAgentId,
    bool clearLastAgentId = false,
    String? lastAgentName,
    bool clearLastAgentName = false,
  }) {
    return Thread(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      lastAgentId: clearLastAgentId ? null : (lastAgentId ?? this.lastAgentId),
      lastAgentName: clearLastAgentName ? null : (lastAgentName ?? this.lastAgentName),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'created_at': createdAt?.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
      'last_agent_id': lastAgentId,
      'last_agent_name': lastAgentName,
    };
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;

    return other is Thread &&
        other.id == id &&
        other.name == name &&
        other.description == description &&
        other.createdAt == createdAt &&
        other.updatedAt == updatedAt &&
        other.lastAgentId == lastAgentId &&
        other.lastAgentName == lastAgentName;
  }

  @override
  int get hashCode =>
      id.hashCode ^
      name.hashCode ^
      description.hashCode ^
      createdAt.hashCode ^
      updatedAt.hashCode ^
      lastAgentId.hashCode ^
      lastAgentName.hashCode;
}
