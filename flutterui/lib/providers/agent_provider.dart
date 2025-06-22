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

final defaultAgentProvider = FutureProvider<AgentListItemModel>((ref) async {
  final agentService = ref.watch(agentServiceProvider);
  try {
    final defaultAgentResponse = await agentService.getDefaultAgent();
    logger.i("[defaultAgentProvider] Fetched default agent: ${defaultAgentResponse.name}");
    // Convert AgentResponseModel to AgentListItemModel
    return AgentListItemModel(
      id: defaultAgentResponse.agentId,
      name: defaultAgentResponse.name,
      description: null,
      model: null,
      tool_types: [],
      metadata: {},
    );
  } catch (e) {
    logger.e("[defaultAgentProvider] Error fetching default agent: ${e.toString()}");
    rethrow;
  }
});
