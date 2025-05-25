import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/agent_model.dart'; // Added for AgentDetailModel
import 'package:flutterui/data/services/agent_service.dart'; // Added for AgentService
import 'package:flutterui/providers/auth_provider.dart'; // Assuming authServiceProvider is here or similar

// Provider for AgentService
// This should ideally be in a separate file or a common providers file.
final agentServiceProvider = Provider<AgentService>((ref) {
  final authService = ref.watch(authServiceProvider); // Assuming authServiceProvider exists
  return AgentService(authService: authService);
});


// State class for the form
class CreateAgentFormState {
  final String name;
  final String description;
  final String instructions;
  final bool enableCodeInterpreter;
  final bool enableFileSearch;
  final bool isLoading;
  final String? errorMessage;
  // For simplicity, file lists (codeInterpreterFiles, fileSearchFiles) are omitted for now.
  // They can be added back if detailed file management per tool is required in the revamp.

  CreateAgentFormState({
    this.name = '',
    this.description = '',
    this.instructions = '',
    this.enableCodeInterpreter = false,
    this.enableFileSearch = false,
    this.isLoading = false,
    this.errorMessage,
  });

  CreateAgentFormState copyWith({
    String? name,
    String? description,
    String? instructions,
    bool? enableCodeInterpreter,
    bool? enableFileSearch,
    bool? isLoading,
    String? errorMessage,
    bool clearErrorMessage = false, // Utility to easily clear error
  }) {
    return CreateAgentFormState(
      name: name ?? this.name,
      description: description ?? this.description,
      instructions: instructions ?? this.instructions,
      enableCodeInterpreter: enableCodeInterpreter ?? this.enableCodeInterpreter,
      enableFileSearch: enableFileSearch ?? this.enableFileSearch,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearErrorMessage ? null : errorMessage ?? this.errorMessage,
    );
  }
}

// Notifier for the form state
class CreateAgentFormNotifier extends StateNotifier<CreateAgentFormState> {
  final Ref _ref;
  // agentId can be passed to the constructor if this becomes a family provider
  // final String? _agentId; 

  CreateAgentFormNotifier(this._ref /*, this._agentId */) : super(CreateAgentFormState());

  void setName(String name) {
    state = state.copyWith(name: name);
  }

  void setDescription(String description) {
    state = state.copyWith(description: description);
  }

  void setInstructions(String instructions) {
    state = state.copyWith(instructions: instructions);
  }

  // Combined method for text field changes
  void updateField({String? name, String? description, String? instructions}) {
    state = state.copyWith(
      name: name ?? state.name,
      description: description ?? state.description,
      instructions: instructions ?? state.instructions,
    );
  }

  void setEnableCodeInterpreter(bool enable) {
    state = state.copyWith(enableCodeInterpreter: enable);
  }

  void setEnableFileSearch(bool enable) {
    state = state.copyWith(enableFileSearch: enable);
  }

  void setLoading(bool isLoading) { // Added method to control loading state externally
    state = state.copyWith(isLoading: isLoading);
  }

  void resetState() {
    state = CreateAgentFormState(); // Resets to default values including isLoading = false
  }

  // agentId is passed from the screen to determine create vs update
  Future<bool> saveAgent({String? agentId}) async {
    state = state.copyWith(isLoading: true, clearErrorMessage: true);

    if (state.name.isEmpty) {
      state = state.copyWith(isLoading: false, errorMessage: "Agent name cannot be empty.");
      return false;
    }
    if (state.instructions.isEmpty) {
      state = state.copyWith(isLoading: false, errorMessage: "Instructions cannot be empty.");
      return false;
    }

    List<Map<String, dynamic>> tools = [];
    if (state.enableCodeInterpreter) {
      tools.add({"type": "code_interpreter"});
    }
    if (state.enableFileSearch) {
      tools.add({"type": "file_search"});
    }

    // For create, ID is usually not sent or is empty. Backend generates it.
    // For update, ID is crucial.
    // The AgentDetailModel requires an ID, so we provide a placeholder for create.
    final agentData = AgentDetailModel(
      id: agentId ?? '', // Use provided agentId for update, or empty for create
      name: state.name,
      description: state.description.isNotEmpty ? state.description : null,
      instructions: state.instructions.isNotEmpty ? state.instructions : null,
      model: "gpt-4-turbo-preview", // TODO: Make this configurable
      tools: tools,
      // toolResources and metadata can be added if needed
    );

    try {
      final agentService = _ref.read(agentServiceProvider);
      if (agentId == null || agentId.isEmpty) {
        // Create new agent
        await agentService.createAgent(agentData);
        print('Agent created: ${state.name}');
      } else {
        // Update existing agent
        await agentService.updateAgent(agentId, agentData);
        print('Agent updated: ${state.name}');
      }
      
      state = state.copyWith(isLoading: false);
      // Consider resetting form or specific fields upon successful save
      // resetState(); 
      return true;
    } catch (e) {
      print('Error saving agent: ${e.toString()}');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      return false;
    }
  }
}

// Provider definition
// If CreateAgentScreen needs to load an agent for editing using agentId,
// this should become a family provider:
// StateNotifierProvider.family<CreateAgentFormNotifier, CreateAgentFormState, String?>
final createAgentFormProvider =
    StateNotifierProvider<CreateAgentFormNotifier, CreateAgentFormState>((ref) {
  return CreateAgentFormNotifier(ref);
});
