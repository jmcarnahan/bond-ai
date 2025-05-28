import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/providers/auth_provider.dart'; // For authServiceProvider
import '../core/utils/logger.dart';

// Provider for AgentService. It depends on AuthService.
final agentServiceProvider = Provider<AgentService>((ref) {
  final authService = ref.watch(
    authServiceProvider,
  ); // Depends on authServiceProvider from auth_provider.dart
  return AgentService(authService: authService);
});

// FutureProvider to fetch the list of agents.
// This will automatically handle loading/error states for us in the UI.
final agentsProvider = FutureProvider<List<AgentListItemModel>>((ref) async {
  // Changed Agent to AgentListItemModel
  logger.i("[agentsProvider] Fetching agents...");
  final agentService = ref.watch(agentServiceProvider);
  try {
    final agents = await agentService.getAgents();
    logger.i("[agentsProvider] Successfully fetched ${agents.length} agents.");
    return agents;
  } catch (e) {
    logger.i("[agentsProvider] Error fetching agents: ${e.toString()}");
    // Re-throw to let the UI handle the error state
    rethrow;
  }
});

// StateNotifierProvider for managing the currently selected agent for chat.
final selectedAgentProvider =
    StateNotifierProvider<SelectedAgentNotifier, AgentListItemModel?>((ref) {
      // Changed Agent to AgentListItemModel
      return SelectedAgentNotifier();
    });

class SelectedAgentNotifier extends StateNotifier<AgentListItemModel?> {
  // Changed Agent to AgentListItemModel
  SelectedAgentNotifier() : super(null);

  void selectAgent(AgentListItemModel agent) {
    // Changed Agent to AgentListItemModel
    state = agent;
    logger.i(
      "[SelectedAgentNotifier] Agent selected: ${agent.name} (ID: ${agent.id})",
    );
  }

  void clearAgent() {
    state = null;
    logger.i("[SelectedAgentNotifier] Agent selection cleared.");
  }
}

// Provider for fetching details of a single agent (e.g., for an edit screen)
final agentDetailProvider = FutureProvider.autoDispose
    .family<AgentDetailModel, String>((ref, agentId) async {
      final agentService = ref.watch(agentServiceProvider);
      logger.i("[agentDetailProvider] Fetching details for agent ID: $agentId");
      return agentService.getAgentDetails(agentId);
    });
