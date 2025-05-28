import 'package:xml/xml.dart';

/// Data class to hold the result of parsing a BondMessage.
class ParsedBondMessage {
  final String id;
  final String type;
  final String role;
  final String content;
  final bool isErrorAttribute; // From the is_error attribute in XML
  final bool parsingHadError; // True if the parser itself encountered an issue

  ParsedBondMessage({
    this.id = '',
    this.type = '',
    this.role = '',
    required this.content,
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
        return ParsedBondMessage(
          id: firstBondMessageElement.getAttribute('id') ?? '',
          type: firstBondMessageElement.getAttribute('type') ?? '',
          role: firstBondMessageElement.getAttribute('role') ?? '',
          content: firstBondMessageElement.text,
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

  /// Extracts and cleans body content from the *first* <_bondmessage> encountered in the accumulatedXml.
  /// This is primarily for live streaming display.
  static String extractStreamingBodyContent(String accumulatedXml) {
    String stringToDisplayForUi = "..."; // Default placeholder

    // Regex to find the start of any <_bondmessage ...> tag
    final bondMessageStartTagRegex = RegExp(r'<_bondmessage[^>]*>');
    final bondMessageStartTagMatch = bondMessageStartTagRegex.firstMatch(
      accumulatedXml,
    );

    if (bondMessageStartTagMatch != null) {
      int bodyStartIndex = bondMessageStartTagMatch.end;
      if (bodyStartIndex <= accumulatedXml.length) {
        String contentAfterStartTag = accumulatedXml.substring(bodyStartIndex);

        // Regex to find the corresponding </_bondmessage> end tag
        final bondMessageEndTagRegex = RegExp(r'</_bondmessage>');
        final bondMessageEndTagMatch = bondMessageEndTagRegex.firstMatch(
          contentAfterStartTag,
        );

        String rawBodyContent;
        if (bondMessageEndTagMatch != null) {
          // If end tag is found, take content up to it
          rawBodyContent = contentAfterStartTag.substring(
            0,
            bondMessageEndTagMatch.start,
          );
        } else {
          // If no end tag yet, take all content after the start tag
          rawBodyContent = contentAfterStartTag;
        }

        // Strip any XML tags *within* this body content for display
        String strippedContent =
            rawBodyContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();

        if (strippedContent.isNotEmpty) {
          stringToDisplayForUi = strippedContent;
        }
        // If strippedContent is empty (e.g., only tags were present), stringToDisplayForUi remains "..."
      }
      // If bodyStartIndex is out of bounds, stringToDisplayForUi remains "..."
    }
    // If no <_bondmessage ...> start tag is found, stringToDisplayForUi remains "..."
    return stringToDisplayForUi;
  }

  /// A utility to strip all XML tags from any given string.
  static String stripAllTags(String rawContent) {
    return rawContent.replaceAll(RegExp(r'<[^>]*>'), '').trim();
  }
}
