import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

final agentsProvider = FutureProvider<List<AgentListItemModel>>((ref) async {
  logger.i("[agentsProvider] Fetching agents...");
  final agentService = ref.watch(agentServiceProvider);
  try {
    logger.i("[agentsProvider] Started ref watch...");
    final agents = await agentService.getAgents();
    logger.i("[agentsProvider] Successfully fetched ${agents.length} agents.");

    return agents;
  } catch (e) {
    logger.i("[agentsProvider] Error fetching agents: ${e.toString()}");
    rethrow;
  }
});

final selectedAgentProvider =
    StateNotifierProvider<SelectedAgentNotifier, AgentListItemModel?>((ref) {
      return SelectedAgentNotifier();
    });

class SelectedAgentNotifier extends StateNotifier<AgentListItemModel?> {
  SelectedAgentNotifier() : super(null);

  void selectAgent(AgentListItemModel agent) {
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

final agentDetailProvider = FutureProvider.autoDispose
    .family<AgentDetailModel, String>((ref, agentId) async {
      final agentService = ref.watch(agentServiceProvider);
      logger.i("[agentDetailProvider] Fetching details for agent ID: $agentId");
      return agentService.getAgentDetails(agentId);
    });
