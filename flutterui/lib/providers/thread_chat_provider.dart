import 'dart:async';
import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/data/models/thread_model.dart';
// import 'package:xml/xml.dart'; // No longer needed directly here
import 'package:flutterui/core/utils/bond_message_parser.dart'; // Import the new parser
import 'package:flutterui/data/services/auth_service.dart';
import 'package:flutterui/data/services/thread_service.dart';
import 'package:flutterui/data/services/chat_service.dart';
import 'package:flutterui/providers/auth_provider.dart'; // For authServiceProvider

// --- Service Providers ---

final threadServiceProvider = Provider<ThreadService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return ThreadService(authService: authService);
});

final chatServiceProvider = Provider<ChatService>((ref) {
  final authService = ref.watch(authServiceProvider);
  return ChatService(authService: authService);
});

// --- Thread List Provider ---

final allThreadsProvider = FutureProvider<List<Thread>>((ref) async {
  print("[allThreadsProvider] Fetching all threads...");
  final threadService = ref.watch(threadServiceProvider);
  try {
    final threads = await threadService.getThreads();
    print(
      "[allThreadsProvider] Successfully fetched ${threads.length} threads.",
    );
    return threads;
  } catch (e) {
    print("[allThreadsProvider] Error fetching all threads: ${e.toString()}");
    rethrow;
  }
});

// --- Active Chat Session State ---

// Represents the state of an active chat session
class ChatSessionState {
  final String? currentThreadId;
  final List<Message> messages;
  final bool isLoadingMessages; // For loading historical messages
  final bool isSendingMessage; // For when a new message is being sent/streamed
  final String? errorMessage;

  ChatSessionState({
    this.currentThreadId,
    this.messages = const [],
    this.isLoadingMessages = false,
    this.isSendingMessage = false,
    this.errorMessage,
  });

  ChatSessionState copyWith({
    String? currentThreadId,
    bool? clearCurrentThreadId, // To explicitly set currentThreadId to null
    List<Message>? messages,
    bool? isLoadingMessages,
    bool? isSendingMessage,
    String? errorMessage,
    bool? clearErrorMessage, // To explicitly set errorMessage to null
  }) {
    return ChatSessionState(
      currentThreadId:
          clearCurrentThreadId == true
              ? null
              : currentThreadId ?? this.currentThreadId,
      messages: messages ?? this.messages,
      isLoadingMessages: isLoadingMessages ?? this.isLoadingMessages,
      isSendingMessage: isSendingMessage ?? this.isSendingMessage,
      errorMessage:
          clearErrorMessage == true ? null : errorMessage ?? this.errorMessage,
    );
  }
}

// Notifier for managing the active chat session
class ChatSessionNotifier extends StateNotifier<ChatSessionState> {
  final ThreadService _threadService;
  final ChatService _chatService;
  StreamSubscription<String>? _chatStreamSubscription;
  StringBuffer _currentAssistantXmlBuffer =
      StringBuffer(); // Buffer for XML chunks

  ChatSessionNotifier(this._threadService, this._chatService)
    : super(ChatSessionState());

  Future<void> setCurrentThread(String threadId) async {
    print("[ChatSessionNotifier] Setting current thread to: $threadId");
    state = state.copyWith(
      currentThreadId: threadId,
      messages: [],
      isLoadingMessages: true,
      clearErrorMessage: true,
    );
    try {
      final messages = await _threadService.getMessagesForThread(threadId);
      state = state.copyWith(messages: messages, isLoadingMessages: false);
      print(
        "[ChatSessionNotifier] Loaded ${messages.length} messages for thread $threadId",
      );
    } catch (e) {
      print(
        "[ChatSessionNotifier] Error loading messages for $threadId: ${e.toString()}",
      );
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
      );
    }
  }

  Future<void> createAndSetNewThread({
    String? name,
    required String agentIdForFirstMessage,
    required String firstMessagePrompt,
  }) async {
    print(
      "[ChatSessionNotifier] Attempting to create new thread with name: $name",
    );
    state = state.copyWith(
      isLoadingMessages: true,
      isSendingMessage: true,
      clearErrorMessage: true,
      messages: [],
    ); // Show loading for new thread creation + first message
    try {
      final newThread = await _threadService.createThread(name: name);
      print("[ChatSessionNotifier] Created new thread: ${newThread.id}");
      state = state.copyWith(
        currentThreadId: newThread.id,
        isLoadingMessages: false,
      ); // Messages list is still empty

      // Send the first message to the new thread
      await sendMessage(
        agentId: agentIdForFirstMessage,
        prompt: firstMessagePrompt,
      );
      // isSendingMessage will be set to false by sendMessage
    } catch (e) {
      print("[ChatSessionNotifier] Error creating new thread: ${e.toString()}");
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
        isSendingMessage: false,
      );
    }
  }

  Future<void> startNewEmptyThread({String? name}) async {
    print("[ChatSessionNotifier] Starting new empty thread with name: $name");
    state = state.copyWith(
      isLoadingMessages: true, // Briefly true while new thread is created
      isSendingMessage: false, // Not sending a message yet
      clearErrorMessage: true,
      messages: [], // Clear messages for the new thread
    );
    try {
      final newThread = await _threadService.createThread(name: name);
      print("[ChatSessionNotifier] Created new empty thread: ${newThread.id}");
      state = state.copyWith(
        currentThreadId: newThread.id,
        messages: [], // Ensure messages are empty
        isLoadingMessages: false,
        isSendingMessage: false,
      );
    } catch (e) {
      print(
        "[ChatSessionNotifier] Error creating new empty thread: ${e.toString()}",
      );
      state = state.copyWith(
        errorMessage: e.toString(),
        isLoadingMessages: false,
        isSendingMessage: false,
        // Potentially clear currentThreadId or revert to a previous valid one if desired
      );
    }
  }

  Future<void> sendMessage({
    required String agentId,
    required String prompt,
  }) async {
    if (state.currentThreadId == null) {
      print("[ChatSessionNotifier] No current thread ID to send message.");
      state = state.copyWith(errorMessage: "No active thread selected.");
      return;
    }
    if (prompt.isEmpty) return;

    print(
      "[ChatSessionNotifier] Sending message to agent $agentId in thread ${state.currentThreadId}",
    );
    state = state.copyWith(isSendingMessage: true, clearErrorMessage: true);

    final userMessage = Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(), // Temp ID
      type: 'text',
      role: 'user',
      content: prompt,
    );
    state = state.copyWith(messages: [...state.messages, userMessage]);

    // Placeholder for assistant's response
    final assistantMessageId =
        (DateTime.now().millisecondsSinceEpoch + 1).toString();
    Message assistantMessage = Message(
      id: assistantMessageId,
      type: 'text',
      role: 'assistant',
      content: '', // Start empty, will be populated by stream
      isError: false,
    );
    int assistantMessageIndex =
        state.messages.length; // Index where it will be added
    state = state.copyWith(messages: [...state.messages, assistantMessage]);
    _currentAssistantXmlBuffer.clear(); // Clear buffer for new message

    try {
      _chatStreamSubscription?.cancel(); // Cancel previous stream if any
      _chatStreamSubscription = _chatService
          .streamChatResponse(
            threadId: state.currentThreadId!,
            agentId: agentId,
            prompt: prompt,
          )
          .listen(
            (chunk) {
              _currentAssistantXmlBuffer.write(chunk);
              String stringToDisplayForUi =
                  BondMessageParser.extractStreamingBodyContent(
                    // Corrected method name
                    _currentAssistantXmlBuffer.toString(),
                  );

              final currentMessages = List<Message>.from(state.messages);
              if (assistantMessageIndex < currentMessages.length) {
                if (currentMessages[assistantMessageIndex].content !=
                        stringToDisplayForUi ||
                    (currentMessages[assistantMessageIndex].content.isEmpty &&
                        stringToDisplayForUi == "...")) {
                  currentMessages[assistantMessageIndex] =
                      currentMessages[assistantMessageIndex].copyWith(
                        content: stringToDisplayForUi,
                      );
                  state = state.copyWith(messages: currentMessages);
                }
              }
            },
            onDone: () {
              print("[ChatSessionNotifier] Message stream done.");
              final completeXmlString = _currentAssistantXmlBuffer.toString();
              _currentAssistantXmlBuffer.clear();

              final parsedMessage =
                  BondMessageParser.parseFirstFoundBondMessage(
                    // Corrected method name
                    completeXmlString,
                  );

              String displayedContent;
              bool messageIsError;

              if (parsedMessage.parsingHadError) {
                displayedContent =
                    parsedMessage
                        .content; // Will be an error message from parser
                messageIsError = true;
                print(
                  "[ChatSessionNotifier] Parsing error from BondMessageParser: ${parsedMessage.content} for XML: $completeXmlString",
                );
              } else if (parsedMessage.role == 'assistant') {
                displayedContent = parsedMessage.content;
                messageIsError = parsedMessage.isErrorAttribute;
              } else {
                // A non-assistant message was the first valid BondMessage (e.g. system 'done' message)
                displayedContent =
                    "Error: Received non-assistant message (role: ${parsedMessage.role}). Expected assistant reply.";
                messageIsError = true;
                print(
                  "[ChatSessionNotifier] Received unexpected role '${parsedMessage.role}' instead of 'assistant' for XML: $completeXmlString",
                );
              }

              final currentMessages = List<Message>.from(state.messages);
              if (assistantMessageIndex < currentMessages.length) {
                currentMessages[assistantMessageIndex] =
                    currentMessages[assistantMessageIndex].copyWith(
                      content: displayedContent,
                      isError: messageIsError,
                    );
                state = state.copyWith(
                  messages: currentMessages,
                  isSendingMessage: false,
                );
              } else {
                // This case should ideally not be reached if indexing is correct
                state = state.copyWith(isSendingMessage: false);
              }
              _chatStreamSubscription = null;
            },
            onError: (error) {
              print(
                "[ChatSessionNotifier] Error in message stream: ${error.toString()}",
              );
              String errorDisplayContent;

              if (_currentAssistantXmlBuffer.isNotEmpty) {
                String partialXml = _currentAssistantXmlBuffer.toString();
                // Use the parser to attempt to extract and clean any streaming content
                String cleanedPartialContent =
                    BondMessageParser.extractStreamingBodyContent(
                      // Corrected method name
                      partialXml,
                    );

                if (cleanedPartialContent.isNotEmpty &&
                    cleanedPartialContent != "...") {
                  errorDisplayContent =
                      "Stream error. Partial: \"$cleanedPartialContent\"";
                } else {
                  // If parser couldn't extract meaningful content, use a more generic message
                  // and optionally include some raw data if it's substantial
                  errorDisplayContent =
                      "Stream error (Could not extract text from partial data).";
                  if (partialXml.length > 50) {
                    errorDisplayContent +=
                        "\nRaw (approx first 50 chars): ${BondMessageParser.stripAllTags(partialXml).substring(0, 50)}...";
                  } else if (partialXml.isNotEmpty) {
                    errorDisplayContent +=
                        "\nRaw: ${BondMessageParser.stripAllTags(partialXml)}";
                  }
                }
              } else {
                errorDisplayContent =
                    "Stream error: Could not get full response.";
              }
              _currentAssistantXmlBuffer
                  .clear(); // Clear buffer after processing

              final currentMessages = List<Message>.from(state.messages);
              if (assistantMessageIndex < currentMessages.length) {
                currentMessages[assistantMessageIndex] =
                    currentMessages[assistantMessageIndex].copyWith(
                      content: errorDisplayContent,
                      isError: true,
                    );
              }
              state = state.copyWith(
                messages: currentMessages,
                isSendingMessage: false,
                errorMessage:
                    error
                        .toString(), // For the general chat state error message
              );
              _chatStreamSubscription = null;
            },
          );
    } catch (e) {
      print("[ChatSessionNotifier] Error sending message: ${e.toString()}");
      state = state.copyWith(
        isSendingMessage: false,
        errorMessage: e.toString(),
      );
    }
  }

  void clearChatSession() {
    print("[ChatSessionNotifier] Clearing chat session.");
    _chatStreamSubscription?.cancel();
    _chatStreamSubscription = null;
    state = ChatSessionState(); // Reset to initial empty state
  }

  @override
  void dispose() {
    _chatStreamSubscription?.cancel();
    super.dispose();
  }
}

// Provider for ChatSessionNotifier
// .autoDispose will clear the state when the provider is no longer listened to (e.g., user navigates away)
// This is good for chat sessions that are specific to a view.
// If you need to preserve chat state across different views, remove .autoDispose
// or use .family with keepAlive: true based on a unique ID.
final chatSessionNotifierProvider =
    StateNotifierProvider.autoDispose<ChatSessionNotifier, ChatSessionState>((
      ref,
    ) {
      final threadService = ref.watch(threadServiceProvider);
      final chatService = ref.watch(chatServiceProvider);
      return ChatSessionNotifier(threadService, chatService);
    });

// If you need to pass parameters (like an initial agentId or threadId) to the ChatSessionNotifier,
// you would use a .family modifier:
// final chatSessionProviderFamily = StateNotifierProvider.autoDispose.family<ChatSessionNotifier, ChatSessionState, String /* e.g. agentId */>((ref, agentId) {
//   final threadService = ref.watch(threadServiceProvider);
//   final chatService = ref.watch(chatServiceProvider);
//   // You might initialize the notifier with agentId if needed
//   return ChatSessionNotifier(threadService, chatService /*, initialAgentId: agentId */);
// });
