import 'package:flutter/foundation.dart' show immutable;

@immutable
class Message {
  final String id;
  final String
  type; // e.g., "text", "tool_call", "tool_output" (align with backend)
  final String role; // e.g., "user", "assistant"
  final String content;
  final bool isError; // New field
  // final DateTime? createdAt; // Optional: if you add timestamps

  const Message({
    required this.id,
    required this.type,
    required this.role,
    required this.content,
    this.isError = false, // Default to false
    // this.createdAt,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as String,
      type: json['type'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      isError: json['is_error'] as bool? ?? false,
      // createdAt: json['created_at'] != null
      //     ? DateTime.parse(json['created_at'] as String)
      //     : null,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'role': role,
      'content': content,
      'is_error': isError,
      // 'created_at': createdAt?.toIso8601String(),
    };
  }

  Message copyWith({
    // Renamed from MessagecopyWith to copyWith
    String? id,
    String? type,
    String? role,
    String? content,
    bool? isError,
    // DateTime? createdAt,
  }) {
    return Message(
      id: id ?? this.id,
      type: type ?? this.type,
      role: role ?? this.role,
      content: content ?? this.content,
      isError: isError ?? this.isError,
      // createdAt: createdAt ?? this.createdAt,
    );
  }
}
