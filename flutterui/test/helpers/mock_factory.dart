import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:mockito/mockito.dart';

import 'package:flutterui/data/models/agent_model.dart';
import 'package:flutterui/data/models/api_response_models.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/thread_model.dart';
import 'package:flutterui/data/models/user_model.dart';
import 'package:flutterui/data/services/agent_service.dart';
import 'package:flutterui/data/services/agent_service/agent_file_service.dart';
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/providers/auth_provider.dart';
import 'package:flutterui/providers/thread_provider.dart';

/// Centralized factory for creating commonly used mock objects in tests.
/// This eliminates duplication of mock classes across test files and provides
/// consistent mock behavior throughout the test suite.
class MockFactory {
  /// Creates a mock HTTP client with configurable responses
  static MockHttpClient createHttpClient({
    Map<String, http.Response>? responses,
  }) {
    return MockHttpClient(responses ?? {});
  }

  /// Creates a mock AuthService with configurable behavior
  static MockAuthService createAuthService({
    String? storedToken,
    User? mockUser,
    bool shouldThrowError = false,
    String? errorMessage,
  }) {
    return MockAuthService()
      ..storedToken = storedToken
      ..mockUser = mockUser
      ..shouldThrowError = shouldThrowError
      ..errorMessage = errorMessage;
  }

  /// Creates a mock ThreadService with configurable behavior
  static MockThreadService createThreadService({
    List<Thread>? mockThreads,
    List<Message>? mockMessages,
    bool shouldThrowError = false,
    String? errorMessage,
  }) {
    return MockThreadService()
      ..mockThreads = mockThreads ?? []
      ..mockMessages = mockMessages ?? []
      ..shouldThrowError = shouldThrowError
      ..errorMessage = errorMessage;
  }

  /// Creates a mock ChatService with configurable behavior
  static MockChatService createChatService({
    bool shouldThrowError = false,
    String? errorMessage,
    List<String>? mockStreamChunks,
  }) {
    return MockChatService()
      ..shouldThrowError = shouldThrowError
      ..errorMessage = errorMessage
      ..mockStreamChunks = mockStreamChunks ?? [];
  }

  /// Creates a mock AgentService with configurable behavior
  static MockAgentService createAgentService({
    List<AgentListItemModel>? mockAgents,
    AgentDetailModel? mockAgentDetail,
    bool shouldThrowError = false,
    String? errorMessage,
  }) {
    return MockAgentService()
      ..mockAgents = mockAgents ?? []
      ..mockAgentDetail = mockAgentDetail
      ..shouldThrowError = shouldThrowError
      ..errorMessage = errorMessage;
  }

  /// Creates a mock WidgetRef for provider testing
  static MockWidgetRef createWidgetRef(ProviderContainer container) {
    return MockWidgetRef(container);
  }

  /// Creates a mock NavigatorObserver for navigation testing
  static MockNavigatorObserver createNavigatorObserver() {
    return MockNavigatorObserver();
  }

  /// Creates a mock AuthNotifier with configurable state
  static MockAuthNotifier createAuthNotifier({
    AuthState? initialState,
  }) {
    return MockAuthNotifier()
      .._currentState = initialState ?? const AuthInitial();
  }
}

// =============================================================================
// MOCK CLASS DEFINITIONS
// =============================================================================

/// Mock HTTP client for testing HTTP requests
// ignore: must_be_immutable
class MockHttpClient extends Mock implements http.BaseClient {
  final Map<String, http.Response> _responses;
  final List<http.BaseRequest> _requests = [];

  MockHttpClient(this._responses);

  List<http.BaseRequest> get requests => List.unmodifiable(_requests);

  void addResponse(String url, http.Response response) {
    _responses[url] = response;
  }

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    _requests.add(request);
    
    final url = request.url.toString();
    final response = _responses[url];
    
    if (response != null) {
      return http.StreamedResponse(
        Stream.value(response.bodyBytes),
        response.statusCode,
        headers: response.headers,
        reasonPhrase: response.reasonPhrase,
      );
    }
    
    // Default response if no specific response configured
    return http.StreamedResponse(
      Stream.value(utf8.encode('{"error": "Not found"}')),
      404,
      headers: {'content-type': 'application/json'},
    );
  }
}

/// Mock AuthService for authentication testing
// ignore: must_be_immutable
class MockAuthService implements AuthService {
  String? storedToken;
  User? mockUser;
  bool shouldThrowError = false;
  String? errorMessage;
  bool launchLoginUrlCalled = false;
  bool storeTokenCalled = false;
  bool clearTokenCalled = false;
  bool getCurrentUserCalled = false;
  bool retrieveTokenCalled = false;

  @override
  Future<String?> retrieveToken() async {
    retrieveTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock retrieve error');
    }
    return storedToken;
  }

  @override
  Future<User> getCurrentUser() async {
    getCurrentUserCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock user error');
    }
    if (mockUser == null) {
      throw Exception('No user found');
    }
    return mockUser!;
  }

  @override
  Future<void> storeToken(String token) async {
    storeTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock store error');
    }
    storedToken = token;
  }

  @override
  Future<void> clearToken() async {
    clearTokenCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock clear error');
    }
    storedToken = null;
  }

  @override
  Future<void> launchLoginUrl() async {
    launchLoginUrlCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock launch error');
    }
  }

  @override
  Future<Map<String, String>> get authenticatedHeaders async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock headers error');
    }
    if (storedToken == null) {
      throw Exception('Not authenticated for this request.');
    }
    return {
      'Authorization': 'Bearer $storedToken',
      'Content-Type': 'application/json',
    };
  }
}

/// Mock ThreadService for thread management testing
// ignore: must_be_immutable
class MockThreadService implements ThreadService {
  List<Thread> mockThreads = [];
  List<Message> mockMessages = [];
  bool shouldThrowError = false;
  String? errorMessage;
  bool getThreadsCalled = false;
  bool getMessagesForThreadCalled = false;
  bool createThreadCalled = false;
  bool deleteThreadCalled = false;
  String? lastThreadIdForMessages;
  String? lastCreatedThreadName;
  String? lastDeletedThreadId;

  @override
  Future<List<Thread>> getThreads() async {
    getThreadsCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get threads error');
    }
    return mockThreads;
  }

  @override
  Future<List<Message>> getMessagesForThread(String threadId, {int limit = 100}) async {
    getMessagesForThreadCalled = true;
    lastThreadIdForMessages = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get messages error');
    }
    return mockMessages;
  }

  @override
  Future<Thread> createThread({String? name}) async {
    createThreadCalled = true;
    lastCreatedThreadName = name;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock create thread error');
    }
    final newThread = Thread(
      id: 'new-thread-${mockThreads.length}',
      name: name ?? 'New Thread',
    );
    mockThreads.add(newThread);
    return newThread;
  }

  @override
  Future<void> deleteThread(String threadId) async {
    deleteThreadCalled = true;
    lastDeletedThreadId = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete thread error');
    }
    mockThreads.removeWhere((thread) => thread.id == threadId);
  }
}

/// Mock ChatService for chat functionality testing
// ignore: must_be_immutable
class MockChatService implements ChatService {
  bool shouldThrowError = false;
  String? errorMessage;
  bool streamChatResponseCalled = false;
  String? lastThreadId;
  String? lastAgentId;
  String? lastPrompt;
  List<String> mockStreamChunks = [];
  bool shouldErrorInStream = false;
  String? streamErrorMessage;
  final StreamController<String> _streamController = StreamController<String>();

  @override
  Stream<String> streamChatResponse({required String threadId, required String agentId, required String prompt}) {
    streamChatResponseCalled = true;
    lastThreadId = threadId;
    lastAgentId = agentId;
    lastPrompt = prompt;

    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock stream error');
    }

    // Simulate streaming response
    Future.delayed(const Duration(milliseconds: 10), () {
      for (final chunk in mockStreamChunks) {
        if (!_streamController.isClosed) {
          _streamController.add(chunk);
        }
      }
      
      if (shouldErrorInStream) {
        _streamController.addError(Exception(streamErrorMessage ?? 'Stream error'));
      } else {
        _streamController.close();
      }
    });

    return _streamController.stream;
  }

  void closeStream() {
    if (!_streamController.isClosed) {
      _streamController.close();
    }
  }
}

/// Mock AgentService for agent management testing
// ignore: must_be_immutable
class MockAgentService implements AgentService {
  List<AgentListItemModel> mockAgents = [];
  Map<String, AgentDetailModel> mockAgentDetails = {};
  AgentDetailModel? mockAgentDetail;
  FileUploadResponseModel? mockUploadResponse;
  bool shouldThrowError = false;
  String? errorMessage;
  bool createAgentCalled = false;
  bool updateAgentCalled = false;
  bool deleteAgentCalled = false;
  bool uploadFileCalled = false;
  bool getAgentDetailsCalled = false;
  AgentDetailModel? lastCreatedAgent;
  AgentDetailModel? lastUpdatedAgent;
  String? lastUpdatedAgentId;
  String? lastUploadedFileName;
  Uint8List? lastUploadedFileBytes;
  String? lastDeletedAgentId;
  String? lastGetDetailsAgentId;

  @override
  Future<List<AgentListItemModel>> getAgents() async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get agents error');
    }
    return mockAgents;
  }

  @override
  Future<AgentDetailModel> getAgentDetails(String agentId) async {
    getAgentDetailsCalled = true;
    lastGetDetailsAgentId = agentId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get agent details error');
    }
    if (!mockAgentDetails.containsKey(agentId)) {
      return mockAgentDetail ?? AgentDetailModel(
        id: agentId,
        name: 'Mock Agent',
        description: 'Mock Description',
        instructions: 'Mock Instructions',
        model: 'gpt-4',
        tools: const [],
        files: const [],
      );
    }
    return mockAgentDetails[agentId]!;
  }

  @override
  Future<AgentResponseModel> createAgent(AgentDetailModel agent) async {
    createAgentCalled = true;
    lastCreatedAgent = agent;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock create agent error');
    }
    final agentId = 'new-agent-${mockAgents.length}';
    mockAgents.add(AgentListItemModel(
      id: agentId,
      name: agent.name,
      description: agent.description,
      model: agent.model,
    ));
    return AgentResponseModel(agentId: agentId, name: agent.name);
  }

  @override
  Future<AgentResponseModel> updateAgent(String agentId, AgentDetailModel agent) async {
    updateAgentCalled = true;
    lastUpdatedAgentId = agentId;
    lastUpdatedAgent = agent;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock update agent error');
    }
    return AgentResponseModel(agentId: agentId, name: agent.name);
  }

  @override
  Future<void> deleteAgent(String agentId) async {
    deleteAgentCalled = true;
    lastDeletedAgentId = agentId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete agent error');
    }
    mockAgents.removeWhere((agent) => agent.id == agentId);
  }

  @override
  Future<FileUploadResponseModel> uploadFile(String fileName, Uint8List fileBytes) async {
    uploadFileCalled = true;
    lastUploadedFileName = fileName;
    lastUploadedFileBytes = fileBytes;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock upload file error');
    }
    return mockUploadResponse ?? FileUploadResponseModel(
      providerFileId: 'provider-${fileName.hashCode}',
      fileName: fileName,
      message: 'File uploaded successfully',
    );
  }

  @override
  Future<void> deleteFile(String providerFileId) async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock delete file error');
    }
  }

  @override
  Future<List<FileInfoModel>> getFiles() async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get files error');
    }
    return [];
  }

  @override
  Future<FileInfoModel> getFileInfo(String providerFileId) async {
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock get file info error');
    }
    return FileInfoModel(
      id: providerFileId,
      fileName: 'mock-file.txt',
      fileSize: 1024,
      createdAt: DateTime.now(),
    );
  }

  @override
  void dispose() {}
}

/// Mock WidgetRef for provider testing
// ignore: must_be_immutable
class MockWidgetRef extends Mock implements WidgetRef {
  final ProviderContainer container;
  
  MockWidgetRef(this.container);
  
  @override
  T read<T>(ProviderListenable<T> provider) {
    return container.read(provider);
  }
}

/// Mock NavigatorObserver for navigation testing
// ignore: must_be_immutable
class MockNavigatorObserver extends Mock implements NavigatorObserver {}

/// Mock Ref for provider testing
// ignore: must_be_immutable
class MockRef extends Mock implements Ref<Object?> {}

/// Mock AuthNotifier for authentication provider testing
class MockAuthNotifier extends AuthNotifier {
  AuthState _currentState = const AuthInitial();

  MockAuthNotifier() : super(MockFactory.createAuthService());

  void setState(AuthState state) {
    _currentState = state;
  }

  @override
  AuthState get state => _currentState;
}

/// Mock ThreadsNotifier for thread provider testing
class MockThreadsNotifier extends ThreadsNotifier {
  bool fetchThreadsCalled = false;
  bool addThreadCalled = false;
  bool removeThreadCalled = false;
  bool selectThreadCalled = false;
  String? lastSelectedThreadId;
  String? lastAddedThreadName;
  String? lastRemovedThreadId;
  bool shouldThrowError = false;
  String? errorMessage;

  MockThreadsNotifier(super.ref);

  @override
  Future<void> fetchThreads() async {
    fetchThreadsCalled = true;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock fetch threads error');
    }
  }

  @override
  Future<void> addThread({String? name}) async {
    addThreadCalled = true;
    lastAddedThreadName = name;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock add thread error');
    }
  }

  @override
  Future<void> removeThread(String threadId) async {
    removeThreadCalled = true;
    lastRemovedThreadId = threadId;
    if (shouldThrowError) {
      throw Exception(errorMessage ?? 'Mock remove thread error');
    }
  }

  @override
  void selectThread(String threadId) {
    selectThreadCalled = true;
    lastSelectedThreadId = threadId;
  }
}