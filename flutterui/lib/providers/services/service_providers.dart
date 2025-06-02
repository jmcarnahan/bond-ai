import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/mcp_service.dart';
import 'package:flutterui/main.dart' show sharedPreferencesProvider;

final authServiceProvider = Provider<AuthService>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return AuthService(sharedPreferences: prefs);
});

final agentServiceProvider = Provider<AgentService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return AgentService(authService: authService);
});

final threadServiceProvider = Provider<ThreadService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return ThreadService(authService: authService);
});

final chatServiceProvider = Provider<ChatService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return ChatService(authService: authService);
});

final mcpServiceProvider = Provider<McpService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return McpService(authService: authService);
});