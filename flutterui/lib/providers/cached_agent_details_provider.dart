import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/providers/services/service_providers.dart';

// Cache for agent details with write-through behavior
final cachedAgentDetailsProvider = StateNotifierProvider<CachedAgentDetailsNotifier, Map<String, AgentDetailModel>>((ref) {
  return CachedAgentDetailsNotifier(ref);
});

// Provider to get cached agent details by ID
final getCachedAgentDetailsProvider = FutureProvider.family<AgentDetailModel?, String>((ref, agentId) async {
  final cache = ref.read(cachedAgentDetailsProvider.notifier);
  return await cache.getAgentDetails(agentId);
});

class CachedAgentDetailsNotifier extends StateNotifier<Map<String, AgentDetailModel>> {
  final Ref ref;

  CachedAgentDetailsNotifier(this.ref) : super({});

  Future<AgentDetailModel?> getAgentDetails(String agentId) async {
    // Check cache first
    if (state.containsKey(agentId)) {
      return state[agentId];
    }

    // Fetch from API if not in cache (write-through behavior)
    try {
      final agentService = ref.read(agentServiceProvider);
      final agentDetail = await agentService.getAgentDetails(agentId);
      
      // Update cache
      state = {...state, agentId: agentDetail};
      
      return agentDetail;
    } catch (e) {
      // Return null if error fetching agent details
      return null;
    }
  }

  void clearCache() {
    state = {};
  }

  void removeFromCache(String agentId) {
    state = Map.from(state)..remove(agentId);
  }
}