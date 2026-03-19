import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/core/utils/bond_message_parser.dart';
import 'chat_session_state.dart';
import '../../core/utils/logger.dart';

mixin ChatStreamHandlerMixin on StateNotifier<ChatSessionState> {
  abstract final StringBuffer currentAssistantXmlBuffer;
  abstract StreamSubscription<String>? chatStreamSubscription;
  Timer? streamIdleTimer;
  static const streamIdleTimeout = Duration(seconds: 120);

  void resetStreamIdleTimer(int assistantMessageIndex) {
    streamIdleTimer?.cancel();
    streamIdleTimer = Timer(streamIdleTimeout, () {
      logger.w("[ChatStreamHandler] Stream idle timeout after ${streamIdleTimeout.inSeconds}s");
      chatStreamSubscription?.cancel();
      handleStreamError("Connection timed out — no data received for ${streamIdleTimeout.inSeconds} seconds.", assistantMessageIndex);
    });
  }

  void cancelStreamIdleTimer() {
    streamIdleTimer?.cancel();
    streamIdleTimer = null;
  }

  void handleStreamData(String chunk, int assistantMessageIndex) {
    // Reset idle timer on ANY data, including keepalives — they prove the
    // connection is alive even when no content is flowing (e.g. tool calls).
    resetStreamIdleTimer(assistantMessageIndex);

    // Skip keepalive comments — they prevent infra timeouts but carry no content
    if (chunk.trim() == '<!-- keepalive -->') return;

    currentAssistantXmlBuffer.write(chunk);
    String stringToDisplayForUi = BondMessageParser.extractStreamingBodyContent(
      currentAssistantXmlBuffer.toString(),
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
  }

  void handleStreamDone(int assistantMessageIndex) {
    if (chatStreamSubscription == null) return; // guard against double-processing
    cancelStreamIdleTimer();
    final completeXmlString = currentAssistantXmlBuffer.toString();
    logger.i(
      "[ChatStreamHandler] Stream done. Total XML length: ${completeXmlString.length} chars",
    );
    currentAssistantXmlBuffer.clear();

    final allMessages = BondMessageParser.parseAllBondMessages(
      completeXmlString,
    );
    logger.i(
      "[ChatStreamHandler] Parsed ${allMessages.length} messages from XML",
    );

    // Extract thread_id from the most recent message if we don't have one
    if (state.currentThreadId == null && allMessages.isNotEmpty) {
      final lastMessage = allMessages.last;
      if (lastMessage.threadId.isNotEmpty) {
        logger.i(
          "[ChatStreamHandler] Extracted thread_id from most recent response: ${lastMessage.threadId}",
        );
        state = state.copyWith(currentThreadId: lastMessage.threadId);

        // Note: We can't directly access providers here since this is a mixin
        // The threads will be refreshed when navigating to the threads screen
      }
    }

    final assistantMessages =
        allMessages
            .where((msg) => msg.role == 'assistant' && !msg.parsingHadError)
            .toList();
    logger.i(
      "[ChatStreamHandler] Found ${assistantMessages.length} assistant messages",
    );

    // Log thread_id and agent_id for all parsed messages
    for (final msg in allMessages) {
      logger.d(
        "[ChatStreamHandler] Parsed message - ID: ${msg.id}, Thread: ${msg.threadId}, Agent: ${msg.agentId ?? 'none'}, Type: ${msg.type}, Role: ${msg.role}",
      );
    }

    final currentMessages = List<Message>.from(state.messages);

    if (assistantMessages.isEmpty) {
      final systemErrors =
          allMessages
              .where(
                (msg) =>
                    msg.role == 'system' &&
                    (msg.isErrorAttribute ||
                        msg.content.toLowerCase().contains('error')),
              )
              .toList();

      if (systemErrors.isNotEmpty &&
          assistantMessageIndex < currentMessages.length) {
        currentMessages[assistantMessageIndex] =
            currentMessages[assistantMessageIndex].copyWith(
              content: systemErrors.first.content,
              isError: true,
            );
      } else if (assistantMessageIndex < currentMessages.length) {
        // Fallback: XML parse failed or stream was truncated.
        // Try to recover readable content via the streaming regex extractor.
        final recovered = BondMessageParser.extractStreamingBodyContent(completeXmlString);
        if (recovered.isNotEmpty && recovered != "...") {
          logger.w(
            "[ChatStreamHandler] Recovered content from unparseable stream (${recovered.length} chars)",
          );
          currentMessages[assistantMessageIndex] =
              currentMessages[assistantMessageIndex].copyWith(
                content: recovered,
              );
        } else {
          logger.w(
            "[ChatStreamHandler] No content recovered from stream, showing error",
          );
          currentMessages[assistantMessageIndex] =
              currentMessages[assistantMessageIndex].copyWith(
                content: "No response received. Please try again.",
                isError: true,
              );
        }
      }
    } else {
      for (int i = 0; i < assistantMessages.length; i++) {
        final parsedMessage = assistantMessages[i];

        if (i == 0 && assistantMessageIndex < currentMessages.length) {
          currentMessages[assistantMessageIndex] =
              currentMessages[assistantMessageIndex].copyWith(
                id: parsedMessage.id,  // Update to real backend message ID
                type: parsedMessage.type,
                content: parsedMessage.content,
                imageData: parsedMessage.imageData,
                agentId: parsedMessage.agentId,
                isError: parsedMessage.isErrorAttribute,
              );
          logger.d(
            "[ChatStreamHandler] Updated message - ID: ${currentMessages[assistantMessageIndex].id}, Agent: ${currentMessages[assistantMessageIndex].agentId ?? 'none'}, Type: ${currentMessages[assistantMessageIndex].type}",
          );
        } else {
          final newMessage = Message(
            id: parsedMessage.id.isNotEmpty
                ? parsedMessage.id
                : (DateTime.now().millisecondsSinceEpoch + i).toString(),
            type: parsedMessage.type,
            role: 'assistant',
            content: parsedMessage.content,
            imageData: parsedMessage.imageData,
            agentId: parsedMessage.agentId,
            isError: parsedMessage.isErrorAttribute,
          );
          currentMessages.add(newMessage);
          logger.d(
            "[ChatStreamHandler] Created new message - ID: ${newMessage.id}, Agent: ${newMessage.agentId ?? 'none'}, Type: ${newMessage.type}",
          );
        }
      }
    }

    state = state.copyWith(messages: currentMessages, isSendingMessage: false);
    chatStreamSubscription = null;
  }

  void handleStreamError(dynamic error, int assistantMessageIndex) {
    if (chatStreamSubscription == null) return; // guard against double-processing
    cancelStreamIdleTimer();
    logger.i(
      "[ChatStreamHandlerMixin] Error in message stream: ${error.toString()}",
    );
    String errorDisplayContent;

    if (currentAssistantXmlBuffer.isNotEmpty) {
      String partialXml = currentAssistantXmlBuffer.toString();
      String cleanedPartialContent =
          BondMessageParser.extractStreamingBodyContent(partialXml);

      if (cleanedPartialContent.isNotEmpty && cleanedPartialContent != "...") {
        errorDisplayContent =
            "Stream error. Partial: \"$cleanedPartialContent\"";
      } else {
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
      errorDisplayContent = "Stream error: Could not get full response.";
    }
    currentAssistantXmlBuffer.clear();

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
      errorMessage: error.toString(),
    );
    chatStreamSubscription = null;
  }
}
