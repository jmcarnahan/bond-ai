import 'package:flutter_riverpod/flutter_riverpod.dart';

class NotificationState {
  final String? messageContent;
  final String? threadName;
  final String? agentId;
  final String? subject;
  final int duration;
  final bool isVisible;

  NotificationState({
    this.messageContent,
    this.threadName,
    this.agentId,
    this.subject,
    this.duration = 60,
    this.isVisible = false,
  });

  NotificationState copyWith({
    String? messageContent,
    String? threadName,
    String? agentId,
    String? subject,
    int? duration,
    bool? isVisible,
  }) {
    return NotificationState(
      messageContent: messageContent ?? this.messageContent,
      threadName: threadName ?? this.threadName,
      agentId: agentId ?? this.agentId,
      subject: subject ?? this.subject,
      duration: duration ?? this.duration,
      isVisible: isVisible ?? this.isVisible,
    );
  }
}

class NotificationNotifier extends StateNotifier<NotificationState> {
  NotificationNotifier() : super(NotificationState());

  void showNotificationWithMessageInfo({
    required Map<String, dynamic> messageInfo,
  }) {
    state = NotificationState(
      messageContent: messageInfo['content'] as String,
      threadName: messageInfo['threadName'] as String,
      agentId: messageInfo['agentId'] as String,
      subject: messageInfo['subject'] as String?,
      duration: messageInfo['duration'] as int? ?? 60,
      isVisible: true,
    );
  }

  void hideNotification() {
    state = state.copyWith(isVisible: false);
  }

  void clearNotification() {
    state = NotificationState();
  }
}

final notificationProvider = StateNotifierProvider<NotificationNotifier, NotificationState>((ref) {
  return NotificationNotifier();
});

// Class to hold pending system message information
class PendingSystemMessage {
  final String message;
  final String agentId;
  final String threadName;

  PendingSystemMessage({
    required this.message,
    required this.agentId,
    required this.threadName,
  });
}

// Single provider to store pending system message information
final pendingSystemMessageProvider = StateProvider<PendingSystemMessage?>((ref) => null);
