import 'package:flutter/foundation.dart';

/// Model for chat attachments sent to the backend
@immutable
class ChatAttachment {
  final String fileId;
  final String suggestedTool;

  const ChatAttachment({
    required this.fileId,
    required this.suggestedTool,
  });

  Map<String, dynamic> toJson() {
    return {
      'file_id': fileId,
      'suggested_tool': suggestedTool,
    };
  }

  factory ChatAttachment.fromJson(Map<String, dynamic> json) {
    return ChatAttachment(
      fileId: json['file_id'] as String,
      suggestedTool: json['suggested_tool'] as String,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is ChatAttachment &&
        other.fileId == fileId &&
        other.suggestedTool == suggestedTool;
  }

  @override
  int get hashCode => Object.hash(fileId, suggestedTool);

  @override
  String toString() => 'ChatAttachment(fileId: $fileId, suggestedTool: $suggestedTool)';
}
