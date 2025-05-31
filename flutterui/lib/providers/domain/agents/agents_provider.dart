import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/providers/services/service_providers.dart';
import 'package:flutterui/providers/domain/base/async_state.dart';
import 'package:flutterui/providers/domain/base/error_handler.dart';
import '../../../core/utils/logger.dart';

@immutable
class AgentsState {
  final AsyncState<List<AgentListItemModel>> agents;
  final AgentListItemModel? selectedAgent;
  final AsyncState<AgentDetailModel> selectedAgentDetails;

  const AgentsState({
    this.agents = const AsyncState(),
    this.selectedAgent,
    this.selectedAgentDetails = const AsyncState(),
  });

  AgentsState copyWith({
    AsyncState<List<AgentListItemModel>>? agents,
    AgentListItemModel? selectedAgent,
    AsyncState<AgentDetailModel>? selectedAgentDetails,
    bool clearSelectedAgent = false,
  }) {
    return AgentsState(
      agents: agents ?? this.agents,
      selectedAgent: clearSelectedAgent ? null : (selectedAgent ?? this.selectedAgent),
      selectedAgentDetails: selectedAgentDetails ?? this.selectedAgentDetails,
    );
  }

  @override
  bool operator ==(Object other) {
    if (identical(this, other)) return true;
    return other is AgentsState &&
        other.agents == agents &&
        other.selectedAgent == selectedAgent &&
        other.selectedAgentDetails == selectedAgentDetails;
  }

  @override
  int get hashCode {
    return Object.hash(agents, selectedAgent, selectedAgentDetails);
  }
}

class AgentsNotifier extends StateNotifier<AgentsState> with ErrorHandlerMixin<AgentsState> {
  final AgentService _agentService;

  AgentsNotifier(this._agentService) : super(const AgentsState()) {
    loadAgents();
  }

  @override
  void handleAppError(AppError error) {
    state = state.copyWith(
      agents: state.agents.toError(error.message),
    );
  }

  Future<void> loadAgents() async {
    logger.i("[AgentsNotifier] Loading agents...");
    state = state.copyWith(agents: state.agents.toLoading());

    try {
      logger.i("[AgentsNotifier] Calling agent service getAgents()...");
      final agents = await _agentService.getAgents();
      logger.i("[AgentsNotifier] Agent service returned ${agents.length} agents");
      state = state.copyWith(agents: state.agents.toSuccess(agents));
      logger.i("[AgentsNotifier] Successfully loaded ${agents.length} agents");
    } catch (error, stackTrace) {
      logger.e("[AgentsNotifier] Error loading agents: $error");
      logger.e("[AgentsNotifier] Stack trace: $stackTrace");
      handleError(error, stackTrace);
    }
  }

  Future<void> refreshAgents() async {
    return loadAgents();
  }

  void selectAgent(AgentListItemModel agent) {
    logger.i("[AgentsNotifier] Selecting agent: ${agent.name} (ID: ${agent.id})");
    state = state.copyWith(selectedAgent: agent);
    loadAgentDetails(agent.id);
  }

  void clearSelectedAgent() {
    logger.i("[AgentsNotifier] Clearing agent selection");
    state = state.copyWith(
      clearSelectedAgent: true,
      selectedAgentDetails: const AsyncState(),
    );
  }

  Future<void> loadAgentDetails(String agentId) async {
    logger.i("[AgentsNotifier] Loading details for agent: $agentId");
    state = state.copyWith(
      selectedAgentDetails: state.selectedAgentDetails.toLoading(),
    );

    try {
      final agentDetails = await _agentService.getAgentDetails(agentId);
      state = state.copyWith(
        selectedAgentDetails: state.selectedAgentDetails.toSuccess(agentDetails),
      );
      logger.i("[AgentsNotifier] Successfully loaded details for agent: $agentId");
    } catch (error, _) {
      state = state.copyWith(
        selectedAgentDetails: state.selectedAgentDetails.toError(error.toString()),
      );
      logger.e("[AgentsNotifier] Error loading agent details: $error");
    }
  }

  Future<void> deleteAgent(String agentId) async {
    logger.i("[AgentsNotifier] Deleting agent: $agentId");
    
    try {
      await _agentService.deleteAgent(agentId);
      
      // Remove from local state
      final currentAgents = state.agents.data ?? [];
      final updatedAgents = currentAgents.where((agent) => agent.id != agentId).toList();
      
      state = state.copyWith(
        agents: state.agents.toSuccess(updatedAgents),
      );

      // Clear selection if the deleted agent was selected
      if (state.selectedAgent?.id == agentId) {
        clearSelectedAgent();
      }

      logger.i("[AgentsNotifier] Successfully deleted agent: $agentId");
    } catch (error, _) {
      logger.e("[AgentsNotifier] Error deleting agent: $error");
      rethrow;
    }
  }
}

final agentsProvider = StateNotifierProvider<AgentsNotifier, AgentsState>((ref) {
  final agentService = ref.watch(agentServiceProvider);
  return AgentsNotifier(agentService);
});

final selectedAgentProvider = Provider<AgentListItemModel?>((ref) {
  return ref.watch(agentsProvider.select((state) => state.selectedAgent));
});

final agentDetailsProvider = Provider<AsyncState<AgentDetailModel>>((ref) {
  return ref.watch(agentsProvider.select((state) => state.selectedAgentDetails));
});

final agentsListProvider = Provider<AsyncState<List<AgentListItemModel>>>((ref) {
  return ref.watch(agentsProvider.select((state) => state.agents));
});