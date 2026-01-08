import 'package:flutter/foundation.dart' show immutable;

@immutable
class Message {
  final String id;
  final String type;
  final String role;
  final String content;
  final String? imageData;
  final String? agentId;
  final bool isError;
  final String? feedbackType;
  final String? feedbackMessage;

  const Message({
    required this.id,
    required this.type,
    required this.role,
    required this.content,
    this.imageData,
    this.agentId,
    this.isError = false,
    this.feedbackType,
    this.feedbackMessage,
  });

  bool get hasFeedback => feedbackType != null;

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as String,
      type: json['type'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      imageData: json['image_data'] as String?,
      agentId: json['agent_id'] as String?,
      isError: json['is_error'] as bool? ?? false,
      feedbackType: json['feedback_type'] as String?,
      feedbackMessage: json['feedback_message'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type,
      'role': role,
      'content': content,
      'image_data': imageData,
      'agent_id': agentId,
      'is_error': isError,
      'feedback_type': feedbackType,
      'feedback_message': feedbackMessage,
    };
  }

  Message copyWith({
    String? id,
    String? type,
    String? role,
    String? content,
    String? imageData,
    String? agentId,
    bool? isError,
    String? feedbackType,
    String? feedbackMessage,
    bool clearFeedback = false,
  }) {
    return Message(
      id: id ?? this.id,
      type: type ?? this.type,
      role: role ?? this.role,
      content: content ?? this.content,
      imageData: imageData ?? this.imageData,
      agentId: agentId ?? this.agentId,
      isError: isError ?? this.isError,
      feedbackType: clearFeedback ? null : (feedbackType ?? this.feedbackType),
      feedbackMessage: clearFeedback ? null : (feedbackMessage ?? this.feedbackMessage),
    );
  }
}
