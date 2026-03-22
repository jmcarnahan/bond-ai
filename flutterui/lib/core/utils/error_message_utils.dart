import 'dart:convert';

/// Converts raw API error strings into human-readable messages.
///
/// Handles common patterns like:
/// - Double-wrapped `Exception:` prefixes and other exception type prefixes
/// - Network/connection errors
/// - JSON response bodies with `detail` fields
/// - HTTP status code mapping
String humanizeErrorMessage(String rawError) {
  if (rawError.isEmpty) {
    return 'An unexpected error occurred. Please try again.';
  }

  // 1. Strip common exception type prefixes
  String cleaned = rawError;
  final prefixPattern = RegExp(r'^(?:Exception|ClientException|FormatException|TimeoutException|SocketException|HttpException):\s*');
  while (prefixPattern.hasMatch(cleaned)) {
    cleaned = cleaned.replaceFirst(prefixPattern, '');
  }
  cleaned = cleaned.trim();

  // 2. Detect network/connection errors
  final lower = cleaned.toLowerCase();
  if (lower.contains('xmlhttprequest error') ||
      lower.contains('connection refused') ||
      lower.contains('connection closed') ||
      lower.contains('network is unreachable') ||
      lower.contains('failed to fetch') ||
      lower.contains('failed host lookup') ||
      lower.contains('connection timed out') ||
      lower.contains('socket') ||
      (lower.contains('connection') && lower.contains('error'))) {
    return 'Unable to connect to the server. Please check your connection and try again.';
  }

  // 3. Try to extract JSON "detail" from the message
  //    Pattern: "Failed to create agent: 409 {"detail": "Agent already exists"}"
  final jsonMatch = RegExp(r'\d{3}\s*(\{.+\})').firstMatch(cleaned);
  if (jsonMatch != null) {
    try {
      final jsonBody = json.decode(jsonMatch.group(1)!);
      if (jsonBody is Map && jsonBody.containsKey('detail')) {
        return _mapDetailToMessage(jsonBody['detail'].toString());
      }
    } catch (_) {
      // JSON parsing failed, fall through to status code mapping
    }
  }

  // 4. Map known status code patterns (use word boundaries to avoid false positives)
  if (RegExp(r'\b409\b').hasMatch(cleaned)) {
    return 'An agent with this name already exists. Please choose a different name.';
  }
  if (RegExp(r'\b403\b').hasMatch(cleaned)) {
    return 'You do not have permission to perform this action.';
  }
  if (RegExp(r'\b404\b').hasMatch(cleaned)) {
    return 'The requested agent was not found.';
  }
  if (RegExp(r'\b500\b').hasMatch(cleaned)) {
    return 'A server error occurred. Please try again later.';
  }

  // 5. Fallback: return cleaned string, capped at reasonable length
  if (cleaned.isEmpty) {
    return 'An unexpected error occurred. Please try again.';
  }
  if (cleaned.length > 200) {
    cleaned = '${cleaned.substring(0, 200)}...';
  }
  return cleaned;
}

String _mapDetailToMessage(String detail) {
  final lower = detail.toLowerCase();
  if (lower.contains('already exists')) {
    return 'An agent with this name already exists. Please choose a different name.';
  }
  if (lower.contains('not found')) {
    return 'The requested agent was not found.';
  }
  if (lower.contains('permission') || lower.contains('forbidden')) {
    return 'You do not have permission to perform this action.';
  }
  if (lower.contains('only admin')) {
    return 'Only admin users can perform this action.';
  }
  if (lower.contains('only the agent owner')) {
    return 'Only the agent owner can modify the system prompt (instructions).';
  }
  // Default: return the detail as-is (usually already human-readable from the API)
  return detail;
}
