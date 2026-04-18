import 'package:xml/xml.dart';
import '../models/parsed_bond_message.dart';

class BondMessageParser {
  // Pre-compiled regex patterns for streaming performance
  static final _assistantMessageRegex = RegExp(
    r'<_bondmessage[^>]*role="assistant"[^>]*>(.*?)(?:</_bondmessage>|$)',
    dotAll: true,
  );
  static final _bondMessageStartTagRegex = RegExp(r'<_bondmessage[^>]*>');
  static final _bondMessageEndTagRegex = RegExp(r'</_bondmessage>');
  static final _htmlTagRegex = RegExp(r'<[^>]*>');

  /// Unescape XML entities back to their literal characters.
  /// Order matters: `&amp;` must be unescaped last so that sequences like
  /// `&amp;lt;` correctly become `&lt;` (not `<`).
  static String unescapeXmlEntities(String text) {
    return text
        .replaceAll('&lt;', '<')
        .replaceAll('&gt;', '>')
        .replaceAll('&quot;', '"')
        .replaceAll('&apos;', "'")
        .replaceAll('&amp;', '&');
  }

  static String extractStreamingBodyContent(String accumulatedXml) {
    String stringToDisplayForUi = "...";

    final assistantMatch = _assistantMessageRegex.firstMatch(accumulatedXml);

    if (assistantMatch != null) {
      String rawBodyContent = assistantMatch.group(1) ?? '';
      String strippedContent = rawBodyContent.replaceAll(_htmlTagRegex, '').trim();

      if (strippedContent.isNotEmpty) {
        stringToDisplayForUi = unescapeXmlEntities(strippedContent);
      }
    } else {
      final bondMessageStartTagMatch = _bondMessageStartTagRegex.firstMatch(accumulatedXml);

      if (bondMessageStartTagMatch != null) {
        final tagContent = bondMessageStartTagMatch.group(0) ?? '';
        if (tagContent.contains('role="system"')) {
          return stringToDisplayForUi;
        }

        int bodyStartIndex = bondMessageStartTagMatch.end;
        if (bodyStartIndex <= accumulatedXml.length) {
          String contentAfterStartTag = accumulatedXml.substring(bodyStartIndex);

          final bondMessageEndTagMatch = _bondMessageEndTagRegex.firstMatch(contentAfterStartTag);

          String rawBodyContent;
          if (bondMessageEndTagMatch != null) {
            rawBodyContent = contentAfterStartTag.substring(0, bondMessageEndTagMatch.start);
          } else {
            rawBodyContent = contentAfterStartTag;
          }

          String strippedContent = rawBodyContent.replaceAll(_htmlTagRegex, '').trim();

          if (strippedContent.isNotEmpty) {
            stringToDisplayForUi = unescapeXmlEntities(strippedContent);
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
          if (content.startsWith('data:image/')) {
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
    return rawContent.replaceAll(_htmlTagRegex, '').trim();
  }
}
