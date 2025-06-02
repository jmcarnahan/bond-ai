import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import '../core/utils/logger.dart';

final agentsProvider = FutureProvider<List<AgentListItemModel>>((ref) async {
  final agentService = ref.watch(agentServiceProvider);
  try {
    final agents = await agentService.getAgents();
    logger.i("[agentsProvider] Loaded ${agents.length} agents");
    return agents;
  } catch (e) {
    logger.e("[agentsProvider] Error fetching agents: ${e.toString()}");
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
  }

  void clearAgent() {
    state = null;
  }
}

final agentDetailProvider = FutureProvider.autoDispose
    .family<AgentDetailModel, String>((ref, agentId) async {
      final agentService = ref.watch(agentServiceProvider);
      return agentService.getAgentDetails(agentId);
    });
