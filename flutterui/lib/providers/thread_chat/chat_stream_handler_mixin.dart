import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart'; // Added import
import 'package:flutterui/data/models/message_model.dart';
import 'package:flutterui/core/utils/bond_message_parser.dart';
import 'chat_session_state.dart';
import '../../core/utils/logger.dart';

// Mixin to handle chat stream logic for ChatSessionNotifier
mixin ChatStreamHandlerMixin on StateNotifier<ChatSessionState> {
  // These fields must be implemented by the class using the mixin
  abstract final StringBuffer currentAssistantXmlBuffer;
  abstract StreamSubscription<String>? chatStreamSubscription;
  // state is available from StateNotifier<ChatSessionState>

  void handleStreamData(String chunk, int assistantMessageIndex) {
    currentAssistantXmlBuffer.write(chunk);
    String stringToDisplayForUi =
        BondMessageParser.extractStreamingBodyContent(
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
    logger.i("[ChatStreamHandlerMixin] Message stream done.");
    final completeXmlString = currentAssistantXmlBuffer.toString();
    currentAssistantXmlBuffer.clear();

    final parsedMessage =
        BondMessageParser.parseFirstFoundBondMessage(completeXmlString);

    String displayedContent;
    bool messageIsError;

    if (parsedMessage.parsingHadError) {
      displayedContent = parsedMessage.content; // Error message from parser
      messageIsError = true;
      logger.i(
        "[ChatStreamHandlerMixin] Parsing error from BondMessageParser: ${parsedMessage.content} for XML: $completeXmlString",
      );
    } else if (parsedMessage.role == 'assistant') {
      displayedContent = parsedMessage.content;
      messageIsError = parsedMessage.isErrorAttribute;
    } else {
      displayedContent =
          "Error: Received non-assistant message (role: ${parsedMessage.role}). Expected assistant reply.";
      messageIsError = true;
      logger.i(
        "[ChatStreamHandlerMixin] Received unexpected role '${parsedMessage.role}' instead of 'assistant' for XML: $completeXmlString",
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
      state = state.copyWith(isSendingMessage: false);
    }
    chatStreamSubscription = null;
  }

  void handleStreamError(dynamic error, int assistantMessageIndex) {
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
