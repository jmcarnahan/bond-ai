import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

// Using centralized service provider from service_providers.dart

// FutureProvider to fetch the list of agents.
// This will automatically handle loading/error states for us in the UI.
final agentsProvider = FutureProvider<List<AgentListItemModel>>((ref) async {
  // Changed Agent to AgentListItemModel
  logger.i("[agentsProvider] Fetching agents...");
  final agentService = ref.watch(agentServiceProvider);
  try {
    logger.i("[agentsProvider] Started ref watch...");
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
