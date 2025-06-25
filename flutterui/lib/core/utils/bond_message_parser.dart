import 'package:xml/xml.dart';

class ParsedBondMessage {
  final String id;
  final String threadId;
  final String? agentId;
  final String type;
  final String role;
  final String content;
  final String? imageData;
  final bool isErrorAttribute;
  final bool parsingHadError;

  ParsedBondMessage({
    this.id = '',
    this.threadId = '',
    this.agentId,
    this.type = '',
    this.role = '',
    required this.content,
    this.imageData,
    this.isErrorAttribute = false,
    this.parsingHadError = false,
  });
}

class BondMessageParser {

  static String extractStreamingBodyContent(String accumulatedXml) {
    String stringToDisplayForUi = "...";

    final assistantMessageRegex = RegExp(r'<_bondmessage[^>]*role="assistant"[^>]*>(.*?)(?:</_bondmessage>|$)', dotAll: true);
    final assistantMatch = assistantMessageRegex.firstMatch(accumulatedXml);
    
    if (assistantMatch != null) {
      String rawBodyContent = assistantMatch.group(1) ?? '';
      String strippedContent = rawBodyContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();
      
      if (strippedContent.isNotEmpty) {
        stringToDisplayForUi = strippedContent;
      }
    } else {
      final bondMessageStartTagRegex = RegExp(r'<_bondmessage[^>]*>');
      final bondMessageStartTagMatch = bondMessageStartTagRegex.firstMatch(accumulatedXml);

      if (bondMessageStartTagMatch != null) {
        final tagContent = bondMessageStartTagMatch.group(0) ?? '';
        if (tagContent.contains('role="system"')) {
          return stringToDisplayForUi;
        }
        
        int bodyStartIndex = bondMessageStartTagMatch.end;
        if (bodyStartIndex <= accumulatedXml.length) {
          String contentAfterStartTag = accumulatedXml.substring(bodyStartIndex);

          final bondMessageEndTagRegex = RegExp(r'</_bondmessage>');
          final bondMessageEndTagMatch = bondMessageEndTagRegex.firstMatch(contentAfterStartTag);

          String rawBodyContent;
          if (bondMessageEndTagMatch != null) {
            rawBodyContent = contentAfterStartTag.substring(0, bondMessageEndTagMatch.start);
          } else {
            rawBodyContent = contentAfterStartTag;
          }

          String strippedContent = rawBodyContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();

          if (strippedContent.isNotEmpty) {
            stringToDisplayForUi = strippedContent;
          }
        }
      }
    }
    
    return stringToDisplayForUi;
  }

  static List<ParsedBondMessage> parseAllBondMessages(String xmlString) {
    final List<ParsedBondMessage> messages = [];
    
    if (xmlString.trim().isEmpty) {
      return messages;
    }
    
    try {
      final wrappedXml = "<stream_wrapper>${xmlString.trim()}</stream_wrapper>";
      final XmlDocument doc = XmlDocument.parse(wrappedXml);

      final bondMessageElements = doc.rootElement.findElements('_bondmessage');

      for (final element in bondMessageElements) {
        String content = element.innerText.trim();
        String? imageData;
        
        final messageType = element.getAttribute('type') ?? '';
        if (messageType == 'image_file' || messageType == 'image') {
          if (content.startsWith('data:image/png;base64,')) {
            imageData = content.substring('data:image/png;base64,'.length);
            content = '[Image]';
          } else if (content.startsWith('data:image/jpeg;base64,')) {
            imageData = content.substring('data:image/jpeg;base64,'.length);
            content = '[Image]';
          } else if (content.startsWith('data:image/')) {
            final commaIndex = content.indexOf(',');
            if (commaIndex != -1 && commaIndex < content.length - 1) {
              imageData = content.substring(commaIndex + 1);
              content = '[Image]';
            }
          }
        }
        
        messages.add(ParsedBondMessage(
          id: element.getAttribute('id') ?? '',
          threadId: element.getAttribute('thread_id') ?? '',
          agentId: element.getAttribute('agent_id'),
          type: messageType,
          role: element.getAttribute('role') ?? '',
          content: content,
          imageData: imageData,
          isErrorAttribute: element.getAttribute('is_error')?.toLowerCase() == 'true',
          parsingHadError: false,
        ));
      }
      
    } catch (e) {
      messages.add(ParsedBondMessage(
        content: "Error parsing XML: ${e.toString()}",
        parsingHadError: true,
        isErrorAttribute: true,
      ));
    }
    
    return messages;
  }

  static String stripAllTags(String rawContent) {
    return rawContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();
  }
}
