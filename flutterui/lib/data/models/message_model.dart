import 'package:flutter/foundation.dart' show immutable;

@immutable
class Message {
  final String id;
  final String type;
  final String role;
  final String content;
  final String? imageData;
  final bool isError;

  const Message({
    required this.id,
    required this.type,
    required this.role,
    required this.content,
    this.imageData,
    this.isError = false,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as String,
      type: json['type'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      imageData: json['image_data'] as String?,
      isError: json['is_error'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'role': role,
      'content': content,
      'image_data': imageData,
      'is_error': isError,
    };
  }

  Message copyWith({
    String? id,
    String? type,
    String? role,
    String? content,
    String? imageData,
    bool? isError,
  }) {
    return Message(
      id: id ?? this.id,
      type: type ?? this.type,
      role: role ?? this.role,
      content: content ?? this.content,
      imageData: imageData ?? this.imageData,
      isError: isError ?? this.isError,
    );
  }
}
