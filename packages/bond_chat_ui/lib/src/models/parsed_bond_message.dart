import 'package:flutter/foundation.dart' show immutable;

@immutable
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
