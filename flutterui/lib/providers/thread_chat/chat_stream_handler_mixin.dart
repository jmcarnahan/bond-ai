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

    // Parse all messages from the stream
    final allMessages = BondMessageParser.parseAllBondMessages(completeXmlString);
    
    // Filter for assistant messages (ignore system messages per Python example)
    final assistantMessages = allMessages.where((msg) => 
      msg.role == 'assistant' && !msg.parsingHadError
    ).toList();

    final currentMessages = List<Message>.from(state.messages);
    
    if (assistantMessages.isEmpty) {
      // No assistant messages found, check if there were system error messages
      final systemErrors = allMessages.where((msg) => 
        msg.role == 'system' && (msg.isErrorAttribute || msg.content.toLowerCase().contains('error'))
      ).toList();
      
      if (systemErrors.isNotEmpty && assistantMessageIndex < currentMessages.length) {
        // Show system error in the assistant message placeholder
        currentMessages[assistantMessageIndex] = currentMessages[assistantMessageIndex].copyWith(
          content: systemErrors.first.content,
          isError: true,
        );
      }
    } else {
      // Process assistant messages - replace the placeholder and add additional messages
      for (int i = 0; i < assistantMessages.length; i++) {
        final parsedMessage = assistantMessages[i];
        
        if (i == 0 && assistantMessageIndex < currentMessages.length) {
          // Replace the placeholder assistant message
          currentMessages[assistantMessageIndex] = currentMessages[assistantMessageIndex].copyWith(
            type: parsedMessage.type,
            content: parsedMessage.content,
            imageData: parsedMessage.imageData,
            isError: parsedMessage.isErrorAttribute,
          );
        } else {
          // Add additional assistant messages
          final newMessage = Message(
            id: (DateTime.now().millisecondsSinceEpoch + i).toString(),
            type: parsedMessage.type,
            role: 'assistant',
            content: parsedMessage.content,
            imageData: parsedMessage.imageData,
            isError: parsedMessage.isErrorAttribute,
          );
          currentMessages.add(newMessage);
        }
      }
    }

    state = state.copyWith(
      messages: currentMessages,
      isSendingMessage: false,
    );
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
