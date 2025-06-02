import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/models/user_model.dart';

/// Centralized test data builders for creating consistent test data across test files.
/// These builders provide sensible defaults while allowing customization for specific test scenarios.
class TestDataBuilders {
  // =============================================================================
  // USER DATA BUILDERS
  // =============================================================================

  /// Creates a test User with default or custom values
  static User buildUser({
    String? email,
    String? name,
  }) {
    return User(
      email: email ?? 'test@example.com',
      name: name ?? 'Test User',
    );
  }

  /// Creates an authenticated test user for login scenarios
  static User buildAuthenticatedUser() {
    return buildUser(
      email: 'authenticated@example.com',
      name: 'Authenticated User',
    );
  }

  /// Creates a test user with special characters for edge case testing
  static User buildUserWithSpecialChars() {
    return buildUser(
      email: 'spëcial@émojis.com',
      name: 'User with émojis 🚀',
    );
  }

  // =============================================================================
  // THREAD DATA BUILDERS
  // =============================================================================

  /// Creates a test Thread with default or custom values
  static Thread buildThread({
    String? id,
    String? name,
  }) {
    return Thread(
      id: id ?? 'thread-123',
      name: name ?? 'Test Thread',
    );
  }

  /// Creates a list of test threads for list testing scenarios
  static List<Thread> buildThreadList({int count = 3}) {
    return List.generate(count, (index) => buildThread(
      id: 'thread-$index',
      name: 'Thread ${index + 1}',
    ));
  }

  /// Creates a thread with a very long name for UI testing
  static Thread buildThreadWithLongName() {
    return buildThread(
      name: 'This is a very long thread name that should test the UI handling of lengthy titles and see how the interface responds to overflow scenarios',
    );
  }

  /// Creates a thread with special characters for edge case testing
  static Thread buildThreadWithSpecialChars() {
    return buildThread(
      name: 'Thread with émojis 🧵 and spëcial chars @#\$%',
    );
  }

  /// Creates a thread with empty name for edge case testing
  static Thread buildThreadWithEmptyName() {
    return buildThread(name: '');
  }

  // =============================================================================
  // MESSAGE DATA BUILDERS
  // =============================================================================

  /// Creates a test Message with default or custom values
  static Message buildMessage({
    String? id,
    String? type,
    String? role,
    String? content,
    String? imageData,
    bool? isError,
  }) {
    return Message(
      id: id ?? 'message-123',
      type: type ?? 'text',
      role: role ?? 'user',
      content: content ?? 'Test message content',
      imageData: imageData,
      isError: isError ?? false,
    );
  }

  /// Creates a user message for chat testing
  static Message buildUserMessage({
    String? content,
  }) {
    return buildMessage(
      role: 'user',
      content: content ?? 'Hello, this is a test user message',
    );
  }

  /// Creates an assistant message for chat testing
  static Message buildAssistantMessage({
    String? content,
  }) {
    return buildMessage(
      role: 'assistant',
      content: content ?? 'Hello! This is a test assistant response',
    );
  }

  /// Creates a system message for chat testing
  static Message buildSystemMessage({
    String? content,
  }) {
    return buildMessage(
      role: 'system',
      content: content ?? 'System message for testing',
    );
  }

  /// Creates a list of messages for conversation testing
  static List<Message> buildMessageList({
    int count = 5,
  }) {
    final messages = <Message>[];
    for (int i = 0; i < count; i++) {
      final isUserMessage = i % 2 == 0;
      messages.add(buildMessage(
        id: 'message-$i',
        role: isUserMessage ? 'user' : 'assistant',
        content: isUserMessage 
          ? 'User message ${i + 1}' 
          : 'Assistant response ${i + 1}',
      ));
    }
    return messages;
  }

  /// Creates a message with very long content for UI testing
  static Message buildMessageWithLongContent() {
    return buildMessage(
      content: 'This is a very long message content that should test how the UI handles lengthy text and ensures proper wrapping, scrolling, and display of extended content in the chat interface. ' * 10,
    );
  }

  /// Creates a message with special characters and emojis
  static Message buildMessageWithSpecialChars() {
    return buildMessage(
      content: 'Message with émojis 🚀🔥💯 and spëcial chars @#\$%^&*()',
    );
  }

  // =============================================================================
  // AGENT DATA BUILDERS
  // =============================================================================

  /// Creates a test AgentListItemModel with default or custom values
  static AgentListItemModel buildAgentListItem({
    String? id,
    String? name,
    String? description,
    String? model,
    List<String>? toolTypes,
  }) {
    return AgentListItemModel(
      id: id ?? 'agent-123',
      name: name ?? 'Test Agent',
      description: description ?? 'Test agent description',
      model: model ?? 'gpt-4',
      // ignore: non_constant_identifier_names
      tool_types: toolTypes,
    );
  }

  /// Creates a test AgentDetailModel with default or custom values
  static AgentDetailModel buildAgentDetail({
    String? id,
    String? name,
    String? description,
    String? instructions,
    String? model,
    List<Map<String, dynamic>>? tools,
    AgentToolResourcesModel? toolResources,
    Map<String, dynamic>? metadata,
    List<dynamic>? files,
  }) {
    return AgentDetailModel(
      id: id ?? 'agent-123',
      name: name ?? 'Test Agent',
      description: description ?? 'Test agent description',
      instructions: instructions ?? 'Test agent instructions',
      model: model ?? 'gpt-4',
      tools: tools ?? [],
      toolResources: toolResources,
      metadata: metadata,
      files: files ?? [],
    );
  }

  /// Creates a list of test agents for list testing scenarios
  static List<AgentListItemModel> buildAgentList({int count = 3}) {
    return List.generate(count, (index) => buildAgentListItem(
      id: 'agent-$index',
      name: 'Agent ${index + 1}',
      description: 'Description for agent ${index + 1}',
    ));
  }

  /// Creates an agent with code interpreter tool
  static AgentDetailModel buildAgentWithCodeInterpreter() {
    return buildAgentDetail(
      name: 'Code Assistant',
      description: 'Agent with code interpreter capabilities',
      instructions: 'You are a helpful coding assistant',
      tools: [
        {'type': 'code_interpreter'}
      ],
      toolResources: AgentToolResourcesModel(
        codeInterpreter: ToolResourceFilesListModel(
          fileIds: ['file-1', 'file-2'],
        ),
      ),
    );
  }

  /// Creates an agent with file search tool
  static AgentDetailModel buildAgentWithFileSearch() {
    return buildAgentDetail(
      name: 'Research Assistant',
      description: 'Agent with file search capabilities',
      instructions: 'You are a helpful research assistant',
      tools: [
        {'type': 'file_search'}
      ],
      toolResources: AgentToolResourcesModel(
        fileSearch: ToolResourceFilesListModel(
          fileIds: ['search-file-1'],
        ),
      ),
    );
  }

  /// Creates an agent with both tools
  static AgentDetailModel buildAgentWithAllTools() {
    return buildAgentDetail(
      name: 'Full-Featured Assistant',
      description: 'Agent with all available tools',
      instructions: 'You are a comprehensive assistant',
      tools: [
        {'type': 'code_interpreter'},
        {'type': 'file_search'},
      ],
      toolResources: AgentToolResourcesModel(
        codeInterpreter: ToolResourceFilesListModel(
          fileIds: ['code-file-1', 'code-file-2'],
        ),
        fileSearch: ToolResourceFilesListModel(
          fileIds: ['search-file-1'],
        ),
      ),
    );
  }

  /// Creates an agent with special characters for edge case testing
  static AgentDetailModel buildAgentWithSpecialChars() {
    return buildAgentDetail(
      name: 'Agent with émojis 🤖',
      description: 'Description with spëcial chars @#\$%',
      instructions: 'Instructions with émojis 🚀 and special characters',
    );
  }

  /// Creates an agent with minimal properties
  static AgentDetailModel buildMinimalAgent() {
    return buildAgentDetail(
      name: 'Minimal Agent',
      description: null,
      instructions: 'Basic instructions',
      tools: [],
    );
  }

  // =============================================================================
  // API RESPONSE DATA BUILDERS
  // =============================================================================

  /// Creates a test AgentResponseModel
  static AgentResponseModel buildAgentResponse({
    String? agentId,
    String? name,
  }) {
    return AgentResponseModel(
      agentId: agentId ?? 'agent-123',
      name: name ?? 'Test Agent',
    );
  }

  /// Creates a test FileUploadResponseModel
  static FileUploadResponseModel buildFileUploadResponse({
    String? providerFileId,
    String? fileName,
    String? message,
  }) {
    return FileUploadResponseModel(
      providerFileId: providerFileId ?? 'file-123',
      fileName: fileName ?? 'test-file.txt',
      message: message ?? 'File uploaded successfully',
    );
  }

  // =============================================================================
  // BULK DATA BUILDERS FOR PERFORMANCE TESTING
  // =============================================================================

  /// Creates a large list of threads for performance testing
  static List<Thread> buildLargeThreadList({int count = 100}) {
    return buildThreadList(count: count);
  }

  /// Creates a large list of messages for performance testing
  static List<Message> buildLargeMessageList({int count = 500}) {
    return buildMessageList(count: count);
  }

  /// Creates a large list of agents for performance testing
  static List<AgentListItemModel> buildLargeAgentList({int count = 50}) {
    return buildAgentList(count: count);
  }

  // =============================================================================
  // EDGE CASE DATA BUILDERS
  // =============================================================================

  /// Creates entities with empty strings for edge case testing
  static Map<String, dynamic> buildEmptyStringEntities() {
    return {
      'user': buildUser(email: '', name: ''),
      'thread': buildThread(id: '', name: ''),
      'message': buildMessage(content: ''),
      'agent': buildAgentListItem(name: '', description: ''),
    };
  }

  /// Creates entities with null values where allowed
  static Map<String, dynamic> buildNullValueEntities() {
    return {
      'thread': buildThread(name: null),
      'agentDetail': buildAgentDetail(
        description: null,
        instructions: null,
        metadata: null,
      ),
    };
  }

  /// Creates entities with maximum length values for boundary testing
  static Map<String, dynamic> buildMaxLengthEntities() {
    final longString = 'A' * 1000; // Very long string
    return {
      'user': buildUser(name: longString),
      'thread': buildThread(name: longString),
      'message': buildMessage(content: longString),
      'agent': buildAgentListItem(name: longString, description: longString),
    };
  }
}