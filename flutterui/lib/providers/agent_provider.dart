import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/providers/auth_provider.dart'; // For authServiceProvider

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
  print("[agentsProvider] Fetching agents...");
  final agentService = ref.watch(agentServiceProvider);
  try {
    final agents = await agentService.getAgents();
    print("[agentsProvider] Successfully fetched ${agents.length} agents.");
    return agents;
  } catch (e) {
    print("[agentsProvider] Error fetching agents: ${e.toString()}");
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
    print(
      "[SelectedAgentNotifier] Agent selected: ${agent.name} (ID: ${agent.id})",
    );
  }

  void clearAgent() {
    state = null;
    print("[SelectedAgentNotifier] Agent selection cleared.");
  }
}

// Provider for fetching details of a single agent (e.g., for an edit screen)
final agentDetailProvider = FutureProvider.autoDispose
    .family<AgentDetailModel, String>((ref, agentId) async {
      final agentService = ref.watch(agentServiceProvider);
      print("[agentDetailProvider] Fetching details for agent ID: $agentId");
      return agentService.getAgentDetails(agentId);
    });

// TODO: Consider a StateNotifierProvider for the Create/Edit Agent screen state
// This would manage text controllers, selected tools, file lists, loading states for file uploads/deletes, etc.
// For example:
// final createAgentFormNotifierProvider = StateNotifierProvider.autoDispose<CreateAgentFormNotifier, CreateAgentFormState>((ref) {
//   return CreateAgentFormNotifier(ref.read(agentServiceProvider));
// });
// class CreateAgentFormState { ... }
// class CreateAgentFormNotifier extends StateNotifier<CreateAgentFormState> { ... }
