import 'package:xml/xml.dart';

/// Data class to hold the result of parsing a BondMessage.
class ParsedBondMessage {
  final String id;
  final String type;
  final String role;
  final String content;
  final String? imageData; // Base64 image data for image_file types
  final bool isErrorAttribute; // From the is_error attribute in XML
  final bool parsingHadError; // True if the parser itself encountered an issue

  ParsedBondMessage({
    this.id = '',
    this.type = '',
    this.role = '',
    required this.content,
    this.imageData,
    this.isErrorAttribute = false,
    this.parsingHadError = false,
  });
}

/// Utility class for parsing BondMessage XML strings.
class BondMessageParser {
  /// Parses the *first* <_bondmessage> element found in the given xmlString.
  /// The xmlString might contain multiple sibling <_bondmessage> elements.
  static ParsedBondMessage parseFirstFoundBondMessage(String xmlString) {
    if (xmlString.trim().isEmpty) {
      return ParsedBondMessage(
        content: "Error: Empty response.",
        parsingHadError: true,
        isErrorAttribute: true, // Treat as an error if empty
      );
    }
    try {
      // Wrap to handle multiple sibling <_bondmessage> if xmlString contains them directly.
      // This ensures XmlDocument.parse has a single root.
      final wrappedXml = "<stream_wrapper>${xmlString.trim()}</stream_wrapper>";
      final XmlDocument doc = XmlDocument.parse(wrappedXml);

      // Find the first <_bondmessage> element.
      final XmlElement? firstBondMessageElement =
          doc.rootElement.findElements('_bondmessage').firstOrNull;

      if (firstBondMessageElement != null) {
        String content = firstBondMessageElement.text.trim(); // Trim whitespace
        String? imageData;
        
        // Check if this is an image_file type with base64 data
        final messageType = firstBondMessageElement.getAttribute('type') ?? '';
        if (messageType == 'image_file') {
          if (content.startsWith('data:image/png;base64,')) {
            // Extract base64 data after the prefix
            imageData = content.substring('data:image/png;base64,'.length);
            content = '[Image]';
          } else if (content.startsWith('data:image/jpeg;base64,')) {
            // Handle JPEG images
            imageData = content.substring('data:image/jpeg;base64,'.length);
            content = '[Image]';
          } else if (content.startsWith('data:image/')) {
            // Handle other image formats - extract the base64 part after the comma
            final commaIndex = content.indexOf(',');
            if (commaIndex != -1 && commaIndex < content.length - 1) {
              imageData = content.substring(commaIndex + 1);
              content = '[Image]';
            }
          }
        }
        
        return ParsedBondMessage(
          id: firstBondMessageElement.getAttribute('id') ?? '',
          type: messageType,
          role: firstBondMessageElement.getAttribute('role') ?? '',
          content: content,
          imageData: imageData,
          isErrorAttribute:
              firstBondMessageElement.getAttribute('is_error')?.toLowerCase() ==
              'true',
          parsingHadError: false,
        );
      } else {
        // This case means the string, even if non-empty, didn't contain a <_bondmessage> tag.
        return ParsedBondMessage(
          content:
              "Error: No <_bondmessage> element found in the provided XML string.",
          parsingHadError: true,
          isErrorAttribute: true, // Treat as an error
        );
      }
    } catch (e) {
      // This catches errors from XmlDocument.parse or issues with finding elements.
      return ParsedBondMessage(
        content: "Error parsing XML: ${e.toString()}",
        parsingHadError: true,
        isErrorAttribute: true, // Treat as an error
      );
    }
  }

  /// Extracts and cleans body content from the first assistant <_bondmessage> encountered in the accumulatedXml.
  /// This is primarily for live streaming display. Ignores system messages.
  static String extractStreamingBodyContent(String accumulatedXml) {
    String stringToDisplayForUi = "..."; // Default placeholder

    // First try to find an assistant message
    final assistantMessageRegex = RegExp(r'<_bondmessage[^>]*role="assistant"[^>]*>(.*?)(?:</_bondmessage>|$)', dotAll: true);
    final assistantMatch = assistantMessageRegex.firstMatch(accumulatedXml);
    
    if (assistantMatch != null) {
      String rawBodyContent = assistantMatch.group(1) ?? '';
      String strippedContent = rawBodyContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();
      
      if (strippedContent.isNotEmpty) {
        stringToDisplayForUi = strippedContent;
      }
    } else {
      // Fallback: look for any message if no assistant message found yet
      final bondMessageStartTagRegex = RegExp(r'<_bondmessage[^>]*>');
      final bondMessageStartTagMatch = bondMessageStartTagRegex.firstMatch(accumulatedXml);

      if (bondMessageStartTagMatch != null) {
        // Check if this is a system message, and if so, skip it
        final tagContent = bondMessageStartTagMatch.group(0) ?? '';
        if (tagContent.contains('role="system"')) {
          return stringToDisplayForUi; // Keep "..." for system messages
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

  /// Parses ALL <_bondmessage> elements found in the given xmlString.
  /// Returns a list of ParsedBondMessage objects.
  static List<ParsedBondMessage> parseAllBondMessages(String xmlString) {
    final List<ParsedBondMessage> messages = [];
    
    if (xmlString.trim().isEmpty) {
      return messages;
    }
    
    try {
      // Wrap to handle multiple sibling <_bondmessage> if xmlString contains them directly.
      final wrappedXml = "<stream_wrapper>${xmlString.trim()}</stream_wrapper>";
      final XmlDocument doc = XmlDocument.parse(wrappedXml);

      // Find all <_bondmessage> elements
      final bondMessageElements = doc.rootElement.findElements('_bondmessage');

      for (final element in bondMessageElements) {
        String content = element.text.trim();
        String? imageData;
        
        // Check if this is an image_file type with base64 data
        final messageType = element.getAttribute('type') ?? '';
        if (messageType == 'image_file') {
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
          type: messageType,
          role: element.getAttribute('role') ?? '',
          content: content,
          imageData: imageData,
          isErrorAttribute: element.getAttribute('is_error')?.toLowerCase() == 'true',
          parsingHadError: false,
        ));
      }
      
    } catch (e) {
      // If parsing fails, return a single error message
      messages.add(ParsedBondMessage(
        content: "Error parsing XML: ${e.toString()}",
        parsingHadError: true,
        isErrorAttribute: true,
      ));
    }
    
    return messages;
  }

  /// A utility to strip all XML tags from any given string.
  static String stripAllTags(String rawContent) {
    return rawContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();
  }
}
